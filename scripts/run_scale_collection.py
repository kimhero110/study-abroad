import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
config.load_env()
from collectors.uk_common import collect_school, LISTERS, SCHOOLS
from storage import db

conn = db.init_db()
# UCL 已有 3 条，全量采 UCL cs/business（~86），KCL（6），Imperial（全量枚举）
for school, limit in [("ucl", None), ("kcl", None), ("imperial", None)]:
    print(f"===== {school} =====", flush=True)
    try:
        stats = collect_school(conn, school, limit=limit)
        conn.commit()
        print(stats, flush=True)
    except Exception as e:
        conn.commit()
        print(f"HALTED {school}: {e}", flush=True)
        break
# final counts
n = conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"]
by = conn.execute("SELECT university, COUNT(*) c FROM programs GROUP BY university").fetchall()
print("TOTAL programs:", n, flush=True)
for r in by: print("  ", r["university"], r["c"], flush=True)
conn.close()
