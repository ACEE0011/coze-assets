#!/usr/bin/env python3
import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent

KNOWN_KEY_GROUPS = {
    "GLM": ["GLM_KEY", "GLM_BASE", "GLM_MODEL"],
    "NIM": [f"NIM_KEY_{i}" for i in range(1, 17)] + ["NIM_BASE", "NIM_MODEL"],
    "GH_MODELS": ["GH_MODELS_KEY", "GH_MODELS_BASE", "GH_MODELS_MODEL"],
    "OPENROUTER": ["OPENROUTER_KEY", "OPENROUTER_BASE"],
    "SAMBANOVA": ["SAMBANOVA_KEY", "SAMBANOVA_BASE"],
    "HF": ["HF_KEY"],
    "PPLX": ["PPLX_KEY_1", "PPLX_KEY_2", "PPLX_BASE", "PPLX_MODEL"],
    "SWA": ["SWA_KEY_1", "SWA_KEY_2", "SWA_BASE", "SWA_MODEL"],
    "TG": ["TG_API_ID", "TG_API_HASH", "TG_PHONE", "TG_BOT_TOKEN_1", "TG_BOT_TOKEN_2", "TG_CHAT_ID"],
    "ONEAPI": ["ONEAPI_ADMIN_TOKEN", "MINER_API_KEY", "MINER_API_BASE"],
    "OTHER": ["APIYI_KEY", "SIXFINGER_KEY", "SERPAPI_KEY"],
    "ALIASES": ["ZHIPU_KEY", "ZHIPU_BASE", "GITHUB_PAT", "GITHUB_BASE", "GH_PAT", "GITHUB_TOKEN"],
}

GROUP_LABELS = {
    "GLM": "智谱 GLM",
    "NIM": "NVIDIA NIM",
    "GH_MODELS": "GitHub Models",
    "OPENROUTER": "OpenRouter",
    "SAMBANOVA": "SambaNova",
    "HF": "HuggingFace",
    "PPLX": "Perplexity",
    "SWA": "神稳AI (SWA)",
    "TG": "Telegram",
    "ONEAPI": "One API",
    "OTHER": "其他API",
    "ALIASES": "变量名别名",
}

SECRET_SYNC_HEADER = "## === 密钥自动同步区 (Auto-Synced) ==="
SECRET_SYNC_FOOTER = "## === 密钥自动同步区结束 ==="

def load_env(env_path: Path) -> dict:
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            result[key] = val
    return result

def generate_secret_block(env_data: dict) -> str:
    lines = [SECRET_SYNC_HEADER]
    
    for group_name, keys in KNOWN_KEY_GROUPS.items():
        group_lines = []
        for key in keys:
            if key in env_data and env_data[key]:
                group_lines.append(f"- {key}: {env_data[key]}")
        
        if group_lines:
            lines.append(f"### {GROUP_LABELS[group_name]}")
            lines.extend(group_lines)
            lines.append("")
    
    lines.append(SECRET_SYNC_FOOTER)
    return "\n".join(lines)

def sync_secrets(workspace: Path = None) -> dict:
    if workspace is None:
        workspace = WORKSPACE
    
    env_path = workspace / ".env"
    secret_path = workspace / "01_credentials" / "SECRET.md"
    
    env_data = load_env(env_path)
    
    if not env_data:
        return {"synced": False, "reason": ".env 文件不存在或为空"}
    
    new_block = generate_secret_block(env_data)
    
    if secret_path.exists():
        content = secret_path.read_text(encoding="utf-8")
        
        if SECRET_SYNC_HEADER in content:
            start_idx = content.find(SECRET_SYNC_HEADER)
            end_idx = content.find(SECRET_SYNC_FOOTER) + len(SECRET_SYNC_FOOTER)
            if end_idx > start_idx:
                old_block = content[start_idx:end_idx]
                if old_block == new_block:
                    return {"synced": False, "reason": "内容一致，无需同步", "env_keys": len(env_data)}
                
                content = content[:start_idx] + new_block + content[end_idx:]
                changed = True
            else:
                content += "\n\n" + new_block
                changed = True
        else:
            content += "\n\n" + new_block
            changed = True
    else:
        content = new_block
        changed = True
    
    if changed:
        secret_path.write_text(content, encoding="utf-8")
    
    return {
        "synced": changed,
        "env_keys": len(env_data),
        "changes": "更新自动同步区" if changed else "无",
    }

def send_tg_notification(message: str):
    try:
        sys.path.insert(0, str(WORKSPACE / "06_RUNTIME" / "connectors"))
        from tg_pusher import TGPusher
        
        bot_token = os.environ.get("TG_BOT_TOKEN_2") or os.environ.get("TG_BOT_TOKEN_1")
        chat_id = os.environ.get("TG_CHAT_ID", "5016609451")
        
        if bot_token:
            pusher = TGPusher(bot_token, chat_id)
            pusher.send_message(message, parse_mode="HTML")
            return True
    except Exception as e:
        print(f"[SecretSyncer] TG推送失败: {e}")
    return False

def main():
    print("🔐 Secret Syncer — 密钥同步检查")
    
    _env_file = WORKSPACE / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                if _key.strip() not in os.environ:
                    os.environ[_key.strip()] = _val.strip().strip('"').strip("'")
    
    report = sync_secrets()
    
    print(f"\n📊 当前状态:")
    print(f"  .env 密钥数: {report['env_keys']}")
    
    if report["synced"]:
        print(f"\n✅ 同步完成: {report['changes']}")
        
        msg = (
            f"🔐 <b>密钥同步通知</b>\n"
            f"日期: {os.popen('date /t').read().strip()}\n"
            f"时间: {os.popen('time /t').read().strip()}\n\n"
            f"<b>状态:</b> .env 密钥已同步到 SECRET.md\n"
            f"<b>密钥数:</b> {report['env_keys']}"
        )
        send_tg_notification(msg)
        print("\n📨 已推送通知到 Telegram")
    else:
        print(f"\n✅ 状态一致: {report['reason']}")
    
    return report

if __name__ == "__main__":
    main()
