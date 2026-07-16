#!/usr/bin/env python3
"""
Daily Runner — 荐股系统每日自动化执行器

无人干预执行流程：
  1. 更新历史推荐表现（PerformanceTracker.update_all）
  2. 运行荐股引擎（StockAdvisor.run）
  3. 推送报告到 Telegram（受 Publication Gate 质量门槛控制）
  4. 检查是否需要触发优化
  5. 更新 CURRENT_STATE.md 健康度
  6. 推送运营者每日摘要（不受 Publication Gate 限制）

容错特性：
  - 每步独立错误处理，不中断整体流程
  - 完整的日志记录
  - 失败重试机制
  - 运行状态持久化
  - 进程锁（防止多实例互踩）
  - 心跳文件（每30s写一次，被kill也能定位卡点）
  - 每步前后写入 status 标记（被kill能从状态文件定位卡点）

用法:
  python daily_runner.py           # 立即执行
  python daily_runner.py --schedule  # 注册为 Windows 定时任务
  python daily_runner.py --check    # 检查上次运行状态
  python daily_runner.py --force    # 强制执行（忽略进程锁）
"""

import os
import sys
import json
import subprocess
import argparse
import time
import traceback
import signal
import atexit
import threading
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(__file__).parent.parent.parent
ADVISOR_DIR = WORKSPACE / "05_TOOLS" / "advisor"
MINER_DIR = WORKSPACE / "05_TOOLS" / "miner"

sys.path.insert(0, str(ADVISOR_DIR))

# 加载 .env 文件（如果存在）
_env_file = WORKSPACE / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key not in os.environ:
                os.environ[_key] = _val

LOG_FILE = ADVISOR_DIR.parent / "mine_output" / "advisor" / "daily_runner.log"
STATUS_FILE = ADVISOR_DIR.parent / "mine_output" / "advisor" / "runner_status.json"
HEARTBEAT_FILE = ADVISOR_DIR.parent / "mine_output" / "advisor" / "runner_heartbeat.json"
LOCK_FILE = ADVISOR_DIR.parent / "mine_output" / "advisor" / "runner.lock"


class RunnerLogger:
    """运行日志记录器"""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        print(log_line.strip())
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)


class RunnerStatus:
    """运行状态管理器
    
    新增字段：
    - run_completed: 是否跑完了完整流程（区别于 step1_ok 这种单步状态）
    - last_completed_time: 上次完整跑完的时间
    - current_step: 当前执行到哪一步（被kill后能定位卡点）
    - step_timings: 每步耗时
    """
    
    def __init__(self, status_file: Path):
        self.status_file = status_file
        self.status = self._load_status()
    
    def _load_status(self) -> dict:
        """加载状态文件"""
        if self.status_file.exists():
            try:
                return json.loads(self.status_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {
            "last_run_time": "",
            "last_run_success": False,
            "run_completed": False,
            "last_completed_time": "",
            "current_step": "",
            "steps": {},
            "step_timings": {},
            "error_message": "",
            "health_score": 0,
            "recommendations": [],
        }
    
    def save_status(self, success: bool, steps: dict = None,
                    error_message: str = "", health_score: int = 0,
                    recommendations: list = None, current_step: str = "",
                    run_completed: bool = False, step_timings: dict = None):
        """保存状态 + 归档历史快照"""
        now = datetime.now().isoformat()
        prev = self.status or {}
        self.status = {
            "last_run_time": now,
            "last_run_success": success,
            "run_completed": run_completed,
            "last_completed_time": now if run_completed else prev.get("last_completed_time", ""),
            "current_step": current_step,
            "steps": steps or {},
            "step_timings": step_timings or {},
            "error_message": error_message,
            "health_score": health_score,
            "recommendations": recommendations or [],
        }
        self.status_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=2), encoding='utf-8')

        # 归档历史快照（便于回溯"哪次跑完、哪次死掉"）
        try:
            archive_dir = self.status_file.parent / "status_archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = archive_dir / f"runner_status_{ts}.json"
            archive_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=2), encoding='utf-8')

            # 只保留最近 30 份快照，避免磁盘膨胀
            all_snapshots = sorted(archive_dir.glob("runner_status_*.json"))
            if len(all_snapshots) > 30:
                for old in all_snapshots[:-30]:
                    old.unlink(missing_ok=True)
        except Exception:
            pass
    
    def update_step(self, step_name: str, status: str, error: str = ""):
        """增量更新单步状态（用于在每步前后写入，便于 kill 后定位卡点）"""
        prev = self.status or {}
        prev_steps = prev.get("steps", {})
        prev_steps[step_name] = status
        prev["steps"] = prev_steps
        prev["current_step"] = step_name
        if error:
            prev["error_message"] = error
        prev["last_run_time"] = datetime.now().isoformat()
        self.status = prev
        try:
            self.status_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
    
    def get_status(self) -> dict:
        """获取状态"""
        return self.status.copy()


class HeartbeatWriter:
    """心跳写入器：每30s更新一次，被kill后能定位卡在哪一步"""
    
    def __init__(self, hb_file: Path):
        self.hb_file = hb_file
        self.hb_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_step = "init"
        self._stop_event = threading.Event()
        self._thread = None
    
    def start(self):
        """启动心跳线程"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止心跳线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
    
    def set_step(self, step: str):
        """设置当前步骤"""
        self.current_step = step
        self._write()
    
    def _run(self):
        """心跳线程主循环"""
        while not self._stop_event.is_set():
            self._write()
            self._stop_event.wait(30)
    
    def _write(self):
        """写入心跳文件"""
        try:
            data = {
                "pid": os.getpid(),
                "step": self.current_step,
                "last_beat": datetime.now().isoformat(),
            }
            self.hb_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass


class ProcessLock:
    """进程锁：防止多个 daily_runner 实例同时运行"""
    
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid = os.getpid()
    
    def acquire(self) -> bool:
        """获取锁。如果已有其他实例在跑，返回 False。"""
        if self.lock_file.exists():
            try:
                existing = json.loads(self.lock_file.read_text(encoding='utf-8'))
                existing_pid = existing.get("pid", 0)
                existing_step = existing.get("step", "unknown")
                existing_start = existing.get("started_at", "")
                
                # 检查进程是否还在
                if self._is_pid_alive(existing_pid):
                    print(f"[LOCK] 已有进程在运行: PID={existing_pid}, step={existing_step}, started={existing_start}")
                    print(f"[LOCK] 当前进程 {self.pid} 退出，避免互踩")
                    return False
                else:
                    print(f"[LOCK] 旧锁文件存在但 PID={existing_pid} 已死，清除旧锁")
                    self.lock_file.unlink(missing_ok=True)
            except Exception:
                # 锁文件损坏，清除
                self.lock_file.unlink(missing_ok=True)
        
        # 写新锁
        lock_data = {
            "pid": self.pid,
            "step": "starting",
            "started_at": datetime.now().isoformat(),
        }
        self.lock_file.write_text(json.dumps(lock_data, ensure_ascii=False, indent=2), encoding='utf-8')
        return True
    
    def release(self):
        """释放锁"""
        try:
            if self.lock_file.exists():
                existing = json.loads(self.lock_file.read_text(encoding='utf-8'))
                if existing.get("pid") == self.pid:
                    self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass
    
    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """检查 PID 是否还活着（Windows）"""
        if pid <= 0:
            return False
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle == 0:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
        return False


def run_performance_update(logger: RunnerLogger, status_manager: RunnerStatus) -> bool:
    """更新历史推荐表现（直接调用，不走subprocess，避免环境变量继承和超时问题）"""
    logger.log("[1/6] 更新历史表现数据...")
    status_manager.update_step("performance_update", "running")
    
    try:
        from performance_tracker import PerformanceTracker
        
        tracker = PerformanceTracker()
        tracker.update_all()
        logger.log("  ✓ 表现数据更新完成")
        status_manager.update_step("performance_update", "success")
        return True
    except Exception as e:
        logger.log(f"  ✗ 更新异常: {e}", "ERROR")
        logger.log(f"  异常详情: {traceback.format_exc()[:500]}", "DEBUG")
        status_manager.update_step("performance_update", "failed", error=str(e))
        return False


def run_stock_advisor(logger: RunnerLogger, status_manager: RunnerStatus) -> tuple[bool, list]:
    """运行荐股引擎"""
    logger.log("[2/6] 运行荐股引擎...")
    status_manager.update_step("stock_advisor", "running")
    
    recommendations = []
    
    try:
        from stock_advisor import StockAdvisor
        advisor = StockAdvisor()
        success, report = advisor.run()
        
        if success:
            logger.log("  ✓ 荐股引擎执行成功")
            
            # 提取推荐股票信息
            import re
            for match in re.finditer(r'推荐\d+：([^（]+)（(\d{6})）', report[:2000]):
                recommendations.append({
                    "name": match.group(1),
                    "code": match.group(2),
                })
            
            rec_str = ', '.join([f"{r['name']}({r['code']})" for r in recommendations])
            logger.log(f"  推荐结果: {rec_str}")
            status_manager.update_step("stock_advisor", "success")
            return True, recommendations
        else:
            logger.log(f"  ⚠ 荐股引擎执行完成但结果不完整", "WARNING")
            status_manager.update_step("stock_advisor", "partial")
            return False, recommendations
    
    except Exception as e:
        logger.log(f"  ✗ 荐股引擎异常: {e}", "ERROR")
        logger.log(f"  异常详情: {traceback.format_exc()[:500]}", "DEBUG")
        status_manager.update_step("stock_advisor", "failed", error=str(e))
        return False, recommendations


def push_to_telegram(logger: RunnerLogger, status_manager: RunnerStatus,
                     recommendations: list = None) -> bool:
    """推送报告到 Telegram（直接调用，不走 subprocess，避免超时/重复执行）"""
    logger.log("[3/6] 推送 Telegram...")
    status_manager.update_step("telegram_push", "running")

    try:
        sys.path.insert(0, str(WORKSPACE / "06_RUNTIME" / "connectors"))
        from tg_pusher import TGPusher

        # 优先读取当天生成的报告文件
        today_str = datetime.now().strftime("%Y%m%d")
        report_paths = [
            WORKSPACE / "mine_output" / "advisor" / f"advisor_{today_str}.md",
            WORKSPACE / "05_TOOLS" / "mine_output" / "advisor" / f"advisor_{today_str}.md",
        ]
        report_text = ""
        for rp in report_paths:
            if rp.exists():
                report_text = rp.read_text(encoding="utf-8")[:3000]
                break

        # 如果报告文件不存在，用已有推荐生成简要摘要
        if not report_text and recommendations:
            rec_lines = "\n".join([f"- {r['name']} ({r['code']})" for r in recommendations])
            report_text = f"今日推荐:\n{rec_lines}\n\n(详细报告生成中)"

        if not report_text:
            logger.log("  ⚠ 无报告内容可推送", "WARNING")
            status_manager.update_step("telegram_push", "skipped", error="no report content")
            return False

        if len(report_text) > 3000:
            report_text += "\n\n... (报告过长，完整内容请查看文件)"

        chat_id = os.environ.get("TG_CHAT_ID", "5016609451")
        pusher = TGPusher(chat_id=chat_id)
        result = pusher.send_message(report_text, parse_mode="HTML")

        if result.get("ok"):
            logger.log("  ✓ TG 推送完成")
            status_manager.update_step("telegram_push", "success")
            return True
        else:
            err_msg = result.get('error', '未知错误')
            logger.log(f"  ⚠ TG 推送失败: {err_msg}", "WARNING")
            status_manager.update_step("telegram_push", "failed", error=err_msg)
            return False
    except Exception as e:
        logger.log(f"  ⚠ TG 推送异常: {e}", "WARNING")
        status_manager.update_step("telegram_push", "failed", error=str(e))
        return False


def push_operator_summary(logger: RunnerLogger, status_manager: RunnerStatus,
                          recommendations: list, health_score: int, gate_result: dict) -> bool:
    """推送运营者摘要到 Telegram（不受 Publication Gate 质量门槛限制）"""
    logger.log("[6/6] 推送运营者摘要...")
    status_manager.update_step("operator_summary", "running")
    
    try:
        sys.path.insert(0, str(WORKSPACE / "06_RUNTIME" / "connectors"))
        from tg_pusher import TGPusher
        
        operator_chat_id = os.environ.get("TG_CHAT_ID", "5016609451")
        pusher = TGPusher(chat_id=operator_chat_id)
        
        rec_str = ', '.join([f"{r['name']}({r['code']})" for r in recommendations]) if recommendations else "无"
        
        gate_level = gate_result.get("route_level", "UNKNOWN")
        gate_name = gate_result.get("route_name", "未知")
        gate_allowed = gate_result.get("allow_publication", False)
        
        if gate_allowed:
            gate_status = "✅ Public档，已推送客户"
        elif gate_result.get("allow_internal_push", False):
            gate_status = "🔵 Internal/Research档，内部验证推送"
        else:
            gate_status = "❌ Discard档，已废弃"
        
        gate_reason = gate_result.get("description", "")
        if gate_level in ("RESEARCH", "INTERNAL"):
            gate_reason = f"健康度{health_score}/100 < 70门槛"
        elif gate_level == "DISCARD":
            gate_reason = "健康度低于30，直接废弃"
        
        summary = (
            f"📊 <b>ACE 荐股系统每日摘要</b>\n"
            f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"<b>推荐股票:</b>\n"
            f"{rec_str}\n\n"
            f"<b>健康度:</b> {health_score}/100\n\n"
            f"<b>Gate路由:</b> {gate_level} ({gate_name})\n"
            f"<b>推送状态:</b> {gate_status}\n"
            f"<b>原因:</b> {gate_reason}"
        )
        
        result = pusher.send_message(summary, parse_mode="HTML")
        
        if result.get("ok"):
            logger.log("  ✓ 运营者摘要推送完成")
            status_manager.update_step("operator_summary", "success")
            return True
        else:
            err_msg = result.get('error', '')
            logger.log(f"  ⚠ 运营者摘要推送失败: {err_msg}", "WARNING")
            status_manager.update_step("operator_summary", "failed", error=err_msg)
            return False
    
    except Exception as e:
        logger.log(f"  ⚠ 运营者摘要推送异常: {e}", "WARNING")
        status_manager.update_step("operator_summary", "failed", error=str(e))
        return False


def check_and_optimize(logger: RunnerLogger, status_manager: RunnerStatus) -> tuple[bool, int]:
    """检查是否需要触发优化"""
    logger.log("[4/6] 检查优化需求...")
    status_manager.update_step("optimization_check", "running")
    
    try:
        from performance_tracker import PerformanceTracker
        from adaptive_scorer import AdaptiveScorer
        
        tracker = PerformanceTracker()
        scorer = AdaptiveScorer()
        
        health = scorer.get_health_score(tracker)
        health_score = health.get('score', 0)
        
        if scorer.should_trigger_optimization(tracker, consecutive_losses_threshold=3):
            logger.log(f"  ⚠ 触发因子优化，正在生成分析报告...", "WARNING")
            logger.log(f"  当前健康度: {health_score}/100 ({health.get('status', 'unknown')})")
            status_manager.update_step("optimization_check", "triggered")
            return True, health_score
        else:
            logger.log(f"  ✓ 表现正常，健康度: {health_score}/100")
            status_manager.update_step("optimization_check", "success")
            return False, health_score
    
    except Exception as e:
        logger.log(f"  ⚠ 优化检查异常: {e}", "WARNING")
        status_manager.update_step("optimization_check", "failed", error=str(e))
        return False, 0


def update_current_state(logger: RunnerLogger, status_manager: RunnerStatus) -> bool:
    """更新 CURRENT_STATE.md"""
    logger.log("[5/6] 更新系统状态...")
    status_manager.update_step("state_update", "running")
    
    try:
        from performance_tracker import PerformanceTracker
        from adaptive_scorer import AdaptiveScorer
        
        tracker = PerformanceTracker()
        scorer = AdaptiveScorer()
        health = scorer.get_health_score(tracker)
        
        state_file = WORKSPACE / 'CURRENT_STATE.md'
        if state_file.exists():
            content = state_file.read_text(encoding='utf-8')
            
            health_section = f"""## 荐股系统健康度

> 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

- **健康度评分**: {health.get('score', 50)}/100 ({health.get('status', 'unknown')})
- **最近30天推荐次数**: {health.get('summary', {}).get('total_recommendations', 0)}
- **T+5胜率**: {health.get('summary', {}).get('win_rates', {}).get('T+5', 'N/A')}%
- **T+5平均收益**: {health.get('summary', {}).get('avg_returns', {}).get('T+5', 'N/A')}%

"""
            
            import re
            if '## 荐股系统健康度' in content:
                pattern = r'## 荐股系统健康度\n.*?(?=\n## |\Z)'
                content = re.sub(pattern, health_section.strip(), content, flags=re.DOTALL)
            else:
                content = content.rstrip() + '\n\n' + health_section
            
            state_file.write_text(content, encoding='utf-8')
            logger.log("  ✓ CURRENT_STATE.md 更新完成")
            status_manager.update_step("state_update", "success")
        else:
            logger.log("  ⚠ CURRENT_STATE.md 不存在", "WARNING")
            status_manager.update_step("state_update", "skipped", error="file not found")
        
        return True
    
    except Exception as e:
        logger.log(f"  ⚠ 更新 CURRENT_STATE 失败: {e}", "WARNING")
        status_manager.update_step("state_update", "failed", error=str(e))
        return False


def force_optimization(logger: RunnerLogger) -> bool:
    """强制触发因子优化（熔断时调用）"""
    logger.log("[F] 强制触发因子优化...")
    
    try:
        from performance_tracker import PerformanceTracker
        from adaptive_scorer import AdaptiveScorer
        
        tracker = PerformanceTracker()
        scorer = AdaptiveScorer()
        
        # 执行自适应调整
        adjusted, adjustments = scorer.analyze_and_adjust(tracker)
        
        if adjusted:
            logger.log(f"  ✓ 权重调整完成: {len(adjustments)} 个因子")
        else:
            logger.log(f"  ⚠ 权重调整未触发，可能样本不足")
        
        # 生成优化任务
        task = scorer.generate_optimization_task(tracker)
        
        # 保存优化任务
        task_dir = ADVISOR_DIR.parent / "mine_output" / "advisor" / "optimization_tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_file = task_dir / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        task_file.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
        
        logger.log(f"  ✓ 优化任务已保存: {task_file.name}")
        return True
    
    except Exception as e:
        logger.log(f"  ✗ 强制优化失败: {e}", "ERROR")
        return False


def run_all(logger: RunnerLogger, status_manager: RunnerStatus):
    """执行完整流程"""
    logger.log("=" * 60)
    logger.log(f"每日荐股自动化执行器启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (PID={os.getpid()})")
    logger.log("=" * 60)
    
    # 启动心跳
    heartbeat = HeartbeatWriter(HEARTBEAT_FILE)
    heartbeat.start()
    heartbeat.set_step("init")
    
    # 记录事件
    try:
        from daily_event_logger import DailyEventLogger
        evt_logger = DailyEventLogger()
        evt_logger.log("DAILY_RUN_START", f"每日荐股自动化执行开始 (PID={os.getpid()})")
    except Exception:
        evt_logger = None
    
    start_time = time.time()
    steps = {}
    step_timings = {}
    recommendations = []
    health_score = 0
    success = True
    gate_result = {}
    run_completed = False
    
    try:
        # 1. 更新历史表现（直接调用，避免subprocess超时/环境变量问题）
        heartbeat.set_step("1_update_performance")
        t0 = time.time()
        step1_ok = run_performance_update(logger, status_manager)
        step_timings["performance_update"] = round(time.time() - t0, 1)
        steps["performance_update"] = step1_ok
        if evt_logger:
            evt_logger.log("PERF_UPDATE", f"历史表现数据更新完成 ({step_timings['performance_update']}s)", 
                          {"success": step1_ok, "elapsed_s": step_timings['performance_update']})
        
        # 2. 运行荐股引擎
        heartbeat.set_step("2_run_advisor")
        t0 = time.time()
        step2_ok, recs = run_stock_advisor(logger, status_manager)
        step_timings["stock_advisor"] = round(time.time() - t0, 1)
        steps["stock_advisor"] = step2_ok
        recommendations = recs
        if evt_logger:
            rec_str = ', '.join([f"{r['name']}({r['code']})" for r in recs])
            evt_logger.log("RECOMMEND", f"荐股引擎执行完成: {rec_str}", 
                          {"success": step2_ok, "count": len(recs), "elapsed_s": step_timings['stock_advisor']})
        
        # 3. Publication Gate：根据健康度决定发布路由
        heartbeat.set_step("3_publication_gate")
        t0 = time.time()
        try:
            sys.path.insert(0, str(WORKSPACE / "04_PROTOCOLS"))
            from publication_gate import PublicationGate

            # 先计算真实健康度，供 Gate 使用（之前用默认值 45 导致路由误判）
            try:
                from performance_tracker import PerformanceTracker
                from adaptive_scorer import AdaptiveScorer
                _tracker = PerformanceTracker()
                _scorer = AdaptiveScorer()
                _health = _scorer.get_health_score(_tracker)
                health_score = _health.get('score', 0)
            except Exception as e:
                logger.log(f"  ⚠ 健康度计算失败，使用默认值 45: {e}", "WARNING")
                health_score = 45

            gate = PublicationGate()

            gate_result = gate.route(health_score, {
                "recommendations": [r['code'] for r in recs],
                "strategy": "POLICY-002",
            })
            
            logger.log(f"  Publication Gate: {gate_result['route_name']} ({gate_result['route_level']})")
            logger.log(f"  健康度: {health_score}/100")
            logger.log(f"  allow_publication: {gate_result.get('allow_publication', False)}")
            logger.log(f"  allow_internal_push: {gate_result.get('allow_internal_push', False)}")
            
            if gate_result.get("allow_publication", False):
                step3_ok = push_to_telegram(logger, status_manager, recommendations)
                logger.log("  ✓ Publication Gate 通过，已推送客户")
            elif gate_result.get("allow_internal_push", False):
                step3_ok = push_to_telegram(logger, status_manager, recommendations)
                logger.log("  ✓ 内部推送允许，已推送至TG（内部验证）")
            else:
                step3_ok = False
                logger.log(f"  ⚠ Publication Gate 拦截：{gate_result['description']}")
                if gate_result["allow_learning"]:
                    logger.log("  ✓ 推荐结果进入 Learning 流程")
                else:
                    logger.log("  ✗ 推荐结果 Discard，不进入 Learning")
                # 健康度不达标时触发优化
                force_optimization(logger)
            steps["telegram_push"] = step3_ok
            if evt_logger:
                evt_logger.log("TG_PUSH", "Telegram推送完成", {
                    "success": step3_ok, 
                    "gate_level": gate_result["route_level"],
                    "allow_publication": gate_result["allow_publication"],
                    "allow_learning": gate_result["allow_learning"]
                })
        except Exception as e:
            logger.log(f"  ✗ Publication Gate 异常: {e}", "ERROR")
            status_manager.update_step("publication_gate", "failed", error=str(e))
            steps["telegram_push"] = False
        
        step_timings["publication_gate"] = round(time.time() - t0, 1)
        
        # 4. 检查优化
        heartbeat.set_step("4_check_optimize")
        t0 = time.time()
        step4_ok, hs = check_and_optimize(logger, status_manager)
        step_timings["optimization_check"] = round(time.time() - t0, 1)
        steps["optimization_check"] = step4_ok
        health_score = hs
        if evt_logger:
            evt_logger.log("OPTIMIZE_CHECK", f"优化检查完成，健康度: {hs}/100", 
                          {"triggered": step4_ok, "health_score": hs, "elapsed_s": step_timings['optimization_check']})
        
        # 5. 更新状态
        heartbeat.set_step("5_update_state")
        t0 = time.time()
        step5_ok = update_current_state(logger, status_manager)
        step_timings["state_update"] = round(time.time() - t0, 1)
        steps["state_update"] = step5_ok
        
        # 6. 推送运营者摘要（不受 Publication Gate 质量门槛限制）
        heartbeat.set_step("6_push_summary")
        t0 = time.time()
        push_operator_summary(logger, status_manager, recommendations, health_score, gate_result)
        step_timings["operator_summary"] = round(time.time() - t0, 1)
        
        # 整体成功判断
        success = step2_ok  # 荐股引擎成功是关键
        run_completed = True  # 跑完所有步骤
        
    except Exception as e:
        success = False
        run_completed = False
        logger.log(f"  ✗ 执行流程异常: {e}", "ERROR")
        logger.log(f"  异常详情: {traceback.format_exc()[:500]}", "DEBUG")
        if evt_logger:
            evt_logger.log("ERROR", f"执行流程异常: {e}", {"error": str(e)})
        
        # 即使流程异常，也推送运营者摘要（记录失败状态）
        if not gate_result:
            gate_result = {"route_level": "ERROR", "route_name": "执行异常", "allow_publication": False, "allow_internal_push": False}
        try:
            push_operator_summary(logger, status_manager, recommendations, health_score, gate_result)
        except Exception:
            pass
    
    elapsed = time.time() - start_time
    logger.log(f"\n{'='*60}")
    logger.log(f"执行完成，耗时 {elapsed:.1f} 秒")
    logger.log(f"整体状态: {'✓ 成功' if success else '✗ 失败'}")
    logger.log(f"跑完标记: {'✓ 完整跑完' if run_completed else '✗ 未跑完'}")
    logger.log(f"健康度: {health_score}/100")
    if step_timings:
        logger.log(f"步骤耗时: {step_timings}")
    final_rec_str = ', '.join([f"{r['name']}({r['code']})" for r in recommendations])
    logger.log(f"推荐结果: {final_rec_str}")
    logger.log(f"{'='*60}")
    
    if evt_logger:
        evt_logger.log("DAILY_RUN_END", f"每日荐股执行完成，耗时 {elapsed:.1f}s", {
            "success": success,
            "run_completed": run_completed,
            "health_score": health_score,
            "elapsed_seconds": round(elapsed, 1),
            "step_timings": step_timings,
            "recommendations": [r['code'] for r in recommendations]
        })
    
    # 停止心跳
    heartbeat.stop()
    
    # 保存状态
    status_manager.save_status(
        success=success,
        steps=steps,
        health_score=health_score,
        recommendations=recommendations,
        current_step="completed" if run_completed else "failed",
        run_completed=run_completed,
        step_timings=step_timings,
    )


def schedule_task():
    """注册 Windows 定时任务（工作日 9:20 执行）"""
    print("注册 Windows 定时任务...")
    
    task_name = "ACE_StockAdvisor_Daily"
    script_path = Path(__file__).resolve()
    python_path = sys.executable
    
    cmd = (
        f'schtasks /create /tn "{task_name}" '
        f'/tr "\\"{python_path}\" \\"{script_path}\"" '
        f'/sc weekly /d MON,TUE,WED,THU,FRI /st 09:20 '
        f'/f /ru SYSTEM'
    )
    
    print(f"\n命令: {cmd}")
    print("\n请手动以管理员身份运行以下命令:")
    print(cmd)
    print("\n或者使用 Windows Task Scheduler GUI 创建任务:")
    print(f"  程序: {python_path}")
    print(f"  参数: {script_path}")
    print(f"  触发器: 每周一~五 9:20")
    print(f"  运行身份: SYSTEM（避免用户登录问题）")


def check_status():
    """检查上次运行状态"""
    status_manager = RunnerStatus(STATUS_FILE)
    status = status_manager.get_status()
    
    print("\n上次运行状态:")
    print(f"  时间: {status.get('last_run_time', '未运行')}")
    print(f"  结果: {'✓ 成功' if status.get('last_run_success') else '✗ 失败'}")
    print(f"  完整跑完: {'✓ 是' if status.get('run_completed') else '✗ 否'}")
    print(f"  上次完成: {status.get('last_completed_time', '从未完成')}")
    print(f"  当前步骤: {status.get('current_step', '未知')}")
    print(f"  健康度: {status.get('health_score', 0)}/100")
    
    if status.get('error_message'):
        print(f"  错误: {status['error_message']}")
    
    if status.get('recommendations'):
        recs = status['recommendations']
        rec_display = ', '.join([f"{r['name']}({r['code']})" for r in recs])
        print(f"  推荐: {rec_display}")
    
    if status.get('steps'):
        print("\n  步骤详情:")
        for step, ok in status['steps'].items():
            if ok is True or ok == 'success':
                mark = '✓'
            elif ok in ('partial', 'skipped'):
                mark = '⚠'
            else:
                mark = '✗'
            print(f"    {mark} {step}: {ok}")
    
    if status.get('step_timings'):
        print("\n  步骤耗时:")
        for step, t in status['step_timings'].items():
            print(f"    {step}: {t}s")


def main():
    parser = argparse.ArgumentParser(description="Stock Advisor Daily Runner")
    parser.add_argument("--schedule", action="store_true", help="Show schedule command")
    parser.add_argument("--check", action="store_true", help="Check last run status")
    parser.add_argument("--force", action="store_true", help="Force run even if another instance is running")
    args = parser.parse_args()
    
    logger = RunnerLogger(LOG_FILE)
    
    try:
        sys.path.insert(0, str(WORKSPACE / "05_TOOLS"))
        from secret_syncer import sync_secrets
        sync_result = sync_secrets(WORKSPACE)
        if sync_result.get("synced"):
            logger.log(f"🔐 密钥同步完成: {sync_result.get('changes')}", "INFO")
        else:
            logger.log(f"🔐 密钥状态一致: {sync_result.get('reason')}", "INFO")
    except Exception as e:
        logger.log(f"🔐 密钥同步检查跳过: {e}", "WARNING")
    
    try:
        sys.path.insert(0, str(WORKSPACE / "04_PROTOCOLS"))
        from provider_consistency_check import check_consistency
        cc_result = check_consistency()
        if cc_result["pass"]:
            logger.log("✅ Provider注册一致性检查通过", "INFO")
        else:
            logger.log(f"⚠ Provider注册不一致 ({len(cc_result['issues'])}项): {', '.join(cc_result['issues'][:3])}", "WARNING")
    except Exception as e:
        logger.log(f"⚠ Provider一致性检查跳过: {e}", "WARNING")
    
    status_manager = RunnerStatus(STATUS_FILE)
    
    if args.schedule:
        schedule_task()
    elif args.check:
        check_status()
    else:
        # 获取进程锁，防止多实例互踩
        lock = ProcessLock(LOCK_FILE)
        if not lock.acquire() and not args.force:
            logger.log("已有其他 daily_runner 实例在运行，本次退出", "WARNING")
            sys.exit(2)
        
        # 注册退出时释放锁
        atexit.register(lock.release)
        # 注册信号处理
        try:
            signal.signal(signal.SIGTERM, lambda s, f: lock.release())
            signal.signal(signal.SIGINT, lambda s, f: lock.release())
        except Exception:
            pass
        
        try:
            run_all(logger, status_manager)
        finally:
            lock.release()


if __name__ == "__main__":
    main()
