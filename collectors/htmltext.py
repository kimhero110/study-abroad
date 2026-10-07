"""Shared HTML -> plain text helper for collectors."""
from __future__ import annotations

import html
import re


def html_to_text(page: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", page)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t)
    t = re.sub(r"<!--[\s\S]*?-->", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()
