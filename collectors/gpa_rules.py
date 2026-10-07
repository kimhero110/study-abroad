"""中国成绩折算标准（gpa_rules）：一等公民数据，不是后台隐藏参数。

设计原则（响应用户批评"处理过于草率"）：
1. 每条规则带官方逐字原文 + 来源 URL + 核实日期（与项目数据同等血缘要求）
2. 面向家长的平实解释（explanation）——解释"2:1 是什么"而不只给数字
3. 规则是唯一事实源；programs.gpa_requirements 由规则同步派生（可追溯）
4. 官方没写的东西宁可留空也不编造；"偏好"类信息如实标注为偏好，不伪装成门槛

已核实的规则：Imperial（官方页面原文已抓取核验 2026-10-03）。
UCL/KCL 的折算标准藏在 PDF/JS 页面，破解后按同样结构入库。
"""
from __future__ import annotations

import json

import config
from storage import db

# 已核实规则清单（excerpt 必须是官方页面逐字文本）
VERIFIED_RULES = [
    {
        "university": "帝国理工学院",
        "region": "uk",
        "requirement_class": "masters_general",
        "tiers": [
            {"tier": "C9", "min_gpa": 80},
            {"tier": "985", "min_gpa": 80},
            {"tier": "211", "min_gpa": 80},
        ],
        "allowed_tiers": ["C9", "985", "211"],
        "preference_note": "85% 或以上的申请者会被优先考虑（80 分是最低线，不是稳妥线）",
        "explanation": (
            "帝国理工对中国大陆申请者的统一要求：本科必须毕业于「211 工程」大学"
            "（985/C9 是 211 的子集，自然符合），最终均分 80% 以上。"
            "这意味着双非和「双一流（非211）」背景目前不具备申请资格——"
            "这是帝国理工官方明确写出的口径，不是我们的推断。"
            "注意「85% 优先」：80 分够格递交，但竞争中处于劣势；"
            "85 分以上才算有竞争力的背景。"
        ),
        "source_url": ("https://www.imperial.ac.uk/study/apply/postgraduate-taught/"
                       "entry-requirements/accepted-qualifications/"),
        "excerpt": ("China — To be considered for admission to a Master's e.g. MSc, MRes, "
                    "MBA etc, applicants should have been awarded a Bachelor's degree from "
                    "a Project 211 university with a final overall mark of 80% or better. "
                    "Preference is given to candidates with 85% or better."),
        "valid_intake": "2026/2027",
    },
    {
        "university": "伦敦大学学院",
        "region": "uk",
        "requirement_class": "ucl_custom_list",
        "tiers": [
            {"tier": "UCL名单内院校（77所）", "min_gpa": 85},
            {"tier": "名单外教育部认可院校", "min_gpa": 90},
        ],
        "allowed_tiers": None,
        "preference_note": "以上为 2:1 项目口径；2:2 项目对应降为 80%（名单内）/ 85%（名单外）。名单内苏州大学、西安电子科大、江南大学、燕山大学、浙工大、国防科大等 ** 注记院校另有专业限制（仅计算机专业享受名单内线）。",
        "explanation": (
            "UCL 不看 985/211 头衔，它有一份自己的中国大学名单（约 77 所），"
            "由校方委员会审定——所以会出现「燕山大学（双非）在名单内、"
            "部分 211 反而在名单外」的情况。"
            "名单内院校：2:1 项目要求均分 85%；名单外的教育部认可院校：2:1 项目要求 90%。"
            "这 5 分差距就是中介口中「UCL 卡名单」的全部秘密——名单本身公开可查，"
            "我们已把 77 所完整名单结构化入库（data/ucl_list.json），"
            "输入你的本科院校名称即可精确匹配，不靠头衔猜。"
        ),
        "source_url": "https://www.ucl.ac.uk/prospective-students/international/china",
        "excerpt": ("UCL Admissions use a list of Chinese Universities reviewed by the "
                    "relevant committee of the university and include a selection of "
                    "Project 211, Project 985, and Double First-Class universities. "
                    "Please note that not all universities from these projects are included. "
                    "Applicants from the list of universities: Upper second-class (2:1): "
                    "Bachelor's degree with a minimum weighted average mark of 85%. "
                    "Lower second-class (2:2): 80%. "
                    "Applicants from all other universities recognised by the Chinese "
                    "Ministry of Education: Upper second-class (2:1): 90%. "
                    "Lower second-class (2:2): 85%. "
                    "（经 Wayback Machine 2026-05-14 官方页快照核实，适用 2026/27 入学）"),
        "valid_intake": "2026/2027",
    },
]

# 英国学位等级速查（静态教育内容，随折算规则展示）
UK_DEGREE_CLASSES = {
    "1st": "一等学位：英国本科毕业成绩前 ~10-15%，最高等级",
    "2:1": "二等上（Upper Second）：英国本科毕业成绩前 ~35%，硕士申请最常见门槛",
    "2:2": "二等下（Lower Second）：英国本科毕业成绩前 ~65%，部分硕士项目接受",
    "3rd": "三等：基本不被硕士项目接受",
}


def sync(conn) -> dict:
    """规则入库（幂等 upsert），并把规则同步到对应学校的 programs.gpa_requirements。"""
    stats = {"rules": 0, "programs_synced": 0}
    for rule in VERIFIED_RULES:
        conn.execute(
            """INSERT INTO gpa_rules (university, region, requirement_class, tiers,
               allowed_tiers, preference_note, explanation, source_url, excerpt,
               verified_at, valid_intake)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(university, requirement_class) DO UPDATE SET
               tiers=excluded.tiers, allowed_tiers=excluded.allowed_tiers,
               preference_note=excluded.preference_note, explanation=excluded.explanation,
               source_url=excluded.source_url, excerpt=excluded.excerpt,
               verified_at=excluded.verified_at, valid_intake=excluded.valid_intake""",
            (rule["university"], rule["region"], rule["requirement_class"],
             json.dumps(rule["tiers"]), json.dumps(rule["allowed_tiers"]),
             rule["preference_note"], rule["explanation"], rule["source_url"],
             rule["excerpt"], db.now(), rule["valid_intake"]))
        stats["rules"] += 1
        # 派生同步到 programs（规则是唯一事实源）
        rule_ref = f'依据《中国成绩折算标准》: {rule["source_url"]}'
        cur = conn.execute(
            "UPDATE programs SET gpa_requirements=?, school_list_req=?, "
            "source_excerpts=json_set(COALESCE(source_excerpts,'{}'), '$.gpa_rule', ?) "
            "WHERE university=? AND (gpa_requirements IS NULL OR gpa_requirements='[]')",
            (json.dumps(rule["tiers"]),
             json.dumps({"has_list": True, "allowed_tiers": rule["allowed_tiers"],
                         "notes": rule["preference_note"]}, ensure_ascii=False),
             rule_ref, rule["university"]))
        stats["programs_synced"] += cur.rowcount
    conn.commit()
    return stats


def list_rules(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM gpa_rules ORDER BY university").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tiers"] = json.loads(d["tiers"])
        d["allowed_tiers"] = json.loads(d["allowed_tiers"]) if d["allowed_tiers"] else None
        out.append(d)
    return out


if __name__ == "__main__":
    config.load_env()
    conn = db.init_db()
    print(sync(conn))
    conn.close()
