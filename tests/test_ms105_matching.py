"""MS-105 unit tests: matching engine vs frozen tier rules (hand-computed expectations).

Covers E-001~E-010 logic: normal tiering, margin boundaries (±5/0/-3), language sub-score,
missing language cap, tier-data missing, list rejection, insufficient rejection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from matching.tier import match_programs, check_hard_filter, assign_tier, build_reason  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


PROG = {
    "university": "测试大学", "name": "MSc CS", "field": "cs",
    "gpa_requirements": '[{"tier":"985","min_gpa":85},{"tier":"211","min_gpa":87},{"tier":"shuangfei","min_gpa":90}]',
    "school_list_req": None,
    "ielts_req": '{"overall":7.0,"min_sub":6.5}',
}
PROG_NO_TIER = {**PROG, "name": "MSc NoTier", "gpa_requirements": '[{"tier":"C9","min_gpa":85}]'}
PROG_LIST = {**PROG, "name": "MSc List",
             "school_list_req": '{"has_list":true,"allowed_tiers":["C9","985"]}'}

# --- E-001: 985/88/IELTS7.0 -> safety boundary tests
bg = {"undergrad_tier": "985", "gpa": 90.0, "ielts": 7.0, "ielts_min_sub": 6.5, "target_field": "cs"}
r = match_programs([PROG], bg)
check("E-001a margin=+5.0 -> safety (boundary >=+5)", r["tiers"]["safety"] and not r["tiers"]["match"])

bg4 = {**bg, "gpa": 89.9}
check("margin=+4.9 -> match", match_programs([PROG], bg4)["tiers"]["match"])

bg0 = {**bg, "gpa": 85.0}
check("margin=0 -> match (boundary)", match_programs([PROG], bg0)["tiers"]["match"])

bgm = {**bg, "gpa": 84.9}
check("margin=-0.1 -> reach", match_programs([PROG], bgm)["tiers"]["reach"])

bgm3 = {**bg, "gpa": 82.0}
check("margin=-3 -> reach (boundary)", match_programs([PROG], bgm3)["tiers"]["reach"])

bgm31 = {**bg, "gpa": 81.9}
r = match_programs([PROG], bgm31)
check("margin=-3.1 -> filtered out -> insufficient",
      r["data_sufficiency"] == "insufficient" and not any(r["tiers"].values()))

# --- language: sub-score fail -> reject
bg_sub = {**bg, "gpa": 90.0, "ielts": 7.0, "ielts_min_sub": 6.0}
check("ielts sub 6.0 < 6.5 -> insufficient", match_programs([PROG], bg_sub)["data_sufficiency"] == "insufficient")

# --- language missing -> cap at match
bg_nolang = {"undergrad_tier": "985", "gpa": 92.0, "ielts": None, "ielts_min_sub": None, "target_field": "cs"}
r = match_programs([PROG], bg_nolang)
check("no language + margin +7 -> capped match", r["tiers"]["match"] and not r["tiers"]["safety"])

# --- tier data missing -> not tiered
r = match_programs([PROG_NO_TIER], bg)
check("no tier req data -> excluded (insufficient when alone)", r["data_sufficiency"] == "insufficient")

# --- list rejection
bg_sf = {**bg, "undergrad_tier": "shuangfei", "gpa": 95.0}
check("list req excludes shuangfei", match_programs([PROG_LIST], bg_sf)["data_sufficiency"] == "insufficient")

# --- target field filter
r = match_programs([PROG], {**bg, "target_field": "business"})
check("field mismatch -> insufficient", r["data_sufficiency"] == "insufficient")

# --- E-003 style: weak background
bg_weak = {"undergrad_tier": "shuangfei", "gpa": 70.0, "ielts": None, "ielts_min_sub": None, "target_field": "cs"}
check("E-003 weak bg -> insufficient zero recs", match_programs([PROG], bg_weak)["data_sufficiency"] == "insufficient")

# --- reasons carry citation basis + disclaimer
rs = build_reason(PROG, bg, "safety")
check("reason mentions margin & official-only note",
      any("余量 +5.0" in x for x in rs) and any("官方公布" in x for x in rs))

# --- multi-program tier distribution
r = match_programs([PROG, {**PROG, "name": "MSc Easy",
                           "gpa_requirements": '[{"tier":"985","min_gpa":80}]'}], bg)
check("two programs tiered independently", len(r["tiers"]["safety"]) == 2)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("ALL PASS (MS-105)")
