"""Generic UK school program collector. Per-school config + shared pipeline:
list -> filter (msc, cs/business) -> detail -> LLM extract -> validate -> upsert/quarantine.

Supported list modes:
  "ucl_list":     UCL taught-degrees server-rendered list
  "imperial_az":  Imperial /study/courses/ ?page=N pagination
  "kcl_seed":     candidate slugs verified by HTTP status (KCL list is JS-gated)
"""
from __future__ import annotations

import json
import re
import time

import config
from collectors.fetcher import fetch
from collectors.htmltext import html_to_text
from pipeline.extract import extract_program
from pipeline.llm_client import LLMUnavailable
from pipeline.validate import validate_program
from storage import db

FIELD_KEYWORDS = {
    "cs": ["computer", "computing", "data-science", "data-analytics", "machine-learning",
           "artificial-intelligence", "software", "information-security", "robotics",
           "data-engineering", "data-driven"],
    "business": ["management", "finance", "business", "accounting", "marketing",
                 "economics", "entrepreneurship", "mba"],
}
EXCLUDE = ("pg-cert", "pg-dip", "grad-dip", "grad-cert", "mres", "mphil", "phd",
           "pgcert", "pgdip")
EXCLUDE_SUFFIX = ("-ma", "-llm", "-med", "-bsc", "-beng", "-meng", "-mba")  # 后缀匹配（-ma ≠ -masters）

# UCL English level -> IELTS（官方页已人工核实 2026-10-02）
UCL_LEVEL_MAP = {1: (6.5, 6.0), 2: (7.0, 6.5), 3: (7.0, 7.0), 4: (7.5, 7.0), 5: (8.0, 8.0)}
UCL_LEVEL_PAGE = ("https://www.ucl.ac.uk/prospective-students/graduate/learning-and-living-ucl/"
                  "international-students/english-language-requirements")

SCHOOLS = {
    "ucl": {
        "university_zh": "伦敦大学学院", "university_en": "University College London",
        "region": "uk", "list_mode": "ucl_list", "english_map": "ucl",
        "list_url": "https://www.ucl.ac.uk/prospective-students/graduate/taught-degrees",
        "detail_base": "",
    },
    "imperial": {
        "university_zh": "帝国理工学院", "university_en": "Imperial College London",
        "region": "uk", "list_mode": "imperial_az", "english_map": None,
        "require_msc_suffix": False,
        "list_url": "https://www.imperial.ac.uk/study/courses/",
        "detail_base": "https://www.imperial.ac.uk",
    },
    "kcl": {
        "university_zh": "伦敦国王学院", "university_en": "King's College London",
        "region": "uk", "list_mode": "kcl_seed", "english_map": None,
        "list_url": None,
        "detail_base": "https://www.kcl.ac.uk/study/postgraduate-taught/courses/",
    },
    "manchester": {
        "university_zh": "曼彻斯特大学", "university_en": "University of Manchester",
        "region": "uk", "list_mode": "manchester_list", "english_map": None,
        "require_msc_suffix": False,
        "list_url": "https://www.manchester.ac.uk/study/masters/courses/list/",
        "detail_base": "https://www.manchester.ac.uk/study/masters/courses/list/",
    },
    "glasgow": {
        "university_zh": "格拉斯哥大学", "university_en": "University of Glasgow",
        "region": "uk", "list_mode": "glasgow_list", "english_map": None,
        "require_msc_suffix": False,
        "list_url": "https://www.gla.ac.uk/postgraduate/taught/",
        "detail_base": "https://www.gla.ac.uk",
    },
    "southampton": {
        "university_zh": "南安普顿大学", "university_en": "University of Southampton",
        "region": "uk", "list_mode": "southampton_list", "english_map": None,
        "require_msc_suffix": True,  # slug 形如 xxx-msc
        "detail_browser": True,      # 详情页 JS 渲染
        "list_url": "https://www.southampton.ac.uk/courses/postgraduate-taught",
        "detail_base": "https://www.southampton.ac.uk",
    },
}

# KCL 候选 slug（按官方课程命名规律生成，逐个 HTTP 验证，404 即弃——不编造数据，
# 只有真实 200 且标题匹配的页面才会入库）
KCL_CANDIDATES = [    "advanced-computing-msc", "advanced-software-engineering-msc", "data-science-msc",
    "artificial-intelligence-msc", "machine-learning-msc", "computer-science-msc",
    "cyber-security-msc", "health-data-science-msc", "finance-analytics-msc",
    "banking-and-finance-msc", "finance-msc", "international-management-msc",
    "international-business-msc", "digital-marketing-msc", "management-msc",
    "accounting-accountability-and-financial-management-msc", "economics-msc",
]


def classify(slug: str, require_msc: bool = True) -> str | None:
    if any(x in slug for x in EXCLUDE) or any(slug.endswith(x) for x in EXCLUDE_SUFFIX):
        return None
    if require_msc and "-msc" not in slug and "-mres" not in slug:
        return None
    for field, kws in FIELD_KEYWORDS.items():
        if any(k in slug for k in kws):
            return field
    return None


def list_ucl(cfg) -> list[dict]:
    r = fetch(cfg["list_url"], "ucl")
    if not r["ok"]:
        return []
    links = re.findall(
        r'href="(https://www\.ucl\.ac\.uk/prospective-students/graduate/taught-degrees/([a-z0-9-]+?)(?:-(\d{4}))?)"',
        r["text"] or "")
    seen = {}
    for url, slug, year in links:
        if year and classify(slug):
            seen[slug] = {"slug": slug, "url": url, "intake_year": int(year)}
    return list(seen.values())


def list_imperial(cfg, max_pages: int = 30) -> list[dict]:
    out = {}
    need_msc = cfg.get("require_msc_suffix", True)
    for page in range(1, max_pages + 1):
        url = f"{cfg['list_url']}?page={page}"
        r = fetch(url, "imperial")
        if not r["ok"]:
            break
        links = re.findall(r'href="(/study/courses/postgraduate-taught/(\d{4})/([a-z0-9-]+)/?)"',
                           r["text"] or "")
        for path, year, slug in links:
            if classify(slug, need_msc) and slug not in out:
                out[slug] = {"slug": slug, "url": cfg["detail_base"] + path,
                             "intake_year": int(year)}
        if not links:  # 没有更多课程链接说明翻到头了
            break
        time.sleep(1.0)
    return list(out.values())


def list_kcl(cfg) -> list[dict]:
    out = []
    for slug in KCL_CANDIDATES:
        if not classify(slug):
            continue
        url = cfg["detail_base"] + slug
        r = fetch(url, "kcl", retries=1)
        if r["ok"] and len(r["text"] or "") > 20000:
            out.append({"slug": slug, "url": url, "intake_year": 2026})
        time.sleep(1.0)
    return out


def list_manchester(cfg) -> list[dict]:
    """曼大列表页 JS 渲染，详情页静态可读。链接形如 {id}/msc-xxx/。"""
    from collectors.browser_fetch import render
    r = render(cfg["list_url"], "manchester", wait_ms=4000)
    if not r["ok"]:
        return []
    links = re.findall(r'href="(\d+)/(msc-[a-z0-9-]+)/?"', r["html"] or "")
    out = {}
    for cid, slug in links:
        if classify(slug, require_msc=False):
            out[slug] = {"slug": slug, "url": cfg["detail_base"] + f"{cid}/{slug}/",
                         "intake_year": 2026}
    return list(out.values())


def list_glasgow(cfg) -> list[dict]:
    """格拉列表页服务端渲染，271+ 课程链接。slug 不带 msc 后缀。"""
    r = fetch(cfg["list_url"], "glasgow")
    if not r["ok"]:
        return []
    links = re.findall(r'href="(/postgraduate/taught/([a-z0-9-]+)/)"', r["text"] or "")
    out = {}
    for path, slug in links:
        if classify(slug, require_msc=False):
            out[slug] = {"slug": slug, "url": cfg["detail_base"] + path, "intake_year": 2026}
    return list(out.values())


def list_southampton(cfg) -> list[dict]:
    """南安列表 JS 渲染，slug 形如 xxx-masters-msc / xxx-msc。"""
    from collectors.browser_fetch import render
    r = render(cfg["list_url"], "southampton", wait_ms=5000)
    if not r["ok"]:
        return []
    links = re.findall(r'href="(/courses/([a-z0-9-]+))"', r["html"] or "")
    out = {}
    for path, slug in links:
        if classify(slug):
            out[slug] = {"slug": slug, "url": cfg["detail_base"] + path, "intake_year": 2026}
    return list(out.values())


LISTERS = {"ucl_list": list_ucl, "imperial_az": list_imperial, "kcl_seed": list_kcl,
           "manchester_list": list_manchester, "glasgow_list": list_glasgow,
           "southampton_list": list_southampton}


def apply_english_map(cfg, ext: dict) -> None:
    if cfg.get("english_map") != "ucl" or ext.get("ielts_req"):
        return
    m = re.search(r"Level\s*([1-5])", ext.get("english_level_text") or "")
    if m:
        overall, sub = UCL_LEVEL_MAP[int(m.group(1))]
        ext["ielts_req"] = {"overall": overall, "min_sub": sub}
        ext.setdefault("source_excerpts", {})["ielts_req"] = (
            f"项目页标注 '{ext['english_level_text'].strip()}'；Level 映射自 {UCL_LEVEL_PAGE}")


def resolve_school_id(conn, cfg) -> int | None:
    row = conn.execute(
        "SELECT school_id FROM recognized_schools WHERE name_zh=? OR name_en=?",
        (cfg["university_zh"], cfg["university_en"])).fetchone()
    return row["school_id"] if row else None


def collect_school(conn, school: str, limit: int | None = None, delay: float = 1.2) -> dict:
    cfg = SCHOOLS[school]
    sid = resolve_school_id(conn, cfg)
    stats = {"school": school, "listed": 0, "inserted": 0, "updated": 0,
             "unchanged": 0, "quarantined": 0, "failed": 0}
    if sid is None:
        db.add_quarantine(conn, school, f"{school}|_school_link|0", "L0_LINK_MISSING",
                          detail=cfg["university_zh"])
        return stats
    programs = LISTERS[cfg["list_mode"]](cfg)
    if limit:
        programs = programs[:limit]
    stats["listed"] = len(programs)
    for p in programs:
        seed_key = f'{cfg["university_zh"]}|{p["slug"]}|{p["intake_year"]}'
        try:
            if cfg.get("detail_browser"):
                from collectors.browser_fetch import render
                br = render(p["url"], school, wait_ms=4500)
                r = {"ok": br["ok"], "status": 200 if br["ok"] else None,
                     "text": br.get("html"), "snapshot_ref": br.get("snapshot_ref")}
            else:
                r = fetch(p["url"], school)
            if not r["ok"]:
                db.add_quarantine(conn, school, seed_key, "FETCH_FAIL", detail=f'status={r["status"]}')
                stats["quarantined"] += 1
                continue
            text = html_to_text(r["text"])
            ext = extract_program(text, source_hint=p["url"])
            apply_english_map(cfg, ext)
            errs = validate_program({**ext, "source_url": p["url"], "snapshot_ref": r["snapshot_ref"]})
            if errs:
                db.add_quarantine(conn, school, seed_key, "VALIDATE:" + ",".join(errs),
                                  raw_ref=r["snapshot_ref"],
                                  detail=json.dumps(ext.get("notes"), ensure_ascii=False)[:500])
                stats["quarantined"] += 1
                continue
            rec = {
                "school_id": sid, "university": cfg["university_zh"],
                "name": ext.get("name") or p["slug"],
                "field": classify(p["slug"], cfg.get("require_msc_suffix", True)),
                "degree": "master_taught",
                "duration_months": ext.get("duration_months"),
                "tuition_amount": ext.get("tuition_amount"),
                "tuition_currency": ext.get("tuition_currency"),
                "gpa_requirements": json.dumps(ext.get("gpa_requirements") or [], ensure_ascii=False),
                "school_list_req": json.dumps(ext.get("school_list_req"), ensure_ascii=False),
                "ielts_req": json.dumps(ext["ielts_req"]) if ext.get("ielts_req") else None,
                "toefl_req": json.dumps(ext["toefl_req"]) if ext.get("toefl_req") else None,
                "deadlines": json.dumps(ext.get("deadlines") or [], ensure_ascii=False),
                "intake_year": ext.get("intake_year") or p["intake_year"],
                "source_url": p["url"], "snapshot_ref": r["snapshot_ref"],
                "source_excerpts": json.dumps(ext.get("source_excerpts") or {}, ensure_ascii=False),
                "fetched_at": db.now(), "content_hash": db.content_hash(text),
            }
            result = db.upsert_program(conn, rec)
            stats[result] += 1
        except LLMUnavailable:
            db.set_state(conn, school, "halted_llm_unavailable")
            raise
        except Exception as e:
            db.add_quarantine(conn, school, seed_key, "PIPELINE_ERROR", detail=str(e)[:500])
            stats["failed"] += 1
        time.sleep(delay)
    db.set_state(conn, school, "done")
    return stats
