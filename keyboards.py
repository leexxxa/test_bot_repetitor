from datetime import date, timedelta
import calendar
from typing import List, Optional

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

import config
from database.db import get_available_slots_for_date, get_days_availability_for_period


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(
        KeyboardButton("Записаться на занятие"),
        KeyboardButton("Мои записи"),
    )
    keyboard.row(
        KeyboardButton("Стоимость занятий"),
        KeyboardButton("О преподавателе"),
    )
    return keyboard


def subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Подписаться", url=config.CHANNEL_LINK),
    )
    keyboard.add(
        InlineKeyboardButton("Проверить подписку", callback_data="CHECK_SUBSCRIPTION"),
    )
    return keyboard


def teacher_info_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "Подробнее о преподавателе",
            url="https://t.me/morozov055",
        )
    )
    return keyboard


def build_calendar(
    year: int,
    month: int,
    prefix: str,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=7)

    keyboard.add(InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="IGNORE"))

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.add(*[InlineKeyboardButton(d, callback_data="IGNORE") for d in week_days])

    month_calendar = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    
    # Получаем статус доступности дней для всего месяца
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    days_availability = get_days_availability_for_period(
        first_day.strftime("%Y-%m-%d"),
        last_day.strftime("%Y-%m-%d")
    )

    for week in month_calendar:
        buttons: List[InlineKeyboardButton] = []
        for day in week:
            day_str = day.strftime("%Y-%m-%d")
            if day.month != month:
                buttons.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
                continue
            if min_date and day < min_date:
                buttons.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
                continue
            if max_date and day > max_date:
                buttons.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
                continue
            
            # Определяем символ дня на основе реальной доступности
            availability = days_availability.get(day_str, 'closed')
            if availability == 'available':
                button_text = f"✅{day.day}"  # Есть свободные слоты
            elif availability == 'full':
                button_text = f"❌{day.day}"  # Слоты заняты
            else:  # 'closed'
                button_text = f"🚫{day.day}"  # День закрыт или нет слотов
            
            buttons.append(
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"{prefix}_DAY:{day_str}",
                )
            )
        keyboard.add(*buttons)

    current_month = date(year=year, month=month, day=1)
    prev_month = current_month - timedelta(days=1)
    next_month = current_month + timedelta(days=32)
    prev_data = f"{prefix}_PREV:{prev_month.year}-{prev_month.month}"
    next_data = f"{prefix}_NEXT:{next_month.year}-{next_month.month}"

    keyboard.add(
        InlineKeyboardButton("<", callback_data=prev_data),
        InlineKeyboardButton(">", callback_data=next_data),
    )

    return keyboard


def booking_calendar_keyboard() -> InlineKeyboardMarkup:
    today = date.today()
    max_date = today + timedelta(days=config.SCHEDULE_DAYS_AHEAD)
    return build_calendar(
        today.year,
        today.month,
        prefix="BOOK",
        min_date=today,
        max_date=max_date,
    )


def admin_calendar_keyboard() -> InlineKeyboardMarkup:
    today = date.today()
    max_date = today + timedelta(days=config.SCHEDULE_DAYS_AHEAD)
    return build_calendar(
        today.year,
        today.month,
        prefix="ADMIN",
        min_date=today,
        max_date=max_date,
    )


def time_slots_keyboard(date_str: str) -> InlineKeyboardMarkup:
    slots = get_available_slots_for_date(date_str)
    keyboard = InlineKeyboardMarkup()
    if not slots:
        keyboard.add(
            InlineKeyboardButton("Нет доступных слотов", callback_data="IGNORE"),
        )
        return keyboard

    row: List[InlineKeyboardButton] = []
    for slot in slots:
        button = InlineKeyboardButton(
            slot["time"],
            callback_data=f"BOOK_TIME:{slot['id']}",
        )
        row.append(button)
        if len(row) == 3:
            keyboard.add(*row)
            row = []
    if row:
        keyboard.add(*row)

    return keyboard


def bookings_list_keyboard(bookings) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    if not bookings:
        keyboard.add(
            InlineKeyboardButton("Нет активных записей", callback_data="IGNORE"),
        )
        return keyboard

    for booking in bookings:
        date_str = booking["date"]
        time_str = booking["time"]
        button_text = f"{date_str} {time_str} — отменить"
        keyboard.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"CANCEL_BOOKING:{booking['id']}",
            )
        )
    return keyboard


def admin_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Добавить рабочий день", callback_data="ADMIN_ADD_DAY"),
    )
    keyboard.add(
        InlineKeyboardButton("Добавить слот", callback_data="ADMIN_ADD_SLOT"),
    )
    keyboard.add(
        InlineKeyboardButton("Удалить слот", callback_data="ADMIN_DELETE_SLOT"),
    )
    keyboard.add(
        InlineKeyboardButton("Отменить запись ученика", callback_data="ADMIN_CANCEL_BOOKING"),
    )
    keyboard.add(
        InlineKeyboardButton("Закрыть день", callback_data="ADMIN_CLOSE_DAY"),
    )
    keyboard.add(
        InlineKeyboardButton("Просмотреть расписание", callback_data="ADMIN_VIEW_DAY"),
    )
    return keyboard

