import os
import json
import asyncio
import argparse
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerChannel, PeerChat, PeerUser, Dialog, InputPeerChannel, InputPeerChat, InputPeerUser

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_FILE = "tg_collections.session"

TEST_SERVER = "149.154.167.40:443"
PROD_SERVER = "149.154.167.50:443"
DC_ID = 2

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "tg_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

parser = argparse.ArgumentParser(description="TG 收藏夹挖掘工具")
parser.add_argument("--phone", required=True, help="Telegram 手机号码（格式：+855xxxxxxx）")
parser.add_argument("--code", help="Telegram 登录验证码")
parser.add_argument("--password", help="两步验证密码（如有设置）")
args = parser.parse_args()

KNOWN_COLLECTIONS = [
    {"title": "频道收藏夹", "fav_id": 6157874911},
    {"title": "我的收藏夹", "fav_id": 8289754698},
    {"title": "我的收藏_1", "fav_id": 8481371849},
    {"title": "我的收藏_2", "fav_id": 7096254332},
    {"title": "我的收藏架", "fav_id": 6096694801}
]

async def get_peer_info(client, peer):
    try:
        if isinstance(peer, PeerChannel):
            channel = await client.get_entity(peer.channel_id)
            return {"type": "channel", "id": peer.channel_id, "title": getattr(channel, "title", str(peer.channel_id))}
        elif isinstance(peer, PeerChat):
            chat = await client.get_entity(peer.chat_id)
            return {"type": "chat", "id": peer.chat_id, "title": getattr(chat, "title", str(peer.chat_id))}
        elif isinstance(peer, PeerUser):
            user = await client.get_entity(peer.user_id)
            return {"type": "user", "id": peer.user_id, "title": f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or str(peer.user_id)}
    except Exception as e:
        return {"type": "unknown", "id": str(peer), "title": f"Unknown ({str(e)})"}
    return {"type": "unknown", "id": str(peer), "title": "Unknown"}

async def fetch_collections(client):
    print("Fetching dialogs to find collections...")
    dialogs = await client.get_dialogs()
    
    collections = []
    for dialog in dialogs:
        entity = dialog.entity
        if hasattr(entity, 'title'):
            title = entity.title
        elif hasattr(entity, 'first_name'):
            title = f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
        else:
            title = str(entity.id)
        
        for known in KNOWN_COLLECTIONS:
            if known["title"] in title or title in known["title"]:
                peer_info = {
                    "type": "channel" if isinstance(entity, (PeerChannel, InputPeerChannel)) else
                            "chat" if isinstance(entity, (PeerChat, InputPeerChat)) else
                            "user" if isinstance(entity, (PeerUser, InputPeerUser)) else "unknown",
                    "id": entity.id,
                    "title": title
                }
                collection = {
                    "fav_id": known["fav_id"],
                    "peer_type": peer_info["type"],
                    "peer_id": peer_info["id"],
                    "title": peer_info["title"],
                    "date": dialog.date.isoformat() if dialog.date else None,
                    "count": dialog.unread_count or 0,
                    "messages": []
                }
                collections.append(collection)
                print(f"Found collection: {collection['title']} (fav_id: {collection['fav_id']}, type: {collection['peer_type']})")
                break
    
    if not collections:
        print(f"Known collections not found in dialogs. Found {len(dialogs)} dialogs:")
        for d in dialogs[:10]:
            e = d.entity
            t = e.title if hasattr(e, 'title') else f"{getattr(e, 'first_name', '')} {getattr(e, 'last_name', '')}".strip()
            print(f"  - {t} (id: {e.id})")
    
    return collections

async def fetch_messages(client, collection):
    print(f"Fetching messages for: {collection['title']} (fav_id: {collection['fav_id']})")
    all_messages = []
    offset_id = 0
    limit = 100
    
    while True:
        try:
            history = await client(GetHistoryRequest(
                peer=collection["peer_id"] if isinstance(collection["peer_id"], int) else collection["title"],
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0
            ))
            
            if not history.messages:
                break
            
            for msg in history.messages:
                message_data = {
                    "id": msg.id,
                    "date": msg.date.isoformat() if msg.date else None,
                    "sender_id": msg.from_id.user_id if msg.from_id and hasattr(msg.from_id, "user_id") else None,
                    "text": msg.text if isinstance(msg.text, str) else str(msg.text),
                    "media": None,
                    "reply_to": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
                    "views": msg.views if hasattr(msg, "views") else None,
                    "forwards": msg.forwards if hasattr(msg, "forwards") else None
                }
                
                if msg.media:
                    media_type = type(msg.media).__name__
                    message_data["media"] = media_type
                    if hasattr(msg.media, "document") and msg.media.document:
                        for attr in msg.media.document.attributes:
                            if hasattr(attr, "file_name"):
                                message_data["media_filename"] = attr.file_name
                                break
                
                all_messages.append(message_data)
            
            offset_id = history.messages[-1].id
            print(f"  Fetched {len(all_messages)} messages...")
            
            if len(history.messages) < limit:
                break
                
        except Exception as e:
            print(f"  Error fetching messages: {e}")
            break
    
    collection["count"] = len(all_messages)
    collection["messages"] = all_messages
    print(f"  Total messages: {len(all_messages)}")

async def save_results(collections):
    timestamp = datetime.now().isoformat().replace(":", "-")
    output_file = os.path.join(OUTPUT_DIR, f"tg_collections_{timestamp}.json")
    
    summary = {
        "export_time": timestamp,
        "total_collections": len(collections),
        "total_messages": sum(c["count"] for c in collections),
        "collections": collections
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    return output_file

async def generate_report(collections):
    timestamp = datetime.now().isoformat().replace(":", "-")
    report_file = os.path.join(OUTPUT_DIR, f"tg_collections_report_{timestamp}.md")
    
    report_lines = []
    report_lines.append("# TG 收藏夹考古报告")
    report_lines.append("")
    report_lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"> 收藏夹数量: {len(collections)}")
    report_lines.append(f"> 消息总数: {sum(c['count'] for c in collections)}")
    report_lines.append("")
    
    report_lines.append("## 收藏夹概览")
    report_lines.append("")
    report_lines.append("| 收藏夹名称 | fav_ID | 类型 | 消息数 |")
    report_lines.append("|------------|--------|------|--------|")
    
    for c in collections:
        report_lines.append(f"| {c['title']} | {c['fav_id']} | {c['peer_type']} | {c['count']} |")
    
    report_lines.append("")
    
    for i, c in enumerate(collections):
        report_lines.append(f"## {i+1}. {c['title']}")
        report_lines.append("")
        report_lines.append(f"- **fav_ID**: {c['fav_id']}")
        report_lines.append(f"- **类型**: {c['peer_type']}")
        report_lines.append(f"- **消息数**: {c['count']}")
        report_lines.append("")
        
        if c["messages"]:
            report_lines.append("### 消息预览")
            report_lines.append("")
            sample_count = min(5, len(c["messages"]))
            for msg in c["messages"][:sample_count]:
                msg_date = msg["date"][:10] if msg["date"] else "Unknown"
                preview = msg["text"][:100].replace("\n", " ") if msg["text"] else "(无文本)"
                report_lines.append(f"- **[{msg_date}]** {preview}...")
            report_lines.append("")
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"Report saved to: {report_file}")
    return report_file

async def main():
    print("=" * 60)
    print("TG 收藏夹挖掘工具")
    print("=" * 60)
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {'*' * len(API_HASH)}")
    print(f"Server: {TEST_SERVER} (DC {DC_ID})")
    print("=" * 60)
    
    phone_number = args.phone
    
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    
    def code_callback():
        if args.code:
            code = args.code
            args.code = None
            return code
        return input("请输入验证码（Telegram发送的验证码）：")

    def password_callback():
        if args.password:
            pwd = args.password
            args.password = None
            return pwd
        return input("请输入两步验证密码：")

    try:
        await client.start(phone=phone_number, code_callback=code_callback, password=password_callback)
        print("✅ 登录成功")
        
        collections = await fetch_collections(client)
        
        if not collections:
            print("❌ 未找到任何收藏夹")
            return
        
        for collection in collections:
            await fetch_messages(client, collection)
        
        json_file = await save_results(collections)
        report_file = await generate_report(collections)
        
        print("=" * 60)
        print("📊 挖掘完成")
        print(f"   收藏夹: {len(collections)}")
        print(f"   消息数: {sum(c['count'] for c in collections)}")
        print(f"   JSON: {json_file}")
        print(f"   报告: {report_file}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
