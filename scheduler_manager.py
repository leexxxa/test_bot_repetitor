from datetime import datetime, date, time, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telebot.async_telebot import AsyncTeleBot

from database.db import get_booking_with_details, get_future_bookings_with_reminders


scheduler = AsyncIOScheduler()
_bot: Optional[AsyncTeleBot] = None


def set_bot(bot: AsyncTeleBot) -> None:
    global _bot
    _bot = bot


def get_scheduler() -> AsyncIOScheduler:
    return scheduler


async def send_reminder(booking_id: int) -> None:
    if _bot is None:
        return

    booking = get_booking_with_details(booking_id)
    if booking is None:
        return
    if booking["status"] != "active":
        return

    chat_id = booking["telegram_id"]
    time_str = booking["time"]
    text = (
        f"Напоминаем, что у вас запланировано занятие завтра в {time_str}.\n"
        f"Ждём вас!"
    )

    await _bot.send_message(chat_id, text)


def schedule_reminder_for_booking(booking_id: int, lesson_date: date, lesson_time: time) -> Optional[datetime]:
    lesson_datetime = datetime.combine(lesson_date, lesson_time)
    now = datetime.utcnow()

    reminder_datetime = lesson_datetime - timedelta(days=1)
    if reminder_datetime <= now:
        return None

    job_id = f"reminder_{booking_id}"
    scheduler.add_job(
        send_reminder,
        "date",
        run_date=reminder_datetime,
        args=[booking_id],
        id=job_id,
        replace_existing=True,
    )
    return reminder_datetime


def remove_reminder_for_booking(booking_id: int) -> None:
    job_id = f"reminder_{booking_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass


def restore_scheduled_reminders() -> None:
    bookings = get_future_bookings_with_reminders()
    for booking in bookings:
        booking_id = booking["id"]
        date_str = booking["date"]
        time_str = booking["time"]

        lesson_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        lesson_time = datetime.strptime(time_str, "%H:%M").time()
        reminder_time_str = booking["reminder_time"]
        if reminder_time_str is None:
            continue
        reminder_datetime = datetime.fromisoformat(reminder_time_str)
        if reminder_datetime <= datetime.utcnow():
            continue

        job_id = f"reminder_{booking_id}"
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=reminder_datetime,
            args=[booking_id],
            id=job_id,
            replace_existing=True,
        )
