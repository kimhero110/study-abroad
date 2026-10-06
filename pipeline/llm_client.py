"""OpenAI-compatible LLM client (REQ-009). Provider-agnostic:
base_url/api_key/model from env; optional fallback endpoint.
Both endpoints down -> raise LLMUnavailable (caller: halt & report to human).
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

import config


class LLMUnavailable(Exception):
    pass


def chat(messages: list[dict], max_tokens: int = 8192, temperature: float = 0.0,
         json_mode: bool = True, timeout: int = 180) -> dict:
    """Returns {"content": str, "model": str, "endpoint": base_url}. Raises LLMUnavailable."""
    last_err = None
    for ep in config.llm_endpoints():
        body = {"model": ep["model"], "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            ep["base_url"] + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": "Bearer " + ep["api_key"],
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if not content:
                raise LLMUnavailable("empty content (reasoning budget exhausted?)")
            return {"content": content, "model": data.get("model"), "endpoint": ep["base_url"]}
        except Exception as e:
            last_err = e
            continue
    raise LLMUnavailable(f"all endpoints failed: {last_err}")


def chat_json(messages: list[dict], retries: int = 3, **kw) -> dict:
    """chat() + robust JSON parse (strip code fences). Raises LLMUnavailable / ValueError."""
    for attempt in range(1, retries + 1):
        r = chat(messages, **kw)
        text = r["content"].strip()
        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return {"data": json.loads(text.strip()), "endpoint": r["endpoint"]}
        except json.JSONDecodeError:
            if attempt == retries:
                raise ValueError(f"LLM returned non-JSON after {retries} attempts")
    raise ValueError("unreachable")
