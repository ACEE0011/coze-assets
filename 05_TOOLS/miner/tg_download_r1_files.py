#!/usr/bin/env python3
"""Download all R1-related files from TG Saved Messages."""
import asyncio, os
from telethon import TelegramClient

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
OUTPUT_DIR = "05_TOOLS/miner/tg_output"

async def download_all():
    client = TelegramClient("tg_collections", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized")
        return

    keywords = [
        "HUIHUI", "DAG", "SIP", "R1", "REALITY", "KERNEL", "CHIP",
        "SEED", "HEART", "SHADOW", "FIVE", "WORLD", "BLUEPRINT",
        "PDF", "ZIP", "JSON", "CONFIG", "CORE", "ENGINE",
        "ARCHITECTURE", "FRAMEWORK", "PROTOCOL",
    ]

    downloaded = 0
    found = 0
    async for msg in client.iter_messages("me", limit=3000):
        if not msg.media:
            continue
        fname = ""
        doc = getattr(msg.media, "document", None)
        if doc:
            for attr in (doc.attributes or []):
                if hasattr(attr, "file_name"):
                    fname = attr.file_name
                    break
        text = (msg.text or "")[:200]

        match = False
        for kw in keywords:
            if kw.lower() in fname.lower() or kw.lower() in text.lower():
                match = True
                break
        if not match:
            continue

        found += 1
        size = doc.size if doc and hasattr(doc, "size") else "?"
        print(f"Found: {fname} (size={size}, date={msg.date})")

        outpath = os.path.join(OUTPUT_DIR, fname)
        if fname and not os.path.exists(outpath):
            try:
                path = await client.download_media(msg, file=OUTPUT_DIR)
                print(f"  -> Downloaded: {path}")
                downloaded += 1
            except Exception as e:
                print(f"  -> Error: {e}")
        else:
            print("  -> Already exists or no filename")

    print(f"\nTotal found: {found}, downloaded: {downloaded}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(download_all())
