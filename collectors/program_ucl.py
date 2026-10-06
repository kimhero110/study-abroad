"""UCL (University College London) program collector — first L1 adapter.

List page is server-rendered; detail pages contain fees/duration/entry/English/deadlines
in clean text. Pipeline: list -> filter (msc, cs/business) -> detail -> LLM extract ->
rule validate -> upsert (natural key) / quarantine on validation failure.
"""
from __future__ import annotations

import json
import re
import time

import config
from collectors.fetcher import fetch
from collectors.htmltext import html_to_text
from pipeline.extract import extract_program
from pipeline.llm_client import LLMUnavailable
from pipeline.validate import validate_program
from storage import db

LIST_URL = "https://www.ucl.ac.uk/prospective-students/graduate/taught-degrees"
SOURCE_ID = "ucl"
UNIVERSITY_ZH = "伦敦大学学院"
UNIVERSITY_EN = "University College London"

FIELD_KEYWORDS = {
    "cs": ["computer-science", "data-science", "machine-learning", "artificial-intelligence",
           "software", "information-security", "data-", "computing", "robotics"],
    "business": ["management", "finance", "business", "accounting", "marketing",
                 "economics", "entrepreneurship", "mba"],
}
EXCLUDE = ("pg-cert", "pg-dip", "grad-dip", "grad-cert", "mres", "mphil", "phd")

# UCL English level -> IELTS，来源：UCL 官方 English language requirements 页（已人工核实 2026-10-02）
ENGLISH_LEVEL_PAGE = ("https://www.ucl.ac.uk/prospective-students/graduate/learning-and-living-ucl/"
                      "international-students/english-language-requirements")
IELTS_LEVEL_MAP = {
    1: {"overall": 6.5, "min_sub": 6.0},
    2: {"overall": 7.0, "min_sub": 6.5},
    3: {"overall": 7.0, "min_sub": 7.0},
    4: {"overall": 7.5, "min_sub": 7.0},
    5: {"overall": 8.0, "min_sub": 8.0},
}


def apply_english_level(ext: dict) -> None:
    """ielts_req 为空但页面标注 Level N 时，按官方映射填充并留证。"""
    if ext.get("ielts_req"):
        return
    m = re.search(r"Level\s*([1-5])", ext.get("english_level_text") or "")
    if not m:
        return
    level = int(m.group(1))
    ext["ielts_req"] = IELTS_LEVEL_MAP[level]
    excerpts = ext.setdefault("source_excerpts", {})
    excerpts["ielts_req"] = (f"项目页标注 '{ext['english_level_text'].strip()}'；"
                             f"Level {level} 映射自 UCL 官方英语要求页: {ENGLISH_LEVEL_PAGE}")


def list_programs() -> list[dict]:
    r = fetch(LIST_URL, SOURCE_ID)
    if not r["ok"]:
        return []
    links = re.findall(r'href="(https://www\.ucl\.ac\.uk/prospective-students/graduate/taught-degrees/([a-z0-9-]+?)(?:-(\d{4}))?)"',
                       r["text"] or "")
    seen = {}
    for url, slug, year in links:
        if year and any(x in slug for x in EXCLUDE):
            continue
        if year:
            seen[slug] = {"slug": slug, "url": url, "intake_year": int(year)}
    return list(seen.values())


def classify(slug: str) -> str | None:
    if "-msc" not in slug:  # MVP: 仅 MSc 授课型硕士
        return None
    for field, kws in FIELD_KEYWORDS.items():
        if any(k in slug for k in kws):
            return field
    return None


def resolve_school_id(conn) -> int | None:
    row = conn.execute(
        "SELECT school_id FROM recognized_schools WHERE name_zh=? OR name_en=?",
        (UNIVERSITY_ZH, UNIVERSITY_EN)).fetchone()
    return row["school_id"] if row else None


def collect(conn, limit: int | None = None, delay: float = 1.2) -> dict:
    programs = [p for p in list_programs() if classify(p["slug"])]
    if limit:
        programs = programs[:limit]
    stats = {"listed": len(programs), "inserted": 0, "updated": 0,
             "unchanged": 0, "quarantined": 0, "failed": 0}
    sid = resolve_school_id(conn)
    if sid is None:
        db.add_quarantine(conn, SOURCE_ID, f"{SOURCE_ID}|_school_link|0",
                          "L0_LINK_MISSING", detail=f"{UNIVERSITY_ZH} not in recognized_schools")
        return stats
    for p in programs:
        seed_key = f'{UNIVERSITY_ZH}|{p["slug"]}|{p["intake_year"]}'
        try:
            r = fetch(p["url"], SOURCE_ID)
            if not r["ok"]:
                db.add_quarantine(conn, SOURCE_ID, seed_key, "FETCH_FAIL",
                                  detail=f'status={r["status"]}')
                stats["quarantined"] += 1
                continue
            text = html_to_text(r["text"])
            ext = extract_program(text, source_hint=p["url"])
            apply_english_level(ext)
            # 校验抽取对象（含血缘字段），先于序列化入库
            errs = validate_program({**ext, "source_url": p["url"], "snapshot_ref": r["snapshot_ref"]})
            if errs:
                db.add_quarantine(conn, SOURCE_ID, seed_key, "VALIDATE:" + ",".join(errs),
                                  raw_ref=r["snapshot_ref"],
                                  detail=json.dumps(ext.get("notes"), ensure_ascii=False))
                stats["quarantined"] += 1
                continue
            rec = {
                "school_id": sid,
                "university": UNIVERSITY_ZH,
                "name": ext.get("name") or p["slug"],
                "field": classify(p["slug"]),
                "degree": "master_taught",
                "duration_months": ext.get("duration_months"),
                "tuition_amount": ext.get("tuition_amount"),
                "tuition_currency": ext.get("tuition_currency"),
                "gpa_requirements": json.dumps(ext.get("gpa_requirements") or [], ensure_ascii=False),
                "school_list_req": json.dumps(ext.get("school_list_req"), ensure_ascii=False),
                "ielts_req": json.dumps(ext.get("ielts_req"), ensure_ascii=False) if ext.get("ielts_req") else None,
                "toefl_req": json.dumps(ext.get("toefl_req"), ensure_ascii=False) if ext.get("toefl_req") else None,
                "deadlines": json.dumps(ext.get("deadlines") or [], ensure_ascii=False),
                "intake_year": ext.get("intake_year") or p["intake_year"],
                "source_url": p["url"],
                "snapshot_ref": r["snapshot_ref"],
                "source_excerpts": json.dumps(ext.get("source_excerpts") or {}, ensure_ascii=False),
                "fetched_at": db.now(),
                "content_hash": db.content_hash(text),
            }
            result = db.upsert_program(conn, rec)
            stats[result] += 1
        except LLMUnavailable as e:
            # 双端点失效 -> 暂停并上报（冻结契约），不静默继续
            db.set_state(conn, SOURCE_ID, "halted_llm_unavailable")
            raise
        except Exception as e:
            db.add_quarantine(conn, SOURCE_ID, seed_key, "PIPELINE_ERROR", detail=str(e)[:500])
            stats["failed"] += 1
        time.sleep(delay)
    db.set_state(conn, SOURCE_ID, "done")
    return stats


if __name__ == "__main__":
    import sys
    config.load_env()
    conn = db.init_db()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(collect(conn, limit=limit))
    conn.commit()
    conn.close()
