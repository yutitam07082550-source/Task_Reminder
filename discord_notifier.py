import os
import requests
from datetime import datetime

def send_daily_briefing_to_discord(tasks_list):
    """
    Sends structured Notion task briefing to Discord via Webhook.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("❌ Error: DISCORD_WEBHOOK_URL environment variable is missing.")
        return False
        
    today_str = datetime.now().strftime("%d/%m/%Y")
    
    # Format Notion tasks section (Filtered for In Progress & Not Started + Info)
    tasks_text = ""
    if tasks_list:
        for idx, task in enumerate(tasks_list, 1):
            name = task.get('name', 'Untitled Task')
            due = task.get('due', 'ไม่ระบุวันส่ง')
            status = task.get('status', '🔴 ยังไม่ได้เริ่ม')
            info = task.get('info', '').strip()
            
            info_line = f"\n> ℹ️ *{info}*" if info else ""
            item_str = f"{status} **{name}**\n> 🗓️ กำหนดส่ง: `{due}`{info_line}\n\n"
            
            if len(tasks_text) + len(item_str) < 1000:
                tasks_text += item_str
            else:
                tasks_text += f"*...และอีก {len(tasks_list) - idx + 1} รายการ*\n"
                break
                
    if not tasks_text.strip():
        tasks_text = "🎉 **ไม่มีงานค้างที่กำลังทำหรือรอเริ่มต้นในขณะนี้**"
        
    # Build Discord Embed Payload
    embed = {
        "title": f"📋 Notion Task Summary ({today_str})",
        "description": "รายการงานที่ต้องส่งจาก Notion (เฉพาะกำลังดำเนินการ & ยังไม่ได้เริ่ม)",
        "color": 3447003,  # Royal Blue Accent
        "fields": [
            {
                "name": "📌 รายการงานค้างประจำวัน",
                "value": tasks_text[:1024],
                "inline": False
            }
        ],
        "footer": {
            "text": "Automated Notion Task Bot • Antigravity AI"
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    payload = {
        "username": "Notion Task Bot 🤖",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "embeds": [embed]
    }
    
    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code >= 400:
            print(f"❌ Discord Webhook Error ({res.status_code}): {res.text}")
            res.raise_for_status()
        print("✅ Successfully sent task briefing to Discord!")
        return True
    except Exception as e:
        print(f"❌ Error sending message to Discord Webhook: {e}")
        return False
