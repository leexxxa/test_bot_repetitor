from datetime import datetime, date, timedelta
from typing import Dict, Any

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery

import config
from database.db import (
    get_or_create_user,
    update_user_contact,
    get_user_by_telegram_id,
    get_active_bookings_for_user,
    get_available_slots_for_date,
    create_booking,
)
from handlers.subscription_handlers import ensure_subscription
from keyboards import (
    main_menu_keyboard,
    teacher_info_keyboard,
    booking_calendar_keyboard,
    time_slots_keyboard,
    bookings_list_keyboard,
    build_calendar,
)
from scheduler_manager import schedule_reminder_for_booking


user_states: Dict[int, Dict[str, Any]] = {}


def register_user_handlers(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message) -> None:
        get_or_create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        text = (
            "Привет! 👋\n"
            "Рад(а) видеть тебя 😊\n\n"
            "Это бот для записи на занятия к репетитору. Здесь ты можешь быстро и удобно "
            "записаться без лишних переписок.\n\n"
            "📚 Меня зовут Дмитрий — я помогаю с подготовкой и обучением "
            "(школа / экзамены / повышение уровня — в зависимости от твоей цели).\n\n"
            "В боте ты можешь:\n"
            "• посмотреть доступные даты и время\n"
            "• узнать стоимость занятий\n"
            "• записаться всего за пару кликов\n\n"
            "Всё максимально просто и понятно — выбери нужный пункт в меню ниже и начнём 🚀"
        )
        await bot.send_message(
            message.chat.id,
            text,
            reply_markup=main_menu_keyboard(),
        )

    @bot.message_handler(func=lambda m: m.text == "Стоимость занятий")
    async def handle_price(message: Message) -> None:
        text = (
            "💰 <b>Стоимость занятий</b>\n\n"
            "• <b>Индивидуальное занятие</b> — 2000 ₽\n"
            "• <b>Групповое занятие</b> — 1500 ₽\n"
            "• <b>Консультация</b> — 500 ₽\n\n"
            "Если есть вопросы по формату или длительности занятия — просто напишите преподавателю 🙂"
        )
        await bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda m: m.text == "О преподавателе")
    async def handle_teacher(message: Message) -> None:
        text = (
            "👨‍🏫 <b>О преподавателе</b>\n\n"
            "Меня зовут Дмитрий. Занимаюсь подготовкой школьников и взрослых:\n"
            "• к контрольным и экзаменам\n"
            "• к поступлению\n"
            "• к повышению уровня для учёбы и работы\n\n"
            "Нажмите кнопку ниже, чтобы посмотреть подробную информацию и связаться со мной."
        )
        await bot.send_message(
            message.chat.id,
            text,
            reply_markup=teacher_info_keyboard(),
        )

    @bot.message_handler(func=lambda m: m.text == "Записаться на занятие")
    async def handle_book_lesson(message: Message) -> None:
        subscribed = await ensure_subscription(bot, message)
        if not subscribed:
            return

        state = {
            "flow": "booking",
            "stage": "choose_date",
        }
        user_states[message.from_user.id] = state

        text = (
            "🗓 <b>Запись на занятие</b>\n\n"
            "Выберите удобную дату в календаре.\n"
            "Доступные дни отмечены в пределах ближайшего месяца."
        )
        await bot.send_message(
            message.chat.id,
            text,
            reply_markup=booking_calendar_keyboard(),
        )

    @bot.message_handler(func=lambda m: m.text == "Мои записи")
    async def handle_my_bookings(message: Message) -> None:
        subscribed = await ensure_subscription(bot, message)
        if not subscribed:
            return

        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await bot.send_message(
                message.chat.id,
                "ℹ️ <b>Активные записи</b>\n\n"
                "Сейчас у вас нет активных записей.\n\n"
                "Чтобы записаться на занятие, выберите пункт "
                "«Записаться на занятие» в главном меню.",
            )
            return

        bookings = get_active_bookings_for_user(user["id"])
        if not bookings:
            await bot.send_message(
                message.chat.id,
                "ℹ️ <b>Активные записи</b>\n\n"
                "Сейчас у вас нет активных записей.\n\n"
                "Чтобы записаться на занятие, выберите пункт "
                "«Записаться на занятие» в главном меню.",
            )
            return

        text = (
            "🗓 <b>Ваши ближайшие занятия</b>\n\n"
            "Нажмите на запись ниже, чтобы отменить её при необходимости."
        )
        await bot.send_message(
            message.chat.id,
            text,
            reply_markup=bookings_list_keyboard(bookings),
        )

    @bot.callback_query_handler(
        func=lambda c: bool(c.data)
        and (
            c.data.startswith("BOOK_DAY:")
            or c.data.startswith("BOOK_PREV:")
            or c.data.startswith("BOOK_NEXT:")
        )
    )
    async def handle_booking_calendar(callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        state = user_states.get(user_id)
        if not state or state.get("flow") != "booking":
            await bot.answer_callback_query(callback.id)
            return

        data = callback.data
        if data.startswith("BOOK_PREV:") or data.startswith("BOOK_NEXT:"):
            _, ym = data.split(":", 1)
            year_str, month_str = ym.split("-")
            year = int(year_str)
            month = int(month_str)
            today = date.today()
            max_date = today + timedelta(days=config.SCHEDULE_DAYS_AHEAD)
            keyboard = build_calendar(
                year,
                month,
                prefix="BOOK",
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

        if data.startswith("BOOK_DAY:"):
            date_str = data.split(":", 1)[1]
            state["stage"] = "choose_time"
            state["date"] = date_str
            user_states[user_id] = state

            slots = get_available_slots_for_date(date_str)
            if not slots:
                text = (
                    "😔 На выбранную дату свободных мест нет.\n\n"
                    "Попробуйте выбрать другой день в календаре."
                )
                await bot.send_message(callback.message.chat.id, text)
                await bot.answer_callback_query(callback.id)
                return

            text = (
                f"⏰ <b>Доступное время</b>\n\n"
                f"Дата: <b>{date_str}</b>\n\n"
                "Выберите удобное время из списка ниже 👇"
            )
            await bot.send_message(
                callback.message.chat.id,
                text,
                reply_markup=time_slots_keyboard(date_str),
            )
            await bot.answer_callback_query(callback.id)
            return

        await bot.answer_callback_query(callback.id)

    @bot.callback_query_handler(func=lambda c: bool(c.data) and c.data.startswith("BOOK_TIME:"))
    async def handle_booking_time(callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        state = user_states.get(user_id)
        if not state or state.get("flow") != "booking" or state.get("stage") != "choose_time":
            await bot.answer_callback_query(callback.id)
            await bot.send_message(
                callback.message.chat.id,
                "ℹ️ Сессия записи устарела.\n\n"
                "Пожалуйста, начните запись заново через пункт "
                "«Записаться на занятие».",
            )
            return

        _, slot_id_str = callback.data.split(":", 1)
        state["slot_id"] = int(slot_id_str)
        state["stage"] = "enter_name"
        user_states[user_id] = state

        await bot.answer_callback_query(callback.id)

        text = (
            "✏️ <b>Как к вам обращаться?</b>\n\n"
            "Пожалуйста, напишите ваше имя.\n"
            "Его увидит только преподаватель."
        )
        await bot.send_message(callback.message.chat.id, text)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("CANCEL_BOOKING:"))
    async def handle_cancel_booking_callback(callback: CallbackQuery) -> None:
        from database.db import cancel_booking
        from scheduler_manager import remove_reminder_for_booking

        _, booking_id_str = callback.data.split(":", 1)
        booking_id = int(booking_id_str)

        remove_reminder_for_booking(booking_id)
        cancel_booking(booking_id)

        await bot.answer_callback_query(callback.id, "Запись отменена")
        await bot.send_message(callback.message.chat.id, "Ваша запись отменена. Слот снова доступен для бронирования.")

    @bot.message_handler(
        func=lambda m: bool(m.text)
        and not m.text.startswith("/")
        and m.from_user.id != config.ADMIN_ID
    )
    async def handle_text(message: Message) -> None:
        user_id = message.from_user.id
        state = user_states.get(user_id)

        if not state or state.get("flow") != "booking":
            return

        if state.get("stage") == "enter_name":
            state["name"] = message.text.strip()
            state["stage"] = "enter_phone"
            user_states[user_id] = state

            await bot.send_message(
                message.chat.id,
                "📞 <b>Номер для связи</b>\n\n"
                "Укажите, пожалуйста, номер телефона в удобном для вас формате.\n\n"
                "Он нужен только для подтверждения записи и связи перед занятием.",
            )
            return

        if state.get("stage") == "enter_phone":
            phone = message.text.strip()
            state["phone"] = phone
            user_states[user_id] = state

            user = get_user_by_telegram_id(user_id)
            if not user:
                user = get_or_create_user(
                    message.from_user.id,
                    message.from_user.username,
                    message.from_user.full_name,
                )

            update_user_contact(user_id, state["name"], phone)

            slot_id = state["slot_id"]
            from database.db import get_day_by_date, get_slots_for_date

            date_str = state["date"]
            day = get_day_by_date(date_str)
            if not day or not day["is_open"]:
                await bot.send_message(
                    message.chat.id,
                    "⚠️ Запись на выбранный день временно недоступна.\n\n"
                    "Пожалуйста, выберите другую дату в календаре.",
                )
                user_states.pop(user_id, None)
                return

            slots = get_slots_for_date(date_str)
            slot = next((s for s in slots if s["id"] == slot_id), None)
            if not slot:
                await bot.send_message(
                    message.chat.id,
                    "⚠️ Это время уже занято или отключено.\n\n"
                    "Пожалуйста, выберите другое время в списке.",
                )
                user_states.pop(user_id, None)
                return

            from database.db import get_active_booking_for_user

            existing_booking = get_active_booking_for_user(user["id"])
            if existing_booking:
                await bot.send_message(
                    message.chat.id,
                    "ℹ️ У вас уже есть активная запись.\n\n"
                    "Чтобы записаться на другое время, сначала отмените текущую "
                    "запись в разделе «Мои записи».",
                )
                user_states.pop(user_id, None)
                return

            lesson_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            lesson_time = datetime.strptime(slot["time"], "%H:%M").time()

            booking_id = create_booking(user["id"], slot_id, None, None)

            reminder_datetime = schedule_reminder_for_booking(booking_id, lesson_date, lesson_time)

            if reminder_datetime is not None:
                from database.db import get_connection

                conn = get_connection()
                cur = conn.cursor()
                job_id = f"reminder_{booking_id}"
                cur.execute(
                    """
                    UPDATE bookings
                    SET reminder_time = ?, reminder_job_id = ?
                    WHERE id = ?
                    """,
                    (reminder_datetime.isoformat(), job_id, booking_id),
                )
                conn.commit()
                conn.close()

            user_states.pop(user_id, None)

            text = (
                "✅ <b>Запись оформлена</b>\n\n"
                f"<b>Дата:</b> {date_str}\n"
                f"<b>Время:</b> {slot['time']}\n"
                f"<b>Имя:</b> {state['name']}\n"
                f"<b>Телефон:</b> {phone}\n\n"
                "📩 За 24 часа до занятия вы получите напоминание в этот чат."
            )
            await bot.send_message(message.chat.id, text)

            from config import ADMIN_ID

            username = user["username"] or ""
            username_part = f"@{username}" if username else "не указан"

            admin_text = (
                "Новая запись на занятие:\n\n"
                f"Username: {username_part}\n"
                f"Имя: {state['name']}\n"
                f"Телефон: {phone}\n"
                f"Дата: {date_str}\n"
                f"Время: {slot['time']}"
            )
            try:
                await bot.send_message(ADMIN_ID, admin_text)
            except Exception:
                pass
