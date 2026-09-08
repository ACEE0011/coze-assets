#!/usr/bin/env python3
"""
ACE Gateway — 轻量级 OpenAI 兼容路由网关
替代 one-api 的核心功能：模型路由、多渠道轮询、API Key 鉴权

对齐疯子的 worker_registry + routing_constraints 配置
监听 localhost:3000，兼容 /v1/chat/completions 和 /v1/models
"""
import os
import json
import time
import uuid
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# 配置：从 miner_env.sh 加载密钥
# ============================================================

def load_env():
    """从 coze-assets/miner_env.sh 加载环境变量"""
    env_paths = [
        Path("/workspace/fengzi-repos/coze-assets/02_miner_config/miner_env.sh"),
        Path("/workspace/fengzi-repos/mine-seed/05_TOOLS/miner/miner_env.sh"),
    ]
    for p in env_paths:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export ") and "=" in line:
                        k, v = line[7:].split("=", 1)
                        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            print(f"[ENV] Loaded from {p}")
            return
    print("[ENV] WARNING: miner_env.sh not found")

load_env()

# API Token（与疯子原配置对齐）
VALID_TOKENS = {t for t in os.environ.get("ACE_VALID_TOKENS", "").split(",") if t}
ADMIN_TOKEN = os.environ.get("ONEAPI_ADMIN_TOKEN", "")

# ============================================================
# 渠道定义：对齐 SECRET.md 中的活跃渠道
# ============================================================

NIM_BASE = "https://integrate.api.nvidia.com/v1"
NIM_KEYS = [os.environ.get(f"NIM_KEY_{i}", "") for i in range(1, 17) if os.environ.get(f"NIM_KEY_{i}")]

CHANNELS: List[Dict] = [
    # #2 Zhipu GLM (type=16, 免费无限量)
    {
        "id": 2, "name": "Zhipu-GLM-Free", "type": "zhipu",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": os.environ.get("ZHIPU_KEY", ""),
        "models": ["glm-4-flash", "glm-4-air", "glm-4-airx"],
        "weight": 1, "status": "alive",
    },
    # #57 GitHub Models (使用 SECRET.md 中 2026-07-02 的新 PAT)
    # 密钥从环境变量 GITHUB_PAT 加载，或从 miner_env.sh 自动加载
    {
        "id": 57, "name": "GitHub-Models-v2", "type": "openai",
        "base_url": "https://models.inference.ai.azure.com",
        "api_key": os.environ.get("GITHUB_PAT_NEW", os.environ.get("GITHUB_PAT", "")),
        "models": ["gpt-4o-mini", "gpt-4o", "DeepSeek-R1", "Llama-3.3-70B-Instruct"],
        "weight": 1, "status": "alive",
    },
    # #59-66 NVIDIA NIM (8 key 轮询)
    {
        "id": 59, "name": "NVIDIA-NIM-Pool", "type": "openai",
        "base_url": NIM_BASE,
        "api_key": NIM_KEYS[0] if NIM_KEYS else "",
        "api_keys": NIM_KEYS,  # 多 key 轮询
        "models": [
            "deepseek-ai/deepseek-v4-pro", "deepseek-ai/deepseek-v4-flash",
            "meta/llama-3.3-70b-instruct", "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/nemotron-3-ultra-550b-a55b", "z-ai/glm-5.1",
            "moonshotai/kimi-k2.6", "openai/gpt-oss-120b",
            "meta/llama-4-maverick-17b-128e-instruct", "minimaxai/minimax-m2.7",
            "mistralai/mistral-medium-3.5-128b", "stepfun-ai/step-3.7-flash",
            "google/gemma-4-31b-it", "nvidia/nemotron-3-super-120b-a12b",
            "minimaxai/minimax-m3", "qwen/qwen3.5-397b-a17b",
            "qwen/qwen3.5-122b-a10b", "qwen/qwen3-next-80b-a3b-instruct",
            "openai/gpt-oss-20b", "bytedance/seed-oss-36b-instruct",
            "stepfun-ai/step-3.5-flash",
        ],
        "weight": 1, "status": "alive",
    },
    # #67 NVIDIA NIM v9 (专用 key)
    {
        "id": 67, "name": "NVIDIA-NIM-v9", "type": "openai",
        "base_url": NIM_BASE,
        "api_key": os.environ.get("NIM_KEY_9", ""),
        "models": ["minimaxai/minimax-m3"],
        "weight": 1, "status": "alive",
    },
    # #7 OpenRouter Free (使用 SECRET.md 中 Key #4)
    # 密钥从环境变量 OPENROUTER_KEY 加载，或从 miner_env.sh 自动加载
    {
        "id": 7, "name": "OpenRouter-Free", "type": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.environ.get("OPENROUTER_KEY", ""),
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-flash-1.5:free",
            "qwen/qwen-3.6-plus",
        ],
        "weight": 1, "status": "alive",
    },
    # SambaNova
    {
        "id": 80, "name": "SambaNova-Free", "type": "openai",
        "base_url": os.environ.get("SAMBANOVA_BASE", "https://api.sambanova.ai/v1"),
        "api_key": os.environ.get("SAMBANOVA_KEY", ""),
        "models": ["Meta-Llama-3.1-8B-Instruct", "Meta-Llama-3.1-70B-Instruct"],
        "weight": 1, "status": "alive",
    },
]

# 模型 → 渠道映射（用于路由）
MODEL_CHANNEL_MAP: Dict[str, List[int]] = {}
for ch in CHANNELS:
    for model in ch["models"]:
        if model not in MODEL_CHANNEL_MAP:
            MODEL_CHANNEL_MAP[model] = []
        MODEL_CHANNEL_MAP[model].append(ch["id"])

# 渠道 ID → 渠道对象
CHANNEL_BY_ID = {ch["id"]: ch for ch in CHANNELS}

# 轮询计数器
_round_robin: Dict[int, int] = {}

def get_next_key(channel: Dict) -> str:
    """从渠道获取下一个 API key（轮询）"""
    keys = channel.get("api_keys")
    if keys:
        idx = _round_robin.get(channel["id"], 0)
        _round_robin[channel["id"]] = (idx + 1) % len(keys)
        return keys[idx]
    return channel["api_key"]

def find_channels_for_model(model: str) -> List[Dict]:
    """找到能处理该模型的所有活跃渠道"""
    channel_ids = MODEL_CHANNEL_MAP.get(model, [])
    return [CHANNEL_BY_ID[cid] for cid in channel_ids if CHANNEL_BY_ID[cid]["status"] == "alive"]

# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(title="ACE Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def verify_token(request: Request):
    """验证 API Token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = auth

    if token in VALID_TOKENS or token == ADMIN_TOKEN:
        return token
    raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/api/status")
async def status():
    """系统状态"""
    return {
        "success": True,
        "message": "",
        "data": {
            "version": "ace-gateway-1.0.0",
            "start_time": datetime.now().isoformat(),
            "channels": len(CHANNELS),
            "models": len(MODEL_CHANNEL_MAP),
        }
    }

@app.get("/v1/models")
async def list_models(token: str = Depends(verify_token)):
    """列出所有可用模型"""
    models = []
    for model_name in sorted(MODEL_CHANNEL_MAP.keys()):
        models.append({
            "id": model_name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "ace-gateway",
        })
    return {"object": "list", "data": models}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, token: str = Depends(verify_token)):
    """OpenAI 兼容的 chat completions 接口"""
    body = await request.json()
    model = body.get("model", "")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 2048)

    # 查找渠道
    channels = find_channels_for_model(model)
    if not channels:
        # 尝试模糊匹配
        for ch in CHANNELS:
            if any(model.lower() in m.lower() or m.lower() in model.lower() for m in ch["models"]):
                channels.append(ch)

    if not channels:
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found in any channel")

    # 按权重排序，尝试每个渠道
    last_error = None
    for channel in channels:
        try:
            result = await forward_to_channel(channel, model, body, stream)
            return result
        except Exception as e:
            print(f"[GATEWAY] Channel {channel['name']} failed for {model}: {e}")
            last_error = str(e)
            continue

    raise HTTPException(status_code=502, detail=f"All channels failed. Last error: {last_error}")

async def forward_to_channel(channel: Dict, model: str, body: Dict, stream: bool):
    """将请求转发到后端渠道"""
    api_key = get_next_key(channel)
    base_url = channel["base_url"].rstrip("/")

    # 构建后端请求 URL
    url = f"{base_url}/chat/completions"

    # GLM 需要特殊处理
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # OpenRouter 额外头
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://ace-gateway.local"
        headers["X-Title"] = "ACE Gateway"

    # 准备请求体
    payload = dict(body)
    # 确保模型名正确
    payload["model"] = model

    timeout = httpx.Timeout(120.0, connect=30.0)

    if stream:
        # Stream 模式：client 必须在 StreamingResponse 生命周期内存活
        # 不能用 async with，因为返回后 client 会立即关闭
        client = httpx.AsyncClient(timeout=timeout)

        async def stream_generator():
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Upstream error: {error_body.decode()[:500]}"
                        )
                    async for chunk in response.aiter_bytes():
                        yield chunk
            finally:
                await client.aclose()

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Upstream {channel['name']} error: {response.text[:500]}"
                )
            return JSONResponse(content=response.json())

# ============================================================
# 渠道管理 API（兼容 one-api 管理接口）
# ============================================================

@app.get("/api/channel/")
async def list_channels(token: str = Depends(verify_token)):
    """列出所有渠道"""
    return {
        "success": True,
        "data": [
            {
                "id": ch["id"],
                "name": ch["name"],
                "type": ch["type"],
                "status": ch["status"],
                "models": ",".join(ch["models"]),
                "base_url": ch["base_url"],
                "weight": ch.get("weight", 1),
            }
            for ch in CHANNELS
        ]
    }

@app.post("/api/channel/")
async def add_channel(channel_data: dict, token: str = Depends(verify_token)):
    """添加渠道"""
    new_id = max(ch["id"] for ch in CHANNELS) + 1
    channel_data["id"] = new_id
    channel_data.setdefault("status", "alive")
    channel_data.setdefault("weight", 1)
    channel_data.setdefault("models", [])
    if isinstance(channel_data["models"], str):
        channel_data["models"] = channel_data["models"].split(",")
    CHANNELS.append(channel_data)
    CHANNEL_BY_ID[new_id] = channel_data
    for model in channel_data["models"]:
        MODEL_CHANNEL_MAP.setdefault(model, []).append(new_id)
    return {"success": True, "data": channel_data}

@app.get("/api/token/")
async def list_tokens(token: str = Depends(verify_token)):
    """列出 API Token"""
    return {
        "success": True,
        "data": [
            {"id": 1, "name": "miner-v2", "key": "jHhtKn***", "unlimited_quota": True},
            {"id": 2, "name": "miner-token", "key": "GfvnDi***", "unlimited_quota": True},
        ]
    }

# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("ACE Gateway v1.0.0 — OpenAI 兼容路由网关")
    print(f"Channels: {len(CHANNELS)}")
    print(f"Models: {len(MODEL_CHANNEL_MAP)}")
    print(f"NIM Keys: {len(NIM_KEYS)}")
    print(f"Listening: http://localhost:3000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")
