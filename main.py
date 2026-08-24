import os
import sys
from dotenv import load_dotenv
from notion_client import fetch_due_tasks
from discord_notifier import send_daily_briefing_to_discord

# Ensure UTF-8 output encoding for Windows terminal console
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load environment variables from .env if present
load_dotenv()

def run_daily_briefing():
    print("🚀 Starting Notion Task Briefing Bot execution...")
    
    # 1. Fetch Notion tasks
    print("📝 Fetching tasks from Notion...")
    tasks = fetch_due_tasks()
    
    # 2. Send notification to Discord
    print("📩 Sending notification to Discord...")
    success = send_daily_briefing_to_discord(tasks)
    
    if success:
        print("🎉 Daily briefing process completed successfully!")
    else:
        print("⚠️ Daily briefing completed with errors.")

if __name__ == "__main__":
    run_daily_briefing()
