#!/usr/bin/env bash
# 启动 study-abroad MVP（本地模式）
cd "$(dirname "$0")/.."
PYTHONPATH=. exec python3 api/server.py
