#!/bin/bash
# 打包 study-abroad 项目用于服务器迁移
# 内容：代码 + 数据库 + 原始快照（血缘证据）+ 安装脚本
# 不含：.venv（目标机重建）、.env（单独携带，不进包防泄漏——见 README）
set -e
cd "$(dirname "$0")/.."

TS=$(date +%Y%m%d-%H%M)
PKG="/tmp/study-abroad-migrate-$TS"

mkdir -p "$PKG"
# 代码（排除环境/缓存/数据目录）
tar --exclude=.venv --exclude=__pycache__ --exclude='*.pyc' --exclude=data \
    -cf - . | tar -xf - -C "$PKG"
# 数据（数据库 + 快照 + UCL 名单）
mkdir -p "$PKG/data"
cp data/catalog.sqlite3 "$PKG/data/"
cp data/ucl_list.json "$PKG/data/"
tar -czf "$PKG/data/raw-snapshots.tar.gz" -C data raw
cp scripts/install_on_target.sh "$PKG/"
echo "打包完成: $PKG"
ls -lh "$PKG"
du -sh "$PKG"
