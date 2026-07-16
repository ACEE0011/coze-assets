# ACE Runtime — 环境变量模板
# 用法: 复制为 .env 并填入真实密钥
# .env 文件已加入 .gitignore，不会被追踪

# === 智谱 GLM ===
GLM_KEY={{GLM_KEY}}
GLM_BASE=https://open.bigmodel.cn/api/paas/v4/chat/completions
GLM_MODEL=glm-4-flash

# === NVIDIA NIM (16 keys) ===
NIM_BASE=https://integrate.api.nvidia.com/v1/chat/completions
NIM_KEY_1={{NIM_KEY_1}}
NIM_KEY_2={{NIM_KEY_2}}
NIM_KEY_3={{NIM_KEY_3}}
NIM_KEY_4={{NIM_KEY_4}}
NIM_KEY_5={{NIM_KEY_5}}
NIM_KEY_6={{NIM_KEY_6}}
NIM_KEY_7={{NIM_KEY_7}}
NIM_KEY_8={{NIM_KEY_8}}
NIM_KEY_9={{NIM_KEY_9}}
NIM_KEY_10={{NIM_KEY_10}}
NIM_KEY_11={{NIM_KEY_11}}
NIM_KEY_12={{NIM_KEY_12}}
NIM_KEY_13={{NIM_KEY_13}}
NIM_KEY_14={{NIM_KEY_14}}
NIM_KEY_15={{NIM_KEY_15}}
NIM_KEY_16={{NIM_KEY_16}}
NIM_MODEL=meta/llama-3.1-8b-instruct

# === GitHub Models ===
GH_MODELS_BASE=https://models.inference.ai.azure.com/chat/completions
GH_MODELS_KEY={{GH_MODELS_KEY}}
GH_MODELS_MODEL=gpt-4o-mini

# === OpenRouter ===
OPENROUTER_KEY={{OPENROUTER_KEY}}
OPENROUTER_BASE=https://openrouter.ai/api/v1

# === SambaNova ===
SAMBANOVA_KEY={{SAMBANOVA_KEY}}
SAMBANOVA_BASE=https://api.sambanova.ai/v1

# === HuggingFace ===
HF_KEY={{HF_KEY}}

# === Perplexity ===
PPLX_KEY_1={{PPLX_KEY_1}}
PPLX_KEY_2={{PPLX_KEY_2}}
PPLX_BASE=https://api.perplexity.ai/chat/completions
PPLX_MODEL=sonar

# === 神稳AI ===
SWA_KEY_1={{SWA_KEY_1}}
SWA_KEY_2={{SWA_KEY_2}}
SWA_BASE=https://api.shenwenai.com/v1/chat/completions
SWA_MODEL=gpt-5.4-mini

# === Telegram ===
TG_API_ID=38398440
TG_API_HASH=3460f304c16a186c2300debc673b2ed0
TG_PHONE={{TG_PHONE}}
TG_BOT_TOKEN_1={{TG_BOT_TOKEN_1}}
TG_BOT_TOKEN_2={{TG_BOT_TOKEN_2}}
TG_CHAT_ID={{TG_CHAT_ID}}

# === One API ===
MINER_API_BASE=http://localhost:3000/v1/chat/completions
MINER_API_KEY={{MINER_API_KEY}}
ONEAPI_ADMIN_TOKEN={{ONEAPI_ADMIN_TOKEN}}

# === Felo ===
FELO_API_KEY={{FELO_API_KEY}}
FELO_BASE_URL=https://api.felo.ai/v1

# === APIYI / SIXFINGER / SERPAPI ===
APIYI_KEY={{APIYI_KEY}}
SIXFINGER_KEY={{SIXFINGER_KEY}}
SERPAPI_KEY={{SERPAPI_KEY}}

# === Ollama ===
OLLAMA_BASE=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen2.5:7b

# === 路径 ===
MINE_SEED={{MINE_SEED}}
