import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
config.load_env()
from collectors.uk_common import collect_school
from storage import db
conn = db.init_db()
print(collect_school(conn, "manchester"), flush=True)
conn.commit()
n = conn.execute("SELECT COUNT(*) c FROM programs WHERE university NOT LIKE '【测试】%'").fetchone()["c"]
print("REAL TOTAL:", n, flush=True)
conn.close()
