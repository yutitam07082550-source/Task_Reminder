import os
import sys
import requests
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure UTF-8 output encoding for terminal
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load environment variables from .env if present
load_dotenv()

def extract_property_text(prop_val):
    if not prop_val:
        return ""
    p_type = prop_val.get("type", "")
    if p_type == "status":
        st = prop_val.get("status")
        return st.get("name", "").strip() if st else ""
    elif p_type == "select":
        sel = prop_val.get("select")
        return sel.get("name", "").strip() if sel else ""
    elif p_type == "checkbox":
        return "Done" if prop_val.get("checkbox") else "To Do"
    elif p_type == "multi_select":
        items = prop_val.get("multi_select", [])
        return ", ".join([i.get("name", "") for i in items if i.get("name")]).strip()
    elif p_type == "rich_text":
        parts = prop_val.get("rich_text", [])
        return "".join([t.get("plain_text", "") for t in parts]).strip()
    elif p_type == "title":
        parts = prop_val.get("title", [])
        return "".join([t.get("plain_text", "") for t in parts]).strip()
    elif p_type == "url":
        return prop_val.get("url", "") or ""
    elif p_type == "formula":
        form = prop_val.get("formula", {})
        f_type = form.get("type", "")
        return str(form.get(f_type, "") or "").strip()
    elif p_type == "number":
        num = prop_val.get("number")
        return str(num) if num is not None else ""
    return ""

def fetch_due_tasks():
    notion_token = os.getenv("NOTION_TOKEN")
    raw_db_id = os.getenv("NOTION_DATABASE_ID") or os.getenv("DATABASE_ID", "")
    if not notion_token or not raw_db_id:
        print("⚠️ Warning: NOTION_TOKEN or NOTION_DATABASE_ID environment variable is missing.")
        return []

    clean_db_id = raw_db_id.split("?")[0].split("/")[-1].replace("-", "")
    if len(clean_db_id) > 32 and clean_db_id.startswith("N"):
        clean_db_id = clean_db_id[1:]
    database_id = clean_db_id[:32]
    
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json={}, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        filtered_tasks = []
        for page in data.get("results", []):
            properties = page.get("properties", {})
            
            # 1. Extract Task Title
            task_name = "Untitled Task"
            for prop_val in properties.values():
                if prop_val.get("type") == "title":
                    task_name = extract_property_text(prop_val) or "Untitled Task"
                    break
            
            # 2. Extract Status Property smartly
            status_val_str = ""
            status_found = False
            
            for prop_name, prop_val in properties.items():
                if prop_val.get("type") in ["status", "checkbox"]:
                    status_val_str = extract_property_text(prop_val)
                    status_found = True
                    break
                    
            if not status_found:
                status_names = ["status", "สถานะ", "state", "progress", "stage", "done", "เสร็จ", "การดำเนินงาน", "ความคืบหน้า"]
                for prop_name, prop_val in properties.items():
                    if any(k in prop_name.lower() for k in status_names):
                        status_val_str = extract_property_text(prop_val)
                        status_found = True
                        break
                        
            if not status_found:
                for prop_name, prop_val in properties.items():
                    if prop_val.get("type") == "select":
                        status_val_str = extract_property_text(prop_val)
                        break

            if not status_val_str:
                status_val_str = "ยังไม่ได้เริ่ม"

            # 3. Extract Due Date
            due_date = "ไม่ระบุวันส่ง"
            for prop_name, prop_val in properties.items():
                if prop_val.get("type") == "date" and prop_val.get("date"):
                    due_date = prop_val.get("date", {}).get("start", "ไม่ระบุวันส่ง")
                    break

            # 4. Extract Info property
            info_str = ""
            for prop_name, prop_val in properties.items():
                if prop_name.lower() in ["info", "information", "detail", "details", "note", "notes", "รายละเอียด"]:
                    info_str = extract_property_text(prop_val)
                    if info_str:
                        break

            # 5. Comprehensive Completion Check
            status_lower = status_val_str.lower()
            done_keywords = [
                "done", "completed", "complete", "เสร็จสิ้น", "เรียบร้อย", "เสร็จแล้ว", "เสร็จ", 
                "closed", "finish", "finished", "✓", "✔", "ส่งแล้ว", "ส่งงานแล้ว", "pass", "passed", 
                "archive", "archived", "100%", "สำเร็จ"
            ]
            
            is_done = any(k in status_lower for k in done_keywords)
            if is_done:
                continue
            
            in_progress_keywords = ["กำลังดำเนินการ", "in progress", "doing", "working", "กำลังทำ", "ongoing", "started", "กำลัง"]
            if any(k in status_lower for k in in_progress_keywords):
                status_badge = f"🟡 {status_val_str}"
            else:
                status_badge = f"🔴 {status_val_str}"
            
            filtered_tasks.append({
                "name": task_name,
                "status": status_badge,
                "raw_status": status_val_str,
                "due": due_date,
                "info": info_str,
                "url": page.get("url", "")
            })

        # Sort tasks: "กำลังดำเนินการ" first, then "ยังไม่ได้เริ่ม"
        def get_task_sort_key(task):
            status_lower = task.get("raw_status", "").lower()
            in_progress_keywords = ["กำลังดำเนินการ", "in progress", "doing", "working", "กำลังทำ", "ongoing", "started", "กำลัง"]
            if any(k in status_lower for k in in_progress_keywords):
                status_rank = 0
            else:
                status_rank = 1
            due = task.get("due", "9999-99-99")
            if due == "ไม่ระบุวันส่ง":
                due = "9999-99-99"
            return (status_rank, due)

        filtered_tasks.sort(key=get_task_sort_key)
        return filtered_tasks
    except Exception as e:
        print(f"❌ Error querying Notion API: {e}")
        return []

def send_daily_briefing_to_discord(tasks_list):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or os.getenv("DISCORD_BOT_TOKEN")
    if not webhook_url:
        print("❌ Error: DISCORD_WEBHOOK_URL (or DISCORD_BOT_TOKEN) environment variable is missing.")
        return False
        
    today_str = datetime.now().strftime("%d/%m/%Y")
    
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
        
    embed = {
        "title": f"📋 Notion Task Summary ({today_str})",
        "description": "รายการงานที่ต้องส่งจาก Notion (เฉพาะกำลังดำเนินการ & ยังไม่ได้เริ่ม)",
        "color": 3447003,
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
        "timestamp": datetime.now(timezone.utc).isoformat()
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

def run_daily_briefing():
    print("🚀 Starting Notion Task Briefing Bot execution...")
    tasks = fetch_due_tasks()
    success = send_daily_briefing_to_discord(tasks)
    if success:
        print("🎉 Daily briefing process completed successfully!")
    else:
        print("⚠️ Daily briefing completed with errors.")

if __name__ == "__main__":
    run_daily_briefing()
