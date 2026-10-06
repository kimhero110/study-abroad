"""Configuration: all settings from environment / .env file. No secrets in code.

LLM client is OpenAI-compatible and provider-agnostic (REQ-009):
  LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
  LLM_FALLBACK_BASE_URL / LLM_FALLBACK_API_KEY / LLM_FALLBACK_MODEL  (optional)
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "catalog.sqlite3"
RAW_DIR = ROOT / "data" / "raw"


def load_env(path: Path | None = None) -> None:
    p = path or (ROOT / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def llm_endpoints() -> list[dict]:
    """Primary + optional fallback OpenAI-compatible endpoint configs."""
    eps = []
    if get("LLM_BASE_URL") and get("LLM_API_KEY") and get("LLM_MODEL"):
        eps.append({
            "base_url": get("LLM_BASE_URL").rstrip("/"),
            "api_key": get("LLM_API_KEY"),
            "model": get("LLM_MODEL"),
        })
    if get("LLM_FALLBACK_BASE_URL") and get("LLM_FALLBACK_API_KEY") and get("LLM_FALLBACK_MODEL"):
        eps.append({
            "base_url": get("LLM_FALLBACK_BASE_URL").rstrip("/"),
            "api_key": get("LLM_FALLBACK_API_KEY"),
            "model": get("LLM_FALLBACK_MODEL"),
        })
    return eps
