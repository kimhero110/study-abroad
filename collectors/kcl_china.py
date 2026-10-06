"""KCL per-program China GPA collector (browser-rendered country dropdown).

KCL 的尺子按项目写在各自 entry-requirements 页的「Select a country → China」里，
标准结构（官方原文 2026-10-04 核实）：
  "China - Degree from Prestigious Institution: ... average score of 85%"
  "China - Degree from a Recognised Institution: ... average score of 88%"
  部分项目（商学院、Data Science MSc 等）"usually only ... prestigious"。
prestigious = UK ENIC 认定 / Project 211 / Double First Class（KCL 官方定义）。
"""
from __future__ import annotations

import json
import re
import time

import config
from collectors.browser_fetch import render
from storage import db

PRESTIGIOUS_TIERS = ["C9", "985", "211", "shuangyiliu"]  # KCL: 211/双一流=prestigious
SOURCE_ID = "kcl_js"


def parse_china_req(text: str, program_name: str = "") -> dict | None:
    """从渲染后的页面文本解析中国要求。返回 None 表示页面无中国段落。

    注意：KCL 页面上「usually only prestigious」注释是针对特定项目清单的
    （商学院 + Data Science MSc/LLM/Political Economy/Public Policy），
    不能用注释存在与否判断，必须按当前项目名是否命中清单判断。
    """
    i = text.find("China - Degree from Prestigious Institution")
    if i < 0:
        return None
    seg = text[i:i + 1500]
    m_pre = re.search(r"Prestigious Institution:.*?average score of (\d+)%", seg, re.S)
    m_rec = re.search(r"Recognised Institution:.*?average score of (\d+)%", seg, re.S)
    if not m_pre:
        return None
    restricted_keywords = ["Data Science", "Laws", "Political Economy", "Public Policy",
                           "Finance", "Business", "Accounting", "Management", "Marketing"]
    only_prestigious = any(k.lower() in program_name.lower() for k in restricted_keywords)
    return {
        "prestigious_gpa": int(m_pre.group(1)),
        "recognised_gpa": int(m_rec.group(1)) if m_rec else None,
        "only_prestigious": only_prestigious,
        "excerpt": re.sub(r"\s+", " ", seg[:600]).strip(),
    }


def collect(conn, delay: float = 2.0) -> dict:
    programs = conn.execute(
        "SELECT program_id, name, source_url FROM programs WHERE university='伦敦国王学院'"
    ).fetchall()
    stats = {"programs": len(programs), "updated": 0, "no_china": 0, "failed": 0}
    for p in programs:
        url = p["source_url"].rstrip("/") + "/entry-requirements"
        r = render(url, SOURCE_ID, wait_ms=4000, actions=[
            {"click": "#country-qualifications-select"},
            {"click_option": ("#country-qualifications-select-options .dropdown-option", "China")},
        ])
        if not r["ok"] or not r["text"]:
            stats["failed"] += 1
            continue
        parsed = parse_china_req(r["text"], program_name=p["name"])
        if not parsed:
            stats["no_china"] += 1
            continue
        tiers = [{"tier": t, "min_gpa": parsed["prestigious_gpa"]} for t in PRESTIGIOUS_TIERS]
        if parsed["recognised_gpa"] and not parsed["only_prestigious"]:
            tiers.append({"tier": "shuangfei", "min_gpa": parsed["recognised_gpa"]})
        list_req = None
        if parsed["only_prestigious"]:
            list_req = {"has_list": True, "allowed_tiers": PRESTIGIOUS_TIERS,
                        "notes": "该项目通常只录取 211/双一流（prestigious）背景"}
        ex = json.loads(p["source_excerpts"] or "{}") if "source_excerpts" in p.keys() else {}
        ex["gpa_requirements"] = parsed["excerpt"] + f" | 来源: {url}"
        conn.execute(
            "UPDATE programs SET gpa_requirements=?, school_list_req=?, source_excerpts=? "
            "WHERE program_id=?",
            (json.dumps(tiers), json.dumps(list_req, ensure_ascii=False) if list_req else None,
             json.dumps(ex, ensure_ascii=False), p["program_id"]))
        stats["updated"] += 1
        time.sleep(delay)
    conn.commit()
    return stats


if __name__ == "__main__":
    config.load_env()
    conn = db.init_db()
    print(collect(conn))
    conn.close()
