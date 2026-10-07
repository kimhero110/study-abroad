"""Polite targeted fetcher: rate-limited (>=1s/req), retries with backoff,
raw snapshot to disk. No anti-bot circumvention; 403/404 marks failure.
"""
from __future__ import annotations

import time
import urllib.request
import urllib.error
from pathlib import Path

import config

_UA = "study-abroad-research-bot/0.1 (personal academic research; contact: local)"
_last_request_at = 0.0


def fetch(url: str, source: str, min_interval: float = 1.2, retries: int = 4,
          timeout: int = 30) -> dict:
    """Fetch url with rate limit + backoff retry. Saves raw snapshot.

    Returns {"ok": bool, "status": int|None, "text": str|None, "snapshot_ref": str|None}
    Never raises on HTTP errors; failure is data.
    """
    global _last_request_at
    for attempt in range(1, retries + 1):
        wait = min_interval - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.status
            text = _decode(raw)
            snap = _save_snapshot(raw, source, url)
            return {"ok": True, "status": status, "text": text, "snapshot_ref": snap}
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return {"ok": False, "status": e.code, "text": None, "snapshot_ref": None}
        except Exception:
            pass
        if attempt < retries:
            time.sleep(2 ** (attempt - 1))
    return {"ok": False, "status": None, "text": None, "snapshot_ref": None}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _save_snapshot(raw: bytes, source: str, url: str) -> str:
    from storage.db import content_hash, now
    day = now()[:10]
    d = config.RAW_DIR / source / day
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{content_hash(url)}.html"
    p.write_bytes(raw)
    return str(p.relative_to(config.ROOT))
