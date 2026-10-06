"""Enrich Imperial programs: English level mapping from course page text.

Verified 2026-10-05 from https://www.imperial.ac.uk/study/apply/english-language/:
  Standard Level = IELTS 6.5 overall (min 6.0 all elements)
  Higher Level   = IELTS 7.0 overall (min 6.5 all elements)
Course pages state "higher/standard university requirement" in English section.
Tuition: NOT on Imperial course pages (separate fees system) — left null, recorded as known gap.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
config.load_env()
from collectors.htmltext import html_to_text
from storage import db

LEVEL_MAP = {
    "higher": {"overall": 7.0, "min_sub": 6.5},
    "standard": {"overall": 6.5, "min_sub": 6.0},
}
LEVEL_PAGE = "https://www.imperial.ac.uk/study/apply/english-language/"


def main():
    conn = db.init_db()
    rows = conn.execute(
        "SELECT program_id, name, snapshot_ref, source_excerpts FROM programs "
        "WHERE university='帝国理工学院'").fetchall()
    stats = {"higher": 0, "standard": 0, "unknown": 0}
    for r in rows:
        try:
            t = html_to_text(Path(r["snapshot_ref"]).read_text(encoding="utf-8"))
        except Exception:
            stats["unknown"] += 1
            continue
        m = re.search(r"(higher|standard)\s+university requirement", t, re.I)
        if not m:
            stats["unknown"] += 1
            continue
        level = m.group(1).lower()
        ielts = LEVEL_MAP[level]
        ex = json.loads(r["source_excerpts"] or "{}")
        ex["ielts_req"] = (f"项目页标注 '{m.group(0)}'；Imperial 官方英语要求页: {LEVEL_PAGE} "
                           f"（{level.capitalize()} = IELTS {ielts['overall']}/{ielts['min_sub']}，2026-10-05 核实）")
        conn.execute("UPDATE programs SET ielts_req=?, source_excerpts=? WHERE program_id=?",
                     (json.dumps(ielts), json.dumps(ex, ensure_ascii=False), r["program_id"]))
        stats[level] += 1
    conn.commit()
    print(stats)
    conn.close()


if __name__ == "__main__":
    main()
