"""Re-extract programs from saved snapshots (fix for 12K-truncation bug).
Affected: schools whose detail pages used browser render (southampton).
Reads snapshot files from DB, re-runs extraction with full text, updates rows.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
config.load_env()
from collectors.htmltext import html_to_text
from pipeline.extract import extract_program
from pipeline.validate import validate_program
from storage import db


def main(school_zh: str, dry: bool = False):
    conn = db.init_db()
    rows = conn.execute(
        "SELECT program_id, name, slug_url FROM programs WHERE university=?", (school_zh,)) if False else conn.execute(
        "SELECT program_id, name, source_url, snapshot_ref, source_excerpts FROM programs WHERE university=?",
        (school_zh,)).fetchall()
    stats = {"total": len(rows), "updated": 0, "failed": 0, "skipped": 0}
    for r in rows:
        try:
            html = Path(r["snapshot_ref"]).read_text(encoding="utf-8")
        except Exception:
            stats["skipped"] += 1
            continue
        text = html_to_text(html)
        try:
            ext = extract_program(text, source_hint=r["source_url"])
        except Exception as e:
            print("EXTRACT FAIL", r["name"], str(e)[:80])
            stats["failed"] += 1
            continue
        errs = validate_program({**ext, "source_url": r["source_url"],
                                 "snapshot_ref": r["snapshot_ref"]})
        if errs:
            print("VALIDATE FAIL", r["name"], errs)
            stats["failed"] += 1
            continue
        if dry:
            print("DRY", r["name"], "->", ext.get("tuition_amount"), ext.get("ielts_req"))
            stats["updated"] += 1
            continue
        ex_old = json.loads(r["source_excerpts"] or "{}")
        ex_new = ext.get("source_excerpts") or {}
        # 保留旧有的 gpa_rule/中国要求 excerpt，不被覆盖
        for k in ("gpa_rule", "gpa_requirements", "school_list_req"):
            if k in ex_old:
                ex_new.setdefault(k, ex_old[k])
        conn.execute(
            """UPDATE programs SET name=?, duration_months=?, tuition_amount=?,
               tuition_currency=?, ielts_req=?, toefl_req=?, deadlines=?,
               source_excerpts=?, gpa_requirements=?, school_list_req=?,
               content_hash=? WHERE program_id=?""",
            (ext.get("name") or r["name"], ext.get("duration_months"),
             ext.get("tuition_amount"), ext.get("tuition_currency"),
             json.dumps(ext["ielts_req"]) if ext.get("ielts_req") else None,
             json.dumps(ext["toefl_req"]) if ext.get("toefl_req") else None,
             json.dumps(ext.get("deadlines") or []),
             json.dumps(ex_new, ensure_ascii=False),
             json.dumps(ext.get("gpa_requirements") or [], ensure_ascii=False),
             json.dumps(ext.get("school_list_req"), ensure_ascii=False),
             db.content_hash(text), r["program_id"]))
        stats["updated"] += 1
        if stats["updated"] % 5 == 0:
            conn.commit()
            print(f"progress {stats['updated']}/{stats['total']}", flush=True)
    conn.commit()
    conn.close()
    return stats


if __name__ == "__main__":
    school = sys.argv[1] if len(sys.argv) > 1 else "南安普顿大学"
    print(main(school, dry="--dry" in sys.argv))
