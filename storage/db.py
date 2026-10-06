"""SQLite storage layer: WAL + busy_timeout + write retry (report-rag pattern),
natural-key upsert, collection state machine, quarantine.

Covers REQ-007 (idempotent collection) and the N-DATA decomposition leaf.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import config

_SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
_CST = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def with_retry(operation, retries: int = 8, backoff: int = 2, label: str = "db"):
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            last = exc
            if attempt >= retries:
                break
            time.sleep(backoff ** (attempt - 1))
    raise sqlite3.OperationalError(f"{label} failed after {retries} retries: {last}")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def upsert_recognized_school(conn: sqlite3.Connection, rec: dict) -> str:
    """Natural key (name_zh, region). Returns 'inserted' | 'updated' | 'unchanged'."""
    return _upsert(conn, "recognized_schools", rec, ["name_zh", "region"])


def upsert_program(conn: sqlite3.Connection, rec: dict) -> str:
    """Natural key (university, name, intake_year)."""
    return _upsert(conn, "programs", rec, ["university", "name", "intake_year"])


def _upsert(conn, table: str, rec: dict, key_fields: list[str]) -> str:
    where = " AND ".join(f"{k}=?" for k in key_fields)
    key_vals = [rec[k] for k in key_fields]
    row = conn.execute(f"SELECT * FROM {table} WHERE {where}", key_vals).fetchone()
    if row is None:
        cols = ", ".join(rec.keys())
        marks = ", ".join("?" for _ in rec)
        with_retry(lambda: conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(rec.values())))
        return "inserted"
    if row["content_hash"] == rec.get("content_hash"):
        return "unchanged"
    sets = ", ".join(f"{k}=?" for k in rec if k not in key_fields)
    vals = [rec[k] for k in rec if k not in key_fields] + key_vals
    with_retry(lambda: conn.execute(f"UPDATE {table} SET {sets} WHERE {where}", vals))
    return "updated"


def add_quarantine(conn, source_id: str, seed_key: str, reason_code: str,
                   raw_ref: str | None = None, detail: str | None = None) -> None:
    with_retry(lambda: conn.execute(
        "INSERT INTO quarantine (source_id, seed_key, reason_code, raw_ref, detail, created_at) VALUES (?,?,?,?,?,?)",
        (source_id, seed_key, reason_code, raw_ref, detail, now())))


def set_state(conn, source_id: str, status: str, last_cursor: str | None = None) -> None:
    def op():
        conn.execute(
            "INSERT INTO collect_state (source_id, last_cursor, status, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(source_id) DO UPDATE SET last_cursor=excluded.last_cursor, status=excluded.status, updated_at=excluded.updated_at",
            (source_id, last_cursor, status, now()))
    with_retry(op)


def get_state(conn, source_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM collect_state WHERE source_id=?", (source_id,)).fetchone()
    return dict(row) if row else None


def seed_reconciliation(conn, seeds: list[dict]) -> dict:
    """THR-SEED: every seed must be accounted for (in programs or quarantine).

    seeds: [{"university":..., "name":..., "intake_year":...}]
    Returns {"expected": N, "covered": n, "missing": [...], "per_school_quarantine": {...}}
    """
    missing, covered = [], 0
    for s in seeds:
        in_prog = conn.execute(
            "SELECT 1 FROM programs WHERE university=? AND name=? AND intake_year=?",
            (s["university"], s["name"], s["intake_year"])).fetchone()
        in_quar = conn.execute(
            "SELECT 1 FROM quarantine WHERE seed_key=?",
            (f'{s["university"]}|{s["name"]}|{s["intake_year"]}',)).fetchone()
        if in_prog or in_quar:
            covered += 1
        else:
            missing.append(s)
    per_school = {}
    for row in conn.execute(
            "SELECT json_extract(detail,'$.university') AS uni, COUNT(*) AS n FROM quarantine GROUP BY uni"):
        per_school[row["uni"]] = row["n"]
    return {"expected": len(seeds), "covered": covered, "missing": missing,
            "per_school_quarantine": per_school}


def mark_stale(conn, days: int = 60) -> int:
    cutoff = (datetime.now(_CST) - timedelta(days=days)).isoformat(timespec="seconds")
    cur = with_retry(lambda: conn.execute(
        "UPDATE programs SET stale=1 WHERE fetched_at < ? AND stale=0", (cutoff,)))
    return cur.rowcount
