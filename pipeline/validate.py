"""Rule validation for extracted program fields. Failures go to quarantine, never to DB.

Ranges (frozen in plan): gpa 0-100, ielts 0-9, toefl 0-120, ISO dates, positive tuition.
"""
from __future__ import annotations

import re
from datetime import date

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_TIERS = {"C9", "985", "211", "shuangyiliu", "shuangfei", "overseas"}


def _valid_date(s) -> bool:
    if not isinstance(s, str) or not _ISO.match(s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def validate_program(rec: dict) -> list[str]:
    """Returns list of failure reason codes; empty = pass."""
    errs = []
    gpa = rec.get("gpa_requirements")
    if gpa is not None and not isinstance(gpa, list):
        errs.append("GPA_SHAPE")
        gpa = None
    for item in gpa or []:
        if not isinstance(item, dict) or item.get("tier") not in _VALID_TIERS:
            errs.append("GPA_TIER_INVALID")
            continue
        g = item.get("min_gpa")
        if not isinstance(g, (int, float)) or not (0 < g <= 100):
            errs.append("GPA_RANGE")
    for key in ("ielts_req", "toefl_req"):
        v = rec.get(key)
        if v is None:
            continue
        if not isinstance(v, dict):
            errs.append(key.upper() + "_SHAPE")
            continue
        limit = 9 if key == "ielts_req" else 120
        for sub in ("overall", "min_sub"):
            x = v.get(sub)
            if x is not None and (not isinstance(x, (int, float)) or not (0 < x <= limit)):
                errs.append(key.upper() + "_RANGE")
    dl = rec.get("deadlines")
    if dl is not None and not isinstance(dl, list):
        errs.append("DEADLINE_SHAPE")
        dl = None
    for d in dl or []:
        if not isinstance(d, dict) or not _valid_date(d.get("close_date")):
            errs.append("DEADLINE_DATE")
    t = rec.get("tuition_amount")
    if t is not None and (not isinstance(t, (int, float)) or t <= 0):
        errs.append("TUITION_RANGE")
    dur = rec.get("duration_months")
    if dur is not None and (not isinstance(dur, int) or not (1 <= dur <= 48)):
        errs.append("DURATION_RANGE")
    if not rec.get("source_url") or not rec.get("snapshot_ref"):
        errs.append("LINEAGE_MISSING")
    return sorted(set(errs))
