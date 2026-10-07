"""MS-101 self-test: schema creation, natural-key upsert idempotency (THR-IDEM pattern),
quarantine, seed reconciliation, stale marking. Pure stdlib, runs anywhere.
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
    path = Path(tmp) / "test.sqlite3"
    conn = db.init_db(path)

    # schema: 4 tables + FK
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    check("schema: 4 tables", {"recognized_schools", "programs", "collect_state", "quarantine"} <= tables)

    school = {"name_zh": "香港大学", "name_en": "HKU", "region": "hk", "recognized": 1,
              "source_url": "https://example.gov.cn/list", "snapshot_ref": "data/raw/moe/x.html",
              "fetched_at": db.now(), "content_hash": "h1"}
    r1 = db.upsert_recognized_school(conn, school)
    r2 = db.upsert_recognized_school(conn, dict(school))
    check("school upsert: insert then unchanged", r1 == "inserted" and r2 == "unchanged")
    r3 = db.upsert_recognized_school(conn, {**school, "content_hash": "h2"})
    check("school upsert: hash change -> updated", r3 == "updated")
    n = conn.execute("SELECT COUNT(*) c FROM recognized_schools").fetchone()["c"]
    check("school upsert: still 1 row (idempotent)", n == 1)

    sid = conn.execute("SELECT school_id FROM recognized_schools").fetchone()["school_id"]
    prog = {"school_id": sid, "university": "香港大学", "name": "MSc Computer Science",
            "field": "cs", "intake_year": 2026, "duration_months": 12,
            "tuition_amount": 210000, "tuition_currency": "HKD",
            "gpa_requirements": '[{"tier":"985","min_gpa":85},{"tier":"shuangfei","min_gpa":88}]',
            "ielts_req": '{"overall":6.5,"min_sub":5.5}',
            "deadlines": '[{"round":1,"close_date":"2025-12-31"}]',
            "source_url": "https://hku.hk/prog", "snapshot_ref": "data/raw/hku/x.html",
            "source_excerpts": '{"ielts_req":"IELTS 6.5 overall..."}',
            "fetched_at": db.now(), "content_hash": "p1"}
    p1 = db.upsert_program(conn, prog)
    p2 = db.upsert_program(conn, dict(prog))
    check("program upsert: insert then unchanged", p1 == "inserted" and p2 == "unchanged")
    n = conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"]
    check("program upsert: 1 row after double run (THR-IDEM pattern)", n == 1)

    # double-run full simulation: row delta = 0
    db.upsert_recognized_school(conn, {**school, "content_hash": "h2"})
    db.upsert_program(conn, prog)
    check("THR-IDEM double-run delta = 0",
          conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"] == 1 and
          conn.execute("SELECT COUNT(*) c FROM recognized_schools").fetchone()["c"] == 1)

    # quarantine + reconciliation
    db.add_quarantine(conn, "hku", "香港中文大学|MSc Finance|2026", "EXTRACT_RANGE_FAIL")
    seeds = [{"university": "香港大学", "name": "MSc Computer Science", "intake_year": 2026},
             {"university": "香港中文大学", "name": "MSc Finance", "intake_year": 2026},
             {"university": "NUS", "name": "MSc Computing", "intake_year": 2026}]
    rec = db.seed_reconciliation(conn, seeds)
    check("reconciliation: 2/3 covered, 1 missing", rec["covered"] == 2 and len(rec["missing"]) == 1)

    # collect_state machine
    db.set_state(conn, "moe_hk", "running")
    db.set_state(conn, "moe_hk", "done", last_cursor="page3")
    st = db.get_state(conn, "moe_hk")
    check("collect_state: status+cursor", st["status"] == "done" and st["last_cursor"] == "page3")

    # stale marking
    conn.execute("UPDATE programs SET fetched_at='2020-01-01T00:00:00+08:00'")
    check("stale marking", db.mark_stale(conn, days=60) == 1)

    conn.close()

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("ALL PASS (MS-101)")
