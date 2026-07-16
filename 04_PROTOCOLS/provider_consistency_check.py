#!/usr/bin/env python3
"""
Provider注册一致性校验器 — AUM-MISSION-SEC-001 子任务2

扫描4份清单，确保新增provider不会遗漏注册：
1. free_llm.py — 已实现 _call_X 的provider
2. task_router.py — LocalMinerAdapter 已注册的provider
3. secret_syncer.py — KNOWN_KEY_GROUPS 已记录的provider
4. .env.tpl — 占位符定义

用法:
    python provider_consistency_check.py           # 直接运行
    python provider_consistency_check.py --notify  # 不一致时推送TG通知
"""

import os
import re
import sys
import argparse
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent

# 统一的provider名称映射
# key = 标准名称, value = 各文件中对应的标识
PROVIDER_MAP = {
    "glm": {
        "free_llm": "_call_glm",
        "task_router": "zhipu",  # task_router用zhipu注册
        "secret_syncer": "GLM",
        "env_tpl": "GLM_KEY",
    },
    "swa": {
        "free_llm": "_call_swa",
        "task_router": "swa",
        "secret_syncer": "SWA",
        "env_tpl": "SWA_KEY_1",
    },
    "pplx": {
        "free_llm": "_call_pplx",
        "task_router": "pplx",
        "secret_syncer": "PPLX",
        "env_tpl": "PPLX_KEY_1",
    },
    "nim": {
        "free_llm": "_call_nim",
        "task_router": "nim",
        "secret_syncer": "NIM",
        "env_tpl": "NIM_KEY_1",
    },
    "github": {
        "free_llm": "_call_github",
        "task_router": "github",
        "secret_syncer": "GH_MODELS",  # 注意这里叫GH_MODELS
        "env_tpl": "GH_MODELS_KEY",
    },
    "ollama": {
        "free_llm": "_call_ollama",
        "task_router": "ollama",
        "secret_syncer": None,  # ollama没有key，不在secret_syncer里
        "env_tpl": "OLLAMA_BASE",
    },
    "openrouter": {
        "free_llm": None,  # openrouter不在free_llm中实现，由task_router直接调用
        "task_router": "openrouter",
        "secret_syncer": "OPENROUTER",
        "env_tpl": "OPENROUTER_KEY",
    },
    "felo": {
        "free_llm": None,  # felo在独立文件felo_provider.py
        "task_router": "felo",
        "secret_syncer": "FELO",
        "env_tpl": "FELO_API_KEY",
    },
    "oneapi": {
        "free_llm": None,
        "task_router": "oneapi",
        "secret_syncer": "ONEAPI",
        "env_tpl": "ONEAPI_ADMIN_TOKEN",
    },
    "local_miner": {
        "free_llm": None,
        "task_router": "local_miner",
        "secret_syncer": None,
        "env_tpl": None,
    },
    "sambanova": {
        "free_llm": None,  # sambanova可能还没实现
        "task_router": None,
        "secret_syncer": "SAMBANOVA",
        "env_tpl": "SAMBANOVA_KEY",
    },
    "hf": {
        "free_llm": None,
        "task_router": None,
        "secret_syncer": "HF",
        "env_tpl": "HF_KEY",
    },
}

def scan_free_llm() -> set:
    """扫描 free_llm.py 中已实现的 _call_X 函数"""
    path = WORKSPACE / "05_TOOLS" / "miner" / "free_llm.py"
    if not path.exists():
        return set()
    
    content = path.read_text(encoding="utf-8")
    # 匹配 def _call_xxx(
    matches = re.findall(r'def (_call_\w+)\(', content)
    
    # 提取 provider 名称（去掉 _call_ 前缀）
    providers = set()
    for m in matches:
        name = m.replace("_call_", "")
        providers.add(name)
    
    return providers

def scan_task_router() -> set:
    """扫描 task_router.py 中 LocalMinerAdapter 注册的 provider"""
    path = WORKSPACE / "05_TOOLS" / "miner" / "task_router.py"
    if not path.exists():
        return set()
    
    content = path.read_text(encoding="utf-8")
    
    # 查找 _providers["xxx"] 的注册
    matches = re.findall(r'self\._providers\["(\w+)"\]\s*=', content)
    
    # 还要查找 PROVIDER_ADAPTERS 里的注册（felo等）
    adapter_matches = re.findall(r'"(\w+)"\s*:\s*(?:lambda|OneAPIAdapter|LocalMinerAdapter|FeloAdapter)', content)
    
    providers = set(matches + adapter_matches)
    return providers

def scan_secret_syncer() -> set:
    """扫描 secret_syncer.py 的 KNOWN_KEY_GROUPS"""
    path = WORKSPACE / "05_TOOLS" / "secret_syncer.py"
    if not path.exists():
        return set()
    
    content = path.read_text(encoding="utf-8")
    
    # 提取 KNOWN_KEY_GROUPS 的 key — 逐行提取带引号的键名
    keys = set()
    in_dict = False
    brace_depth = 0
    for line in content.splitlines():
        stripped = line.strip()
        if "KNOWN_KEY_GROUPS = {" in stripped:
            in_dict = True
            brace_depth = 1
            continue
        if not in_dict:
            continue
        
        # 计算大括号深度
        brace_depth += stripped.count("{") - stripped.count("}")
        
        # 提取 "XXX": 格式的键
        match = re.match(r'"(\w+)"\s*:', stripped)
        if match:
            keys.add(match.group(1))
        
        if brace_depth <= 0:
            break
    
    return keys

def scan_env_tpl() -> set:
    """扫描 .env.tpl 中的 provider 占位符"""
    path = WORKSPACE / ".env.tpl"
    if not path.exists():
        return set()
    
    content = path.read_text(encoding="utf-8")
    providers = set()
    
    # 根据占位符判断provider存在性
    if "GLM_KEY=" in content:
        providers.add("glm")
    if "NIM_KEY_1=" in content:
        providers.add("nim")
    if "SWA_KEY_1=" in content:
        providers.add("swa")
    if "PPLX_KEY_1=" in content:
        providers.add("pplx")
    if "GH_MODELS_KEY=" in content:
        providers.add("github")
    if "OPENROUTER_KEY=" in content:
        providers.add("openrouter")
    if "OLLAMA_BASE=" in content:
        providers.add("ollama")
    if "FELO_API_KEY=" in content:
        providers.add("felo")
    if "SAMBANOVA_KEY=" in content:
        providers.add("sambanova")
    if "HF_KEY=" in content:
        providers.add("hf")
    if "ONEAPI_ADMIN_TOKEN=" in content:
        providers.add("oneapi")
    
    return providers

def check_consistency() -> dict:
    """执行四份清单的一致性检查"""
    free_llm_providers = scan_free_llm()
    task_router_providers = scan_task_router()
    secret_syncer_groups = scan_secret_syncer()
    env_tpl_providers = scan_env_tpl()
    
    # 转换为标准名称进行对比
    # 注意：需要处理名称映射差异
    
    # free_llm: glm, swa, pplx, nim, github, ollama
    # task_router: github, zhipu, openrouter, ollama, swa, pplx, nim (+ felo via PROVIDER_ADAPTERS)
    # secret_syncer: GLM, NIM, GH_MODELS, OPENROUTER, SAMBANOVA, HF, PPLX, SWA, TG, ONEAPI, OTHER, FELO, ALIASES
    # env_tpl: glm, nim, swa, pplx, github, openrouter, ollama, felo, sambanova, hf
    
    issues = []
    
    # 检查每个已知provider的四份清单一致性
    for std_name, mapping in PROVIDER_MAP.items():
        fl_name = mapping["free_llm"]
        tr_name = mapping["task_router"]
        ss_name = mapping["secret_syncer"]
        et_name = mapping["env_tpl"]
        
        # free_llm 检查
        if fl_name:
            fl_found = fl_name.replace("_call_", "") in free_llm_providers
            if not fl_found:
                issues.append(f"[{std_name}] free_llm.py 缺少 _call_{std_name} 实现")
        
        # task_router 检查
        if tr_name:
            tr_found = tr_name in task_router_providers
            if not tr_found:
                issues.append(f"[{std_name}] task_router.py 的 LocalMinerAdapter/PROVIDER_ADAPTERS 缺少 '{tr_name}' 注册")
        
        # secret_syncer 检查
        if ss_name:
            ss_found = ss_name in secret_syncer_groups
            if not ss_found:
                issues.append(f"[{std_name}] secret_syncer.py 的 KNOWN_KEY_GROUPS 缺少 '{ss_name}' 组")
        
        # env_tpl 检查
        if et_name:
            # 对于 env_tpl，我们检查是否有对应的 key 占位符
            et_found = std_name in env_tpl_providers
            if not et_found:
                issues.append(f"[{std_name}] .env.tpl 缺少 '{et_name}' 占位符")
    
    # 反向检查：task_router 里有没有 PROVIDER_MAP 没定义的 provider
    for tr_p in task_router_providers:
        found = False
        for std_name, mapping in PROVIDER_MAP.items():
            if mapping["task_router"] == tr_p:
                found = True
                break
        if not found:
            issues.append(f"[?] task_router.py 注册了未知 provider '{tr_p}'（未在 PROVIDER_MAP 中定义）")
    
    return {
        "free_llm": sorted(free_llm_providers),
        "task_router": sorted(task_router_providers),
        "secret_syncer": sorted(secret_syncer_groups),
        "env_tpl": sorted(env_tpl_providers),
        "issues": issues,
        "pass": len(issues) == 0,
    }

def send_notification(report: dict):
    """推送不一致通知到 Telegram"""
    try:
        sys.path.insert(0, str(WORKSPACE / "06_RUNTIME" / "connectors"))
        from tg_pusher import TGPusher
        
        bot_token = os.environ.get("TG_BOT_TOKEN_2") or os.environ.get("TG_BOT_TOKEN_1")
        chat_id = os.environ.get("TG_CHAT_ID", "5016609451")
        
        if not bot_token:
            return
        
        issues_text = "\n".join(f"  • {i}" for i in report["issues"][:10])
        if len(report["issues"]) > 10:
            issues_text += f"\n  ... 还有 {len(report['issues']) - 10} 项"
        
        msg = (
            f"⚠️ <b>Provider注册一致性告警</b>\n"
            f"时间: {os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}\n\n"
            f"<b>发现 {len(report['issues'])} 处不一致:</b>\n"
            f"{issues_text}\n\n"
            f"<b>各清单provider数:</b>\n"
            f"  free_llm: {len(report['free_llm'])}\n"
            f"  task_router: {len(report['task_router'])}\n"
            f"  secret_syncer: {len(report['secret_syncer'])}\n"
            f"  env_tpl: {len(report['env_tpl'])}"
        )
        
        pusher = TGPusher(bot_token, chat_id)
        pusher.send_message(msg, parse_mode="HTML")
    except Exception as e:
        print(f"[ConsistencyCheck] 通知发送失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="Provider注册一致性校验器")
    parser.add_argument("--notify", action="store_true", help="不一致时推送TG通知")
    args = parser.parse_args()
    
    print("🔍 Provider注册一致性检查")
    print("=" * 50)
    
    report = check_consistency()
    
    print(f"\n📋 free_llm.py 实现 ({len(report['free_llm'])}):")
    for p in report['free_llm']:
        print(f"  ✓ _call_{p}")
    
    print(f"\n📋 task_router.py 注册 ({len(report['task_router'])}):")
    for p in report['task_router']:
        print(f"  ✓ {p}")
    
    print(f"\n📋 secret_syncer.py 分组 ({len(report['secret_syncer'])}):")
    for p in report['secret_syncer']:
        print(f"  ✓ {p}")
    
    print(f"\n📋 .env.tpl 占位符 ({len(report['env_tpl'])}):")
    for p in report['env_tpl']:
        print(f"  ✓ {p}")
    
    print("\n" + "=" * 50)
    
    if report["pass"]:
        print("✅ 全部一致，无遗漏")
        return 0
    else:
        print(f"❌ 发现 {len(report['issues'])} 处不一致:")
        for issue in report["issues"]:
            print(f"  ⚠ {issue}")
        
        if args.notify:
            send_notification(report)
            print("\n📨 已推送告警通知")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
