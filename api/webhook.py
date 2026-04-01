from fastapi import FastAPI, Request, Response, status
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Update

import config
from database.db import init_db, ensure_days_for_next_month
from handlers.user_handlers import register_user_handlers
from handlers.admin_handlers import register_admin_handlers
from handlers.subscription_handlers import register_subscription_handlers


app = FastAPI()

# Инициализация
bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode="HTML")
register_subscription_handlers(bot)
register_user_handlers(bot)
register_admin_handlers(bot)

@app.on_event("startup")
async def _startup() -> None:
    init_db()
    ensure_days_for_next_month()


@app.get("/")
async def health():
    return {"ok": True}


@app.post("/")
async def telegram_webhook(request: Request):
    if config.WEBHOOK_SECRET:
        token = request.headers.get("x-telegram-bot-api-secret-token") or request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )
        if token != config.WEBHOOK_SECRET:
            return Response(status_code=status.HTTP_403_FORBIDDEN)

    data = await request.json()
    update = Update.de_json(data)
    await bot.process_new_updates([update])
    return {"ok": True}
