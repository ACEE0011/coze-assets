"""---
id: PROTO-002
type: protocol
title: "Recovery Scanner — 7层文明恢复扫描器"
status: active
source: "R2 Development + R1 Archaeology"
created: 2026-07-12
confidence: 0.92
evidence: [E-036, E-038]
lineage:
  - OPS-004
  - TG-ARCH-002
related: [PROTO-001, INV-L0-001]
tags: [recovery, scanner, telegram, archaeology]
archaeology:
  state: evolved
  sources: 5
---
"""
#!/usr/bin/env python3
"""
REC-001: Recovery Scanner — 恢复扫描器
========================================

OPS-004 (Recovery First): Before creating new, recover existing.
OPS-006 (Search Policy): Layer0 Runtime → Layer1 Workspace → Layer2 GitHub →
                          Layer3 Telegram → Layer4 Archive → Layer5 Internet

核心思想:
  Session 也是 Civilization Asset。登录不是问题，Session 是否还活着才是问题。
  先考古再登录，避免重复劳动。

扫描目标:
  - Telethon Session (*.session, *.session-journal) — SQLite 数据库
  - Pyrogram Session (*.session) — SQLite 数据库
  - StringSession — 嵌入在配置/代码中的字符串
  - API Credentials (api_id, api_hash) — .env / miner_env.sh / config
  - ZIP/Archive 中的 Session 文件

六层扫描:
  L1 Workspace:   ace_workspace/ 下的 *.session, *.sqlite, *.db
  L2 Config:      .env, miner_env.sh, config.py, settings.py 中的 StringSession
  L3 Archive:     *.zip, *.7z, *.tar 中列目录寻找 session 文件
  L4 R1 Snapshot: R1_full_snapshot, R1_core_backup, snapshot, archive, backup
  L5 GitHub:      coze-assets 等私有仓库中的 session/config
  L6 Windows:     AppData, Documents, Desktop, Downloads 等

输出:
  02_MEMORY/recovery/recovery_report_YYYYMMDD.json
  02_MEMORY/recovery/recovery_report_YYYYMMDD.md
"""
import os, sys, json, zipfile, argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

WORKSPACE = Path(__file__).parent.parent
RECOVERY_DIR = WORKSPACE / "02_MEMORY" / "recovery"
RECOVERY_DIR.mkdir(parents=True, exist_ok=True)

# Telethon session file name variants
SESSION_NAMES = [
    "telegram.session", "anon.session", "main.session",
    "default.session", "client.session", "user.session",
    "miner.session", "raspberry_safe.session", "sck01.session",
]

# Session file extensions
SESSION_EXTENSIONS = [".session", ".session-journal"]

# SQLite extensions (some sessions use these)
SQLITE_EXTENSIONS = [".sqlite", ".db"]

# Config file patterns to search for StringSession / credentials
CONFIG_PATTERNS = [".env", ".sh", ".tpl", ".py", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"]

# Credential keywords to search in config files
CREDENTIAL_KEYWORDS = [
    "StringSession", "TelegramClient(", "TG_SESSION", "TELEGRAM_SESSION",
    "SESSION=", "38398440", "3460f304", "api_id", "api_hash",
    "telethon", "pyrogram",
]

# Workspace directories to scan (L1)
WORKSPACE_SCAN_DIRS = [
    WORKSPACE,
    WORKSPACE / "05_TOOLS",
    WORKSPACE / "05_TOOLS" / "miner",
]

# Windows directories to scan (L6)
WINDOWS_SCAN_DIRS = [
    Path(os.path.expanduser("~")),
    Path(os.path.expanduser("~/Documents")),
    Path(os.path.expanduser("~/Desktop")),
    Path(os.path.expanduser("~/Downloads")),
    Path(os.path.expanduser("~/AppData/Roaming")),
    Path(os.path.expanduser("~/AppData/Local")),
]


class RecoveryScanner:
    """Recovery Scanner — 六层恢复扫描"""

    def __init__(self):
        self.findings: List[Dict[str, Any]] = []
        self.scan_log: List[str] = []

    def _log(self, msg: str):
        print(f"  {msg}")
        self.scan_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _add_finding(self, path: str, ftype: str, source: str, size: int = 0,
                     modified: str = "", recovery_prob: int = 3, extra: dict = None):
        """Add a finding to the list"""
        finding = {
            "path": path,
            "type": ftype,
            "source": source,
            "size_bytes": size,
            "modified": modified,
            "recovery_prob": recovery_prob,  # 1-5 stars
            "found_at": datetime.now().isoformat(),
        }
        if extra:
            finding.update(extra)
        self.findings.append(finding)

    # ---- L1: Workspace Scan ----
    def scan_workspace(self):
        """L1: Scan workspace directories for session files"""
        self._log("[L1] Scanning Workspace directories...")
        found_count = 0

        for scan_dir in WORKSPACE_SCAN_DIRS:
            if not scan_dir.exists():
                continue
            self._log(f"  Scanning: {scan_dir}")
            for root, dirs, files in os.walk(scan_dir):
                # Skip hidden dirs and node_modules
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "__pycache__"]
                for fname in files:
                    fpath = Path(root) / fname
                    # Check session extensions
                    if fpath.suffix in SESSION_EXTENSIONS:
                        try:
                            stat = fpath.stat()
                            self._add_finding(
                                path=str(fpath),
                                ftype="TelethonSession" if not self._is_pyrogram(fpath) else "PyrogramSession",
                                source="Workspace",
                                size=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                recovery_prob=5,
                            )
                            found_count += 1
                            self._log(f"  FOUND: {fpath} ({stat.st_size} bytes)")
                        except Exception:
                            pass
                    # Check SQLite files that might be sessions
                    elif fpath.suffix in SQLITE_EXTENSIONS:
                        if self._looks_like_session(fpath):
                            try:
                                stat = fpath.stat()
                                self._add_finding(
                                    path=str(fpath),
                                    ftype="PossibleSession",
                                    source="Workspace",
                                    size=stat.st_size,
                                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    recovery_prob=3,
                                )
                                found_count += 1
                                self._log(f"  FOUND (possible): {fpath}")
                            except Exception:
                                pass

        self._log(f"[L1] Done: {found_count} session files found")
        return found_count

    def _is_pyrogram(self, fpath: Path) -> bool:
        """Check if a .session file is Pyrogram format"""
        try:
            with open(fpath, "rb") as f:
                header = f.read(16)
                # Pyrogram sessions have "SQLite format 3" header too, but we check
                # for pyrogram-specific table names
                return b"pyrogram" in fpath.name.lower().encode()
        except Exception:
            return False

    def _looks_like_session(self, fpath: Path) -> bool:
        """Check if a SQLite file looks like a Telethon/Pyrogram session"""
        try:
            with open(fpath, "rb") as f:
                header = f.read(100)
                if not header.startswith(b"SQLite format 3"):
                    return False
            # Try to read tables
            import sqlite3
            conn = sqlite3.connect(str(fpath))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()
            session_tables = {"sessions", "entities", "sent_files", "version"}
            return bool(tables & session_tables)
        except Exception:
            return False

    # ---- L2: Config Scan ----
    def scan_configs(self):
        """L2: Scan config files for StringSession and credentials"""
        self._log("[L2] Scanning config files for StringSession / credentials...")
        found_count = 0

        scan_dirs = list(WORKSPACE_SCAN_DIRS)
        # Also scan home dir config files
        home = Path(os.path.expanduser("~"))
        for name in [".env", "miner_env.sh", ".bashrc", ".zshrc", ".profile"]:
            p = home / name
            if p.exists():
                scan_dirs.append(p.parent)

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "__pycache__"]
                # Limit depth to avoid scanning entire home dir
                depth = len(Path(root).parts) - len(scan_dir.parts)
                if depth > 3:
                    dirs.clear()
                    continue
                for fname in files:
                    fpath = Path(root) / fname
                    if fpath.suffix not in CONFIG_PATTERNS and fpath.name not in CONFIG_PATTERNS:
                        continue
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore")
                        hits = []
                        for kw in CREDENTIAL_KEYWORDS:
                            if kw in content:
                                hits.append(kw)
                        if hits:
                            stat = fpath.stat()
                            self._add_finding(
                                path=str(fpath),
                                ftype="Config",
                                source="Workspace",
                                size=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                recovery_prob=4 if "StringSession" in hits else 3,
                                extra={"keywords_found": hits},
                            )
                            found_count += 1
                            self._log(f"  FOUND: {fpath} (keywords: {', '.join(hits)})")
                    except Exception:
                        pass

        self._log(f"[L2] Done: {found_count} config files with credentials found")
        return found_count

    # ---- L3: Archive Scan ----
    def scan_archives(self):
        """L3: Scan ZIP archives for session files (list only, no extraction)"""
        self._log("[L3] Scanning archives for session files...")
        found_count = 0

        scan_dirs = [WORKSPACE, Path(os.path.expanduser("~")) / "Downloads"]
        archive_exts = {".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".tar.bz2"}

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
                depth = len(Path(root).parts) - len(scan_dir.parts)
                if depth > 4:
                    dirs.clear()
                    continue
                for fname in files:
                    fpath = Path(root) / fname
                    # Check if it's an archive
                    is_archive = any(fname.endswith(ext) for ext in archive_exts)
                    if not is_archive:
                        continue

                    # Only handle .zip for now (can list without extracting)
                    if fname.endswith(".zip"):
                        try:
                            with zipfile.ZipFile(fpath, "r") as zf:
                                names = zf.namelist()
                                for name in names:
                                    name_lower = name.lower()
                                    # Check if any entry looks like a session file
                                    if (any(name_lower.endswith(ext) for ext in SESSION_EXTENSIONS) or
                                        any(session_name in name_lower for session_name in
                                            ["session", "telegram", "telethon", "pyrogram"])):
                                        stat = fpath.stat()
                                        self._add_finding(
                                            path=f"{fpath}!/{name}",
                                            ftype="SessionInArchive",
                                            source="Archive",
                                            size=stat.st_size,
                                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                            recovery_prob=4,
                                            extra={"archive": str(fpath), "inner_path": name},
                                        )
                                        found_count += 1
                                        self._log(f"  FOUND: {fpath}!/{name}")
                        except Exception as e:
                            # Not a valid zip or password protected
                            pass
                    else:
                        # For .7z and .tar, just note the archive exists
                        # Check if filename suggests session content
                        fname_lower = fname.lower()
                        if any(kw in fname_lower for kw in ["session", "backup", "snapshot", "telegram", "tg"]):
                            stat = fpath.stat()
                            self._add_finding(
                                path=str(fpath),
                                ftype="PossibleSessionArchive",
                                source="Archive",
                                size=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                recovery_prob=2,
                                extra={"note": "Need manual inspection"},
                            )
                            found_count += 1
                            self._log(f"  FOUND (possible): {fpath}")

        self._log(f"[L3] Done: {found_count} archive entries found")
        return found_count

    # ---- L4: R1 Snapshot Scan ----
    def scan_r1_snapshots(self):
        """L4: Scan R1 snapshot/backup directories"""
        self._log("[L4] Scanning R1 snapshot directories...")
        found_count = 0

        # R1 snapshot directory name patterns
        r1_patterns = ["R1_full_snapshot", "R1_core_backup", "snapshot", "archive",
                       "backup", "R1_backup", "ace_backup"]

        # Search in workspace and common locations
        search_roots = [WORKSPACE, Path(os.path.expanduser("~"))]
        for root_dir in search_roots:
            if not root_dir.exists():
                continue
            for root, dirs, files in os.walk(root_dir):
                # Check if directory name matches R1 patterns
                dir_name = Path(root).name.lower()
                is_r1_dir = any(p.lower() in dir_name for p in r1_patterns)
                if is_r1_dir:
                    self._log(f"  Found R1 directory: {root}")
                    # Scan inside for session files
                    for sub_root, sub_dirs, sub_files in os.walk(root):
                        sub_dirs[:] = [d for d in sub_dirs if not d.startswith(".")]
                        for fname in sub_files:
                            fpath = Path(sub_root) / fname
                            if fpath.suffix in SESSION_EXTENSIONS:
                                try:
                                    stat = fpath.stat()
                                    self._add_finding(
                                        path=str(fpath),
                                        ftype="TelethonSession",
                                        source="R1_Snapshot",
                                        size=stat.st_size,
                                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                        recovery_prob=5,
                                    )
                                    found_count += 1
                                    self._log(f"  FOUND: {fpath}")
                                except Exception:
                                    pass
                            elif fpath.suffix in SQLITE_EXTENSIONS:
                                if self._looks_like_session(fpath):
                                    try:
                                        stat = fpath.stat()
                                        self._add_finding(
                                            path=str(fpath),
                                            ftype="PossibleSession",
                                            source="R1_Snapshot",
                                            size=stat.st_size,
                                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                            recovery_prob=4,
                                        )
                                        found_count += 1
                                        self._log(f"  FOUND (possible): {fpath}")
                                    except Exception:
                                        pass
                    # Don't recurse further into R1 dirs (already scanned)
                    dirs.clear()

                # Also limit depth
                depth = len(Path(root).parts) - len(root_dir.parts)
                if depth > 3:
                    dirs.clear()

        self._log(f"[L4] Done: {found_count} R1 snapshot session files found")
        return found_count

    # ---- L5: GitHub Scan ----
    def scan_github(self):
        """L5: Check GitHub repos for session/config files"""
        self._log("[L5] Checking GitHub repositories...")
        found_count = 0

        # Check if coze-assets or other repos are cloned locally
        github_dirs = [
            Path(os.path.expanduser("~/ace_workspace/coze-assets")),
            Path(os.path.expanduser("~/ace_workspace/ace_core")),
            Path(os.path.expanduser("~/coze-assets")),
        ]

        for gdir in github_dirs:
            if not gdir.exists():
                continue
            self._log(f"  Scanning GitHub repo: {gdir}")
            for root, dirs, files in os.walk(gdir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
                for fname in files:
                    fpath = Path(root) / fname
                    if fpath.suffix in SESSION_EXTENSIONS:
                        try:
                            stat = fpath.stat()
                            self._add_finding(
                                path=str(fpath),
                                ftype="TelethonSession",
                                source="GitHub",
                                size=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                recovery_prob=5,
                            )
                            found_count += 1
                            self._log(f"  FOUND: {fpath}")
                        except Exception:
                            pass
                    # Also check for config with credentials
                    if fpath.suffix in CONFIG_PATTERNS:
                        try:
                            content = fpath.read_text(encoding="utf-8", errors="ignore")
                            hits = [kw for kw in CREDENTIAL_KEYWORDS if kw in content]
                            if hits:
                                stat = fpath.stat()
                                self._add_finding(
                                    path=str(fpath),
                                    ftype="Config",
                                    source="GitHub",
                                    size=stat.st_size,
                                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    recovery_prob=4,
                                    extra={"keywords_found": hits},
                                )
                                found_count += 1
                                self._log(f"  FOUND: {fpath} (keywords: {', '.join(hits)})")
                        except Exception:
                            pass

        # Also check git log for session files that might have been committed
        self._log("  Checking git history for session files...")
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:", "--", "*.session"],
                cwd=str(WORKSPACE),
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line:
                        self._add_finding(
                            path=f"git:mine-seed:{line}",
                            ftype="SessionInGitHistory",
                            source="GitHub",
                            size=0,
                            recovery_prob=2,
                            extra={"note": "Found in git history, may need git checkout"},
                        )
                        found_count += 1
                        self._log(f"  FOUND in git history: {line}")
        except Exception:
            pass

        self._log(f"[L5] Done: {found_count} GitHub session/config files found")
        return found_count

    # ---- L6: Windows Scan ----
    def scan_windows(self):
        """L6: Scan Windows directories for session files"""
        self._log("[L6] Scanning Windows directories...")
        found_count = 0

        for scan_dir in WINDOWS_SCAN_DIRS:
            if not scan_dir.exists():
                continue
            self._log(f"  Scanning: {scan_dir}")
            for root, dirs, files in os.walk(scan_dir):
                # Skip problematic directories
                skip_dirs = {".git", "node_modules", "__pycache__", "Microsoft",
                             "Packages", "Temp", "Cache", "pip", "npm", "yarn"}
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
                # Limit depth to 4
                depth = len(Path(root).parts) - len(scan_dir.parts)
                if depth > 4:
                    dirs.clear()
                    continue

                for fname in files:
                    fpath = Path(root) / fname
                    # Check session extensions
                    if fpath.suffix in SESSION_EXTENSIONS:
                        try:
                            stat = fpath.stat()
                            self._add_finding(
                                path=str(fpath),
                                ftype="TelethonSession",
                                source="Windows",
                                size=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                recovery_prob=5,
                            )
                            found_count += 1
                            self._log(f"  FOUND: {fpath} ({stat.st_size} bytes)")
                        except Exception:
                            pass
                    # Also check for telethon/pyrogram directories
                    dir_lower = Path(root).name.lower()
                    if dir_lower in ("telethon", "pyrogram", "telegram", "tg"):
                        if fpath.suffix in SQLITE_EXTENSIONS:
                            try:
                                stat = fpath.stat()
                                self._add_finding(
                                    path=str(fpath),
                                    ftype="PossibleSession",
                                    source="Windows",
                                    size=stat.st_size,
                                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    recovery_prob=4,
                                )
                                found_count += 1
                                self._log(f"  FOUND (possible): {fpath}")
                            except Exception:
                                pass

        self._log(f"[L6] Done: {found_count} Windows session files found")
        return found_count

    # ---- L7: Telegram Layer ----
    def scan_telegram(self):
        """L7: Scan Telegram civilization layer (OPS-006 Layer3)
        Scans: local TG output files, TG sessions, and if session is alive,
        fetches Saved Messages file list.
        """
        self._log("[L7] Scanning Telegram civilization layer...")
        found_count = 0

        # 7.1 Scan local TG output directory (archaeology results)
        tg_output_dirs = [
            WORKSPACE / "05_TOOLS" / "miner" / "tg_output",
            WORKSPACE / "02_MEMORY" / "tg_sessions",
        ]

        for tg_dir in tg_output_dirs:
            if not tg_dir.exists():
                continue
            self._log(f"  Scanning local TG dir: {tg_dir}")
            for root, dirs, files in os.walk(tg_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    try:
                        stat = fpath.stat()
                        # Classify by file type
                        if fname.endswith(".json") and "civilization_map" in fname:
                            ftype = "TGCivilizationMap"
                            rec_prob = 5
                        elif fname.endswith(".session"):
                            ftype = "TGSession"
                            rec_prob = 5
                        elif fname.endswith(".zip"):
                            ftype = "TGArchive"
                            rec_prob = 4
                        elif fname.endswith((".md", ".txt")):
                            ftype = "TGDocument"
                            rec_prob = 3
                        else:
                            continue
                        self._add_finding(
                            path=str(fpath),
                            ftype=ftype,
                            source="Telegram-Local",
                            size=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            recovery_prob=rec_prob,
                        )
                        found_count += 1
                    except Exception:
                        pass

        # 7.2 Try to connect to TG and list Saved Messages files (if session exists)
        tg_session_dir = WORKSPACE / "02_MEMORY" / "tg_sessions"
        session_files = list(tg_session_dir.glob("user*.session")) if tg_session_dir.exists() else []
        if not session_files:
            # Also check miner dir
            miner_session = WORKSPACE / "05_TOOLS" / "miner" / "tg_collections.session"
            if miner_session.exists():
                session_files = [miner_session]

        if session_files:
            self._log(f"  Found {len(session_files)} user session file(s), attempting connection...")
            try:
                from telethon import TelegramClient

                API_ID = int(os.environ["TG_API_ID"])
                API_HASH = os.environ["TG_API_HASH"]
                session_path = str(session_files[0].with_suffix(""))  # remove .session

                async def _tg_list_saved_files():
                    client = TelegramClient(session_path, API_ID, API_HASH)
                    await client.connect()
                    if not await client.is_user_authorized():
                        self._log("  Session not authorized, skipping live TG scan")
                        await client.disconnect()
                        return 0

                    me = await client.get_me()
                    self._log(f"  Connected as @{me.username} (id={me.id})")
                    count = 0
                    file_count = 0
                    async for msg in client.iter_messages("me", limit=500):
                        count += 1
                        if msg.media and hasattr(msg.media, "document") and msg.media.document:
                            file_count += 1
                            fname = "unknown"
                            fsize = 0
                            for attr in (msg.media.document.attributes or []):
                                if hasattr(attr, "file_name"):
                                    fname = attr.file_name
                                if hasattr(msg.media.document, "size"):
                                    fsize = msg.media.document.size
                            self._add_finding(
                                path=f"tg://saved/{msg.id}/{fname}",
                                ftype="TGSavedFile",
                                source="Telegram-SavedMessages",
                                size=fsize,
                                modified=msg.date.isoformat() if msg.date else None,
                                recovery_prob=5,
                                extra={"msg_id": msg.id, "file_name": fname},
                            )
                    await client.disconnect()
                    self._log(f"  TG Saved Messages: {count} messages, {file_count} files")
                    return file_count

                import asyncio
                tg_found = asyncio.run(_tg_list_saved_files())
                found_count += tg_found
            except ImportError:
                self._log("  Telethon not available, skipping live TG scan")
            except Exception as e:
                self._log(f"  TG connection failed: {e}")
        else:
            self._log("  No user session file found, skipping live TG scan")

        self._log(f"[L7] Done: {found_count} TG civilization assets found")
        return found_count

    # ---- Run All Scans ----
    def scan_all(self):
        """Run all 7 layers of scanning (OPS-006 order: L1 Workspace → L7 Telegram)"""
        print("=" * 60)
        print("REC-001: Recovery Scanner — OPS-004 Recovery First")
        print("=" * 60)

        total = 0
        total += self.scan_workspace()      # L1
        total += self.scan_configs()        # L2
        total += self.scan_archives()       # L3
        total += self.scan_r1_snapshots()   # L4
        total += self.scan_github()         # L5
        total += self.scan_windows()        # L6
        total += self.scan_telegram()       # L7 (new: Telegram civilization layer)

        print(f"\n{'=' * 60}")
        print(f"Scan Complete: {total} findings across 7 layers")
        print(f"{'=' * 60}")

        return self.findings

    # ---- Generate Report ----
    def generate_report(self, findings: List[Dict[str, Any]] = None):
        """Generate recovery report"""
        if findings is None:
            findings = self.findings

        now = datetime.now()
        date_str = now.strftime("%Y%m%d")

        # Separate sessions from configs
        sessions = [f for f in findings if f["type"] in (
            "TelethonSession", "PyrogramSession", "PossibleSession",
            "SessionInArchive", "SessionInGitHistory")]
        configs = [f for f in findings if f["type"] == "Config"]
        archives = [f for f in findings if f["type"] in ("SessionInArchive", "PossibleSessionArchive")]

        # Determine if login is needed
        # A session file > 0 bytes is potentially usable
        usable_sessions = [s for s in sessions if s.get("size_bytes", 0) > 0]

        if usable_sessions:
            action = f"Restore {usable_sessions[0]['path']}"
            need_login = False
        elif configs:
            # Check if any config has StringSession
            string_session_configs = [c for c in configs
                                       if any(kw in c.get("keywords_found", [])
                                              for kw in ["StringSession"])]
            if string_session_configs:
                action = f"Extract StringSession from {string_session_configs[0]['path']}"
                need_login = False
            else:
                action = "Login required — no session or StringSession found"
                need_login = True
        else:
            action = "Login required — no recovery assets found"
            need_login = True

        report = {
            "timestamp": now.isoformat(),
            "summary": {
                "total_findings": len(findings),
                "session_files": len(sessions),
                "config_files": len(configs),
                "archive_entries": len(archives),
                "usable_sessions": len(usable_sessions),
                "need_login": need_login,
                "suggested_action": action,
            },
            "findings": findings,
            "scan_log": self.scan_log,
        }

        # Save JSON report
        json_path = RECOVERY_DIR / f"recovery_report_{date_str}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        # Generate Markdown report
        md_lines = [
            f"# Recovery Report — {now.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary",
            "",
            f"- Total findings: **{len(findings)}**",
            f"- Session files: **{len(sessions)}**",
            f"- Config files: **{len(configs)}**",
            f"- Usable sessions: **{len(usable_sessions)}**",
            f"- Need login: **{'Yes' if need_login else 'No'}**",
            "",
            "## Suggested Action",
            "",
            f"```\n{action}\n```",
            "",
        ]

        # Session table
        if sessions:
            md_lines.append("## Session Files")
            md_lines.append("")
            md_lines.append("| File | Type | Source | Modified | Size | Recovery |")
            md_lines.append("|------|------|--------|----------|------|----------|")
            for s in sessions:
                stars = "*" * s["recovery_prob"]
                size_str = self._fmt_size(s.get("size_bytes", 0))
                md_path = s["path"].replace(str(WORKSPACE), ".").replace(str(Path(os.path.expanduser("~"))), "~")
                if len(md_path) > 50:
                    md_path = "..." + md_path[-47:]
                md_lines.append(
                    f"| {md_path} | {s['type']} | {s['source']} | "
                    f"{s.get('modified', '')[:10]} | {size_str} | {stars} |"
                )
            md_lines.append("")

        # Config table
        if configs:
            md_lines.append("## Config Files with Credentials")
            md_lines.append("")
            md_lines.append("| File | Source | Keywords | Modified | Recovery |")
            md_lines.append("|------|--------|----------|----------|----------|")
            for c in configs:
                stars = "*" * c["recovery_prob"]
                kws = ", ".join(c.get("keywords_found", []))
                md_path = c["path"].replace(str(WORKSPACE), ".").replace(str(Path(os.path.expanduser("~"))), "~")
                if len(md_path) > 50:
                    md_path = "..." + md_path[-47:]
                md_lines.append(
                    f"| {md_path} | {c['source']} | {kws} | "
                    f"{c.get('modified', '')[:10]} | {stars} |"
                )
            md_lines.append("")

        # Recovery result box
        md_lines.append("## Recovery Result")
        md_lines.append("")
        md_lines.append("```")
        md_lines.append(f"Found Session:   {'+' + str(len(usable_sessions)) if usable_sessions else '- 0'}")
        md_lines.append(f"Found Config:    {'+' + str(len(configs)) if configs else '- 0'}")
        md_lines.append(f"Need Login:      {'YES' if need_login else 'NO'}")
        md_lines.append(f"")
        md_lines.append(f"Suggested Action:")
        md_lines.append(f"{action}")
        md_lines.append("```")

        md_path = RECOVERY_DIR / f"recovery_report_{date_str}.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        print(f"\nReport saved:")
        print(f"  JSON: {json_path}")
        print(f"  MD:   {md_path}")

        return report

    @staticmethod
    def _fmt_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"


def main():
    parser = argparse.ArgumentParser(description="REC-001 Recovery Scanner")
    parser.add_argument("--layer", type=int, choices=[1, 2, 3, 4, 5, 6, 7],
                        help="Scan only a specific layer (7=Telegram)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    scanner = RecoveryScanner()

    if args.layer:
        layer_methods = {
            1: scanner.scan_workspace,
            2: scanner.scan_configs,
            3: scanner.scan_archives,
            4: scanner.scan_r1_snapshots,
            5: scanner.scan_github,
            6: scanner.scan_windows,
            7: scanner.scan_telegram,
        }
        method = layer_methods.get(args.layer)
        if method:
            count = method()
            print(f"\nLayer {args.layer}: {count} findings")
    else:
        findings = scanner.scan_all()
        report = scanner.generate_report()

        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
