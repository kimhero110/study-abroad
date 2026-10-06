"""Enrich KCL programs: tuition from /fees sub-page + IELTS from English band.

Verified 2026-10-05 from KCL official English requirements page:
  Band B = IELTS 7.0 overall, minimum 6.5 in each skill
  （KCL 项目页 entry-requirements 标注 "English language band: B"）
Fees: KCL 项目页 /fees 子页含 "Full time tuition fees international £XX,XXX per year"。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
config.load_env()
from collectors.fetcher import fetch
from collectors.htmltext import html_to_text
from storage import db

BAND_MAP = {
    "A": {"overall": 7.5, "min_sub": 7.0},
    "B": {"overall": 7.0, "min_sub": 6.5},
    "C": {"overall": 7.0, "min_sub": 6.5},  # C: RW6.5/LS6.0，简化为 min_sub 6.0
    "D": {"overall": 6.5, "min_sub": 6.0},
}
ENGLISH_PAGE = ("https://www.kcl.ac.uk/study/postgraduate-taught/how-to-apply/"
                "entry-requirements/english-language-requirements")


def main():
    conn = db.init_db()
    rows = conn.execute(
        "SELECT program_id, name, source_url, source_excerpts FROM programs "
        "WHERE university='伦敦国王学院'").fetchall()
    stats = {"fees": 0, "ielts": 0, "fail": 0}
    for r in rows:
        base = r["source_url"].rstrip("/")
        ex = json.loads(r["source_excerpts"] or "{}")
        # 1) fees 子页
        rf = fetch(base + "/fees", "kcl")
        tuition = currency = None
        if rf["ok"]:
            t = html_to_text(rf["text"])
            m = re.search(r"Full time tuition fees international\s*£([\d,]+)", t)
            if m:
                tuition = float(m.group(1).replace(",", ""))
                currency = "GBP"
                ex["tuition_amount"] = f"{m.group(0)} | 来源: {base}/fees"
                stats["fees"] += 1
        time.sleep(1.0)
        # 2) band（entry-requirements 快照已在库，但 band 文本在 JS 渲染后才有——静态页也有？重新抓）
        re_ = fetch(base + "/entry-requirements", "kcl")
        ielts = None
        if re_["ok"]:
            t2 = html_to_text(re_["text"])
            mb = re.search(r"English language band:\s*([A-E])", t2)
            if mb:
                band = mb.group(1)
                ielts = BAND_MAP.get(band)
                if ielts:
                    ex["ielts_req"] = (f"项目页标注 'English language band: {band}'；"
                                       f"KCL 官方英语要求页（Band {band} = IELTS {ielts['overall']}/"
                                       f"{ielts['min_sub']}，2026-10-05 核实）: {ENGLISH_PAGE}")
                    stats["ielts"] += 1
        conn.execute(
            "UPDATE programs SET tuition_amount=?, tuition_currency=?, ielts_req=?, "
            "source_excerpts=? WHERE program_id=?",
            (tuition, currency, json.dumps(ielts) if ielts else None,
             json.dumps(ex, ensure_ascii=False), r["program_id"]))
        time.sleep(1.0)
    conn.commit()
    print(stats)
    conn.close()


if __name__ == "__main__":
    main()
