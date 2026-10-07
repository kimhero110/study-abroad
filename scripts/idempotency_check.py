"""THR-IDEM evidence: natural-key upsert idempotency on real records.

Re-upserts a sample of real programs/schools read straight from the catalog and
asserts the row count does not change ("unchanged" or "updated" in place, never a
new row). Writes reports/idempotency.json.

Note: full collector double-run needs the LLM endpoints; this isolates the storage
idempotency guarantee that the collectors rely on (REQ-007).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from storage import db  # noqa: E402

CST = timezone(timedelta(hours=8))


def main() -> int:
    conn = db.connect()
    before = {
        "recognized_schools": conn.execute("SELECT COUNT(*) c FROM recognized_schools").fetchone()["c"],
        "programs": conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"],
    }

    results = {"recognized_schools": [], "programs": []}
    for r in conn.execute("SELECT * FROM recognized_schools LIMIT 10"):
        rec = {k: r[k] for k in r.keys() if k != "school_id"}
        results["recognized_schools"].append(db.upsert_recognized_school(conn, rec))
    for r in conn.execute("SELECT * FROM programs LIMIT 50"):
        rec = {k: r[k] for k in r.keys() if k != "program_id"}
        results["programs"].append(db.upsert_program(conn, rec))
    conn.commit()

    after = {
        "recognized_schools": conn.execute("SELECT COUNT(*) c FROM recognized_schools").fetchone()["c"],
        "programs": conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"],
    }
    conn.close()

    delta = {k: after[k] - before[k] for k in before}
    report = {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "before": before,
        "after": after,
        "delta": delta,
        "sample_upsert_outcomes": {k: sorted(set(v)) for k, v in results.items()},
        "THR-IDEM_pass": all(v == 0 for v in delta.values()),
    }
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "idempotency.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    print("delta:", delta)
    print("outcomes:", report["sample_upsert_outcomes"])
    print("THR-IDEM_pass:", report["THR-IDEM_pass"])
    print("wrote reports/idempotency.json")
    return 0 if report["THR-IDEM_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
