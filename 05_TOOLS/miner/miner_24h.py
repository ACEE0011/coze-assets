#!/usr/bin/env python3
"""
24小时自动矿场 v5 - 任务路由+裁判+观察层
架构升级：
  P0: Registry + Observation — 工人注册中心 + 经验数据链
  P1: Task Router — 按任务需求匹配工人画像，不是谁分高谁上
  P2: Judge Layer — GLM做裁判对比输出质量
  P3: Auto Promote/Retire — 基于裁判胜率，不是基于评分
"""
import json, time, requests, os, sys, random, traceback
from datetime import datetime

API_BASE = os.environ.get("MINER_API_BASE", "http://localhost:3000/v1/chat/completions")
API_KEY = os.environ.get("MINER_API_KEY", "")
OUTPUT_DIR = os.environ.get("MINER_OUTPUT_DIR", "/home/coze/mine_output")

sys.path.insert(0, os.environ.get("BASE_DIR", "/home/coze"))
from task_router import registry, observation, router, judge, TASK_PROFILES

# === CONSTRAINT MONKEY PATCH v5 (2026-06-20) ===
# 运行时替换router.get_fallback_chain，注入约束过滤
_original_get_fallback_chain = router.get_fallback_chain.__func__

_AVOID_RULES = [
    ("*", "gh_r1"),           # RC-001
    ("*", "nim_ultra_550b"),  # RC-002
    ("*", "gh_4o"),           # RC-003
    ("persona_deep", "nim_mistral_675b"),  # RC-004
    ("canonical_v2", "gh_r1"),             # RC-005
    ("canonical_v2", "nim_ultra_550b"),    # RC-006
    ("persona_deep", "nim_ultra_550b"),    # RC-007
    ("signal_mean_reversion", "glm_4_flash"),     # RC-014
    ("signal_volume_price_divergence", "glm_4_flash"),  # RC-015
]
_PREFER_RULES = [
    ("signal_mean_reversion", "nim_deepseek"),  # RC-016
]

def _constrained_get_fallback_chain(self_task_router, task_name):
    """带约束过滤的get_fallback_chain"""
    chain = _original_get_fallback_chain(self_task_router, task_name)
    if not chain:
        return chain
    filtered = []
    for wid, mdl in chain:
        blocked = False
        for avoid_task, avoid_wid in _AVOID_RULES:
            if (avoid_task == "*" or avoid_task == task_name) and wid == avoid_wid:
                print(f"[CONSTRAINT] AVOID {task_name}->{wid} ({avoid_task}->{avoid_wid}) [{time.strftime('%H:%M:%S')}]")
                blocked = True
                break
        if not blocked:
            filtered.append((wid, mdl))
    if not filtered:
        print(f"[CONSTRAINT] WARN all AVOID for {task_name}, keeping original chain")
        return chain
    for pref_task, pref_wid in _PREFER_RULES:
        if pref_task == task_name:
            pref_items = [x for x in filtered if x[0] == pref_wid]
            rest_items = [x for x in filtered if x[0] != pref_wid]
            if pref_items:
                filtered = pref_items + rest_items
                print(f"[CONSTRAINT] PREFER {task_name}->{pref_wid} (front) [{time.strftime('%H:%M:%S')}]")
    return filtered

import types
router.get_fallback_chain = types.MethodType(_constrained_get_fallback_chain, router)
print("[CONSTRAINT] Monkey patch applied: 9 AVOID + 1 PREFER rules active")
# === END CONSTRAINT MONKEY PATCH ===


os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== 核心调用：任务驱动路由 ====================



def _stream_call(model, messages, max_tokens, temperature, timeout):
    """流式调用 - 边生成边返回，避免整体超时"""
    try:
        resp = requests.post(
            API_BASE,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            },
            timeout=timeout,
            stream=True
        )
        if resp.status_code != 200:
            try:
                err = resp.json()
                return None, err.get("error", {}).get("message", f"HTTP {resp.status_code}")
            except:
                return None, f"HTTP {resp.status_code}"
        
        content = ""
        t0 = time.time()
        tokens_in = 0
        tokens_out = 0
        for line in resp.iter_lines():
            if time.time() - t0 > timeout:
                # 已开始输出但超时，返回已有内容
                return {"content": content, "tokens_in": tokens_in, "tokens_out": tokens_out, "partial": True}, None
            if not line:
                continue
            line = line.decode("utf-8", errors="replace")
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                if "choices" in chunk and chunk["choices"]:
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        content += delta["content"]
                if "usage" in chunk and chunk["usage"]:
                    tokens_in = chunk["usage"].get("prompt_tokens", tokens_in)
                    tokens_out = chunk["usage"].get("completion_tokens", tokens_out)
            except json.JSONDecodeError:
                continue
        
        if not tokens_out:
            tokens_out = len(content.split())
        
        return {"content": content, "tokens_in": tokens_in, "tokens_out": tokens_out, "partial": False}, None
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, str(e)

def call_model(prompt, task_name, max_retries=2, max_tokens=2000, temperature=0.3, timeout=180):
    """
    按任务路由：不传model_type，传task_name
    Router自动匹配最合适的工人
    """
    chain = router.get_fallback_chain(task_name)
    
    if not chain:
        # fallback: 直接走GLM兜底
        chain = [("glm_flash", "glm-4-flash"), ("glm_air", "glm-4-air")]
    
    for worker_id, model in chain:
        w = registry.get_worker(worker_id)
        if not w:
            continue
        if w.get("status") != "alive":
            continue
        
        for attempt in range(max_retries):
            try:
                t0 = time.time()
                result, err = _stream_call(
                    model,
                    [
                        {"role": "system", "content": "你是R1系统考古分析师。严格按指令输出。所有结论必须标注[FACT]/[INFERENCE]/[HYPOTHESIS]/[MYTH]。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens, temperature, timeout
                )
                elapsed = time.time() - t0
                
                if result:
                    content = result["content"]
                    tokens_out = result["tokens_out"]
                    tokens_in = result["tokens_in"]
                    
                    partial = result.get("partial", False)
                    if partial:
                        log(f"  [{model}] 流式部分输出({elapsed:.0f}s, {len(content)} chars)")
                    # P0: 更新Registry + Observation
                    registry.update_stats(worker_id, elapsed, True)
                    corps = w.get("corps", "?")
                    observation.record(task_name, worker_id, model, corps, elapsed, True, tokens_in, tokens_out)
                    
                    return {
                        "worker_id": worker_id,
                        "model": model,
                        "corps": corps,
                        "content": content,
                        "success": True,
                        "elapsed": elapsed,
                        "tokens_out": tokens_out
                    }
                elif err:
                    msg = str(err)
                    if "429" in msg or "rate" in msg.lower():
                        wait = min(2 ** attempt * 4, 30)
                        log(f"  [{model}] 429限速，等{wait}s")
                        time.sleep(wait)
                        continue
                    else:
                        log(f"  [{model}] 错误: {msg[:80]}")
                        registry.update_stats(worker_id, elapsed, False)
                        observation.record(task_name, worker_id, model, w.get("corps","?"), elapsed, False, 0, 0, msg)
                        break
            except requests.exceptions.Timeout:
                elapsed = time.time() - t0
                log(f"  [{model}] 超时({elapsed:.0f}s)，切下一个")
                registry.update_stats(worker_id, elapsed, False)
                observation.record(task_name, worker_id, model, w.get("corps","?"), elapsed, False, 0, 0, "timeout")
                break
            except Exception as e:
                elapsed = time.time() - t0
                log(f"  [{model}] 异常: {str(e)[:80]}")
                registry.update_stats(worker_id, elapsed, False)
                observation.record(task_name, worker_id, model, w.get("corps","?"), elapsed, False, 0, 0, str(e))
                break
        
        # 连续失败3次标记为throttled(不直接dead，可能只是临时限流)
        w = registry.get_worker(worker_id)
        if w and w.get("success_rate", 1) < 0.3:
            recent_obs = [o for o in observation.data["observations"][-10:] 
                         if o["worker_id"] == worker_id and not o["success"]]
            if len(recent_obs) >= 3:
                registry.update_status(worker_id, "throttled", "连续3次失败")
                log(f"  ⚠️ {worker_id} 标记throttled")
    
    return {"worker_id": "?", "model": "?", "corps": "?", "content": "", "success": False, "elapsed": 0}


def call_model_judge(prompt, task_name, max_tokens=2000, temperature=0.3, timeout=180):
    """
    P2: 双模型输出+裁判 — 重要任务让两个工人干，裁判打分
    用于: canonical_v2等关键任务
    """
    chain = router.get_fallback_chain(task_name)
    if len(chain) < 2:
        return call_model(prompt, task_name, max_tokens=max_tokens, 
                         temperature=temperature, timeout=timeout)
    
    # 选前两个不同军团的工人
    worker_a_id, model_a = chain[0]
    corps_a = registry.get_worker(worker_a_id).get("corps", "?")
    worker_b_id, model_b = None, None
    for wid, m in chain[1:]:
        c = registry.get_worker(wid).get("corps", "?")
        if c != corps_a:
            worker_b_id, model_b = wid, m
            break
    if not worker_b_id:
        worker_b_id, model_b = chain[1]
    
    # 并行调用两个工人
    result_a = _call_single(prompt, task_name, worker_a_id, model_a, max_tokens, temperature, timeout)
    result_b = _call_single(prompt, task_name, worker_b_id, model_b, max_tokens, temperature, timeout)
    
    if not result_a["success"] and not result_b["success"]:
        return result_a
    if not result_a["success"]:
        return result_b
    if not result_b["success"]:
        return result_a
    
    # 裁判判分
    corps_b = registry.get_worker(worker_b_id).get("corps", "?")
    verdict = judge.judge(task_name, result_a["content"], worker_a_id, 
                          result_b["content"], worker_b_id, prompt)
    
    winner = verdict.get("winner", "平局")
    log(f"  ⚖️ 裁判: {worker_a_id} vs {worker_b_id} → {winner}")
    
    if winner == "B":
        # B胜 → 记录quality score到observation
        observation.record(task_name, worker_b_id, model_b, corps_b, 
                          result_b["elapsed"], True, 0, result_b.get("tokens_out",0),
                          quality_score=verdict.get("quality_b", 7))
        return result_b
    else:
        # A胜或平局 → 用A
        observation.record(task_name, worker_a_id, model_a, corps_a, 
                          result_a["elapsed"], True, 0, result_a.get("tokens_out",0),
                          quality_score=verdict.get("quality_a", 7))
        return result_a


def _call_single(prompt, task_name, worker_id, model, max_tokens, temperature, timeout):
    """单个工人调用(供judge模式使用)"""
    w = registry.get_worker(worker_id)
    if not w or w.get("status") != "alive":
        return {"worker_id": worker_id, "model": model, "corps": "?", "content": "", "success": False, "elapsed": 0}
    
    try:
        t0 = time.time()
        result, err = _stream_call(
            model,
            [
                {"role": "system", "content": "你是R1系统考古分析师。严格按指令输出。所有结论必须标注[FACT]/[INFERENCE]/[HYPOTHESIS]/[MYTH]。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens, temperature, timeout
        )
        elapsed = time.time() - t0
        
        if result:
            content = result["content"]
            tokens_out = result["tokens_out"]
            tokens_in = result["tokens_in"]
            registry.update_stats(worker_id, elapsed, True)
            corps = w.get("corps", "?")
            observation.record(task_name, worker_id, model, corps, elapsed, True, tokens_in, tokens_out)
            return {"worker_id": worker_id, "model": model, "corps": corps, 
                    "content": content, "success": True, "elapsed": elapsed, "tokens_out": tokens_out}
        else:
            registry.update_stats(worker_id, elapsed, False)
            observation.record(task_name, worker_id, model, w.get("corps","?"), elapsed, False, 0, 0, str(err))
            return {"worker_id": worker_id, "model": model, "corps": w.get("corps","?"), 
                    "content": "", "success": False, "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        registry.update_stats(worker_id, elapsed, False)
        observation.record(task_name, worker_id, model, w.get("corps","?"), elapsed, False, 0, 0, str(e))
        return {"worker_id": worker_id, "model": model, "corps": w.get("corps","?"), 
                "content": "", "success": False, "elapsed": elapsed}


# ==================== 日志与存储 ====================

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)
    with open(f"{OUTPUT_DIR}/miner.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")

def save_result(task_name, result):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = f"{OUTPUT_DIR}/{task_name}_{ts}.md"
    with open(outfile, "w") as f:
        f.write(f"# {task_name}\n\n")
        f.write(f"军团: {result.get('corps','?')} | 工人: {result.get('worker_id','?')} | 模型: {result.get('model','?')} | 耗时: {result.get('elapsed',0):.1f}s\n\n")
        f.write(result.get("content", ""))
    log(f"  产出: {outfile} ({result.get('elapsed',0):.1f}s, {len(result.get('content',''))} chars) [{result.get('corps','?')}]")
    return outfile

def _run_production_mode(registry, corps_stats):
    """云端生产模式 — 无R1数据时运行可用任务"""
    from pathlib import Path
    import shutil

    log("=" * 50)
    log("生产模式 — 市场情绪 + 模型基准测试")
    log("=" * 50)

    tasks_done = []

    # 任务1：市场情绪分析
    log("\n>>> 开始: 市场情绪分析")
    try:
        prompt = "你是疯子矿场的市场分析师。简短分析当前A股市场情绪（100字以内），输出格式：[情绪] [方向] [建议]"
        result = call_model(prompt, "market_sentiment")
        if result:
            save_result("market_sentiment", result)
            tasks_done.append("market_sentiment")
    except Exception as e:
        log(f"  市场情绪分析失败: {e}")

    # 任务2：模型基准测试
    log("\n>>> 开始: 模型基准测试")
    test_prompt = "用一句话解释什么是动量因子在量化交易中的应用。"
    for model_key, model_name in [("glm_flash", "glm-4-flash"), ("nim_deepseek", "deepseek-ai/deepseek-v4-flash"), ("github_mini", "gpt-4o-mini")]:
        try:
            result = call_model(test_prompt, f"benchmark_{model_key}")
            if result:
                save_result(f"benchmark_{model_key}", result)
                tasks_done.append(f"benchmark_{model_key}")
        except Exception as e:
            log(f"  {model_name} 基准测试失败: {e}")

    # 复制产出到 cloud/
    cloud_out = Path(os.environ.get("MINE_SEED", "/workspace/fengzi-repos/mine-seed")) / "cloud" / "miner"
    cloud_out.mkdir(parents=True, exist_ok=True)
    for task in tasks_done:
        latest = sorted(Path(OUTPUT_DIR).glob(f"{task}_*.md"), reverse=True)
        if latest:
            shutil.copy(latest[0], cloud_out)
            log(f"  产出复制到 cloud/: {latest[0].name}")

    log(f"\n{'='*50}")
    log(f"生产模式完成: {len(tasks_done)} 个任务")
    log(f"{'='*50}")

def load_r1_data():
    r1_path = os.environ.get("R1_DATA_PATH", "/app/data/所有对话/主对话/R1_Ω_FINAL.json")
    if not os.path.exists(r1_path):
        r1_path = os.environ.get("R1_DATA_PATH_FALLBACK", "/home/coze/R1_Ω_FINAL.json")
    if not os.path.exists(r1_path):
        import logging
        logging.warning(f"[MINER] R1 data not found, skipping archaeology tasks")
        return None
    with open(r1_path, "r") as f:
        return json.load(f)

def get_slices_sample(data, n=50, slice_type=None):
    slices = data["core_data"]["slices"]
    if slice_type:
        filtered = [s for s in slices if s.get("type") == slice_type]
        if filtered: slices = filtered
    n = min(n, len(slices))
    return random.sample(slices, n)

def get_unique_sources(data):
    sources = set()
    for s in data["core_data"]["slices"]:
        if "source" in s: sources.add(s["source"])
    return sorted(sources)

def get_slice_types_stats(data):
    from collections import Counter
    types = Counter(s.get("type", "unknown") for s in data["core_data"]["slices"])
    return dict(types)


# ============ 矿工任务库 ============

def task_slice_classification(data):
    stats = get_slice_types_stats(data)
    sources = get_unique_sources(data)
    sample = get_slices_sample(data, 30)
    sample_text = ""
    for i, s in enumerate(sample):
        content_preview = s.get("content", "")[:200]
        sample_text += f"\n[{i}] source={s.get('source','?')} type={s.get('type','?')} length={s.get('slice_length','?')}\ncontent: {content_preview}\n"
    prompt = f"""分析以下R1系统代码切片样本，完成：
1. 切片类型统计: {json.dumps(stats, ensure_ascii=False)}
2. 唯一源文件数: {len(sources)}
3. 样本内容（30个随机切片）:
{sample_text}
请分析：
A. 代码切片的分层结构（哪些是核心模块，哪些是工具/辅助）
B. 每种type的功能推断 [INFERENCE]
C. 哪些源文件包含架构关键代码 [FACT]
D. 切片之间的依赖/调用模式推断 [INFERENCE]"""
    result = call_model(prompt, "slice_classification", max_tokens=3000)
    if result["success"]:
        return save_result("slice_classification", result)
    return None

def task_persona_deep_analysis(data):
    personas = data.get("personality_config", {}).get("personas", {})
    alignment = data.get("personality_config", {}).get("alignment_settings", {})
    lang_vectors = data.get("personality_config", {}).get("language_style_vectors", {})
    tech_modules = data.get("personality_config", {}).get("technical_modules", {})
    guidelines = data.get("personality_config", {}).get("usage_guidelines", {})
    prompt = f"""深度分析R1系统的人格配置：
1. 人格列表 ({len(personas)}个):
{json.dumps(list(personas.keys()), ensure_ascii=False)}
2. 人格详细配置（前4个）:
{json.dumps(dict(list(personas.items())[:4]), ensure_ascii=False, indent=2)[:3000]}
3. 对齐设置:
{json.dumps(alignment, ensure_ascii=False, indent=2)[:1000]}
4. 语言风格向量:
{json.dumps(lang_vectors, ensure_ascii=False, indent=2)[:1000]}
5. 技术模块:
{json.dumps(tech_modules, ensure_ascii=False, indent=2)[:500]}
6. 使用指南:
{json.dumps(guidelines, ensure_ascii=False, indent=2)[:500]}
请分析：
A. 12个人格的职责分工和层级关系 [INFERENCE]
B. 对齐设置5个维度的设计意图 [INFERENCE]
C. 语言风格向量的编码规则 [INFERENCE]
D. 人格激活/路由机制推测 [HYPOTHESIS]
E. 与R1.txt 10人格的映射关系 [HYPOTHESIS]"""
    result = call_model(prompt, "persona_deep", max_tokens=3000, timeout=300)
    if result["success"]:
        return save_result("persona_deep", result)
    return None

def task_shadow_layer_analysis(data):
    shadow = data.get("framework_config", {}).get("shadow_layer", {})
    modules = data.get("framework_config", {}).get("modules", {})
    architecture = data.get("framework_config", {}).get("architecture", {})
    prompt = f"""深度分析R1系统的Shadow Layer和架构模式：
1. Shadow Layer完整配置:
{json.dumps(shadow, ensure_ascii=False, indent=2)[:2000]}
2. 所有模块配置:
{json.dumps(modules, ensure_ascii=False, indent=2)[:2000]}
3. 架构模式:
{json.dumps(architecture, ensure_ascii=False, indent=2)}
请分析：
A. Shadow Layer 6个function的具体交互机制 [INFERENCE]
B. bidirectional双向映射的数据流方向 [INFERENCE]
C. dual-core同步的触发条件和同步内容 [INFERENCE]
D. self_error_detection的错误类型和处理链路 [HYPOTHESIS]
E. Shadow与主线的优先级关系(ROOT_DIRECTIVE) [FACT]
F. 架构模式"v2-self-evolving"的演化机制 [HYPOTHESIS]"""
    result = call_model(prompt, "shadow_analysis", max_tokens=3000, timeout=300)
    if result["success"]:
        return save_result("shadow_analysis", result)
    return None

def task_routing_flow_analysis(data):
    flow_v2 = data.get("routing_config", {}).get("flow_v2", {})
    dual_core = data.get("routing_config", {}).get("dual_core_config", {})
    prompt = f"""深度分析R1系统的路由配置：
1. Flow V2完整配置:
{json.dumps(flow_v2, ensure_ascii=False, indent=2)[:3000]}
2. Dual Core配置:
{json.dumps(dual_core, ensure_ascii=False, indent=2)}
请分析：
A. flow_v2每个step的输入输出和状态转换 [FACT]
B. auto_correct=true的触发条件和纠正逻辑 [INFERENCE]
C. shadow_alignment=true对齐的维度和机制 [INFERENCE]
D. prefer_intent合并逻辑的优先级规则 [INFERENCE]
E. self_evolve_on_output的演化触发和反馈回路 [HYPOTHESIS]
F. flow_v3为空说明什么？系统演化阶段判断 [HYPOTHESIS]"""
    result = call_model(prompt, "routing_analysis", max_tokens=3000, timeout=300)
    if result["success"]:
        return save_result("routing_analysis", result)
    return None

def task_code_slice_mining(data):
    sample = get_slices_sample(data, 50)
    sample_text = ""
    for i, s in enumerate(sample):
        content_preview = s.get("content", "")[:300]
        sample_text += f"\n---[{i}]---\nsource: {s.get('source','?')}\ntype: {s.get('type','?')}\nlength: {s.get('slice_length','?')}\ncontent:\n{content_preview}\n"
    prompt = f"""对以下50个R1代码切片进行分类和评估：
{sample_text}
请输出：
1. 每个切片的架构层级分类：Kernel/Protocol/Routing/Lexicon/Memory/Utility/Test/Config/Unknown
2. 发现的重复模式（出现3次以上的）[FACT]
3. 可能遗漏的架构组件推测 [HYPOTHESIS]
4. 最有分析价值的5个切片编号及原因"""
    result = call_model(prompt, "slice_mining", max_tokens=3000, timeout=300)
    if result["success"]:
        return save_result("slice_mining", result)
    return None

def task_upgrade_path_analysis(data):
    upgrade = data.get("framework_config", {}).get("upgrade_path", [])
    uni_root = data.get("uni_root_integration", {})
    system_config = data.get("system_config", {})
    prompt = f"""分析R1系统的升级路径和系统集成：
1. 升级路径:
{json.dumps(upgrade, ensure_ascii=False, indent=2)}
2. Uni-Root集成状态:
{json.dumps(uni_root, ensure_ascii=False, indent=2)}
3. 系统配置:
{json.dumps(system_config, ensure_ascii=False, indent=2)[:2000]}
请分析：
A. V∞-v3到v5的演化方向和递进关系 [FACT]
B. uni_root_integration完成意味着什么 [INFERENCE]
C. SYSTEM_ROOT和V∞_BLUEPRINT_V2的设计意图 [INFERENCE]
D. conflicts_resolved字段暗示的系统矛盾 [INFERENCE]
E. 系统最终形态推测 [HYPOTHESIS]"""
    result = call_model(prompt, "upgrade_analysis", max_tokens=2500, timeout=300)
    if result["success"]:
        return save_result("upgrade_analysis", result)
    return None

def task_canonical_v2_synthesis(data):
    """关键任务 → 双模型+裁判"""
    all_outputs = ""
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith(".md") and f != "summary.md" and not f.startswith("canonical"):
            with open(f"{OUTPUT_DIR}/{f}") as fh:
                all_outputs += f"\n---{f}---\n{fh.read()[:1000]}\n"
    v1_path = "/app/data/所有对话/主对话/R1_Canonical_Structure_v1.md"
    if os.path.exists(v1_path):
        with open(v1_path) as f: v1 = f.read()[:2000]
    else: v1 = "v1 not found"
    prompt = f"""基于所有矿工分析产出，合成R1 Canonical Structure v2。
之前的产出摘要:
{all_outputs[:5000]}
Canonical Structure v1概要:
{v1}
请输出完整的R1 Canonical Structure v2，要求：
1. 树状结构图，每个节点标[FACT]/[INFERENCE]/[HYPOTHESIS]
2. 比v1新增的发现用★标注
3. 与v1的diff（新增/修改/删除）
4. 争议登记表更新
5. 下一步验证建议"""
    result = call_model_judge(prompt, "canonical_v2", max_tokens=4000, timeout=300)
    if result["success"]:
        return save_result("canonical_v2", result)
    return None


# ============ P3: 自动淘汰/升级(基于Judge胜率) ============

def auto_retire_by_judge():
    """基于裁判胜率淘汰：胜率<30%且参与>5场的工人"""
    retired = []
    for task, workers in judge.history.get("win_rates", {}).items():
        for wid, stats in workers.items():
            total = stats.get("wins",0) + stats.get("losses",0) + stats.get("draws",0)
            if total < 5:
                continue
            wr = stats.get("wins", 0) / total
            if wr < 0.3:
                registry.update_status(wid, "dead", f"{task}胜率{wr:.0%}过低")
                retired.append(f"{wid}({task}:{wr:.0%})")
    return retired

def auto_promote_by_judge():
    """基于裁判胜率升级：某任务胜率>80%且参与>5场 → 写入worker strength"""
    promoted = []
    for task, workers in judge.history.get("win_rates", {}).items():
        task_profile = TASK_PROFILES.get(task, {})
        task_caps = task_profile.get("requirements", [])
        for wid, stats in workers.items():
            total = stats.get("wins",0) + stats.get("losses",0) + stats.get("draws",0)
            if total < 5:
                continue
            wr = stats.get("wins", 0) / total
            if wr > 0.8:
                w = registry.get_worker(wid)
                if w:
                    strengths = set(w.get("strengths", []))
                    new_strengths = strengths | set(task_caps)
                    if new_strengths != strengths:
                        w["strengths"] = list(new_strengths)
                        promoted.append(f"{wid}+{task}({wr:.0%})")
    if promoted:
        registry._save()
    return promoted


# ============ 主控循环 ============

def run_shift():
    log("=" * 60)
    log("矿场开工！v5 任务路由+裁判+观察层")
    log("P0:Registry+Observation | P1:TaskRouter | P2:Judge | P3:AutoPromote")
    log("=" * 60)
    
    # P3: 班次开始前自动淘汰/升级
    retired = auto_retire_by_judge()
    if retired:
        log(f"💀 裁判淘汰: {retired}")
    promoted = auto_promote_by_judge()
    if promoted:
        log(f"⬆️ 裁判升级: {promoted}")
    
    # 健康检查：复活throttled工人(可能已经恢复)
    for wid, w in registry.data["workers"].items():
        if w.get("status") == "throttled":
            registry.update_status(wid, "alive", "班次开始自动恢复")
            log(f"🔄 {wid} 恢复alive")
    
    data = load_r1_data()
    if data is None:
        corps_stats = {"🚀GLM": 0, "🏆NIM": 0, "🆓GH": 0}
        log("⚠️ R1数据不可用，切换到生产模式")
        _run_production_mode(registry, corps_stats)
        return
    
    log(f"R1数据加载完成: {len(data['core_data']['slices'])} 切片")
    
    tasks = [
        ("切片分类统计", task_slice_classification),
        ("人格深度分析", task_persona_deep_analysis),
        ("Shadow层分析", task_shadow_layer_analysis),
        ("路由流程分析", task_routing_flow_analysis),
        ("代码切片深挖", task_code_slice_mining),
        ("升级路径分析", task_upgrade_path_analysis),
    ]
    
    results = []
    corps_stats = {"🚀GLM": 0, "🏆NIM": 0, "🆓GH": 0}
    
    for name, task_fn in tasks:
        log(f"\n>>> 开始: {name}")
        try:
            outfile = task_fn(data)
            if outfile:
                results.append({"task": name, "status": "✅", "file": outfile})
            else:
                results.append({"task": name, "status": "❌", "file": ""})
        except Exception as e:
            log(f"  异常: {str(e)[:100]}")
            traceback.print_exc()
            results.append({"task": name, "status": "❌", "file": str(e)[:50]})
        time.sleep(2)
    
    log(f"\n>>> 开始: Canonical v2综合 (双模型+裁判)")
    try:
        outfile = task_canonical_v2_synthesis(data)
        if outfile:
            results.append({"task": "Canonical v2综合", "status": "✅", "file": outfile})
        else:
            results.append({"task": "Canonical v2综合", "status": "❌", "file": ""})
    except Exception as e:
        log(f"  异常: {str(e)[:100]}")
        results.append({"task": "Canonical v2综合", "status": "❌", "file": str(e)[:50]})
    
    # 统计军团贡献
    for r in results:
        if r["status"] == "✅" and r.get("file"):
            try:
                with open(r["file"]) as f:
                    first_line = f.readline()
                    for c in corps_stats:
                        if c in first_line:
                            corps_stats[c] += 1
            except:
                pass
    
    success = sum(1 for r in results if r["status"] == "✅")
    
    log("\n" + "=" * 60)
    log("班次结束！汇总：")
    log(f"  成功: {success}/{len(results)}")
    for r in results:
        log(f"  {r['status']} {r['task']}: {r['file']}")
    log(f"  军团: {' | '.join(f'{k}:{v}' for k,v in corps_stats.items())}")
    
    # 输出各层报告
    log("\n" + registry.report())
    log("\n" + observation.report())
    log("\n" + judge.report())
    
    with open(f"{OUTPUT_DIR}/summary.json", "w") as f:
        json.dump({"results": results, "corps_stats": corps_stats, 
                   "shift_time": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    return results

if __name__ == "__main__":
    shift_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    log(f"矿场启动 - 第{shift_num}班次 (v5 任务路由+裁判)")
    run_shift()
    log("矿场停工 - 等待下一班次")
