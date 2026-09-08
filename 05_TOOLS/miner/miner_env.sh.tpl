#!/bin/bash
# 矿场环境变量 - 所有API凭证集中管理
# 用法: source miner_env.sh && python3 miner_24h.py

# === One API ===
export MINER_API_BASE="http://localhost:3000/v1/chat/completions"
export MINER_API_KEY="{{ONE_API_KEY}}"

# === One API Admin ===
export ONEAPI_ADMIN_TOKEN="{{ONEAPI_ADMIN_TOKEN}}"

# === NVIDIA NIM Keys (8号) ===
export NIM_KEY_1="{{NIM_KEY_1}}"
export NIM_KEY_2="{{NIM_KEY_2}}"
export NIM_KEY_3="{{NIM_KEY_3}}"
export NIM_KEY_4="{{NIM_KEY_4}}"
export NIM_KEY_5="{{NIM_KEY_5}}"
export NIM_KEY_6="{{NIM_KEY_6}}"
export NIM_KEY_7="{{NIM_KEY_7}}"
export NIM_KEY_8="{{NIM_KEY_8}}"

# === GitHub Models ===
export GITHUB_PAT="{{GITHUB_PAT}}"

# === 智谱GLM ===
export ZHIPU_KEY="{{ZHIPU_KEY}}"

# === Telegram ===
export TG_API_ID="{{TG_API_ID}}"
export TG_API_HASH="{{TG_API_HASH}}"
export TG_PHONE="{{TG_PHONE}}"
export TG_BOT_TOKEN_1="{{TG_BOT_TOKEN_1}}"
export TG_BOT_TOKEN_2="{{TG_BOT_TOKEN_2}}"
export TG_CHAT_ID="{{TG_CHAT_ID}}"

echo "✅ 矿场环境变量已加载"
export NIM_KEY_9="{{NIM_KEY_9}}"
export NIM_KEY_10="{{NIM_KEY_10}}"
export NIM_KEY_11="{{NIM_KEY_11}}"
export NIM_KEY_12="{{NIM_KEY_12}}"

# === NIM Dedicated Model Keys ===
# KEY_10: deepseek-ai/deepseek-v4-pro专用
# KEY_11: nvidia/nemotron-3-ultra-550b-a55b专用
# KEY_12: stepfun-ai/step-3.7-flash专用

# === SambaNova (免费$5额度, OpenAI兼容) ===
export SAMBANOVA_KEY="{{SAMBANOVA_KEY}}"
export SAMBANOVA_BASE="https://api.sambanova.ai/v1"

# OpenRouter Free Tier (added 2026-06-13)
export OPENROUTER_KEY="{{OPENROUTER_KEY}}"
export OPENROUTER_BASE="https://openrouter.ai/api/v1"

# HuggingFace (added 2026-06-13, DNS blocked)
export HF_KEY="{{HF_KEY}}"

# === Signal Discovery Models (2026-06-13: deepseek unreachable, fallback to glm) ===
export SIGNAL_MODEL="glm-4-flash"
export CODE_MODEL="glm-4-flash"
export ADVISOR_MODEL="glm-4-flash"

# === NIM New Keys (2026-06-14 老板提供) ===
export NIM_KEY_13="{{NIM_KEY_13}}"
export NIM_KEY_14="{{NIM_KEY_14}}"
# KEY_13: minimaxai/minimax-m3专用
# KEY_14: stepfun-ai/step-3.7-flash专用

# NIM_KEY_15: mistral-medium-3.5-128b专用 (2026-06-14)
export NIM_KEY_15="{{NIM_KEY_15}}"
# NIM_KEY_16: deepseek-v4-pro专用 (2026-06-14)
export NIM_KEY_16="{{NIM_KEY_16}}"

# === Felo API (PROV-FELO-001, 跨语言证据补充通道) ===
export FELO_API_KEY="{{FELO_API_KEY}}"
export FELO_BASE_URL="https://api.felo.ai/v1"
