import asyncio
from datetime import date, timedelta

from telebot.async_telebot import AsyncTeleBot

import config
from database.db import init_db, ensure_days_for_next_month
from handlers.user_handlers import register_user_handlers
from handlers.admin_handlers import register_admin_handlers
from handlers.subscription_handlers import register_subscription_handlers
from scheduler_manager import set_bot, get_scheduler, restore_scheduled_reminders


bot = AsyncTeleBot(config.BOT_TOKEN, parse_mode="HTML")


def setup() -> None:
    init_db()
    ensure_days_for_next_month()


async def main() -> None:
    setup()

    register_subscription_handlers(bot)
    register_user_handlers(bot)
    register_admin_handlers(bot)

    set_bot(bot)
    scheduler = get_scheduler()
    scheduler.start()
    restore_scheduled_reminders()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        try:
            await bot.remove_webhook()
        except Exception:
            pass
    await bot.infinity_polling()


if __name__ == "__main__":
    asyncio.run(main())
