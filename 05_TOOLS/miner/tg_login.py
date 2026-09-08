#!/usr/bin/env python3
"""
Telegram Login Utility - main entry point.
Supports user login (with 2FA) and bot login.
"""
import os
import sys
import asyncio
from pathlib import Path

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError, FloodWaitError
except ImportError:
    print("Error: telethon not installed. Run: pip install telethon")
    sys.exit(1)

# Credentials must be supplied by the local environment.
try:
    API_ID = int(os.environ["TG_API_ID"])
    API_HASH = os.environ["TG_API_HASH"]
    PHONE = os.environ["TG_PHONE"]
except (KeyError, ValueError) as exc:
    raise SystemExit("TG_API_ID, TG_API_HASH, and TG_PHONE must be set in the local environment") from exc

SESSION_DIR = Path(__file__).parent.parent.parent / "02_MEMORY" / "tg_sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

LOGIN_CODE_FILE = Path(__file__).parent / "tg_login_code.txt"


async def user_login(session_name="user_session"):
    session_file = str(SESSION_DIR / f"{session_name}.session")
    print(f"Session: {session_file}", flush=True)

    client = TelegramClient(session_file, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✓ Already logged in: {getattr(me, 'first_name', '')} (id={me.id})", flush=True)
        await client.disconnect()
        return True

    print(f"\n--- Step 1: Sending code to {PHONE} ---", flush=True)
    try:
        result = await client.send_code_request(PHONE)
    except FloodWaitError as e:
        print(f"✗ FLOOD WAIT: {e.seconds}s ({e.seconds//60} min)", flush=True)
        await client.disconnect()
        return False
    except Exception as e:
        print(f"✗ Send code error: {type(e).__name__}: {e}", flush=True)
        await client.disconnect()
        return False

    sent_type = type(result.type).__name__
    type_map = {
        "SentCodeTypeApp": "Telegram app notification",
        "SentCodeTypeSms": "SMS message",
        "SentCodeTypeCall": "Voice call",
        "SentCodeTypeFlashCall": "Flash call",
        "SentCodeTypeMissedCall": "Missed call",
        "SentCodeTypeEmailCode": "Email code",
    }
    print(f"✓ Code type: {sent_type} ({type_map.get(sent_type, 'Unknown')})", flush=True)

    print(f"\n--- Step 2: Enter verification code ---", flush=True)
    print(f"Write code to: {LOGIN_CODE_FILE}")
    print("Format: line 1 = code, line 2 = 2FA password (if needed)", flush=True)

    phone_code_hash = result.phone_code_hash

    for attempt in range(120):
        await asyncio.sleep(5)
        if LOGIN_CODE_FILE.exists():
            try:
                lines = LOGIN_CODE_FILE.read_text().strip().splitlines()
                code = lines[0].strip() if lines else ""
                pwd = lines[1].strip() if len(lines) > 1 else ""

                if code:
                    print(f"\n✓ Code: {code}", flush=True)
                    LOGIN_CODE_FILE.unlink()

                    try:
                        await client.sign_in(phone=PHONE, code=code, phone_code_hash=phone_code_hash)
                    except SessionPasswordNeededError:
                        print("✓ 2FA required", flush=True)
                        if pwd:
                            await client.sign_in(password=pwd)
                        else:
                            print("Write 2FA password to tg_login_code.txt", flush=True)
                            for _ in range(60):
                                await asyncio.sleep(5)
                                if LOGIN_CODE_FILE.exists():
                                    new_pwd = LOGIN_CODE_FILE.read_text().strip().splitlines()[0].strip()
                                    if new_pwd:
                                        LOGIN_CODE_FILE.unlink()
                                        await client.sign_in(password=new_pwd)
                                        break
                            else:
                                print("✗ Timeout waiting for 2FA", flush=True)
                                await client.disconnect()
                                return False
                    except Exception as e:
                        print(f"✗ Login error: {type(e).__name__}: {e}", flush=True)
                        await client.disconnect()
                        return False

                    me = await client.get_me()
                    print(f"\n🎉 LOGIN SUCCESS!")
                    print(f"User: {getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}")
                    print(f"ID: {me.id}")
                    print(f"Session: {session_file}", flush=True)
                    await client.disconnect()
                    return True
            except Exception as e:
                print(f"✗ Error: {e}", flush=True)
                continue

    print("✗ Timeout", flush=True)
    await client.disconnect()
    return False


async def bot_login(bot_token, session_name="bot_session"):
    session_file = str(SESSION_DIR / f"{session_name}.session")
    client = TelegramClient(session_file, API_ID, API_HASH)
    await client.connect()

    try:
        me = await client.sign_in(bot_token=bot_token)
        print(f"✓ Bot login success: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', 'N/A')})", flush=True)
        await client.disconnect()
        return True
    except Exception as e:
        print(f"✗ Bot login failed: {type(e).__name__}: {e}", flush=True)
        await client.disconnect()
        return False


async def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("=== Telegram Login Utility ===", flush=True)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python tg_login.py user          # User login (with 2FA)")
        print("  python tg_login.py bot <token>   # Bot login")
        print("\nEnvironment variables:")
        print("  TG_API_ID, TG_API_HASH, TG_PHONE")
        sys.exit(1)

    command = sys.argv[1]

    if command == "user":
        await user_login()
    elif command == "bot":
        if len(sys.argv) < 3:
            print("Error: bot token required")
            sys.exit(1)
        await bot_login(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
