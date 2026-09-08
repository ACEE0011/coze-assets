#!/bin/bash
# 矿场环境变量 - 所有API凭证集中管理
# 用法: source miner_env.sh && python3 miner_24h.py

# === One API ===
export MINER_API_BASE="http://localhost:3000/v1/chat/completions"
export MINER_API_KEY="${MINER_API_KEY:?set MINER_API_KEY in the local environment}"

# === One API Admin ===
export ONEAPI_ADMIN_TOKEN="${ONEAPI_ADMIN_TOKEN:?set ONEAPI_ADMIN_TOKEN in the local environment}"

# === NVIDIA NIM Keys (8号) ===
export NIM_KEY_1="[REDACTED_NIM_KEY]"
export NIM_KEY_2="[REDACTED_NIM_KEY]"
export NIM_KEY_3="[REDACTED_NIM_KEY]"
export NIM_KEY_4="[REDACTED_NIM_KEY]"
export NIM_KEY_5="[REDACTED_NIM_KEY]"
export NIM_KEY_6="[REDACTED_NIM_KEY]"
export NIM_KEY_7="[REDACTED_NIM_KEY]"
export NIM_KEY_8="[REDACTED_NIM_KEY]"

# === GitHub Models ===
export GITHUB_PAT="${GITHUB_PAT:?set GITHUB_PAT in the local environment}"

# === 智谱GLM ===
export ZHIPU_KEY="${ZHIPU_KEY:?set ZHIPU_KEY in the local environment}"

# === Telegram ===
export TG_BOT_TOKEN_1="${TG_BOT_TOKEN_1:-}"
export TG_BOT_TOKEN_2="${TG_BOT_TOKEN_2:-}"

echo "✅ 矿场环境变量已加载"
export NIM_KEY_9="[REDACTED_NIM_KEY]"
export NIM_KEY_10="[REDACTED_NIM_KEY]"
export NIM_KEY_11="[REDACTED_NIM_KEY]"
export NIM_KEY_12="[REDACTED_NIM_KEY]"

# === NIM Dedicated Model Keys ===
# KEY_10: deepseek-ai/deepseek-v4-pro专用
# KEY_11: nvidia/nemotron-3-ultra-550b-a55b专用
# KEY_12: stepfun-ai/step-3.7-flash专用

# === SambaNova (免费$5额度, OpenAI兼容) ===
export SAMBANOVA_KEY="${SAMBANOVA_KEY:-}"
export SAMBANOVA_BASE="https://api.sambanova.ai/v1"

# OpenRouter Free Tier (added 2026-06-13)
export OPENROUTER_KEY="[REDACTED_OPENROUTER_KEY]"
export OPENROUTER_BASE="https://openrouter.ai/api/v1"

# HuggingFace (updated 2026-07-10, token valid, user: zhangapple22)
export HF_KEY=[REDACTED_HF_TOKEN]

# === Signal Discovery Models (2026-06-13: deepseek unreachable, fallback to glm) ===
export SIGNAL_MODEL="glm-4-flash"
export CODE_MODEL="glm-4-flash"
export ADVISOR_MODEL="glm-4-flash"

# === NIM New Keys (2026-06-14 老板提供) ===
export NIM_KEY_13="[REDACTED_NIM_KEY]"
export NIM_KEY_14="[REDACTED_NIM_KEY]"
# KEY_13: minimaxai/minimax-m3专用
# KEY_14: stepfun-ai/step-3.7-flash专用

# NIM_KEY_15: mistral-medium-3.5-128b专用 (2026-06-14)
export NIM_KEY_15="[REDACTED_NIM_KEY]"
# NIM_KEY_16: deepseek-v4-pro专用 (2026-06-14)
export NIM_KEY_16="[REDACTED_NIM_KEY]"

# New Providers from SECRET.md (2026-07-10)
export APIYI_KEY="${APIYI_KEY:-}"
export SIXFINGER_KEY="${SIXFINGER_KEY:-}"
export SERPAPI_KEY="${SERPAPI_KEY:-}"
