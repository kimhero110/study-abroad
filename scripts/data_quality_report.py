"""D-stage self-test / C-stage evidence generator: data coverage & quality.

Produces `reports/data_quality.json` and prints a summary. Pure stdlib.

Maps to WP-001 thresholds:
  THR-DATA-1  programs_count_and_field_completeness  (>=0.95)
  THR-CITE    citation coverage                      (==1.0)
  REQ-003     tiered output (reach/match/safety each >=3 on normal cases)
  REQ-009?    (verified elsewhere)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

CST = timezone(timedelta(hours=8))
KEY_FIELDS = ["gpa_requirements", "ielts_req", "toefl_req", "tuition_amount",
              "deadlines", "source_url", "snapshot_ref"]
# language requirement is satisfied by either ielts or toefl
LANG_FIELDS = ("ielts_req", "toefl_req")

E2E_CASES = [
    ("E-001", {"undergrad_tier": "985", "gpa": 88, "ielts": 7.0, "ielts_min_sub": 6.5,
               "target_field": "cs", "undergrad_school": "复旦大学"}),
    ("E-002", {"undergrad_tier": "shuangfei", "gpa": 78, "ielts": 6.0, "ielts_min_sub": 5.5,
               "target_field": "cs", "undergrad_school": "某双非"}),
    ("E-004", {"undergrad_tier": "211", "gpa": 85, "ielts": 6.5, "ielts_min_sub": 6.0,
               "target_field": "business", "undergrad_school": "上海大学"}),
]


def _nonempty(v) -> bool:
    return v is not None and v != "" and v != "null" and v != "[]"


def main() -> int:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    real = conn.execute(
        "SELECT COUNT(*) n FROM programs WHERE university NOT LIKE '【测试】%'").fetchone()["n"]
    total = conn.execute("SELECT COUNT(*) n FROM programs").fetchone()["n"]

    by_region = {r["region"]: r["n"] for r in conn.execute(
        "SELECT s.region, COUNT(*) n FROM programs p "
        "JOIN recognized_schools s ON p.school_id=s.school_id "
        "WHERE p.university NOT LIKE '【测试】%' GROUP BY s.region")}
    by_university = {r["university"]: r["n"] for r in conn.execute(
        "SELECT university, COUNT(*) n FROM programs WHERE university NOT LIKE '【测试】%' "
        "GROUP BY university ORDER BY n DESC")}

    recognized = {r["region"]: r["n"] for r in conn.execute(
        "SELECT region, COUNT(*) n FROM recognized_schools GROUP BY region")}

    completeness = {}
    for col in KEY_FIELDS:
        n = conn.execute(
            f"SELECT COUNT(*) n FROM programs WHERE university NOT LIKE '【测试】%' "
            f"AND {col} IS NOT NULL AND {col} NOT IN ('', 'null', '[]')").fetchone()["n"]
        completeness[col] = round(n / max(real, 1), 4)
    lang_n = conn.execute(
        "SELECT COUNT(*) n FROM programs WHERE university NOT LIKE '【测试】%' AND "
        "(ielts_req IS NOT NULL AND ielts_req NOT IN ('', 'null')) OR "
        "(toefl_req IS NOT NULL AND toefl_req NOT IN ('', 'null'))").fetchone()["n"]
    completeness["language_either"] = round(lang_n / max(real, 1), 4)

    cite_n = conn.execute(
        "SELECT COUNT(*) n FROM programs WHERE university NOT LIKE '【测试】%' "
        "AND source_url IS NOT NULL AND source_url != '' "
        "AND snapshot_ref IS NOT NULL AND snapshot_ref != ''").fetchone()["n"]
    citation_coverage = round(cite_n / max(real, 1), 4)

    # matchable = has non-empty gpa_requirements OR a usable school list requirement
    matchable = 0
    for r in conn.execute("SELECT gpa_requirements, school_list_req FROM programs "
                          "WHERE university NOT LIKE '【测试】%'"):
        try:
            g = json.loads(r["gpa_requirements"] or "[]")
        except json.JSONDecodeError:
            g = []
        try:
            s = json.loads(r["school_list_req"] or "null")
        except json.JSONDecodeError:
            s = None
        if g or (isinstance(s, dict) and (s.get("type") == "ucl_custom_list" or s.get("allowed_tiers"))):
            matchable += 1
    conn.close()

    from api.server import match
    e2e = []
    for cid, bg in E2E_CASES:
        r = match(bg)
        tiers = {k: len(v) for k, v in r["tiers"].items()}
        e2e.append({
            "case": cid, "background": bg, "data_sufficiency": r["data_sufficiency"],
            "tiers": tiers, "dropped_no_citation": r.get("dropped_no_citation", 0),
            "each_tier_ge_3": all(tiers[t] >= 3 for t in ("reach", "match", "safety"))
                              and r["data_sufficiency"] == "ok",
        })

    report = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "db_path": str(config.DB_PATH),
        "programs": {
            "total": total,
            "real": real,
            "demo": total - real,
            "by_region": by_region,
            "by_university": by_university,
        },
        "recognized_schools_by_region": recognized,
        "field_completeness": completeness,
        "citation_coverage": citation_coverage,
        "matchable_programs": matchable,
        "matchable_ratio": round(matchable / max(real, 1), 4),
        "e2e_cases": e2e,
        "threshold_eval": {
            "THR-DATA-1_programs_ge_60": real >= 60,
            "THR-DATA-1_field_completeness_ge_0_95": completeness["gpa_requirements"] >= 0.95,
            "THR-CITE_citation_coverage_eq_1": citation_coverage == 1.0,
            "REQ-003_each_tier_ge_3_all_cases": all(c["each_tier_ge_3"] for c in e2e),
        },
    }
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "data_quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"real programs: {real} (total {total})")
    print("field completeness:", json.dumps(completeness, ensure_ascii=False))
    print(f"citation coverage: {citation_coverage}")
    print(f"matchable: {matchable}/{real} = {report['matchable_ratio']}")
    for c in e2e:
        print(f"  {c['case']} {c['background']['undergrad_tier']}/{c['background']['gpa']}"
              f"/{c['background']['target_field']}: {c['data_sufficiency']} {c['tiers']}"
              f" each>=3={c['each_tier_ge_3']}")
    print("threshold_eval:", json.dumps(report["threshold_eval"], ensure_ascii=False))
    print("wrote reports/data_quality.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
