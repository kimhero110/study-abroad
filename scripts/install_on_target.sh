#!/bin/bash
# 在目标服务器上安装 study-abroad（Debian/Ubuntu 系）
# 用法: bash install_on_target.sh
set -e
cd "$(dirname "$0")"

echo "==> 1/5 检查 Python"
python3 --version  # 需要 3.11+，低了请先装

echo "==> 2/5 解压快照数据"
tar -xzf data/raw-snapshots.tar.gz -C data/ && rm data/raw-snapshots.tar.gz

echo "==> 3/5 建虚拟环境 + 装依赖"
python3 -m venv .venv
.venv/bin/pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null \
  || .venv/bin/pip install playwright

echo "==> 4/5 装 Chromium（Playwright 浏览器内核）"
.venv/bin/playwright install chromium
# 若启动报缺系统库（Debian/Ubuntu）: sudo .venv/bin/playwright install-deps chromium

echo "==> 5/5 自检"
PYTHONPATH=. .venv/bin/python tests/test_ms101_storage.py
PYTHONPATH=. .venv/bin/python tests/test_ms105_matching.py

echo ""
echo "完成。还差最后一步：把 .env（LLM 配置）从旧机器拷到本目录，然后："
echo "  PYTHONPATH=. SA_BIND_HOST=0.0.0.0 .venv/bin/python api/server.py"
echo "  （SA_BIND_HOST=0.0.0.0 表示监听所有网卡；也可填具体内网 IP）"
