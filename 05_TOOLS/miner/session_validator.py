#!/usr/bin/env python3
"""
Session Validator — Phase 2 of Recovery Engine
================================================

Flow:
  connect() → is_user_authorized() → get_me()

Outputs:
  - Alive      → Recovery success, no login needed
  - Revoked    → Need re-login
  - Duplicated → AuthKeyDuplicated, need investigation
  - Unregistered → AuthKeyUnregistered, session expired
"""
import asyncio, sys, os, json
from pathlib import Path
from datetime import datetime

# Load credentials from miner_env.sh
WORKSPACE = Path(__file__).parent.parent.parent
ENV_FILE = WORKSPACE / "05_TOOLS" / "miner" / "miner_env.sh"

def load_credentials():
    """Load api_id and api_hash from miner_env.sh"""
    api_id = None
    api_hash = None
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export TG_API_ID="):
                api_id = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("export TG_API_HASH="):
                api_hash = line.split("=", 1)[1].strip().strip('"').strip("'")
    # Fallback to known values
    if not api_id:
        api_id = "38398440"
    if not api_hash:
                api_hash = os.environ.get("TG_API_HASH", "")
    return api_id, api_hash


async def validate_session(session_path: str, api_id: str, api_hash: str):
    """Validate a single session file"""
    from telethon import TelegramClient
    from telethon.errors import (
        AuthKeyUnregisteredError, AuthKeyDuplicatedError,
        SessionRevokedError, UserDeactivatedError,
        AuthKeyError, FloodWaitError
    )

    session_name = Path(session_path).stem
    print(f"\n{'='*60}")
    print(f"Validating: {session_name}")
    print(f"Path: {session_path}")
    print(f"{'='*60}")

    # Telethon takes session name without .session extension
    session_dir = str(Path(session_path).parent)
    session_base = Path(session_path).stem

    result = {
        "session": session_name,
        "path": session_path,
        "timestamp": datetime.now().isoformat(),
    }

    client = TelegramClient(
        str(Path(session_dir) / session_base),
        api_id,
        api_hash
    )

    try:
        print("[1/3] Connecting...")
        await client.connect()
        print(f"  Connected: {client.is_connected()}")

        if not client.is_connected():
            result["status"] = "connection_failed"
            result["need_login"] = True
            print("  FAIL: Could not connect")
            return result

        print("[2/3] Checking is_user_authorized()...")
        authorized = await client.is_user_authorized()
        print(f"  is_user_authorized: {authorized}")

        if not authorized:
            result["status"] = "not_authorized"
            result["need_login"] = True
            print("  NOT authorized — need login")
            await client.disconnect()
            return result

        print("[3/3] Calling get_me()...")
        try:
            me = await client.get_me()
            if me:
                result["status"] = "alive"
                result["need_login"] = False
                result["need_2fa"] = False
                result["can_push"] = True
                result["user"] = {
                    "id": me.id,
                    "username": me.username,
                    "phone": me.phone,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "is_bot": me.bot,
                }
                print(f"  ALIVE!")
                print(f"  User: id={me.id} @{me.username} phone={me.phone}")
                print(f"  Name: {me.first_name} {me.last_name or ''}")
                print(f"  Is Bot: {me.bot}")
                print(f"\n  Recovery: SUCCESS")
                print(f"  Need Login: NO")
                print(f"  Need 2FA: NO")
                print(f"  Can Push TG: YES")
            else:
                result["status"] = "no_user"
                result["need_login"] = True
                print("  get_me() returned None")
        except AuthKeyUnregisteredError:
            result["status"] = "auth_key_unregistered"
            result["need_login"] = True
            result["reason"] = "Auth key not registered — session expired or revoked by Telegram"
            print("  ERROR: AuthKeyUnregistered — session expired")
        except AuthKeyDuplicatedError:
            result["status"] = "auth_key_duplicated"
            result["need_login"] = True
            result["reason"] = "Auth key duplicated — same key used elsewhere"
            print("  ERROR: AuthKeyDuplicated — key used elsewhere")
        except SessionRevokedError:
            result["status"] = "session_revoked"
            result["need_login"] = True
            result["reason"] = "Session revoked — user terminated this session"
            print("  ERROR: SessionRevoked — user terminated session")
        except UserDeactivatedError:
            result["status"] = "user_deactivated"
            result["need_login"] = True
            result["reason"] = "User account deactivated"
            print("  ERROR: UserDeactivated")
        except FloodWaitError as e:
            result["status"] = "flood_wait"
            result["need_login"] = False
            result["wait_seconds"] = e.seconds
            result["reason"] = f"Flood wait — need to wait {e.seconds}s"
            print(f"  ERROR: FloodWait — wait {e.seconds}s")
        except Exception as e:
            result["status"] = "error"
            result["need_login"] = True
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            print(f"  ERROR: {type(e).__name__}: {e}")

    except Exception as e:
        result["status"] = "connection_error"
        result["need_login"] = True
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        print(f"  CONNECTION ERROR: {type(e).__name__}: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()

    return result


async def main():
    api_id, api_hash = load_credentials()
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:8]}...{api_hash[-4:]}")

    # Sessions to validate (user sessions first, then bots)
    sessions = [
        r"C:\Users\User\tg_collections.session",
        r"C:\Users\User\ace_workspace\mine-seed\05_TOOLS\miner\tg_collections.session",
        r"C:\Users\User\ace_workspace\mine-seed\05_TOOLS\miner\tg_bot_Bot2_Sck01Bot.session",
    ]

    results = []
    for sf in sessions:
        if not Path(sf).exists():
            print(f"\n[SKIP] Not found: {sf}")
            continue
        result = await validate_session(sf, api_id, api_hash)
        results.append(result)
        # If we found an alive user session, stop
        if result.get("status") == "alive" and not result.get("user", {}).get("is_bot"):
            print(f"\n>>> Found alive USER session, stopping validation <<<")
            break

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "validations": results,
        "summary": {
            "total": len(results),
            "alive": sum(1 for r in results if r.get("status") == "alive"),
            "need_login": sum(1 for r in results if r.get("need_login")),
        }
    }

    report_dir = WORKSPACE / "02_MEMORY" / "recovery"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"session_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Validation Report")
    print(f"{'='*60}")
    for r in results:
        status = r.get("status", "unknown")
        user = r.get("user", {})
        emoji = "OK" if status == "alive" else "X"
        print(f"  [{emoji}] {r['session']}: {status}")
        if user:
            print(f"      User: @{user.get('username')} ({user.get('id')})")
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
