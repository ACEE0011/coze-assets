#!/usr/bin/env python3
"""
TG interactive login v2 — 支持强制SMS和查看验证码类型
"""
import asyncio
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_FILE = str(Path(__file__).parent / "tg_collections")
PHONE = os.environ["TG_PHONE"]


async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\nAlready logged in: {getattr(me, 'first_name', '')} (id={me.id})")
        await client.disconnect()
        return

    print(f"\n=== Step 1: Send code to {PHONE} ===")

    # First attempt: normal send
    try:
        result = await client.send_code_request(PHONE)
        sent_type = type(result.type).__name__
        print(f"\nCode type: {sent_type}")

        # Decode the type for user info
        type_map = {
            "SentCodeTypeApp": "Telegram app notification (check your Telegram app)",
            "SentCodeTypeSms": "SMS message",
            "SentCodeTypeCall": "Phone call (voice will read the code)",
            "SentCodeTypeFlashCall": "Flash call (missed call, number IS the code)",
            "SentCodeTypeMissedCall": "Missed call (last digits are the code)",
            "SentCodeTypeEmailCode": "Email code",
            "SentCodeTypeFragmentSms": "Fragment SMS (check fragment.com)",
            "SentCodeTypeFirebaseSms": "Firebase SMS (official app only)",
        }
        description = type_map.get(sent_type, "Unknown type")
        print(f"Description: {description}")

        if hasattr(result, 'timeout') and result.timeout:
            print(f"Timeout: {result.timeout} seconds")

        if hasattr(result, 'next_type') and result.next_type:
            next_type = type(result.next_type).__name__
            print(f"Next available type: {next_type}")

        # If code was sent to app (not SMS), try to force SMS
        if "App" in sent_type:
            print("\n>>> Code was sent to Telegram app, not SMS.")
            print(">>> Trying to force SMS delivery...")
            try:
                result2 = await client.send_code_request(PHONE, force_sms=True)
                new_type = type(result2.type).__name__
                print(f"Resent code type: {new_type}")
                result = result2
            except Exception as e:
                print(f"Force SMS failed: {type(e).__name__}: {e}")
                print("Will use the original code delivery method.")

    except FloodWaitError as e:
        print(f"\nFLOOD WAIT: Need to wait {e.seconds} seconds ({e.seconds//60} min) before retrying.")
        await client.disconnect()
        return
    except Exception as e:
        print(f"\nSend code error: {type(e).__name__}: {e}")
        await client.disconnect()
        return

    print("\n=== Step 2: Enter code ===")
    print("Check: Telegram app notifications, SMS, or phone call")
    code = input("\nEnter the verification code: ").strip()

    try:
        await client.sign_in(
            phone=PHONE,
            code=code,
            phone_code_hash=result.phone_code_hash,
        )
    except SessionPasswordNeededError:
        pwd = input("\nTwo-step verification password: ").strip()
        await client.sign_in(password=pwd)
    except Exception as e:
        print(f"\nLogin error: {type(e).__name__}: {e}")
        await client.disconnect()
        return

    me = await client.get_me()
    print(f"\n=== LOGIN SUCCESS ===")
    print(f"User: {getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')} (id={me.id})")
    print(f"Phone: {getattr(me, 'phone', 'N/A')}")
    print(f"Session saved to {SESSION_FILE}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
