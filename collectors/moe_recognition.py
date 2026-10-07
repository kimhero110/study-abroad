"""L0 collector: 中留服「认证院校查询」(yxcx.cscse.edu.cn).

API discovered from SPA bundle (app.580622fe.js):
  POST /api/xlxwrzz/xlxwrz/getUniversityListOrPage
  body: {"currentPage":1,"pageSize":100,"country":"英国","universityIndex":"","universityName":""}
  resp: {"code":200,"data":[{"CHINESE_NAME":..,"ENGLISH_NAME":..,"ICON":..}],"total":N}

Source semantics (recorded in lineage): 该名单为「2020-06-28 至 2025-06-28 期间通过学历认证的
申请中涉及的国外颁证院校」，是中留服官方查询入口，作为 L0 正面清单来源。
系统契约：只存正面记录，未命中 ≠ 不认可（CR-FND-01 冻结契约）。

NOTE: cscse.edu.cn 全系 IP 从境外网络不可达（连接超时）。本采集器需在中国内地网络运行
（用户本机）。境外环境下失败属预期，按已知限制记录。
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
import urllib.error

import config
from storage import db

# cscse 服务器使用旧版 TLS 重协商，Python 3.12/OpenSSL 3 默认禁用
_SSL_CTX = ssl.create_default_context()
if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
    _SSL_CTX.options |= ssl.OP_LEGACY_SERVER_CONNECT
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BASE = "https://yxcx.cscse.edu.cn/api/xlxwrzz/xlxwrz/getUniversityListOrPage"
LIST_PAGE = "https://yxcx.cscse.edu.cn/"
SOURCE_ID = "cscse_yxcx"
REGION_COUNTRIES = {"hk": ["中国香港"], "sg": ["新加坡"], "uk": ["英国"]}
SOURCE_NOTE = "中留服认证院校查询（2020-2025 认证涉及院校，官方查询入口）"


def _post(body: dict, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        BASE,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json;charset=utf-8",
                 "User-Agent": "study-abroad-research-bot/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect_region(conn, region: str, min_interval: float = 1.2) -> dict:
    countries = REGION_COUNTRIES[region]
    inserted = updated = 0
    for country in countries:
        page = 1
        while True:
            payload = {"currentPage": page, "pageSize": 100, "country": country,
                       "universityIndex": "", "universityName": ""}
            try:
                resp = _post(payload)
            except Exception as e:
                db.add_quarantine(conn, SOURCE_ID, f"{SOURCE_ID}|{country}|page{page}",
                                  "SOURCE_UNREACHABLE", detail=str(e)[:500])
                return {"region": region, "ok": False, "error": str(e)[:200]}
            items = resp.get("data") or []
            total = resp.get("total") or 0
            for it in items:
                rec = {
                    "name_zh": (it.get("CHINESE_NAME") or "").strip(),
                    "name_en": (it.get("ENGLISH_NAME") or "").strip(),
                    "region": region,
                    "recognized": 1,
                    "source_url": LIST_PAGE,
                    "snapshot_ref": f"api:{BASE} country={country} page={page}",
                    "fetched_at": db.now(),
                    "content_hash": db.content_hash(json.dumps(it, ensure_ascii=False, sort_keys=True)),
                }
                if not rec["name_zh"]:
                    continue
                r = db.upsert_recognized_school(conn, rec)
                inserted += r == "inserted"
                updated += r == "updated"
            if page * 100 >= total or not items:
                break
            page += 1
            time.sleep(min_interval)
    db.set_state(conn, f"{SOURCE_ID}_{region}", "done", last_cursor=f"pages={page}")
    return {"region": region, "ok": True, "inserted": inserted, "updated": updated, "total": total}


def collect_all(db_path=None) -> list[dict]:
    conn = db.init_db(db_path)
    results = []
    for region in ("hk", "sg", "uk"):
        results.append(collect_region(conn, region))
    conn.commit()
    conn.close()
    return results


if __name__ == "__main__":
    config.load_env()
    for r in collect_all():
        print(r)
