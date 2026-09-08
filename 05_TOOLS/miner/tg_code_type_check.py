#!/usr/bin/env python3
"""Check what code type Telegram returns (non-interactive)"""
import asyncio
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_FILE = str(Path(__file__).parent / "tg_collections")
PHONE = os.environ["TG_PHONE"]

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"ALREADY_LOGGED_IN: {getattr(me, 'first_name', '')} (id={me.id})")
        await client.disconnect()
        return

    try:
        result = await client.send_code_request(PHONE)
        sent_type = type(result.type).__name__

        type_map = {
            "SentCodeTypeApp": "Telegram app notification",
            "SentCodeTypeSms": "SMS message",
            "SentCodeTypeCall": "Phone call",
            "SentCodeTypeFlashCall": "Flash call",
            "SentCodeTypeMissedCall": "Missed call",
            "SentCodeTypeEmailCode": "Email code",
            "SentCodeTypeFragmentSms": "Fragment SMS",
            "SentCodeTypeFirebaseSms": "Firebase SMS (official app only)",
        }

        print(f"SENT_CODE_TYPE: {sent_type}")
        print(f"DESCRIPTION: {type_map.get(sent_type, 'Unknown')}")
        print(f"HASH: {result.phone_code_hash[:20]}...")
        if hasattr(result, 'timeout') and result.timeout:
            print(f"TIMEOUT: {result.timeout}s")
        if hasattr(result, 'next_type') and result.next_type:
            next_type = type(result.next_type).__name__
            print(f"NEXT_TYPE: {next_type}")

        # If App type, try force_sms
        if "App" in sent_type:
            print("\nTrying force_sms=True...")
            try:
                result2 = await client.send_code_request(PHONE, force_sms=True)
                new_type = type(result2.type).__name__
                print(f"FORCE_SMS_TYPE: {new_type}")
                print(f"FORCE_SMS_DESC: {type_map.get(new_type, 'Unknown')}")
            except FloodWaitError as e:
                print(f"FLOOD_WAIT: {e.seconds}s")
            except Exception as e:
                print(f"FORCE_SMS_ERROR: {type(e).__name__}: {e}")

    except FloodWaitError as e:
        print(f"FLOOD_WAIT: {e.seconds}s ({e.seconds//60} min)")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
