import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


BOT_TOKEN = os.getenv("BOT_TOKEN", "8553153257:AAHJ-49k7HuUawYnraCBHJaPzk_Jpwnm4TA")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8731364308"))

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@telergambots")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/telergambots")
default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
db_path = os.getenv("DB_PATH", default_db_path)
if os.getenv("VERCEL") == "1" or os.getenv("WEBHOOK_MODE") == "1":
    db_path = os.getenv("DB_PATH", "/tmp/bot.db")
try:
    target_dir = os.path.dirname(db_path) or "."
    if not os.access(target_dir, os.W_OK):
        db_path = "/tmp/bot.db"
except Exception:
    db_path = "/tmp/bot.db"
DB_PATH = db_path

SCHEDULE_DAYS_AHEAD = int(os.getenv("SCHEDULE_DAYS_AHEAD", "30"))

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
