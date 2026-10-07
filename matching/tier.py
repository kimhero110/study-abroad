"""Matching engine: pure deterministic rules, NO LLM (THR-NOLLM).

Frozen tier rules (technical-plan「分档规则」):
  Step 1 hard filter: list req; gpa >= min_gpa - 3; ielts overall/min_sub
                      (language missing -> keep but cap at match, flag language_pending)
  Step 2 tier: margin = gpa - min_gpa(user tier)
               safety: margin >= +5 and language ok
               match:  0 <= margin < +5
               reach:  -3 <= margin < 0
               no tier-specific requirement data -> not tiered
  Step 3 reject: all tiers empty -> insufficient
"""
from __future__ import annotations

import json


def _loads(s):
    return json.loads(s) if isinstance(s, str) and s else (s if isinstance(s, (list, dict)) else None)


_UCL_LIST = None


def _ucl_list():
    """UCL 自有名单（data/ucl_list.json，官方页核实）。"""
    global _UCL_LIST
    if _UCL_LIST is None:
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "data" / "ucl_list.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        _UCL_LIST = {u["zh"] for u in d["universities"]} | {u["en"].lower() for u in d["universities"]}
    return _UCL_LIST


def _ucl_lookup(school: str) -> bool:
    s = (school or "").strip().lower()
    if not s:
        return False
    for name in _ucl_list():
        if name.lower() in s or s in name.lower():
            return True
    return False


def ucl_requirement(program: dict, bg: dict) -> tuple[float | None, str | None]:
    """UCL 自有名单逻辑（官方规则）：
    名单内 2:1=85 / 2:2=80；名单外 2:1=90 / 2:2=85。
    返回 (min_gpa, note)。未提供校名返回 (None, 原因)。
    """
    req = _loads(program.get("school_list_req")) or {}
    degree_class = req.get("degree_class", "2:1")
    school = bg.get("undergrad_school")
    if not school:
        return None, "UCL 按自有名单（77所）划线，需要提供本科院校名称才能匹配"
    on_list = _ucl_lookup(school)
    table = {"2:1": (85, 90), "2:2": (80, 85)}
    in_gpa, out_gpa = table.get(degree_class, table["2:1"])
    min_gpa = in_gpa if on_list else out_gpa
    note = (f"你的本科院校{'在' if on_list else '不在'}UCL 自有名单内"
            f"（{'名单内' if on_list else '名单外'}线 {min_gpa}%，{degree_class} 项目）")
    return min_gpa, note


def effective_requirement(program: dict, bg: dict) -> tuple[float | None, str | None, str | None]:
    """统一计算项目对当前背景的最低均分要求。
    返回 (min_gpa, note, exclude_reason)。exclude_reason 非空表示该项目对当前背景不可参与分档。
    """
    req = _loads(program.get("school_list_req")) or {}
    if req.get("type") == "ucl_custom_list":
        min_gpa, note = ucl_requirement(program, bg)
        if min_gpa is None:
            return None, None, note  # 缺校名，不入档
        return min_gpa, note, None
    # 名单要求（tier 制）
    if req.get("has_list") and req.get("allowed_tiers"):
        if bg["undergrad_tier"] not in req["allowed_tiers"]:
            return None, None, "本科院校层次不在该项目名单要求内"
    gpa_reqs = {i["tier"]: i["min_gpa"] for i in (_loads(program.get("gpa_requirements")) or [])}
    tier = bg["undergrad_tier"]
    if tier not in gpa_reqs:
        return None, None, "no_tier_data"
    return gpa_reqs[tier], None, None


def check_hard_filter(program: dict, bg: dict) -> tuple[bool, str | None, bool]:
    """Returns (kept, reject_reason, language_pending)."""
    lang_pending = False

    # 均分要求（UCL 自有名单 / tier 制统一入口）
    min_gpa, note, exclude = effective_requirement(program, bg)
    if exclude:
        return False, exclude, lang_pending
    if bg["gpa"] < min_gpa - 3:
        return False, f"均分 {bg['gpa']} 低于要求 {min_gpa} 超过 3 分冲刺上限", lang_pending

    # 语言
    ielts = _loads(program.get("ielts_req"))
    if ielts and ielts.get("overall"):
        if bg.get("ielts") is None:
            lang_pending = True  # 未考语言：不剔除，封顶 match
        else:
            if bg["ielts"] < ielts["overall"]:
                return False, f"IELTS {bg['ielts']} 低于要求 {ielts['overall']}", lang_pending
            if ielts.get("min_sub") and bg.get("ielts_min_sub") is not None \
                    and bg["ielts_min_sub"] < ielts["min_sub"]:
                return False, f"IELTS 单项 {bg['ielts_min_sub']} 低于要求 {ielts['min_sub']}", lang_pending

    return True, None, lang_pending


def assign_tier(program: dict, bg: dict, lang_pending: bool) -> str:
    """margin 分档（冻结边界 +5/0/-3）。"""
    min_gpa, note, exclude = effective_requirement(program, bg)
    margin = bg["gpa"] - min_gpa
    if margin >= 5:
        return "match" if lang_pending else "safety"  # 语言未达标封顶 match（冻结规则）
    if 0 <= margin < 5:
        return "match"
    return "reach"  # -3 <= margin < 0（更低于 Step 1 已剔除）


def match_programs(programs: list[dict], bg: dict) -> dict:
    """bg: {"undergrad_tier","gpa","ielts"|None,"ielts_min_sub"|None,"target_field"}"""
    tiers = {"reach": [], "match": [], "safety": []}
    for p in programs:
        if bg.get("target_field") and p.get("field") != bg["target_field"]:
            continue
        kept, reason, lang_pending = check_hard_filter(p, bg)
        if not kept:
            if reason != "no_tier_data":
                continue
            continue  # 无 tier 数据一律不入档（冻结规则）
        tier = assign_tier(p, bg, lang_pending)
        if lang_pending and tier == "safety":
            tier = "match"  # 语言未达标封顶 match
        tiers[tier].append(p)

    total = sum(len(v) for v in tiers.values())
    if total == 0:
        return {"tiers": tiers, "data_sufficiency": "insufficient",
                "insufficient_reason": "按当前背景与已采集的官方要求，没有符合条件的项目；"
                                       "可能是背景差距过大或该方向数据不足。"}
    return {"tiers": tiers, "data_sufficiency": "ok"}


def build_reason(program: dict, bg: dict, tier: str) -> list[str]:
    """Deterministic template reasons (no LLM)."""
    min_gpa, note, exclude = effective_requirement(program, bg)
    margin = bg["gpa"] - min_gpa
    tier_zh = {"safety": "保底", "match": "匹配", "reach": "冲刺"}[tier]
    reasons = []
    if note:
        reasons.append(note)
    reasons.append(f"你的均分 {bg['gpa']} 相对该项目要求 {min_gpa} "
                   f"余量 {margin:+.1f} 分，按规则划入{tier_zh}档")
    ielts = _loads(program.get("ielts_req"))
    if ielts and ielts.get("overall"):
        if bg.get("ielts") is None:
            reasons.append(f"该项目要求 IELTS {ielts['overall']}，你尚未提供语言成绩（档位已封顶为「匹配」）")
        else:
            reasons.append(f"语言达标：IELTS {bg['ielts']} ≥ 要求 {ielts['overall']}")
    reasons.append("分档完全基于官方公布的硬性要求；录取案例数据建设中。")
    return reasons
