from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery

import config
from database.db import get_or_create_user, set_user_subscription
from keyboards import subscription_keyboard, main_menu_keyboard


async def is_user_subscribed(bot: AsyncTeleBot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(config.CHANNEL_USERNAME, user_id)
        status = getattr(member, "status", None)
        return status not in ("left", "kicked")
    except Exception:
        return False


async def ensure_subscription(bot: AsyncTeleBot, message: Message) -> bool:
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )

    if user["is_subscribed"]:
        return True

    subscribed = await is_user_subscribed(bot, message.from_user.id)
    if subscribed:
        set_user_subscription(message.from_user.id, True)
        return True

    text = (
        "📢 <b>Доступ к записи</b>\n\n"
        "Для записи на занятия нужно быть подписанным на канал с обновлениями.\n\n"
        "1️⃣ Нажмите «Подписаться на канал»\n"
        "2️⃣ Вернитесь в бот\n"
        "3️⃣ Нажмите «Проверить подписку»\n\n"
        "После этого запись станет доступна ✅"
    )
    await bot.send_message(
        message.chat.id,
        text,
        reply_markup=subscription_keyboard(),
    )
    return False


def register_subscription_handlers(bot: AsyncTeleBot) -> None:
    @bot.callback_query_handler(func=lambda c: c.data == "CHECK_SUBSCRIPTION")
    async def handle_check_subscription(callback: CallbackQuery) -> None:
        subscribed = await is_user_subscribed(bot, callback.from_user.id)
        if subscribed:
            set_user_subscription(callback.from_user.id, True)
            text = (
                "✅ <b>Подписка подтверждена</b>\n\n"
                "Спасибо, что подписались на канал.\n"
                "Теперь вы можете записаться на занятие через меню бота."
            )
            await bot.answer_callback_query(callback.id, "Подписка подтверждена")
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=main_menu_keyboard(),
            )
        else:
            text = (
                "📢 Для записи на занятия нужно быть подписанным на канал.\n\n"
                "Пожалуйста, подпишитесь и затем нажмите «Проверить подписку»."
            )
            await bot.answer_callback_query(callback.id)
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=subscription_keyboard(),
            )
