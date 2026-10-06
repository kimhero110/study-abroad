"""Demo seed: clearly-labeled test programs so the full match flow is testable
before scale-up (MS-107) completes real extraction for all schools.

Test rows have university prefixed with 【测试】and must NOT be presented as real data.
Remove with: python3 scripts/seed_demo_data.py --clear
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from storage import db  # noqa: E402

DEMO = [
    {"university": "【测试】甲大学", "name": "MSc Computer Science", "field": "cs",
     "gpa_requirements": '[{"tier":"985","min_gpa":83},{"tier":"211","min_gpa":85},{"tier":"shuangfei","min_gpa":88}]',
     "ielts_req": '{"overall":7.0,"min_sub":6.5}'},
    {"university": "【测试】乙大学", "name": "MSc Data Science", "field": "cs",
     "gpa_requirements": '[{"tier":"985","min_gpa":80},{"tier":"211","min_gpa":82},{"tier":"shuangfei","min_gpa":85}]',
     "ielts_req": '{"overall":6.5,"min_sub":6.0}'},
    {"university": "【测试】丙大学", "name": "MSc Finance", "field": "business",
     "gpa_requirements": '[{"tier":"985","min_gpa":85},{"tier":"211","min_gpa":87},{"tier":"shuangfei","min_gpa":90}]',
     "ielts_req": '{"overall":7.0,"min_sub":6.0}'},
]


def main(clear=False):
    conn = db.init_db()
    if clear:
        n = conn.execute("DELETE FROM programs WHERE university LIKE '【测试】%'").rowcount
        conn.commit()
        print(f"cleared {n} demo rows")
        return
    row = conn.execute("SELECT school_id FROM recognized_schools LIMIT 1").fetchone()
    sid = row["school_id"]
    for d in DEMO:
        rec = {
            "school_id": sid, "university": d["university"], "name": d["name"],
            "field": d["field"], "degree": "master_taught", "duration_months": 12,
            "tuition_amount": 30000, "tuition_currency": "GBP",
            "gpa_requirements": d["gpa_requirements"],
            "school_list_req": None,
            "ielts_req": d["ielts_req"], "toefl_req": None,
            "deadlines": '[{"round":1,"close_date":"2026-03-31"}]',
            "intake_year": 2026,
            "source_url": "https://example.test/demo",
            "snapshot_ref": "demo",
            "source_excerpts": '{"note":"演示测试数据，非真实项目"}',
            "fetched_at": db.now(),
            "content_hash": db.content_hash(d["university"] + d["name"]),
        }
        print(db.upsert_program(conn, rec), d["name"])
    conn.commit()
    conn.close()


if __name__ == "__main__":
    config.load_env()
    main(clear="--clear" in sys.argv)
