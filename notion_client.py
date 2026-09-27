import os
import sys
import requests
import json
from dotenv import load_dotenv

# Ensure UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load environment variables from .env
load_dotenv()

def extract_property_text(prop_val):
    """
    Extracts clean text from a Notion property value regardless of property type.
    """
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
    """
    Queries Notion Database for tasks.
    Analyzes actual task status from Notion and filters out completed tasks.
    Returns only uncompleted tasks (In Progress, To Do, Not Started, etc.).
    """
    notion_token = os.getenv("NOTION_TOKEN")
    raw_db_id = os.getenv("NOTION_DATABASE_ID", "")
    if not notion_token or not raw_db_id:
        print("⚠️ Warning: NOTION_TOKEN or NOTION_DATABASE_ID environment variable is missing.")
        return []

    # Clean and sanitize database ID
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
        response = requests.post(url, headers=headers, json={}, timeout=10)
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
            
            # Priority 1: Check property of type 'status' or 'checkbox'
            for prop_name, prop_val in properties.items():
                if prop_val.get("type") in ["status", "checkbox"]:
                    status_val_str = extract_property_text(prop_val)
                    status_found = True
                    break
                    
            # Priority 2: Check explicitly named status properties
            if not status_found:
                status_names = ["status", "สถานะ", "state", "progress", "stage", "done", "เสร็จ", "การดำเนินงาน", "ความคืบหน้า"]
                for prop_name, prop_val in properties.items():
                    if any(k in prop_name.lower() for k in status_names):
                        status_val_str = extract_property_text(prop_val)
                        status_found = True
                        break
                        
            # Priority 3: Fallback to first 'select' property
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
                continue  # Skip completed task
            
            # Determine status badge while keeping original status name
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

        # Sort tasks: "กำลังดำเนินการ" (In Progress) first, then "ยังไม่ได้เริ่ม" (Not Started)
        def get_task_sort_key(task):
            status_lower = task.get("raw_status", "").lower()
            in_progress_keywords = ["กำลังดำเนินการ", "in progress", "doing", "working", "กำลังทำ", "ongoing", "started", "กำลัง"]
            if any(k in status_lower for k in in_progress_keywords):
                status_rank = 0  # In Progress first
            else:
                status_rank = 1  # Not Started / To Do second
            
            due = task.get("due", "9999-99-99")
            if due == "ไม่ระบุวันส่ง":
                due = "9999-99-99"
                
            return (status_rank, due)

        filtered_tasks.sort(key=get_task_sort_key)
            
        return filtered_tasks
    except Exception as e:
        print(f"❌ Error querying Notion API: {e}")
        return []

if __name__ == "__main__":
    tasks = fetch_due_tasks()
    print("--- Uncompleted Notion Tasks ---")
    for t in tasks:
        print(f"{t['status']} | {t['name']} | Due: {t['due']} | Info: {t.get('info', '')}")
