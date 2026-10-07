"""THR-NOLLM static audit (REQ-008): the matching engine must never call an LLM.

Frozen assertion patterns (from thresholds.wp-001.json THR-NOLLM):
  (1) no import/reference matching openai|anthropic|ollama|deepseek|
      requests.*chat|http.*11434|/chat/completions
  (2) no environment-variable reference to LLM_|DEEPSEEK|OLLAMA
  (3) matching/ dependencies limited to storage/ and the standard library

Writes reports/audit.json; exits non-zero if any pattern hits.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CST = timezone(timedelta(hours=8))

PATTERNS = [
    ("import_llm_client", re.compile(
        r"\b(openai|anthropic|ollama|deepseek)\b|requests\..*chat|https?://[^\s]*11434|/chat/completions",
        re.IGNORECASE)),
    ("llm_env_ref", re.compile(r"LLM_|DEEPSEEK|OLLAMA", re.IGNORECASE)),
]
# local package imports allowed in matching/
ALLOWED_LOCAL = {"storage"}
STDLIB_OK = re.compile(r"^(__future__|json|re|math|datetime|pathlib|typing|collections|functools|itertools|decimal)$")


def main() -> int:
    matching = ROOT / "matching"
    hits = []
    imported = set()
    for path in sorted(matching.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name, pat in PATTERNS:
            for m in pat.finditer(text):
                hits.append({"file": str(path.relative_to(ROOT)), "pattern": name,
                             "match": m.group(0)})
        for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z_][\w\.]*)", text, re.MULTILINE):
            imported.add(m.group(1).split(".")[0])
    bad_local = sorted(i for i in imported
                       if not STDLIB_OK.fullmatch(i) and i not in ALLOWED_LOCAL and i != "matching")

    report = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "audited_dir": "matching/",
        "patterns": [p[0] for p in PATTERNS],
        "hits": hits,
        "imports": sorted(imported),
        "disallowed_local_imports": bad_local,
        "THR-NOLLM_pass": not hits and not bad_local,
    }
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    print("hits:", hits)
    print("imports:", sorted(imported))
    print("disallowed_local_imports:", bad_local)
    print("THR-NOLLM_pass:", report["THR-NOLLM_pass"])
    print("wrote reports/audit.json")
    return 0 if report["THR-NOLLM_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
