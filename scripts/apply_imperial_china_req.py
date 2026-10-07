"""Apply Imperial College's verified China entry requirement to all imperial programs.

Source (verified 2026-10-03, official text captured):
  https://www.imperial.ac.uk/study/apply/postgraduate-taught/entry-requirements/accepted-qualifications/
  "China — To be considered for admission to a Master's e.g. MSc, MRes, MBA etc, applicants
   should have been awarded a Bachelor's degree from a Project 211 university with a final
   overall mark of 80% or better. Preference is given to candidates with 85% or better."

Interpretation (recorded in school_list_req.notes): Imperial 只接受 Project 211 及以上
（C9/985/211），最低 80%（85% 优先）。双非/双一流(非211) 无申请资格 → allowed_tiers。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

import config  # noqa: E402
from storage import db  # noqa: E402

SOURCE_URL = ("https://www.imperial.ac.uk/study/apply/postgraduate-taught/"
              "entry-requirements/accepted-qualifications/")
EXCERPT = ("China — applicants should have been awarded a Bachelor's degree from a "
           "Project 211 university with a final overall mark of 80% or better. "
           "Preference is given to candidates with 85% or better.")

GPA_REQS = [{"tier": "C9", "min_gpa": 80}, {"tier": "985", "min_gpa": 80},
            {"tier": "211", "min_gpa": 80}]
LIST_REQ = {"has_list": True, "allowed_tiers": ["C9", "985", "211"],
            "notes": "Imperial 官方：仅 Project 211 及以上大学，最低 80%（85% 优先）"}


def main():
    config.load_env()
    conn = db.init_db()
    rows = conn.execute(
        "SELECT program_id, source_excerpts FROM programs WHERE university='帝国理工学院'"
    ).fetchall()
    n = 0
    for r in rows:
        ex = json.loads(r["source_excerpts"] or "{}")
        ex["gpa_requirements"] = EXCERPT + f" | 来源: {SOURCE_URL}"
        conn.execute(
            "UPDATE programs SET gpa_requirements=?, school_list_req=?, source_excerpts=? "
            "WHERE program_id=?",
            (json.dumps(GPA_REQS), json.dumps(LIST_REQ, ensure_ascii=False),
             json.dumps(ex, ensure_ascii=False), r["program_id"]))
        n += 1
    conn.commit()
    print(f"updated {n} imperial programs with China GPA requirement")
    conn.close()


if __name__ == "__main__":
    main()
