import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


BOT_TOKEN = os.getenv("BOT_TOKEN", "8553153257:AAHJ-49k7HuUawYnraCBHJaPzk_Jpwnm4TA")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8731364308"))

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@telergambots")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/telergambots")
default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
DB_PATH = os.getenv("DB_PATH", default_db_path)
# Для серверлес окружений (например, Vercel) используем временную директорию
if os.getenv("VERCEL") or os.getenv("WEBHOOK_MODE") == "1":
    DB_PATH = os.getenv("DB_PATH", "/tmp/bot.db")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")


WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
