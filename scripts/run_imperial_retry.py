import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
config.load_env()
from collectors.uk_common import collect_school
from storage import db
conn = db.init_db()
stats = collect_school(conn, "imperial")
conn.commit()
print("STATS:", stats, flush=True)
n = conn.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"]
print("TOTAL programs:", n, flush=True)
conn.close()
