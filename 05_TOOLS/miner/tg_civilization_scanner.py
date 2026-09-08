#!/usr/bin/env python3
"""
TG Civilization Scanner — Telegram 文明地图扫描器
==================================================
纯考古工具，不设计，不重构。
扫描 TG 全部内容，分类输出 Telegram Civilization Map。

扫描范围:
  - Saved Messages (自我对话)
  - 所有对话 (dialogs)
  - 频道/群组/机器人/私聊
  - 收藏夹
  - 文件

分类:
  Projects / Ideas / RFC / Snapshots / Blueprints / Seed / Experience / Protocol / Unknown
"""
import os, sys, json, asyncio, re
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel, PeerUser

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_FILE = os.path.join(os.path.dirname(__file__), "tg_collections.session")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "tg_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Classification keywords
CLASSIFY_RULES = {
    "Projects": [
        r"项目|project|R1|R2|ACE|TRAE|mine.?seed|ace_core|claw",
        r"矿场|矿工|挖掘|worker|miner",
        r"stock|选股|荐股|advisor",
    ],
    "Ideas": [
        r"想法|idea|思考|think|灵感|insight",
        r"假设|hypothesis|猜想",
        r"为什么|what if|如果能",
    ],
    "RFC": [
        r"RFC|提案|proposal|协议草案|draft",
        r"规范|specification|标准",
    ],
    "Snapshots": [
        r"snapshot|快照|备份|backup|archive|归档",
        r"保存|save|export|导出",
        r"v\d+\.\d+|版本|version",
    ],
    "Blueprints": [
        r"蓝图|blueprint|架构|architecture|设计图",
        r"芯片|chip|kernel|内核|core",
        r"层|layer|模块|module|组件",
        r"五界|five.?realm|KRMGCE",
    ],
    "Seed": [
        r"seed|种子|基因|gene|DNA",
        r"原则|principle|axiom|公理|约束|constraint",
        r"宪章|constitution|manifest|宣言",
    ],
    "Experience": [
        r"经验|experience|教训|lesson",
        r"测试结果|test result|验证|verify",
        r"失败|fail|成功|success|bug|fix",
        r"考古|archaeology|恢复|recovery",
    ],
    "Protocol": [
        r"协议|protocol|OPS|EFP|RP|heartbeat|心跳",
        r"流程|flow|pipeline|工作流",
        r"调度|schedule|cron|task",
    ],
}

def classify_text(text: str) -> str:
    if not text:
        return "Unknown"
    for category, patterns in CLASSIFY_RULES.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return category
    return "Unknown"

def classify_dialog(title: str, entity_type: str, sample_texts: list) -> str:
    # Title-based classification
    title_cat = classify_text(title)
    if title_cat != "Unknown":
        return title_cat
    # Content-based classification (vote from sample texts)
    votes = {}
    for text in sample_texts:
        cat = classify_text(text[:500] if text else "")
        votes[cat] = votes.get(cat, 0) + 1
    if votes:
        best = max(votes, key=votes.get)
        if best != "Unknown" and votes[best] >= 2:
            return best
    # Type-based fallback
    if entity_type == "bot":
        return "Protocol"
    if entity_type == "channel":
        return "Snapshots"
    return "Unknown"

async def scan_all():
    print("=" * 60)
    print("TG Civilization Scanner")
    print("=" * 60)

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: Session not authorized!")
        return
    me = await client.get_me()
    print(f"Logged in: {me.first_name} (@{me.username})")
    print(f"User ID: {me.id}")

    dialogs = await client.get_dialogs()
    print(f"Total dialogs: {len(dialogs)}")

    civilization_map = {
        "Projects": [], "Ideas": [], "RFC": [],
        "Snapshots": [], "Blueprints": [], "Seed": [],
        "Experience": [], "Protocol": [], "Unknown": [],
    }

    saved_messages_data = {"messages": [], "files": []}
    all_dialogs_summary = []

    # Civilization keywords - only deep scan dialogs matching these
    CIVILIZATION_KEYWORDS = re.compile(
        r"R1|R2|ACE|TRAE|mine|矿|chip|芯片|kernel|内核|blueprint|蓝图|"
        r"seed|种子|protocol|协议|constraint|约束|archaeol|考古|"
        r"recover|恢复|memory|记忆|experience|经验|continuity|连续|"
        r"curator|馆长|router|路由|observation|观察|heartbeat|心跳|"
        r"worker|矿工|stock|选股|advisor|signal|信号|lineage|"
        r"五界|five.?realm|KRMGCE|reality|real|bot|Sck|huione|"
        r"收藏|favor|saved|张宁景|DingYuanYing|丁元英|"
        r"AI|GPT|Claude|Ollama|model|模型|prompt|"
        r"架构|architecture|系统|system|engine|引擎|"
        r"RFC|设计|design|spec|规范|宪章|constitution|"
        r"文明|civilization|cognitive|认知|autonomous|自治|"
        r"evolution|演化|evolve|学习|learn|shadow|影子|"
        r"guardian|守护|governor|治理|judge|裁判",
        re.IGNORECASE
    )

    for i, dialog in enumerate(dialogs):
        entity = dialog.entity
        # Determine type
        if isinstance(entity, User):
            etype = "user"
            title = f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
            if getattr(entity, 'bot', False):
                etype = "bot"
        elif isinstance(entity, Channel):
            etype = "channel" if entity.broadcast else "supergroup"
            title = entity.title or "Untitled"
        elif isinstance(entity, Chat):
            etype = "chat"
            title = entity.title or "Untitled"
        else:
            etype = "unknown"
            title = str(getattr(entity, 'id', 'Unknown'))

        # Check if this is Saved Messages
        is_saved = (entity.id == me.id) if isinstance(entity, User) else False

        # Decide whether to deep scan this dialog
        should_deep_scan = is_saved or bool(CIVILIZATION_KEYWORDS.search(title))

        # Fetch sample messages only for relevant dialogs
        sample_texts = []
        sample_messages = []
        if should_deep_scan:
            try:
                async for msg in client.iter_messages(dialog.entity, limit=50):
                    msg_data = {
                        "id": msg.id,
                        "date": msg.date.isoformat() if msg.date else None,
                        "text": (msg.text or "")[:500],
                        "has_media": bool(msg.media),
                        "media_type": type(msg.media).__name__ if msg.media else None,
                        "file_name": None,
                    }
                    if msg.media and hasattr(msg.media, "document") and msg.media.document:
                        for attr in (msg.media.document.attributes or []):
                            if hasattr(attr, "file_name"):
                                msg_data["file_name"] = attr.file_name
                                break
                    sample_messages.append(msg_data)
                    if msg.text:
                        sample_texts.append(msg.text)
            except Exception as e:
                sample_texts.append(f"[Error reading messages: {e}]")

        # Classify
        category = "Unknown"
        if is_saved:
            category = "SavedMessages"
        else:
            category = classify_dialog(title, etype, sample_texts)

        # Count files
        file_count = sum(1 for m in sample_messages if m.get("has_media"))
        msg_count = len(sample_messages)

        dialog_entry = {
            "title": title,
            "type": etype,
            "entity_id": entity.id,
            "category": category,
            "is_saved_messages": is_saved,
            "deep_scanned": should_deep_scan,
            "sample_msg_count": msg_count,
            "file_count_in_sample": file_count,
            "last_message_date": sample_messages[0]["date"] if sample_messages else (dialog.date.isoformat() if dialog.date else None),
            "pinned": dialog.pinned,
            "sample_messages": sample_messages[:10] if is_saved else sample_messages[:3],
        }

        all_dialogs_summary.append(dialog_entry)

        if is_saved:
            saved_messages_data["messages"] = sample_messages
            saved_messages_data["file_count"] = file_count
            saved_messages_data["total_sampled"] = msg_count
            # Also classify saved messages content
            for m in sample_messages:
                m["category"] = classify_text(m.get("text", ""))
        else:
            if category in civilization_map:
                civilization_map[category].append(dialog_entry)
            else:
                civilization_map["Unknown"].append(dialog_entry)

        # Progress
        if (i + 1) % 10 == 0:
            print(f"  Scanned {i+1}/{len(dialogs)} dialogs...")

    # Also scan Saved Messages deeply (fetch more)
    print("\nDeep scanning Saved Messages...")
    try:
        saved_deep = []
        file_list = []
        async for msg in client.iter_messages("me", limit=500):
            msg_data = {
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": (msg.text or "")[:1000],
                "has_media": bool(msg.media),
                "media_type": type(msg.media).__name__ if msg.media else None,
                "file_name": None,
                "file_size": None,
                "category": classify_text((msg.text or "")[:500]),
            }
            if msg.media and hasattr(msg.media, "document") and msg.media.document:
                for attr in (msg.media.document.attributes or []):
                    if hasattr(attr, "file_name"):
                        msg_data["file_name"] = attr.file_name
                        break
                msg_data["file_size"] = msg.media.document.size if hasattr(msg.media.document, "size") else None
                file_list.append({
                    "file_name": msg_data["file_name"],
                    "file_size": msg_data["file_size"],
                    "date": msg_data["date"],
                    "msg_id": msg.id,
                    "text_preview": (msg.text or "")[:100],
                })
            saved_deep.append(msg_data)
        saved_messages_data["deep_scan"] = saved_deep
        saved_messages_data["files"] = file_list
        saved_messages_data["total_deep"] = len(saved_deep)
        print(f"  Saved Messages: {len(saved_deep)} messages, {len(file_list)} files")
    except Exception as e:
        print(f"  Error scanning Saved Messages: {e}")

    await client.disconnect()

    # Build output
    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Count by category
    category_stats = {}
    for cat, items in civilization_map.items():
        category_stats[cat] = len(items)
    category_stats["SavedMessages"] = 1

    output = {
        "scan_time": now,
        "scanned_by": f"@{me.username} (id={me.id})",
        "total_dialogs": len(dialogs),
        "category_stats": category_stats,
        "civilization_map": civilization_map,
        "saved_messages": saved_messages_data,
        "all_dialogs_summary": all_dialogs_summary,
    }

    # Save JSON
    json_path = os.path.join(OUTPUT_DIR, f"tg_civilization_map_{now}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON saved: {json_path}")

    # Generate Markdown Civilization Map
    md_path = os.path.join(OUTPUT_DIR, f"tg_civilization_map_{now}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Telegram Civilization Map\n\n")
        f.write(f"> Scan time: {now}\n")
        f.write(f"> Scanned by: @{me.username}\n")
        f.write(f"> Total dialogs: {len(dialogs)}\n\n")

        f.write("## Overview\n\n")
        f.write("| Category | Count |\n|----------|-------|\n")
        for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
            f.write(f"| {cat} | {count} |\n")
        f.write("\n")

        # Saved Messages summary
        sm = saved_messages_data
        f.write("## Saved Messages (自我对话)\n\n")
        f.write(f"- Deep scan messages: {sm.get('total_deep', 0)}\n")
        f.write(f"- Files: {len(sm.get('files', []))}\n\n")
        if sm.get("files"):
            f.write("### Files in Saved Messages\n\n")
            f.write("| File Name | Size | Date | Text Preview |\n")
            f.write("|-----------|------|------|-------------|\n")
            for fdata in sm["files"][:50]:
                fname = fdata.get("file_name", "?")
                fsize = fdata.get("file_size", 0)
                fdate = (fdata.get("date") or "")[:10]
                fprev = (fdata.get("text_preview") or "")[:50].replace("\n", " ")
                f.write(f"| {fname} | {fsize} | {fdate} | {fprev} |\n")
            f.write("\n")

        # Saved Messages content classification
        if sm.get("deep_scan"):
            sm_cats = {}
            for m in sm["deep_scan"]:
                cat = m.get("category", "Unknown")
                sm_cats[cat] = sm_cats.get(cat, 0) + 1
            f.write("### Saved Messages Content Classification\n\n")
            f.write("| Category | Count |\n|----------|-------|\n")
            for cat, count in sorted(sm_cats.items(), key=lambda x: -x[1]):
                f.write(f"| {cat} | {count} |\n")
            f.write("\n")

        # Each category
        for cat, items in sorted(civilization_map.items(), key=lambda x: -len(x[1])):
            if not items:
                continue
            f.write(f"## {cat} ({len(items)} dialogs)\n\n")
            for item in items:
                f.write(f"### {item['title']}\n")
                f.write(f"- Type: {item['type']}\n")
                f.write(f"- ID: {item['entity_id']}\n")
                f.write(f"- Pinned: {item['pinned']}\n")
                f.write(f"- Last message: {item.get('last_message_date', 'Unknown')}\n")
                if item.get("sample_messages"):
                    f.write(f"- Sample messages:\n")
                    for m in item["sample_messages"][:3]:
                        preview = (m.get("text") or "(no text)")[:100].replace("\n", " ")
                        f.write(f"  - [{m.get('date', '?')[:10]}] {preview}\n")
                f.write("\n")

    print(f"Markdown saved: {md_path}")
    print("\n" + "=" * 60)
    print("Scan complete!")
    print(f"  Dialogs: {len(dialogs)}")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print("=" * 60)

    return output

if __name__ == "__main__":
    asyncio.run(scan_all())
