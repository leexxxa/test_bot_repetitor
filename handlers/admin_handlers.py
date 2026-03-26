from datetime import datetime, date, timedelta
from typing import Dict, Any

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery

import config
from database.db import (
    add_time_slot,
    deactivate_time_slot,
    close_day,
    create_day_if_not_exists,
    get_slots_for_date,
    get_day_by_date,
    get_connection,
)
from keyboards import admin_main_keyboard, admin_calendar_keyboard, build_calendar


admin_states: Dict[int, Dict[str, Any]] = {}


def is_admin(message: Message) -> bool:
    return message.from_user.id == config.ADMIN_ID


def register_admin_handlers(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["admin"])
    async def handle_admin_command(message: Message) -> None:
        if not is_admin(message):
            return
        text = "🛠 Панель управления расписанием"
        await bot.send_message(
            message.chat.id,
            text,
            reply_markup=admin_main_keyboard(),
        )

    @bot.callback_query_handler(
        func=lambda c: bool(c.data)
        and c.data.startswith("ADMIN_")
        and not c.data.startswith("ADMIN_DAY:")
    )
    async def handle_admin_callback(callback: CallbackQuery) -> None:
        if callback.from_user.id != config.ADMIN_ID:
            await bot.answer_callback_query(callback.id)
            return

        data = callback.data
        user_id = callback.from_user.id

        if data.startswith("ADMIN_PREV:") or data.startswith("ADMIN_NEXT:"):
            _, ym = data.split(":", 1)
            year_str, month_str = ym.split("-")
            year = int(year_str)
            month = int(month_str)
            today = date.today()
            max_date = today + timedelta(days=config.SCHEDULE_DAYS_AHEAD)
            keyboard = build_calendar(
                year,
                month,
                prefix="ADMIN",
                min_date=today,
                max_date=max_date,
            )
            await bot.edit_message_reply_markup(
                callback.message.chat.id,
                callback.message.message_id,
                reply_markup=keyboard,
            )
            await bot.answer_callback_query(callback.id)
            return

        if data == "ADMIN_ADD_DAY":
            admin_states[user_id] = {"action": "add_day", "stage": "choose_date"}
            text = (
                "📅 Выберите дату, которую нужно открыть для записи."
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=admin_calendar_keyboard(),
            )
            await bot.answer_callback_query(callback.id)
            return

        if data == "ADMIN_ADD_SLOT":
            admin_states[user_id] = {"action": "add_slot", "stage": "choose_date"}
            text = (
                "⏰ Выберите дату, к которой нужно добавить время для записи."
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=admin_calendar_keyboard(),
            )
            await bot.answer_callback_query(callback.id)
            return

        if data == "ADMIN_DELETE_SLOT":
            admin_states[user_id] = {"action": "delete_slot", "stage": "choose_date"}
            text = (
                "❌ Выберите дату, для которой нужно отключить время."
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=admin_calendar_keyboard(),
            )
            await bot.answer_callback_query(callback.id)
            return

        if data == "ADMIN_CLOSE_DAY":
            admin_states[user_id] = {"action": "close_day", "stage": "choose_date"}
            text = (
                "🚫 Выберите день, для которого нужно закрыть запись."
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=admin_calendar_keyboard(),
            )
            await bot.answer_callback_query(callback.id)
            return

        if data == "ADMIN_VIEW_DAY":
            admin_states[user_id] = {"action": "view_day", "stage": "choose_date"}
            text = (
                "📋 Выберите день для просмотра расписания."
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=admin_calendar_keyboard(),
            )
            await bot.answer_callback_query(callback.id)
            return

        await bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ADMIN_DAY:"))
    async def handle_admin_calendar_day(callback: CallbackQuery) -> None:
        if callback.from_user.id != config.ADMIN_ID:
            await bot.answer_callback_query(callback.id)
            return

        user_id = callback.from_user.id
        state = admin_states.get(user_id)
        if not state:
            await bot.answer_callback_query(callback.id)
            return

        date_str = callback.data.split(":", 1)[1]
        action = state.get("action")

        if action == "add_day":
            create_day_if_not_exists(date_str)
            await bot.send_message(
                callback.message.chat.id,
                f"День <b>{date_str}</b> открыт для записи.",
            )
            await bot.answer_callback_query(callback.id)
            admin_states.pop(user_id, None)
            return

        if action == "add_slot":
            state["date"] = date_str
            state["stage"] = "enter_time"
            admin_states[user_id] = state
            await bot.send_message(
                callback.message.chat.id,
                f"Укажите время для <b>{date_str}</b> в формате <b>ЧЧ:ММ</b>\n"
                f"(например, 10:00).",
            )
            await bot.answer_callback_query(callback.id)
            return

        if action == "delete_slot":
            slots = get_slots_for_date(date_str)
            if not slots:
                await bot.send_message(
                    callback.message.chat.id,
                    "На эту дату нет добавленных времён.",
                )
                await bot.answer_callback_query(callback.id)
                admin_states.pop(user_id, None)
                return

            text_lines = ["Времена на выбранную дату:"]
            for slot in slots:
                text_lines.append(f"{slot['id']}: {slot['time']}")
            text_lines.append("Введите ID времени, которое нужно отключить:")
            admin_states[user_id] = {
                "action": "delete_slot",
                "stage": "enter_slot_id",
                "date": date_str,
            }
            await bot.send_message(
                callback.message.chat.id,
                "\n".join(text_lines),
            )
            await bot.answer_callback_query(callback.id)
            return

        if action == "close_day":
            close_day(date_str)
            await bot.send_message(
                callback.message.chat.id,
                f"День <b>{date_str}</b> закрыт для новых записей.\n\n"
                f"Текущие записи сохраняются.",
            )
            await bot.answer_callback_query(callback.id)
            admin_states.pop(user_id, None)
            return

        if action == "view_day":
            day = get_day_by_date(date_str)
            slots = get_slots_for_date(date_str, include_inactive=True)
            lines = [f"📋 Расписание на {date_str}:"]
            if not day:
                lines.append("День отсутствует в расписании.")
            else:
                lines.append(f"Статус дня: {'открыт' if day['is_open'] else 'закрыт'}")
                if not slots:
                    lines.append("На этот день нет добавленных времён.")
                else:
                    for slot in slots:
                        status = "активен"
                        if not slot["is_active"]:
                            status = "неактивен"
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute(
                            """
                            SELECT COUNT(*)
                            FROM bookings
                            WHERE slot_id = ? AND status = 'active'
                            """,
                            (slot["id"],),
                        )
                        count = cur.fetchone()[0]
                        conn.close()
                        if count > 0:
                            status = "активно (есть запись)"
                        if not slot["is_active"]:
                            status = "отключено"
                        lines.append(f"{slot['time']} — {status}")
            await bot.send_message(
                callback.message.chat.id,
                "\n".join(lines),
            )
            await bot.answer_callback_query(callback.id)
            admin_states.pop(user_id, None)
            return

        await bot.answer_callback_query(callback.id)

    @bot.message_handler(func=lambda m: is_admin(m))
    async def handle_admin_text(message: Message) -> None:
        user_id = message.from_user.id
        state = admin_states.get(user_id)
        if not state:
            await bot.send_message(
                message.chat.id,
                "Сначала выберите действие в панели управления и укажите дату.\n\n"
                "После этого можно вводить время или другие данные.",
            )
            return

        action = state.get("action")

        if action == "add_slot" and state.get("stage") == "enter_time":
            date_str = state["date"]
            time_text = message.text.strip()
            try:
                datetime.strptime(time_text, "%H:%M")
            except ValueError:
                await bot.send_message(
                    message.chat.id,
                    "Не удалось распознать время.\n\n"
                    "Пожалуйста, используйте формат <b>ЧЧ:ММ</b> (например, 10:00).",
                )
                return

            slot_id = add_time_slot(date_str, time_text)
            if slot_id is None:
                await bot.send_message(
                    message.chat.id,
                    "Такое время уже есть в расписании на этот день.",
                )
            else:
                await bot.send_message(
                    message.chat.id,
                    f"Время <b>{time_text}</b> добавлено для <b>{date_str}</b>.",
                )
            admin_states.pop(user_id, None)
            return

        if action == "delete_slot" and state.get("stage") == "enter_slot_id":
            try:
                slot_id = int(message.text.strip())
            except ValueError:
                await bot.send_message(
                    message.chat.id,
                    "Введите корректный числовой ID времени.",
                )
                return
            deactivate_time_slot(slot_id)
            await bot.send_message(
                message.chat.id,
                f"Время с ID {slot_id} отключено для записи.",
            )
            admin_states.pop(user_id, None)
            return
