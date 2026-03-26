import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple, Dict, Any

from config import DB_PATH, SCHEDULE_DAYS_AHEAD


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            is_subscribed INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            is_open INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_id INTEGER NOT NULL,
            time TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (day_id) REFERENCES days (id) ON DELETE CASCADE,
            UNIQUE (day_id, time)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reminder_time TEXT,
            reminder_job_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (slot_id) REFERENCES time_slots (id)
        )
        """
    )

    conn.commit()
    conn.close()


def ensure_days_for_next_month() -> None:
    today = date.today()
    end_date = today + timedelta(days=SCHEDULE_DAYS_AHEAD)

    conn = get_connection()
    cur = conn.cursor()

    current = today
    while current <= end_date:
        date_str = current.isoformat()
        cur.execute("SELECT id FROM days WHERE date = ?", (date_str,))
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO days (date, is_open) VALUES (?, ?)", (date_str, 1))
        current += timedelta(days=1)

    conn.commit()
    conn.close()


def get_or_create_user(telegram_id: int, username: Optional[str], full_name: Optional[str]) -> sqlite3.Row:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row

    cur.execute(
        "INSERT INTO users (telegram_id, username, full_name, is_subscribed) VALUES (?, ?, ?, ?)",
        (telegram_id, username, full_name, 0),
    )
    conn.commit()

    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def set_user_subscription(telegram_id: int, is_subscribed: bool) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_subscribed = ? WHERE telegram_id = ?",
        (1 if is_subscribed else 0, telegram_id),
    )
    conn.commit()
    conn.close()


def update_user_contact(telegram_id: int, name: str, phone: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET full_name = ?, phone = ? WHERE telegram_id = ?",
        (name, phone, telegram_id),
    )
    conn.commit()
    conn.close()


def get_user_by_telegram_id(telegram_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_active_booking_for_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*, d.date, s.time
        FROM bookings b
        JOIN time_slots s ON b.slot_id = s.id
        JOIN days d ON s.day_id = d.id
        WHERE b.user_id = ? AND b.status = 'active'
        ORDER BY d.date, s.time
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_active_bookings_for_user(user_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*, d.date, s.time
        FROM bookings b
        JOIN time_slots s ON b.slot_id = s.id
        JOIN days d ON s.day_id = d.id
        WHERE b.user_id = ? AND b.status = 'active'
        ORDER BY d.date, s.time
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_day_by_date(date_str: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM days WHERE date = ?", (date_str,))
    row = cur.fetchone()
    conn.close()
    return row


def create_day_if_not_exists(date_str: str) -> sqlite3.Row:
    existing = get_day_by_date(date_str)
    if existing:
        return existing

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO days (date, is_open) VALUES (?, ?)", (date_str, 1))
    conn.commit()
    cur.execute("SELECT * FROM days WHERE date = ?", (date_str,))
    row = cur.fetchone()
    conn.close()
    return row


def add_time_slot(date_str: str, time_str: str) -> Optional[int]:
    day = create_day_if_not_exists(date_str)
    day_id = day["id"]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO time_slots (day_id, time, is_active) VALUES (?, ?, ?)",
            (day_id, time_str, 1),
        )
        conn.commit()
        slot_id = cur.lastrowid
    except sqlite3.IntegrityError:
        slot_id = None
    conn.close()
    return slot_id


def deactivate_time_slot(slot_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE time_slots SET is_active = 0 WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()


def close_day(date_str: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE days SET is_open = 0 WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()


def open_day(date_str: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE days SET is_open = 1 WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()


def get_slots_for_date(date_str: str, include_inactive: bool = False) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    if include_inactive:
        cur.execute(
            """
            SELECT s.*, d.date
            FROM time_slots s
            JOIN days d ON s.day_id = d.id
            WHERE d.date = ?
            ORDER BY s.time
            """,
            (date_str,),
        )
    else:
        cur.execute(
            """
            SELECT s.*, d.date
            FROM time_slots s
            JOIN days d ON s.day_id = d.id
            WHERE d.date = ? AND s.is_active = 1
            ORDER BY s.time
            """,
            (date_str,),
        )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_available_slots_for_date(date_str: str) -> List[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.*, d.date
        FROM time_slots s
        JOIN days d ON s.day_id = d.id
        WHERE d.date = ?
          AND d.is_open = 1
          AND s.is_active = 1
          AND NOT EXISTS (
              SELECT 1 FROM bookings b
              WHERE b.slot_id = s.id AND b.status = 'active'
          )
        ORDER BY s.time
        """,
        (date_str,),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def create_booking(user_id: int, slot_id: int, reminder_time: Optional[datetime], reminder_job_id: Optional[str]) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) FROM bookings
        WHERE user_id = ? AND status = 'active'
        """,
        (user_id,),
    )
    count = cur.fetchone()[0]
    if count > 0:
        conn.close()
        raise ValueError("User already has an active booking")

    created_at = datetime.utcnow().isoformat()
    reminder_time_str = reminder_time.isoformat() if reminder_time else None

    cur.execute(
        """
        INSERT INTO bookings (user_id, slot_id, status, created_at, reminder_time, reminder_job_id)
        VALUES (?, ?, 'active', ?, ?, ?)
        """,
        (user_id, slot_id, created_at, reminder_time_str, reminder_job_id),
    )
    conn.commit()
    booking_id = cur.lastrowid
    conn.close()
    return booking_id


def cancel_booking(booking_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE bookings
        SET status = 'cancelled', reminder_job_id = NULL, reminder_time = NULL
        WHERE id = ?
        """,
        (booking_id,),
    )
    conn.commit()
    conn.close()


def get_booking_with_details(booking_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*, u.telegram_id, u.full_name, u.phone, d.date, s.time
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN time_slots s ON b.slot_id = s.id
        JOIN days d ON s.day_id = d.id
        WHERE b.id = ?
        """,
        (booking_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_future_bookings_with_reminders() -> List[sqlite3.Row]:
    now_iso = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*, u.telegram_id, d.date, s.time
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN time_slots s ON b.slot_id = s.id
        JOIN days d ON s.day_id = d.id
        WHERE b.status = 'active'
          AND b.reminder_time IS NOT NULL
          AND b.reminder_time > ?
        """,
        (now_iso,),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)

