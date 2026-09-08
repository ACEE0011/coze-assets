#!/bin/bash
# 本地（非Coze容器）路径适配层
# 用法: source local_env.sh && python3 miner_24h.py

export ONE_API_URL="http://localhost:3000/v1/chat/completions"
export ONE_API_KEY="${ONE_API_KEY:?set ONE_API_KEY in the local environment}"
export SIGNAL_MODEL="deepseek-ai/deepseek-v4-flash"
export CODE_MODEL="deepseek-ai/deepseek-v4-flash"
export ADVISOR_MODEL="glm-4-flash"

# 创建兼容目录结构
mkdir -p /tmp/mine_output/signals
touch /tmp/mine_output/observation_log.json

# 路径覆盖
export REPO_DIR="/workspace/fengzi-repos/mine-seed"
export TEMPLATE_DIR="/workspace/fengzi-repos/mine-seed/05_TOOLS/signals/template"
export DATA_DIR="/tmp/sp500_data"
export OUTPUT_DIR="/tmp/mine_output"

# task_router 路径覆盖
export WORKER_REGISTRY="/workspace/fengzi-repos/coze-assets/02_miner_config/worker_registry.json"
export OBSERVATION_FILE="/tmp/mine_output/observation_log.json"
export JUDGE_FILE="/tmp/mine_output/judge_history.json"
export ROUTING_CONSTRAINTS="/workspace/fengzi-repos/coze-assets/02_miner_config/routing_constraints.json"

# miner_24h 的 API 配置
export MINER_API_BASE="http://localhost:3000/v1/chat/completions"
export MINER_API_KEY="${MINER_API_KEY:?set MINER_API_KEY in the local environment}"
