"""REQ-004 / THR-CITE self-test: citation enforcement at the service boundary.

A recommendation may only be emitted if it carries a valid citation — both an
official source URL and a local snapshot reference. Programs missing either are
discarded and counted in `dropped_no_citation`, never surfaced to the user.

Pure stdlib; runs anywhere: `python3 tests/test_req004_citation.py`.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from storage import db  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


with tempfile.TemporaryDirectory() as tmp:
    config.DB_PATH = Path(tmp) / "citation.sqlite3"
    conn = db.init_db(config.DB_PATH)

    school = {"name_zh": "香港大学", "name_en": "HKU", "region": "hk", "recognized": 1,
              "source_url": "https://example.gov.cn/list", "snapshot_ref": "moe/hk.html",
              "fetched_at": db.now(), "content_hash": "s1"}
    db.upsert_recognized_school(conn, school)
    sid = conn.execute("SELECT school_id FROM recognized_schools").fetchone()["school_id"]

    def prog(name, url, snap):
        return {"school_id": sid, "university": "香港大学", "name": name, "field": "cs",
                "gpa_requirements": '[{"tier":"985","min_gpa":83}]',
                "ielts_req": '{"overall":6.5,"min_sub":6.0}',
                "source_url": url, "snapshot_ref": snap,
                "source_excerpts": '{"ielts_req":"IELTS 6.5 overall"}',
                "intake_year": 2026, "fetched_at": db.now(),
                "content_hash": db.content_hash(name)}

    db.upsert_program(conn, prog("MSc Good", "https://hku.hk/msc", "hku/msc.html"))
    db.upsert_program(conn, prog("MSc NoUrl", "", "hku/msc2.html"))
    db.upsert_program(conn, prog("MSc NoSnap", "https://hku.hk/msc3", ""))
    conn.commit()
    conn.close()

    from api.server import match  # import after DB path is set

    bg = {"undergrad_tier": "985", "gpa": 90.0, "ielts": 7.0,
          "ielts_min_sub": 6.5, "target_field": "cs"}
    r = match(bg)

    kept = [p for tier in r["tiers"].values() for p in tier]
    check("only citations-complete program is recommended", len(kept) == 1)
    check("kept program is the one with URL + snapshot",
          kept and kept[0]["program"] == "MSc Good")
    check("every recommended item has a non-empty citation URL",
          all(p["citations"] and p["citations"][0]["url"] for p in kept))
    check("dropped_no_citation counts both invalid programs",
          r.get("dropped_no_citation") == 2)
    check("no invalid program leaked into any tier",
          all(p["program"] != "MSc NoUrl" and p["program"] != "MSc NoSnap" for p in kept))

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("ALL PASS (REQ-004 citation enforcement)")
