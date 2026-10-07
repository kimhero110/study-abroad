"""Query/compute HTTP API — Python stdlib only (zero dependency).

Endpoints:
  GET  /api/schools/recognition?name=...   L0 认可查询（命中/未命中冻结契约）
  GET  /api/programs?field=cs|business     项目列表
  GET  /api/programs/{id}                  项目详情
  POST /api/match                          背景 -> 三档选校（引用强制）
  GET  /                                   单页 UI (web/index.html)

Bind 127.0.0.1 only. No admin endpoints. (FastAPI migration deferred.)
"""
from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import config
from matching.tier import match_programs, build_reason
from storage import db

LIST_PAGE_URL = "https://yxcx.cscse.edu.cn/"
NOTICE = ("本结果全部基于官方公开信息，仅供参考；申请要求以学校官网为准。"
          "录取案例数据建设中。未出现在认可名单中不等于不被认可。")


def _conn() -> sqlite3.Connection:
    return db.connect()


def recognition(name: str) -> dict:
    conn = _conn()
    row = conn.execute(
        "SELECT name_zh, name_en, region, source_url, snapshot_ref, fetched_at "
        "FROM recognized_schools WHERE name_zh LIKE ? OR name_en LIKE ? LIMIT 1",
        (f"%{name}%", f"%{name}%")).fetchone()
    conn.close()
    if row:
        return {"name": row["name_zh"], "name_en": row["name_en"], "region": row["region"],
                "found": True, "recognized": True,
                "source_url": row["source_url"], "fetched_at": row["fetched_at"]}
    return {"name": name, "found": False, "recognized": None,
            "message": "该院校未出现在教育部认可名单中（未收录不等于不认可），请至官方渠道核实",
            "list_url": LIST_PAGE_URL}


def list_gpa_rules() -> list[dict]:
    conn = _conn()
    from collectors.gpa_rules import list_rules
    rows = list_rules(conn)
    conn.close()
    return rows


def list_schools(region: str | None, keyword: str | None) -> list[dict]:
    conn = _conn()
    sql = "SELECT name_zh, name_en, region, source_url, fetched_at FROM recognized_schools"
    conds, args = [], []
    if region in ("hk", "sg", "uk"):
        conds.append("region=?")
        args.append(region)
    if keyword:
        conds.append("(name_zh LIKE ? OR name_en LIKE ?)")
        args += [f"%{keyword}%", f"%{keyword}%"]
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY region, name_zh"
    rows = [dict(r) for r in conn.execute(sql, args)]
    conn.close()
    return rows


def list_programs(field: str | None) -> list[dict]:
    conn = _conn()
    sql = ("SELECT program_id, university, name, field, tuition_amount, tuition_currency, "
           "duration_months, deadlines, stale FROM programs")
    args: tuple = ()
    if field in ("cs", "business"):
        sql += " WHERE field=?"
        args = (field,)
    rows = [dict(r) for r in conn.execute(sql, args)]
    conn.close()
    return rows


def get_program(pid: int) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM programs WHERE program_id=?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def match(bg: dict) -> dict:
    conn = _conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT p.*, s.recognized FROM programs p "
        "JOIN recognized_schools s ON p.school_id=s.school_id")]
    conn.close()

    result = match_programs(rows, bg)
    out_tiers = {}
    dropped = 0
    for tier, progs in result["tiers"].items():
        out_tiers[tier] = []
        for p in progs:
            # 引用强制（REQ-004）：无有效出处（URL + 快照）的推荐丢弃并记录
            if not p.get("source_url") or not p.get("snapshot_ref"):
                dropped += 1
                continue
            citations = [{"type": "program_page", "url": p["source_url"],
                          "snapshot_ref": p["snapshot_ref"],
                          "excerpts": json.loads(p["source_excerpts"] or "{}")}]
            out_tiers[tier].append({
                "program_id": p["program_id"], "university": p["university"],
                "program": p["name"], "recognized": bool(p.get("recognized")),
                "reasons": build_reason(p, bg, tier),
                "citations": citations,
            })
    resp = {"tiers": out_tiers,
            "data_sufficiency": result["data_sufficiency"],
            "case_layer": "not_available_in_mvp",
            "notice": NOTICE}
    if result["data_sufficiency"] == "insufficient":
        resp["insufficient_reason"] = result["insufficient_reason"]
    if dropped:
        resp["dropped_no_citation"] = dropped
    return resp


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj: dict | list, status: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/" or u.path == "/index.html":
            return self._file(config.ROOT / "web" / "index.html")
        if u.path == "/api/schools/recognition":
            name = (q.get("name") or [""])[0].strip()
            if not name:
                return self._json({"detail": "name required"}, 400)
            return self._json(recognition(name))
        if u.path == "/api/gpa-rules":
            return self._json({"rules": list_gpa_rules()})
        if u.path == "/api/schools":
            return self._json({"schools": list_schools(
                (q.get("region") or [None])[0], (q.get("keyword") or [None])[0])})
        if u.path == "/api/programs":
            return self._json({"programs": list_programs((q.get("field") or [None])[0])})
        if u.path.startswith("/api/programs/"):
            try:
                pid = int(u.path.rsplit("/", 1)[1])
            except ValueError:
                return self._json({"detail": "invalid id"}, 400)
            p = get_program(pid)
            return self._json(p) if p else self._json({"detail": "not found"}, 404)
        return self._json({"detail": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/match":
            return self._json({"detail": "not found"}, 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception:
            return self._json({"detail": "invalid json"}, 400)
        required = {"undergrad_tier", "gpa"}
        if not required <= body.keys():
            return self._json({"detail": f"required: {sorted(required)}"}, 400)
        valid_tiers = {"C9", "985", "211", "shuangyiliu", "shuangfei", "overseas"}
        if body["undergrad_tier"] not in valid_tiers:
            return self._json({"detail": f"undergrad_tier must be one of {sorted(valid_tiers)}"}, 400)
        try:
            body["gpa"] = float(body["gpa"])
            if not (0 < body["gpa"] <= 100):
                raise ValueError
        except (TypeError, ValueError):
            return self._json({"detail": "gpa must be 0-100"}, 400)
        for k in ("ielts", "ielts_min_sub"):
            if body.get(k) is not None:
                try:
                    body[k] = float(body[k])
                except (TypeError, ValueError):
                    return self._json({"detail": f"{k} must be number"}, 400)
        return self._json(match(body))


def main(port: int = 8322):
    config.load_env()
    db.init_db()
    host = config.get("SA_BIND_HOST", "127.0.0.1")  # 默认仅本机；tailnet 开放用 SA_BIND_HOST
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"study-abroad API on http://{host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
