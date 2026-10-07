"""Browser-based fetcher (Playwright/Chromium) for JS-rendered pages.
Used only when static fetch can't reach content (KCL country tables, UCL, NUS, HKU...).
Same politeness rules: one page at a time, snapshots saved.
"""
from __future__ import annotations

import time

import config


def render(url: str, source: str, wait_ms: int = 3000,
           actions: list[dict] | None = None, timeout: int = 45000) -> dict:
    """Render url in headless Chromium.

    actions: optional list of {"select": (selector, value)} / {"click": selector}
             / {"wait_ms": int} applied after load, before extracting text.
    Returns {"ok": bool, "text": str|None, "html": str|None, "snapshot_ref": str|None}
    """
    from playwright.sync_api import sync_playwright
    from storage.db import content_hash, now

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="study-abroad-research-bot/0.1 (personal academic research)")
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            for act in actions or []:
                if "select" in act:
                    sel, val = act["select"]
                    page.select_option(sel, label=val)
                    page.wait_for_timeout(2000)
                elif "click" in act:
                    page.click(act["click"])
                    page.wait_for_timeout(2000)
                elif "click_option" in act:
                    # 在容器内按文本点击选项，如 ("#opts .dropdown-option", "China")
                    sel, text = act["click_option"]
                    for o in page.query_selector_all(sel):
                        if (o.inner_text() or "").strip() == text:
                            o.click()
                            break
                    page.wait_for_timeout(3000)
                elif "wait_ms" in act:
                    page.wait_for_timeout(act["wait_ms"])
            html = page.content()
            text = page.inner_text("body")
            browser.close()
    except Exception as e:
        return {"ok": False, "text": None, "html": None, "snapshot_ref": None, "error": str(e)[:300]}

    day = now()[:10]
    d = config.RAW_DIR / source / day
    d.mkdir(parents=True, exist_ok=True)
    pth = d / f"{content_hash(url + str(actions))}.html"
    pth.write_text(html, encoding="utf-8")
    return {"ok": True, "text": text, "html": html,
            "snapshot_ref": str(pth.relative_to(config.ROOT))}
