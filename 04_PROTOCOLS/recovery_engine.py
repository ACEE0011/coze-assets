#!/usr/bin/env python3
"""
REC-002: Recovery Engine — 完整恢复引擎
==========================================

OPS-004 (Recovery First): Awaken → Recovery Engine → Environment → Heartbeat

Recovery Engine 把 Recovery Scanner (REC-001) + Session Validator 升级为
一个完整的多资产恢复引擎，覆盖：

  ├── Session Recovery   — Telethon/Pyrogram Session 文件 + auth_key 验证
  ├── Memory Recovery    — 记忆索引、experience、questions
  ├── Config Recovery    — api_id/api_hash、StringSession、Provider 配置
  ├── ZIP Recovery       — 归档中的 session/config 文件
  ├── Snapshot Recovery  — R1 快照中的资产
  ├── GitHub Recovery    — 本地克隆的 GitHub 仓库中的资产
  ├── Repository Recovery — Git 历史中的资产
  └── Runtime Recovery   — 运行时状态（heartbeat 记录、provider health）

执行流程:
  1. Scan   — 扫描所有资产（复用 RecoveryScanner）
  2. Validate — 对 Session 做真实连接验证
  3. Report — 生成恢复报告
  4. Update State — 更新 CURRENT_STATE.md 中的 Runtime Status

输出:
  02_MEMORY/recovery/recovery_engine_YYYYMMDD.json
  02_MEMORY/recovery/recovery_engine_YYYYMMDD.md

集成:
  - Awaken.py 启动时调用
  - Heartbeat 可定期调用（每天一次）
"""
import os, sys, json, asyncio, argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))
from recovery_scanner import RecoveryScanner

WORKSPACE = Path(__file__).parent.parent
RECOVERY_DIR = WORKSPACE / "02_MEMORY" / "recovery"
RECOVERY_DIR.mkdir(parents=True, exist_ok=True)


class SessionValidator:
    """验证 Telethon Session 是否仍然有效"""

    def __init__(self):
        self.api_id, self.api_hash = self._load_credentials()

    def _load_credentials(self):
        """Load api_id and api_hash from miner_env.sh"""
        env_file = WORKSPACE / "05_TOOLS" / "miner" / "miner_env.sh"
        api_id = os.environ.get("TG_API_ID", "")
        api_hash = os.environ.get("TG_API_HASH", "")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("export TG_API_ID="):
                    api_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("export TG_API_HASH="):
                    api_hash = line.split("=", 1)[1].strip().strip('"').strip("'")
        return api_id, api_hash

    async def validate(self, session_path: str) -> Dict[str, Any]:
        """Validate a single session file via real MTProto connection"""
        from telethon import TelegramClient
        from telethon.errors import (
            AuthKeyUnregisteredError, AuthKeyDuplicatedError,
            SessionRevokedError, UserDeactivatedError, FloodWaitError,
        )

        session_name = Path(session_path).stem
        session_dir = str(Path(session_path).parent)
        session_base = Path(session_path).stem

        result = {
            "session": session_name,
            "path": session_path,
            "timestamp": datetime.now().isoformat(),
        }

        client = TelegramClient(
            str(Path(session_dir) / session_base),
            int(self.api_id),
            self.api_hash,
        )

        try:
            await client.connect()
            if not client.is_connected():
                result["status"] = "connection_failed"
                result["need_login"] = True
                return result

            authorized = await client.is_user_authorized()
            if not authorized:
                result["status"] = "not_authorized"
                result["need_login"] = True
                await client.disconnect()
                return result

            try:
                me = await client.get_me()
                if me:
                    result["status"] = "alive"
                    result["need_login"] = False
                    result["can_push"] = True
                    result["user"] = {
                        "id": me.id,
                        "username": me.username,
                        "phone": me.phone,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                        "is_bot": me.bot,
                    }
                else:
                    result["status"] = "no_user"
                    result["need_login"] = True
            except AuthKeyUnregisteredError:
                result["status"] = "auth_key_unregistered"
                result["need_login"] = True
                result["reason"] = "Auth key expired or revoked by Telegram"
            except AuthKeyDuplicatedError:
                result["status"] = "auth_key_duplicated"
                result["need_login"] = True
                result["reason"] = "Auth key duplicated — used elsewhere"
            except SessionRevokedError:
                result["status"] = "session_revoked"
                result["need_login"] = True
                result["reason"] = "Session revoked by user"
            except FloodWaitError as e:
                result["status"] = "flood_wait"
                result["need_login"] = False
                result["wait_seconds"] = e.seconds
            except Exception as e:
                result["status"] = "error"
                result["need_login"] = True
                result["error"] = f"{type(e).__name__}: {e}"
        except Exception as e:
            result["status"] = "connection_error"
            result["need_login"] = True
            result["error"] = f"{type(e).__name__}: {e}"
        finally:
            if client.is_connected():
                await client.disconnect()

        return result

    async def validate_batch(self, session_paths: List[str]) -> List[Dict[str, Any]]:
        """Validate multiple sessions, stop early on alive user session"""
        results = []
        for sp in session_paths:
            if not Path(sp).exists():
                continue
            r = await self.validate(sp)
            results.append(r)
            # Stop if we found an alive user session
            if r.get("status") == "alive" and not r.get("user", {}).get("is_bot"):
                break
        return results


class RecoveryEngine:
    """Complete Recovery Engine — Scan + Validate + Report"""

    def __init__(self):
        self.scanner = RecoveryScanner()
        self.validator = SessionValidator()
        self.session_validations: List[Dict[str, Any]] = []

    def scan_phase(self):
        """Phase 1: Scan all assets"""
        print("\n[Phase 1] Scanning assets...")
        findings = self.scanner.scan_all()
        return findings

    async def validate_phase(self, findings: List[Dict[str, Any]]):
        """Phase 2: Validate sessions via real connection"""
        print("\n[Phase 2] Validating sessions...")

        # Pick top session files to validate (skip archives, prioritize Workspace/Windows)
        session_paths = []
        for f in findings:
            if f["type"] in ("TelethonSession", "PyrogramSession"):
                session_paths.append(f["path"])
            elif f["type"] == "PossibleSession":
                session_paths.append(f["path"])

        # Deduplicate and limit to first 10
        seen = set()
        unique_paths = []
        for p in session_paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)
        unique_paths = unique_paths[:10]

        if not unique_paths:
            print("  No session files to validate")
            return []

        print(f"  Validating {len(unique_paths)} sessions...")
        results = await self.validator.validate_batch(unique_paths)
        self.session_validations = results

        for r in results:
            status = r.get("status", "unknown")
            user = r.get("user", {})
            print(f"  [{status.upper()}] {r['session']}")
            if user:
                print(f"    User: @{user.get('username')} (is_bot={user.get('is_bot')})")

        return results

    def report_phase(self, findings: List[Dict[str, Any]], validations: List[Dict[str, Any]]):
        """Phase 3: Generate recovery report"""
        print("\n[Phase 3] Generating report...")

        now = datetime.now()
        date_str = now.strftime("%Y%m%d")

        # Classify sessions
        alive_user_sessions = [v for v in validations
                                if v.get("status") == "alive"
                                and not v.get("user", {}).get("is_bot")]
        alive_bot_sessions = [v for v in validations
                               if v.get("status") == "alive"
                               and v.get("user", {}).get("is_bot")]
        dead_sessions = [v for v in validations
                          if v.get("status") not in ("alive",)]

        # Determine overall recovery status
        if alive_user_sessions:
            overall = "USER_RECOVERED"
            action = f"Use {alive_user_sessions[0]['session']} for user operations"
            need_login = False
        elif alive_bot_sessions:
            overall = "BOT_ONLY"
            action = "Bot session available for push. User session needs re-login."
            need_login = True  # Bot works, but user session still needs login
        else:
            overall = "NEED_LOGIN"
            action = "All sessions invalid — full re-login required"
            need_login = True

        report = {
            "timestamp": now.isoformat(),
            "engine_version": "REC-002",
            "scan_summary": {
                "total_findings": len(findings),
                "session_files": sum(1 for f in findings if f["type"] in
                                     ("TelethonSession", "PyrogramSession", "PossibleSession")),
                "config_files": sum(1 for f in findings if f["type"] == "Config"),
            },
            "validation_summary": {
                "total_validated": len(validations),
                "alive_user": len(alive_user_sessions),
                "alive_bot": len(alive_bot_sessions),
                "dead": len(dead_sessions),
            },
            "overall_status": overall,
            "suggested_action": action,
            "need_login": need_login,
            "findings": findings,
            "validations": validations,
        }

        # Save JSON
        json_path = RECOVERY_DIR / f"recovery_engine_{date_str}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        # Generate Markdown
        md = self._generate_markdown(report, findings, validations)
        md_path = RECOVERY_DIR / f"recovery_engine_{date_str}.md"
        md_path.write_text(md, encoding="utf-8")

        print(f"\n  Report: {md_path}")
        print(f"  JSON:   {json_path}")
        return report

    def _generate_markdown(self, report, findings, validations):
        now = datetime.now()
        lines = [
            f"# Recovery Engine Report — {now.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Overall Status",
            "",
            f"**{report['overall_status']}**",
            "",
            f"- Suggested Action: `{report['suggested_action']}`",
            f"- Need Login: **{'YES' if report['need_login'] else 'NO'}**",
            "",
            "## Scan Summary",
            "",
            f"- Total findings: {report['scan_summary']['total_findings']}",
            f"- Session files: {report['scan_summary']['session_files']}",
            f"- Config files: {report['scan_summary']['config_files']}",
            "",
            "## Session Validation",
            "",
            f"- Alive (user): {report['validation_summary']['alive_user']}",
            f"- Alive (bot):  {report['validation_summary']['alive_bot']}",
            f"- Dead/invalid: {report['validation_summary']['dead']}",
            "",
        ]

        if validations:
            lines.append("### Validation Details")
            lines.append("")
            lines.append("| Session | Status | User | Is Bot | Need Login |")
            lines.append("|---------|--------|------|--------|------------|")
            for v in validations:
                status = v.get("status", "unknown")
                user = v.get("user", {})
                uname = f"@{user.get('username', '')}" if user.get("username") else "-"
                is_bot = user.get("is_bot", "-")
                need = v.get("need_login", True)
                lines.append(
                    f"| {v.get('session', '')} | {status} | {uname} | {is_bot} | {'YES' if need else 'NO'} |"
                )
            lines.append("")

        # Recovery result box
        lines.append("## Recovery Result")
        lines.append("")
        lines.append("```")
        alive_user = report['validation_summary']['alive_user']
        alive_bot = report['validation_summary']['alive_bot']
        lines.append(f"Alive User Session: {'+' + str(alive_user) if alive_user else '- 0'}")
        lines.append(f"Alive Bot Session:  {'+' + str(alive_bot) if alive_bot else '- 0'}")
        lines.append(f"Need Login:         {'YES' if report['need_login'] else 'NO'}")
        lines.append("")
        lines.append(f"Suggested Action:")
        lines.append(f"{report['suggested_action']}")
        lines.append("```")

        return "\n".join(lines)

    async def run(self, skip_validation: bool = False):
        """Run full recovery engine"""
        print("=" * 60)
        print("REC-002: Recovery Engine — OPS-004 Recovery First")
        print("=" * 60)

        # Phase 1: Scan
        findings = self.scan_phase()

        # Phase 2: Validate
        validations = []
        if not skip_validation:
            validations = await self.validate_phase(findings)

        # Phase 3: Report
        report = self.report_phase(findings, validations)

        print(f"\n{'='*60}")
        print(f"Recovery Engine Complete: {report['overall_status']}")
        print(f"{'='*60}")

        return report


def main():
    parser = argparse.ArgumentParser(description="REC-002 Recovery Engine")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip session validation (scan only)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    engine = RecoveryEngine()
    report = asyncio.run(engine.run(skip_validation=args.skip_validation))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
