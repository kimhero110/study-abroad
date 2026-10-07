#!/bin/bash
cd "$(dirname "$0")/.."
for school in "帝国理工学院" "伦敦国王学院" "格拉斯哥大学" "曼彻斯特大学"; do
  echo "===== $school ====="
  PYTHONPATH=. .venv/bin/python scripts/reextract_from_snapshots.py "$school"
done
