"""HK recognized schools collector: 香港教育局「可頒授學位的高等教育院校」名单（22 所）。

Source semantics: 教育部认可的香港高校 = 香港教育局可颁授学位院校（两地学历互认框架下
内地认可其学位的香港院校）。来源为香港特别行政区政府教育局官方页面。

Data integrity: 中文名从官方页面解析（繁体→简体映射表），英文名逐一在官方英文页
验证存在后才入库——不凭记忆写数据。
"""
from __future__ import annotations

import re

import config
from collectors.fetcher import fetch
from collectors.htmltext import html_to_text
from storage import db

URL_TC = "https://www.edb.gov.hk/tc/edu-system/postsecondary/local-higher-edu/institutions/index.html"
URL_EN = "https://www.edb.gov.hk/en/edu-system/postsecondary/local-higher-edu/institutions/index.html"
SOURCE_ID = "edb_hk"

# 繁体名 -> (简体名, 官方英文名)；英文名将逐一对官方英文页验证
HK_SCHOOLS = {
    "明德學院": ("明德学院", "Centennial College"),
    "香港城市大學": ("香港城市大学", "City University of Hong Kong"),
    "宏恩基督教學院": ("宏恩基督教学院", "Gratia Christian College"),
    "港專學院": ("港专学院", "HKCT Institute of Higher Education"),
    "香港演藝學院": ("香港演艺学院", "Hong Kong Academy for Performing Arts"),
    "香港浸會大學": ("香港浸会大学", "Hong Kong Baptist University"),
    "香港珠海學院": ("香港珠海学院", "Hong Kong Chu Hai College"),
    "香港都會大學": ("香港都会大学", "Hong Kong Metropolitan University"),
    "香港能仁專上學院": ("香港能仁专上学院", "Hong Kong Nang Yan College of Higher Education"),
    "香港樹仁大學": ("香港树仁大学", "Hong Kong Shue Yan University"),
    "嶺南大學": ("岭南大学", "Lingnan University"),
    "聖方濟各大學": ("圣方济各大学", "Saint Francis University"),
    "職業訓練局 - 香港高等教育科技學院": ("职业训练局-香港高等教育科技学院",
                                        "Technological and Higher Education Institute of Hong Kong"),
    "香港中文大學": ("香港中文大学", "The Chinese University of Hong Kong"),
    "香港教育大學": ("香港教育大学", "The Education University of Hong Kong"),
    "香港恒生大學": ("香港恒生大学", "The Hang Seng University of Hong Kong"),
    "香港理工大學": ("香港理工大学", "The Hong Kong Polytechnic University"),
    "香港科技大學": ("香港科技大学", "The Hong Kong University of Science and Technology"),
    "香港大學": ("香港大学", "The University of Hong Kong"),
    "東華學院": ("东华学院", "Tung Wah College"),
    "香港伍倫貢學院": ("香港伍伦贡学院", "UOW College Hong Kong"),
    "耀中幼教學院": ("耀中幼教学院", "Yew Chung College of Early Childhood Education"),
}


def collect(conn) -> dict:
    stats = {"parsed_from_page": 0, "verified_en": 0, "inserted": 0,
             "updated": 0, "unchanged": 0, "failed": []}
    r_tc = fetch(URL_TC, SOURCE_ID)
    r_en = fetch(URL_EN, SOURCE_ID)
    if not r_tc["ok"] or not r_en["ok"]:
        db.add_quarantine(conn, SOURCE_ID, f"{SOURCE_ID}|_fetch|0", "FETCH_FAIL")
        return stats
    text_tc = html_to_text(r_tc["text"])
    text_en = html_to_text(r_en["text"])

    # 只收录「可頒授學位」段落内出现的院校（避免页面其他位置的名字混入）
    seg_start = text_tc.find("可頒授學位的高等教育院校")
    segment = text_tc[seg_start:seg_start + 3000] if seg_start > 0 else text_tc

    for tc_name, (zh, en) in HK_SCHOOLS.items():
        if tc_name.replace(" ", "") not in segment.replace(" ", ""):
            stats["failed"].append(f"NOT_ON_OFFICIAL_PAGE:{tc_name}")
            continue
        stats["parsed_from_page"] += 1
        if en.lower() not in text_en.lower():
            stats["failed"].append(f"EN_NOT_VERIFIED:{en}")
            continue
        stats["verified_en"] += 1
        rec = {
            "name_zh": zh, "name_en": en, "region": "hk", "recognized": 1,
            "source_url": URL_TC, "snapshot_ref": r_tc["snapshot_ref"],
            "fetched_at": db.now(),
            "content_hash": db.content_hash(f"{zh}|{en}|edb"),
        }
        res = db.upsert_recognized_school(conn, rec)
        stats[res] += 1
    db.set_state(conn, SOURCE_ID, "done")
    return stats


if __name__ == "__main__":
    config.load_env()
    conn = db.init_db()
    print(collect(conn))
    conn.commit()
    conn.close()
