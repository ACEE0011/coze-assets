#!/usr/bin/env python3
"""
任务路由器 v3 - ProviderAdapter 抽象 + 动态 Registry 生成
核心设计：
1. ProviderAdapter → 统一 Provider 抽象，解耦 Registry 与具体实现
2. Task Classifier → 识别任务需求(requirements)
3. Worker Match → 按需求匹配工人画像(strengths/weaknesses)
4. Judge Layer → 裁判对比输出质量
5. Observation Log → 持久化经验数据链
6. Registry → 动态生成（扫描 Provider → Probe → 生成 → Cache）

AUM-MISSION-OPS-003:
- ProviderAdapter 抽象层：OneAPI / LocalMiner / FreeLLM 均可适配
- 动态 Registry：启动时扫描环境变量，Probe 可用 Provider，生成 worker 配置
- OneAPI Down 自动 fallback 到 local_miner
- Shadow Observer 无需修改
"""
import json, time, os, threading, requests, urllib.request
from datetime import datetime
from pathlib import Path

# P1-保守适配：使用 Path 动态获取路径，支持 Windows/Linux
_BASE_DIR = Path(__file__).parent
_DATA_DIR = _BASE_DIR / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 加载 .env 文件（如果存在，往上两级找 mine-seed 根目录）
_env_file = _BASE_DIR.parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key not in os.environ:
                os.environ[_key] = _val

REGISTRY_FILE = os.environ.get("WORKER_REGISTRY", str(_BASE_DIR / "worker_registry.json"))
OBSERVATION_FILE = os.environ.get("OBSERVATION_FILE", str(_BASE_DIR / "observation_log.json"))
JUDGE_FILE = os.environ.get("JUDGE_FILE", str(_BASE_DIR / "judge_history.json"))

API_BASE = os.environ.get("MINER_API_BASE", "http://localhost:3000/v1/chat/completions")
API_KEY = os.environ.get("MINER_API_KEY", "{{ONE_API_KEY}}")


# ==================== ProviderAdapter 抽象层 ====================
# 统一 Provider 接口，TaskRouter 只认识 Adapter，不认识具体 Provider
class ProviderAdapter:
    """Provider 适配器基类 — 定义统一的调用接口"""
    
    def __init__(self, name: str):
        self.name = name
    
    def is_available(self) -> bool:
        """检查 Provider 是否可用"""
        return False
    
    def probe(self) -> list:
        """探测 Provider 下可用的模型/能力"""
        return []
    
    def call(self, model: str, messages: list, max_tokens: int = 500, 
             temperature: float = 0.7) -> dict:
        """调用 Provider"""
        return {"error": f"Provider {self.name} not available"}
    
    def get_models(self) -> dict:
        """获取该 Provider 下所有模型的能力画像"""
        return {}


class OneAPIAdapter(ProviderAdapter):
    """OneAPI Provider 适配器 — 原路径"""
    
    def __init__(self):
        super().__init__("oneapi")
    
    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{API_BASE.rstrip('/')}/v1/models", 
                               headers={"Authorization": f"Bearer {API_KEY}"},
                               timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def probe(self) -> list:
        try:
            resp = requests.get(f"{API_BASE.rstrip('/')}/v1/models", 
                               headers={"Authorization": f"Bearer {API_KEY}"},
                               timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            pass
        return []
    
    def call(self, model: str, messages: list, max_tokens: int = 500,
             temperature: float = 0.7) -> dict:
        try:
            resp = requests.post(
                API_BASE,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data:
                    return {
                        "content": data["choices"][0]["message"]["content"],
                        "model": model,
                        "provider": "oneapi",
                        "success": True,
                    }
            return {"error": f"OneAPI returned {resp.status_code}", "success": False}
        except Exception as e:
            return {"error": f"OneAPI error: {e}", "success": False}
    
    def get_models(self) -> dict:
        # OneAPI 的模型能力需要从配置中获取，这里先返回常见模型的默认画像
        return {
            "glm-4-flash": {
                "capabilities": ["technical_analysis", "risk_assessment", "structured_output", "fast", "chinese"],
                "context_window": 128000,
                "avg_latency": 5,
                "success_rate": 0.95,
            },
            "gpt-4o-mini": {
                "capabilities": ["technical_analysis", "risk_assessment", "structured_output", "fast", "reasoning"],
                "context_window": 128000,
                "avg_latency": 3,
                "success_rate": 0.98,
            },
            "qwen2.5-7b": {
                "capabilities": ["technical_analysis", "risk_assessment", "chinese", "fast"],
                "context_window": 32000,
                "avg_latency": 2,
                "success_rate": 0.90,
            },
        }


class LocalMinerAdapter(ProviderAdapter):
    """LocalMiner Provider 适配器 — fallback 路径，复用 local_miner.py 的 Provider"""
    
    def __init__(self):
        super().__init__("local_miner")
        self._providers = {}
        self._init_providers()
    
    def _init_providers(self):
        """初始化 local_miner 的各个 Provider"""
        # GitHub Models
        if os.environ.get("GITHUB_PAT"):
            self._providers["github"] = {
                "call": self._call_github,
                "models": {"gpt-4o-mini": {"capabilities": ["reasoning", "risk_assessment", "structured_output", "fast"]}},
                "available": True,
            }
        
        # Zhipu GLM
        if os.environ.get("ZHIPU_KEY"):
            self._providers["zhipu"] = {
                "call": self._call_zhipu,
                "models": {"glm-4-flash": {"capabilities": ["technical_analysis", "risk_assessment", "structured_output", "fast", "chinese"]}},
                "available": True,
            }
        
        # OpenRouter
        if os.environ.get("OPENROUTER_KEY"):
            self._providers["openrouter"] = {
                "call": self._call_openrouter,
                "models": {"meta-llama/llama-3.3-70b-instruct:free": {"capabilities": ["reasoning", "risk_assessment", "long_context"]}},
                "available": True,
            }
        
        # Ollama
        if self._check_ollama():
            self._providers["ollama"] = {
                "call": self._call_ollama,
                "models": {"qwen2.5-vl": {"capabilities": ["technical_analysis", "risk_assessment", "vision", "chinese"]}},
                "available": True,
            }
        
        # 神稳AI (SWA) — AUM-MISSION-RUNNER-001 子任务2 接入矿池
        # 仅在至少有一个真实 key 时才注册，避免空 worker
        swa_keys = [os.environ.get(f"SWA_KEY_{i}", "") for i in range(1, 11)]
        swa_keys = [k for k in swa_keys if k and not k.startswith("{{")]
        if swa_keys:
            self._providers["swa"] = {
                "call": self._call_swa,
                "models": {
                    os.environ.get("SWA_MODEL", "gpt-5.4-mini"): {
                        "capabilities": ["reasoning", "analysis", "structured_output", "chinese", "long_context"],
                        "context_window": 32000,
                        "avg_latency": 8,
                        "success_rate": 0.92,
                    }
                },
                "available": True,
            }
        
        # Perplexity (PPLX) — 带熔断/退避/key轮询
        pplx_keys = [os.environ.get(f"PPLX_KEY_{i}", "") for i in range(1, 11)]
        pplx_keys = [k for k in pplx_keys if k and not k.startswith("{{")]
        if pplx_keys:
            self._providers["pplx"] = {
                "call": self._call_pplx,
                "models": {
                    os.environ.get("PPLX_MODEL", "sonar"): {
                        "capabilities": ["reasoning", "analysis", "search", "structured_output"],
                        "context_window": 16000,
                        "avg_latency": 5,
                        "success_rate": 0.90,
                    }
                },
                "available": True,
            }
        
        # NVIDIA NIM — 16 key 轮询
        nim_keys = [os.environ.get(f"NIM_KEY_{i}", "") for i in range(1, 17)]
        nim_keys = [k for k in nim_keys if k and not k.startswith("{{")]
        if nim_keys:
            self._providers["nim"] = {
                "call": self._call_nim,
                "models": {
                    os.environ.get("NIM_MODEL", "meta/llama-3.1-8b-instruct"): {
                        "capabilities": ["reasoning", "analysis", "fast", "structured_output"],
                        "context_window": 128000,
                        "avg_latency": 3,
                        "success_rate": 0.95,
                    }
                },
                "available": True,
            }
    
    def _check_ollama(self) -> bool:
        try:
            base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
            req = urllib.request.Request(f"{base}/api/tags")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False
    
    def _call_github(self, model, messages, max_tokens=500, temperature=0.7):
        pat = os.environ.get("GITHUB_PAT", "")
        base = os.environ.get("GITHUB_BASE", "https://models.inference.ai.azure.com")
        data = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(data).encode(),
            headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read().decode())
                if "choices" in result:
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "model": model,
                        "provider": "github",
                        "success": True,
                    }
            return {"error": "No choices", "success": False}
        except Exception as e:
            return {"error": f"GitHub error: {e}", "success": False}
    
    def _call_zhipu(self, model, messages, max_tokens=500, temperature=0.7):
        key = os.environ.get("ZHIPU_KEY", "")
        base = os.environ.get("ZHIPU_BASE", "https://open.bigmodel.cn/api/paas/v4")
        data = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(data).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read().decode())
                if "choices" in result:
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "model": model,
                        "provider": "zhipu",
                        "success": True,
                    }
            return {"error": "No choices", "success": False}
        except Exception as e:
            return {"error": f"Zhipu error: {e}", "success": False}
    
    def _call_openrouter(self, model, messages, max_tokens=500, temperature=0.7):
        key = os.environ.get("OPENROUTER_KEY", "")
        base = os.environ.get("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
        data = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ace.local",
            "X-Title": "ACE Miner",
        }
        req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read().decode())
                if "choices" in result:
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "model": model,
                        "provider": "openrouter",
                        "success": True,
                    }
            return {"error": "No choices", "success": False}
        except Exception as e:
            return {"error": f"OpenRouter error: {e}", "success": False}
    
    def _call_ollama(self, model, messages, max_tokens=500, temperature=0.7):
        base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "huihui_ai/qwen2.5-vl-abliterated:7b")
        data = {
            "model": ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        req = urllib.request.Request(f"{base}/api/chat", data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                result = json.loads(r.read().decode())
                if "message" in result:
                    return {
                        "content": result["message"]["content"],
                        "model": ollama_model,
                        "provider": "ollama",
                        "success": True,
                    }
            return {"error": "No message", "success": False}
        except Exception as e:
            return {"error": f"Ollama error: {e}", "success": False}
    
    def _call_swa(self, model, messages, max_tokens=500, temperature=0.7):
        """调用神稳AI — AUM-MISSION-RUNNER-001 子任务2
        
        委托给 free_llm._call_swa，自带熔断/退避/key轮询。
        路由调度场景下熔断机制同样生效。
        """
        try:
            # 优先复用 free_llm 的完整实现（带熔断/退避/key轮询）
            import sys
            _free_llm_dir = str(_BASE_DIR)
            if _free_llm_dir not in sys.path:
                sys.path.insert(0, _free_llm_dir)
            from free_llm import _call_swa as free_llm_call_swa
            
            result = free_llm_call_swa(messages, max_tokens, temperature)
            if result and "content" in result:
                return {
                    "content": result["content"],
                    "model": result.get("model", model),
                    "provider": "swa",
                    "success": True,
                }
            return {"error": "SWA returned no content", "success": False}
        except Exception as e:
            return {"error": f"SWA error: {e}", "success": False}
    
    def _call_pplx(self, model, messages, max_tokens=500, temperature=0.7):
        """调用 Perplexity — 委托给 free_llm，自带熔断/退避/key轮询"""
        try:
            import sys
            _free_llm_dir = str(_BASE_DIR)
            if _free_llm_dir not in sys.path:
                sys.path.insert(0, _free_llm_dir)
            from free_llm import _call_pplx as free_llm_call_pplx
            
            result = free_llm_call_pplx(messages, max_tokens, temperature)
            if result and "content" in result:
                return {
                    "content": result["content"],
                    "model": result.get("model", model),
                    "provider": "pplx",
                    "success": True,
                }
            return {"error": "PPLX returned no content", "success": False}
        except Exception as e:
            return {"error": f"PPLX error: {e}", "success": False}
    
    def _call_nim(self, model, messages, max_tokens=500, temperature=0.7):
        """调用 NVIDIA NIM — 委托给 free_llm，自带 key 轮询"""
        try:
            import sys
            _free_llm_dir = str(_BASE_DIR)
            if _free_llm_dir not in sys.path:
                sys.path.insert(0, _free_llm_dir)
            from free_llm import _call_nim as free_llm_call_nim
            
            result = free_llm_call_nim(messages, max_tokens, temperature)
            if result and "content" in result:
                return {
                    "content": result["content"],
                    "model": result.get("model", model),
                    "provider": "nim",
                    "success": True,
                }
            return {"error": "NIM returned no content", "success": False}
        except Exception as e:
            return {"error": f"NIM error: {e}", "success": False}
    
    def is_available(self) -> bool:
        return len(self._providers) > 0
    
    def probe(self) -> list:
        models = []
        for provider_name, info in self._providers.items():
            for model_name in info["models"]:
                models.append(f"{provider_name}/{model_name}")
        return models
    
    def call(self, model: str, messages: list, max_tokens: int = 500,
             temperature: float = 0.7) -> dict:
        # 解析 model 格式: provider/model
        if "/" in model:
            provider_name, model_name = model.split("/", 1)
        else:
            # 默认按优先级尝试
            for provider_name in ["zhipu", "github", "ollama", "swa", "openrouter"]:
                if provider_name in self._providers:
                    info = self._providers[provider_name]
                    model_name = list(info["models"].keys())[0]
                    break
            else:
                return {"error": "No available provider", "success": False}
        
        if provider_name in self._providers:
            return self._providers[provider_name]["call"](model_name, messages, max_tokens, temperature)
        return {"error": f"Provider {provider_name} not available", "success": False}
    
    def get_models(self) -> dict:
        result = {}
        for provider_name, info in self._providers.items():
            for model_name, model_info in info["models"].items():
                full_name = f"{provider_name}/{model_name}"
                result[full_name] = model_info
        return result


# ==================== Provider 注册表 ====================
PROVIDER_ADAPTERS = {
    "oneapi": OneAPIAdapter,
    "local_miner": LocalMinerAdapter,
    "felo": lambda: __import__("felo_provider").FeloAdapter(),
}

# ==================== 任务画像定义 ====================
# 每种任务需要的capability → 匹配worker的strengths
TASK_PROFILES = {
    "slice_classification": {
        "requirements": ["classification", "extraction", "fast_response"],
        "avoid": [],  # 不需要的能力(匹配到weakness就降权)
        "max_latency": 30,
        "min_context": 8000,
        "strategy": "speed",
    },
    "persona_deep": {
        "requirements": ["deep_reasoning", "analysis", "long_context"],
        "avoid": [],
        "max_latency": 300,
        "min_context": 32000,
        "strategy": "quality",
    },
    "shadow_analysis": {
        "requirements": ["reasoning", "analysis", "structured_output"],
        "avoid": [],
        "max_latency": 300,
        "min_context": 16000,
        "strategy": "quality",
    },
    "routing_analysis": {
        "requirements": ["reasoning", "analysis", "coding"],
        "avoid": [],
        "max_latency": 300,
        "min_context": 16000,
        "strategy": "quality",
    },
    "slice_mining": {
        "requirements": ["analysis", "extraction", "coding"],
        "avoid": [],
        "max_latency": 300,
        "min_context": 16000,
        "strategy": "balanced",
    },
    "upgrade_analysis": {
        "requirements": ["reasoning", "analysis", "long_context"],
        "avoid": [],
        "max_latency": 300,
        "min_context": 16000,
        "strategy": "quality",
    },
    "canonical_v2": {
        "requirements": ["synthesis", "deep_reasoning", "long_context", "structured_output"],
        "avoid": ["latency"],  # 接受慢
        "max_latency": 600,
        "min_context": 64000,
        "strategy": "quality",
    },
    # P1-保守方案：矿工审计任务画像
    # 矿工只做"裁判"，不做"教练"
    # 输出仅作 Evidence 附加字段，不影响 Admission 决策
    "audit_only": {
        "requirements": ["technical_analysis", "risk_assessment", "structured_output"],
        "avoid": ["latency"],  # 审计允许慢
        "max_latency": 120,
        "min_context": 16000,
        "strategy": "quality",
        "description": "P1-保守方案：推荐后矿工审计",
        "affects_admission": False,  # 明确：不影响 Admission 决策
        "output_as_evidence_only": True,  # 明确：仅作 Evidence 附加字段
    },
}


class WorkerRegistry:
    """P0: 工人注册中心 — 动态生成，不是静态配置
    
    启动流程：
    1. 扫描环境变量（API Key 是否存在）
    2. 实例化 ProviderAdapter，Probe 可用模型
    3. 根据模型能力画像生成 worker 配置
    4. 写入 Cache（worker_registry.json）
    
    Registry = Capability Snapshot，不是死人名单
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.data = self._load()
        # 如果 Registry 为空，动态生成
        if not self.data["workers"]:
            self._generate_from_providers()
    
    def _load(self):
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": "1.0", "workers": {}}
    
    def _save(self):
        with open(REGISTRY_FILE, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def _generate_from_providers(self):
        """从 ProviderAdapter 动态生成 worker 配置
        
        流程：扫描 → Probe → 生成 → Cache
        """
        print(f"  🧪 Registry 动态生成: 扫描 ProviderAdapter...")
        
        workers = {}
        provider_order = ["oneapi", "local_miner", "felo"]  # OneAPI -> local_miner -> Felo
        
        for provider_name in provider_order:
            adapter_class = PROVIDER_ADAPTERS.get(provider_name)
            if not adapter_class:
                continue
            
            try:
                adapter = adapter_class() if provider_name != "local_miner" else adapter_class()
                if not adapter.is_available():
                    print(f"  ⏭️ {provider_name}: 不可用，跳过")
                    continue
                
                print(f"  ✅ {provider_name}: 可用，开始 Probe...")
                models = adapter.get_models()
                
                for model_name, model_info in models.items():
                    # 生成 worker ID
                    worker_id = f"{provider_name}_{model_name.replace('/', '_')}"
                    
                    # 确定军团（corps）
                    corps_map = {
                        "oneapi": "OneAPI",
                        "zhipu": "GLM",
                        "github": "GitHub",
                        "ollama": "Ollama",
                        "openrouter": "OpenRouter",
                        "swa": "SWA",
                        "felo": "Felo",
                    }
                    corps = corps_map.get(provider_name, provider_name.capitalize())
                    if "/" in model_name:
                        provider_part = model_name.split("/")[0]
                        corps = corps_map.get(provider_part, corps)
                    
                    workers[worker_id] = {
                        "provider": provider_name,
                        "model": model_name,
                        "corps": corps,
                        "status": "alive",
                        "strengths": model_info.get("capabilities", []),
                        "weaknesses": [],
                        "context_window": model_info.get("context_window", 32000),
                        "avg_latency": model_info.get("avg_latency", 10),
                        "success_rate": model_info.get("success_rate", 0.9),
                        "rpm": 0,
                        "last_update": datetime.now().isoformat(),
                    }
                    print(f"    🔧 {worker_id}: strengths={model_info.get('capabilities', [])}")
                
            except Exception as e:
                print(f"  ⚠️ {provider_name}: Probe 失败 - {e}")
                continue
        
        if workers:
            self.data["workers"] = workers
            self._save()
            print(f"  📦 Registry 生成完成: {len(workers)} 个 worker")
        else:
            print(f"  ⚠️ 无可用 Provider，Registry 保持空")
    
    def get_alive(self, corps=None):
        """获取存活工人列表"""
        workers = []
        for wid, w in self.data["workers"].items():
            if w.get("status") != "alive":
                continue
            if corps and w.get("corps") != corps:
                continue
            workers.append((wid, w))
        return workers
    
    def get_worker(self, worker_id):
        return self.data["workers"].get(worker_id)
    
    def update_status(self, worker_id, status, reason=""):
        """更新工人状态"""
        with self.lock:
            if worker_id in self.data["workers"]:
                self.data["workers"][worker_id]["status"] = status
                if reason:
                    self.data["workers"][worker_id]["last_reason"] = reason
                self.data["workers"][worker_id]["last_update"] = datetime.now().isoformat()
                self._save()
    
    def update_stats(self, worker_id, elapsed, success):
        """更新工人运行时统计"""
        with self.lock:
            w = self.data["workers"].get(worker_id)
            if not w:
                return
            alpha = 0.3
            w["avg_latency"] = round(w.get("avg_latency", 10) * (1 - alpha) + elapsed * alpha, 1)
            sr = w.get("success_rate", 0.9)
            w["success_rate"] = round(sr * (1 - alpha) + (1.0 if success else 0.0) * alpha, 3)
            self._save()
    
    def report(self):
        """输出Registry状态"""
        lines = ["📋 Worker Registry 状态报告", "=" * 50]
        corps_set = set(w.get("corps", "") for w in self.data["workers"].values())
        for corps in sorted(corps_set):
            workers = self.get_alive(corps=corps)
            alive = len(workers)
            total_rpm = sum(w.get("rpm", 0) for _, w in workers)
            emoji = {"GLM": "🚀", "GitHub": "🆓", "Ollama": "🏠", "OpenRouter": "🌐", "OneAPI": "🔗"}.get(corps, "?")
            lines.append(f"\n{emoji} {corps}军团: {alive}存活 | {total_rpm}RPM")
            for wid, w in workers:
                lines.append(f"  {wid}: lat={w.get('avg_latency',0):.1f}s sr={w.get('success_rate',0):.2f} {w.get('strengths',[])}")
        dead = [(wid, w) for wid, w in self.data["workers"].items() if w.get("status") != "alive"]
        if dead:
            lines.append(f"\n💀 离线: {len(dead)}")
            for wid, w in dead:
                lines.append(f"  {wid}: {w.get('status')} - {w.get('last_reason','')}")
        return "\n".join(lines)


class ObservationLog:
    """P0: 观察层 — 任务→调用→结果→评估 的完整数据链"""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = self._load()
    def _load(self):
        if os.path.exists(OBSERVATION_FILE):
            try:
                with open(OBSERVATION_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {"observations": [], "stats_by_task": {}, "stats_by_worker": {}}
    def _save(self):
        with open(OBSERVATION_FILE, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    def record(self, task_name, worker_id, model, corps, elapsed, success, 
               tokens_in=0, tokens_out=0, error_msg="", quality_score=None):
        """记录一次完整的观察"""
        entry = {
            "ts": datetime.now().isoformat(),
            "task": task_name,
            "worker_id": worker_id,
            "model": model,
            "corps": corps,
            "elapsed": round(elapsed, 2),
            "success": success,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": error_msg[:100] if error_msg else "",
            "quality": quality_score,  # Judge打的分
        }
        with self.lock:
            self.data["observations"].append(entry)
            # 只保留最近2000条
            if len(self.data["observations"]) > 2000:
                self.data["observations"] = self.data["observations"][-2000:]
            # 按任务统计
            ts = self.data["stats_by_task"]
            if task_name not in ts:
                ts[task_name] = {"total": 0, "success": 0, "avg_time": 0, "by_corps": {}}
            ts[task_name]["total"] += 1
            if success:
                ts[task_name]["success"] += 1
            old_avg = ts[task_name]["avg_time"]
            n = ts[task_name]["total"]
            ts[task_name]["avg_time"] = round(old_avg * (n-1)/n + elapsed/n, 1)
            if corps not in ts[task_name]["by_corps"]:
                ts[task_name]["by_corps"][corps] = {"total": 0, "success": 0}
            ts[task_name]["by_corps"][corps]["total"] += 1
            if success:
                ts[task_name]["by_corps"][corps]["success"] += 1
            # 按工人统计
            ws = self.data["stats_by_worker"]
            if worker_id not in ws:
                ws[worker_id] = {"total": 0, "success": 0, "avg_time": 0, "tasks": {}}
            ws[worker_id]["total"] += 1
            if success:
                ws[worker_id]["success"] += 1
            old_avg = ws[worker_id]["avg_time"]
            n = ws[worker_id]["total"]
            ws[worker_id]["avg_time"] = round(old_avg * (n-1)/n + elapsed/n, 1)
            if task_name not in ws[worker_id]["tasks"]:
                ws[worker_id]["tasks"][task_name] = 0
            ws[worker_id]["tasks"][task_name] += 1
            self._save()
        return entry
    def get_task_corps_winrate(self, task_name):
        """获取某任务各军团胜率"""
        ts = self.data.get("stats_by_task", {}).get(task_name, {}).get("by_corps", {})
        result = {}
        for corps, stats in ts.items():
            total = stats.get("total", 0)
            if total >= 3:  # 至少3次才有统计意义
                result[corps] = round(stats.get("success", 0) / total, 2)
        return result
    def report(self):
        lines = ["📊 Observation Log 汇总", "=" * 50]
        ts = self.data.get("stats_by_task", {})
        for task, stats in ts.items():
            sr = round(stats["success"]/max(1,stats["total"])*100, 0)
            lines.append(f"\n  {task}: {sr}%({stats['total']}次) avg={stats['avg_time']}s")
            for corps, cs in stats.get("by_corps", {}).items():
                csr = round(cs["success"]/max(1,cs["total"])*100, 0)
                lines.append(f"    {corps}: {csr}%({cs['total']}次)")
        return "\n".join(lines)


class TaskRouter:
    """P1: 任务路由器 — 按任务需求匹配工人画像 + O→E→C→R约束路由"""
    CONSTRAINT_FILE = os.environ.get("ROUTING_CONSTRAINTS", str(_BASE_DIR / "routing_constraints.json"))

    def __init__(self, registry=None, observation=None):
        self.registry = registry or WorkerRegistry()
        self.observation = observation or ObservationLog()
        self._constraints = self._load_constraints()

    def _load_constraints(self):
        """加载路由约束：Observation→Experience→Constraint 产物"""
        if os.path.exists(self.CONSTRAINT_FILE):
            try:
                with open(self.CONSTRAINT_FILE) as f:
                    data = json.load(f)
                index = {}
                for rule in data.get("rules", []):
                    if rule.get("action") != "AVOID":
                        continue
                    conf = rule.get("confidence", "")
                    confirmed = rule.get("confirmed_ts") is not None
                    if (conf == "HIGH" and confirmed) or (conf == "MEDIUM" and confirmed):
                        task = rule["task"]
                        worker = rule["worker"]
                        index.setdefault(task, set()).add(worker)
                return index
            except Exception:
                pass
        return {}

    def _is_constrained(self, task_name, worker_id):
        """检查某个 task→worker 组合是否被约束(Constraint→Route)"""
        avoid_set = self._constraints.get(task_name, set())
        return worker_id in avoid_set
    def match(self, task_name, top_n=5):
        """
        核心路由：task requirements → worker strengths 匹配
        返回按匹配度排序的工人列表
        """
        profile = TASK_PROFILES.get(task_name, {
            "requirements": ["fast_response"],
            "avoid": [],
            "max_latency": 120,
            "min_context": 8000,
            "strategy": "balanced",
        })
        requirements = set(profile["requirements"])
        avoid = set(profile["avoid"])

        max_latency = profile["max_latency"]
        min_context = profile["min_context"]
        candidates = []
        for wid, w in self.registry.get_alive():
            # O→E→C→R: Constraint→Route 闭环 — 跳过被约束的组合
            if self._is_constrained(task_name, wid):
                print(f"  ⛔ AVOID: {task_name}→{wid} (constraint生效)")
                continue
            score = 0
            strengths = set(w.get("strengths", []))
            weaknesses = set(w.get("weaknesses", []))
            # 匹配度：需求∩优势
            matched = requirements & strengths
            score += len(matched) * 20  # 每匹配一个+20
            # 惩罚：需求∩劣势
            penalized = requirements & weaknesses
            score -= len(penalized) * 30  # 需求匹配到弱点-30
            # 避免：avoid∩优势 降权(不需要的优势没用)
            # 不扣分，只是不加
            # 延迟惩罚
            avg_lat = w.get("avg_latency", 10)
            if avg_lat > max_latency:
                score -= 20
            elif avg_lat < max_latency * 0.3:
                score += 10  # 快于预期加分
            # 成功率加成
            sr = w.get("success_rate", 0.9)
            score += int(sr * 20)
            # 上下文窗口检查
            ctx = w.get("context_window", 32000)
            if ctx < min_context:
                score -= 50  # 上下文不够重罚
            # 军团偏好：根据历史胜率
            corps_wr = self.observation.get_task_corps_winrate(task_name)
            corps = w.get("corps", "")
            if corps in corps_wr:
                score += int(corps_wr[corps] * 15)
            # 策略权重
            strategy = profile["strategy"]
            if strategy == "speed":
                score += max(0, 20 - avg_lat)  # 越快越好
            elif strategy == "quality":
                score += len(matched) * 5  # 匹配度更重要
            candidates.append((wid, w, score))
        candidates.sort(key=lambda x: -x[2])
        return candidates[:top_n]

    def check_anti_permanent(self):
        """反永久化：检查是否有约束到了review时间"""
        try:
            from constraint_proposer import check_review_schedule, process_review
            due = check_review_schedule()
            if due:
                # 加载最近观察数据
                from constraint_proposer import load_observations
                obs = load_observations()
                for rule in due:
                    process_review(rule, obs)
                # 保存更新后的约束
                from constraint_proposer import save_constraints
                import json
                with open(os.environ.get('ROUTING_CONSTRAINTS', '/home/coze/routing_constraints.json')) as f:
                    constraints = json.load(f)
                save_constraints(constraints)
                pardoned = [r for r in constraints.get('rules', []) if r.get('review_status') == 'PARDONED']
                if pardoned:
                    print(f'🔓 反永久化：{len(pardoned)}条规则已洗白，从AVOID降级为MONITOR')
        except Exception as e:
            print(f'review检查异常(非致命): {e}')


    def get_fallback_chain(self, task_name):
        """获取任务的完整fallback链"""
        matched = self.match(task_name, top_n=10)
        if not matched:
            print(f"  ⚠️ fallback_chain为空: {task_name} (所有worker被AVOID或无可用)")
            return []
        return [(wid, w["model"]) for wid, w, score in matched]
    
    def call_worker(self, worker_id: str, messages: list, max_tokens: int = 500,
                    temperature: float = 0.7) -> dict:
        """通过 ProviderAdapter 调用工人
        
        TaskRouter 不直接知道 OneAPI 还是 LocalMiner，
        通过 ProviderAdapter 解耦，自动选择正确的 Adapter。
        """
        worker = self.registry.get_worker(worker_id)
        if not worker:
            return {"error": f"Worker {worker_id} not found", "success": False}
        
        provider_name = worker.get("provider", "local_miner")
        model = worker.get("model", "")
        
        # 获取对应的 ProviderAdapter
        adapter_class = PROVIDER_ADAPTERS.get(provider_name)
        if not adapter_class:
            return {"error": f"Provider {provider_name} not registered", "success": False}
        
        try:
            adapter = adapter_class() if provider_name != "local_miner" else adapter_class()
            if not adapter.is_available():
                return {"error": f"Provider {provider_name} not available", "success": False}
            
            result = adapter.call(model, messages, max_tokens, temperature)
            if result.get("success"):
                return {
                    "content": result.get("content", ""),
                    "model": model,
                    "provider": provider_name,
                    "worker_id": worker_id,
                    "success": True,
                }
            return {"error": result.get("error", "Unknown error"), "success": False}
        
        except Exception as e:
            return {"error": f"Call failed: {e}", "success": False}


class JudgeLayer:
    """P2: 裁判层 — 对比输出质量，积累胜率数据"""
    def __init__(self, observation=None):
        self.observation = observation or ObservationLog()
        self.lock = threading.Lock()
        self.history = self._load()
    def _load(self):
        if os.path.exists(JUDGE_FILE):
            try:
                with open(JUDGE_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {"comparisons": [], "win_rates": {}}
    def _save(self):
        with open(JUDGE_FILE, "w") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    def judge(self, task_name, output_a, worker_a, output_b, worker_b, prompt=""):
        """
        让裁判模型对比两个输出，判断谁更好
        用最快的GLM做裁判(因为只需要对比，不需要深度推理)
        """
        judge_prompt = f"""你是一个严格的质量裁判。对比以下两个AI对同一任务的输出，判断谁更好。

任务: {task_name}
原始提示词摘要: {prompt[:500]}

--- 输出A (Worker: {worker_a}) ---
{output_a[:1500]}

--- 输出B (Worker: {worker_b}) ---
{output_b[:1500]}

请严格按以下格式输出：
胜者: A 或 B 或 平局
理由: 一句话说明
质量分A: 1-10
质量分B: 1-10"""
        try:
            resp = requests.post(
                API_BASE,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "glm-4-flash",  # GLM做裁判，快+免费
                    "messages": [
                        {"role": "system", "content": "你是质量裁判。严格对比输出质量，给出公正判断。"},
                        {"role": "user", "content": judge_prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.1
                },
                timeout=30
            )
            data = resp.json()
            if "choices" in data:
                result_text = data["choices"][0]["message"]["content"]
                # 解析结果
                winner = "平局"
                reason = ""
                qa, qb = 5, 5
                for line in result_text.split("\n"):
                    if "胜者" in line:
                        if "A" in line and "B" not in line:
                            winner = "A"
                        elif "B" in line and "A" not in line:
                            winner = "B"
                    elif "理由" in line:
                        reason = line.split(":", 1)[-1].strip() if ":" in line else line
                    elif "质量分A" in line:
                        try:
                            qa = int(''.join(c for c in line if c.isdigit()) or "5")
                        except:
                            pass
                    elif "质量分B" in line:
                        try:
                            qb = int(''.join(c for c in line if c.isdigit()) or "5")
                        except:
                            pass
                # 记录
                entry = {
                    "ts": datetime.now().isoformat(),
                    "task": task_name,
                    "worker_a": worker_a,
                    "worker_b": worker_b,
                    "winner": winner,
                    "reason": reason,
                    "quality_a": qa,
                    "quality_b": qb
                }
                with self.lock:
                    self.history["comparisons"].append(entry)
                    if len(self.history["comparisons"]) > 500:
                        self.history["comparisons"] = self.history["comparisons"][-500:]
                    # 更新胜率
                    wr = self.history["win_rates"]
                    if task_name not in wr:
                        wr[task_name] = {}
                    for wk in [worker_a, worker_b]:
                        if wk not in wr[task_name]:
                            wr[task_name][wk] = {"wins": 0, "losses": 0, "draws": 0}
                    if winner == "A":
                        wr[task_name][worker_a]["wins"] += 1
                        wr[task_name][worker_b]["losses"] += 1
                    elif winner == "B":
                        wr[task_name][worker_b]["wins"] += 1
                        wr[task_name][worker_a]["losses"] += 1
                    else:
                        wr[task_name][worker_a]["draws"] += 1
                        wr[task_name][worker_b]["draws"] += 1
                    self._save()
                return entry
        except Exception as e:
            return {"error": str(e)[:100], "winner": "error"}
        return {"winner": "unknown"}
    def get_worker_winrate(self, task_name, worker_id):
        """获取某工人在某任务的胜率"""
        wr = self.history.get("win_rates", {}).get(task_name, {}).get(worker_id, {})
        total = wr.get("wins", 0) + wr.get("losses", 0) + wr.get("draws", 0)
        if total == 0:
            return None
        return round(wr.get("wins", 0) / total, 2)
    def report(self):
        lines = ["⚖️ Judge Layer 胜率报告", "=" * 50]
        wr = self.history.get("win_rates", {})
        for task, workers in wr.items():
            lines.append(f"\n  {task}:")
            for wid, stats in sorted(workers.items(), key=lambda x: -(x[1].get("wins",0))):
                total = stats.get("wins",0) + stats.get("losses",0) + stats.get("draws",0)
                if total > 0:
                    wr_pct = round(stats.get("wins",0)/total*100)
                    lines.append(f"    {wid}: {wr_pct}%胜({total}场)")
        total_comparisons = len(self.history.get("comparisons", []))
        lines.append(f"\n  总对比次数: {total_comparisons}")
        return "\n".join(lines)


# ==================== 便捷接口 ====================
# 全局实例
registry = WorkerRegistry()
observation = ObservationLog()
router = TaskRouter(registry, observation)
judge = JudgeLayer(observation)

if __name__ == "__main__":
    print(registry.report())
    print("\n" + observation.report())
    # 测试任务路由
    print("\n🎯 任务路由测试:")
    for task in TASK_PROFILES:
        matched = router.match(task, top_n=3)
        print(f"\n  {task}:")
        for wid, w, score in matched:
            print(f"    {wid} ({w['corps']}) score={score} strengths={w.get('strengths',[])}")
    print("\n" + judge.report())
