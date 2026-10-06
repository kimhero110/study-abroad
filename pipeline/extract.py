"""LLM extraction of program fields from page text (JSON-schema-constrained prompt).

LLM ONLY extracts; it never decides anything in matching (REQ-008).
Every numeric field must come with a verbatim excerpt from the page (source_excerpts),
enabling field-level human audit (THR-EXTRACT) and snapshot fallback (REQ-004).
"""
from __future__ import annotations

from pipeline.llm_client import chat_json

SYSTEM = """你是留学项目页结构化抽取器。从给定网页正文中抽取字段，输出严格 JSON。
规则：
1. 只输出网页中明确出现的信息；没有就输出 null，禁止推测。
2. 每个非 null 的数字/日期字段必须同时在 source_excerpts 中给出网页原文片段（逐字引用，<=200字符）。
3. gpa_requirements：若页面按申请者背景分档要求（如不同院校层次不同均分），逐档输出；
   tier 取值限 C9/985/211/shuangyiliu/shuangfei/overseas；无法映射的档位放 notes。
4. 输出 JSON 结构：
{
 "name": str, "duration_months": int|null,
 "tuition_amount": number|null, "tuition_currency": str|null,
 "tuition_basis": "overseas|uk|home|null",
 "gpa_requirements": [{"tier": str, "min_gpa": number}]|[],
 "school_list_req": {"has_list": bool, "notes": str|null}|null,
 "ielts_req": {"overall": number, "min_sub": number|null}|null,
 "toefl_req": {"overall": number, "min_sub": number|null}|null,
 "deadlines": [{"round": int, "close_date": "YYYY-MM-DD"}]|[],
 "intake_year": int|null,
 "english_level_text": str|null,
 "source_excerpts": {"<field>": "<原文片段>"},
 "notes": str|null
}"""


import re

# (关键词, 优先级) —— 高优先级先分预算；通用词（Application 等）易命中导航 boilerplate，降权
SECTION_KEYWORDS = [
    ("Entry requirements", 3), ("entry requirements", 3), ("IELTS", 3),
    ("English language", 3), ("Tuition fees", 3), ("tuition fees", 3),
    ("Fees and funding", 3), ("Fees & funding", 3), ("Fees", 2),
    ("deadline", 2), ("Deadline", 2), ("Duration", 2), ("Programme starts", 2),
    ("Course overview", 1), ("How to apply", 1), ("Application", 1),
]
_SCORE_RE = re.compile(r"£\s?\d|\d\.\d\s*(overall|subtest)|average score|\d{1,2}%|\d{4}-\d{2}-\d{2}")


def _best_occurrence(page_text: str, kw: str) -> int:
    """同一关键词多处出现时，选「附近含数字/金额/分数线」的那次（导航栏只命中文字）。"""
    best, best_score = -1, 0
    start = 0
    while True:
        i = page_text.find(kw, start)
        if i < 0:
            break
        ctx = page_text[i:i + 1500]
        score = len(_SCORE_RE.findall(ctx))
        if score > best_score:
            best, best_score = i, score
        start = i + len(kw)
    return best


def focused_text(page_text: str, budget: int = 100000) -> str:
    """正文窗口化只用于超大页面兜底；正常页面（<100K 字符）全文送入。
    项目页通常 30-60K 字符（~10-15K token），模型上下文足够；
    此前 12K 截断导致正文缺失（南安事故根因：前 N 字符全是 CSS/nav）。"""
    if len(page_text) <= budget:
        return page_text
    hits = []  # (priority, pos)
    for kw, pri in SECTION_KEYWORDS:
        start, cnt = 0, 0
        while cnt < 2:
            i = page_text.find(kw, start)
            if i < 0:
                break
            hits.append((pri, i))
            start = i + len(kw)
            cnt += 1
    if not hits:
        return page_text[:budget]
    # 优先级降序 + 位置升序；重叠窗口合并
    hits.sort(key=lambda x: (-x[0], x[1]))
    windows = []
    for pri, pos in hits:
        width = 4000 if pri == 3 else 2500
        s, e = max(0, pos - 800), min(len(page_text), pos + width)
        if windows and s <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], e))
        else:
            windows.append((s, e))
    out, total = [page_text[:600]], 600
    for s, e in windows:
        chunk = page_text[s:e]
        if total + len(chunk) > budget:
            chunk = chunk[:budget - total]
        if not chunk:
            break
        out.append(chunk)
        total += len(chunk)
        if total >= budget:
            break
    return "\n...\n".join(out)


def extract_program(page_text: str, source_hint: str = "") -> dict:
    """page_text -> extracted dict. Raises LLMUnavailable/ValueError."""
    text = focused_text(page_text)
    r = chat_json([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"来源：{source_hint}\n\n网页正文：\n{text}"},
    ], max_tokens=8192)
    return r["data"]
