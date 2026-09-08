#!/bin/bash
# 种子归档脚本 — 同步运行时数据到 mine-seed 仓库
# 执行: bash /home/coze/seed_archive.sh

set -e
REPO="/home/coze/shared/mine-seed"
DATE_TAG=$(date +%Y-%m-%d)
cd "$REPO"

# Ensure remote URL has credentials for push
git remote set-url origin "https://github.com/zhangapple21-web/mine-seed.git"

# Pull latest to avoid conflicts
git pull origin main 2>/dev/null || true

# === 03_DATA — 运行时数据 ===
cp /home/coze/experience.json              "$REPO/03_DATA/experience.json"
cp /home/coze/mine_output/observation_log.json "$REPO/03_DATA/observation_log.json"
cp /home/coze/worker_registry.json          "$REPO/03_DATA/WORKERS/worker_registry.json"
cp /home/coze/routing_constraints.json      "$REPO/03_DATA/CONSTRAINTS/routing_constraints.json"
cp /home/coze/signal_taxonomy.json          "$REPO/03_DATA/CONSTRAINTS/signal_taxonomy.json"
cp /home/coze/mine_output/signals/signal_registry.json "$REPO/03_DATA/CONSTRAINTS/signal_registry.json"

# Seeds
mkdir -p "$REPO/03_DATA/seeds"
cp /home/coze/mine_output/seeds/*.json       "$REPO/03_DATA/seeds/" 2>/dev/null || true
cp /home/coze/mine_output/signals/seed_*.json "$REPO/03_DATA/seeds/" 2>/dev/null || true
cp /home/coze/mine_output/signals/thought_seed_*.json "$REPO/03_DATA/seeds/" 2>/dev/null || true
cp /home/coze/mine_output/signals/seed_*.md   "$REPO/03_DATA/seeds/" 2>/dev/null || true

# === 05_TOOLS — 脚本代码 ===
cp /home/coze/miner_24h.py                  "$REPO/05_TOOLS/miner/miner_24h.py"
cp /home/coze/experience_engine.py          "$REPO/05_TOOLS/memory/experience_engine.py"
cp /home/coze/signal_discovery.py           "$REPO/05_TOOLS/signals/signal_discovery.py"
cp /home/coze/mine_output/signals/dragon_leader_v2.py "$REPO/05_TOOLS/signals/dragon_leader_v2.py"
cp /home/coze/miner_cron.sh                 "$REPO/05_TOOLS/miner/miner_cron.sh"
cp /home/coze/signal_cron.sh                "$REPO/05_TOOLS/signals/signal_cron.sh"
cp /home/coze/archivist_cron.sh             "$REPO/05_TOOLS/memory/archivist_cron.sh"

# Check if anything changed
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "→ 数据无变化，跳过空提交"
    exit 0
fi

# Add, commit, push
git add -A
git commit -m "seed: sync live runtime data $DATE_TAG"
git push origin main

echo "→ 种子归档完成: $DATE_TAG"
