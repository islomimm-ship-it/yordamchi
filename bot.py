"""
Sarhisob ULTRA Bot — kreditlar, xarajatlar, vazifalar, maqsadlar,
muhim eslatmalar va ish/sog'liq/sport rejalarini kuzatuvchi Telegram bot.

Barcha amallar tugmalar (keyboard) orqali bajariladi — ID yoki maxsus
format yozish shart emas.

Har kuni foydalanuvchi belgilagan vaqtda (standart 08:00, Asia/Tashkent)
bot to'liq kunlik sarhisobni avtomatik yuboradi.

MUHIM: BOT_TOKEN hech qachon kod ichiga yozilmaydi — faqat muhit
o'zgaruvchisi (environment variable) orqali beriladi.

Ishga tushirish:
    1. BOT_TOKEN muhit o'zgaruvchisini belgilang
    2. pip install -r requirements.txt
    3. python bot.py
"""

import asyncio
import csv
import io
import logging
import os
import sqlite3
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "sarhisob_ultra.db")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TIMEZONE = ZoneInfo("Asia/Tashkent")
DEFAULT_REMIND_TIME = "08:00"

UZ_MONTHS = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

EXPENSE_CATEGORIES = [
    "🍔 Oziq-ovqat", "🚕 Transport", "🏠 Kommunal", "👕 Kiyim-kechak",
    "🎉 Ko'ngilochar", "💊 Sog'liq", "📚 Ta'lim", "🔧 Boshqa",
]

ROUTINE_LABELS = {"ish": "🏛 Davlat ishi", "soglik": "💊 Sog'liq", "sport": "⚽ Sport"}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("sarhisob_ultra_bot")

# ---------------------------------------------------------------------------
# Klaviaturalar
# ---------------------------------------------------------------------------

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["💳 Kreditlar", "💸 Xarajatlar"],
        ["💵 Daromad", "📋 Vazifalar"],
        ["🎯 Maqsadlar", "📌 Muhimlar"],
        ["🗓 Rejalar", "📈 Haftalik hisobot"],
        ["⚙️ Sozlamalar", "📅 Bugungi holat"],
    ],
    resize_keyboard=True,
)

DAROMAD_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Daromad qo'shish"],
        ["📋 Daromadlar ro'yxati", "📊 Oylik balans"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

KREDIT_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Kredit qo'shish"],
        ["📋 Kreditlar ro'yxati", "💵 To'lov qilish"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

XARAJAT_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Xarajat qo'shish"],
        ["📊 Oylik xarajatlarim", "💰 Limit belgilash"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

VAZIFA_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Vazifa qo'shish"],
        ["📋 Bugungi vazifalar", "✅ Bajarildi belgilash"],
        ["❌ Bajarilmagan vazifalar"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

MAQSAD_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Maqsad qo'shish"],
        ["📋 Maqsadlar ro'yxati", "✅ Erishildi belgilash"],
        ["💰 Pul qo'shish"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

MUHIM_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Muhim qo'shish"],
        ["📋 Muhimlar ro'yxati", "🗑 Muhimni o'chirish"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

REJALAR_MENU = ReplyKeyboardMarkup(
    [
        ["➕ Reja qo'shish"],
        ["🏛 Ish rejalari", "💊 Sog'liq rejalari", "⚽ Sport rejalari"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

SETTINGS_MENU = ReplyKeyboardMarkup(
    [
        ["⏰ Eslatma vaqtini o'zgartirish"],
        ["📤 Ma'lumotlarni eksport qilish"],
        ["⬅️ Orqaga"],
    ],
    resize_keyboard=True,
)

STEP_MENU = ReplyKeyboardMarkup([["◀️ Oldingi qadam"], ["❌ Bekor qilish"]], resize_keyboard=True)
CANCEL_MENU = ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)

YES_NO_INLINE = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Ha", callback_data="yn:yes"), InlineKeyboardButton("Yo'q", callback_data="yn:no")]]
)

DUE_DAY_INLINE = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(str(d), callback_data=f"day:{d}") for d in (1, 5, 10, 15)],
        [InlineKeyboardButton(str(d), callback_data=f"day:{d}") for d in (20, 25, 28)],
        [InlineKeyboardButton("✍️ Boshqa kun", callback_data="day:custom")],
    ]
)

TIME_INLINE = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("07:00", callback_data="time:07:00"),
         InlineKeyboardButton("07:30", callback_data="time:07:30"),
         InlineKeyboardButton("08:00", callback_data="time:08:00")],
        [InlineKeyboardButton("08:30", callback_data="time:08:30"),
         InlineKeyboardButton("09:00", callback_data="time:09:00"),
         InlineKeyboardButton("✍️ Boshqa", callback_data="time:custom")],
    ]
)

ROUTINE_CAT_INLINE = InlineKeyboardMarkup(
    [[InlineKeyboardButton(v, callback_data=f"rcat:{k}") for k, v in ROUTINE_LABELS.items()]]
)

# Conversation states (matn ko'rinishida, har biri o'ziga xos)
CR_PERSON, CR_AMOUNT, CR_DUE_DAY, CR_NOTE = range(4)
PAY_SELECT, PAY_AMOUNT = range(4, 6)
EXP_AMOUNT, EXP_NOTE = range(6, 8)
BUDGET_AMOUNT = 8
TASK_TEXT = 9
GOAL_TITLE, GOAL_DEADLINE = range(10, 12)
GOAL_SAVINGS_CHOICE, GOAL_TARGET = range(19, 21)
CONTRIB_SELECT, CONTRIB_AMOUNT = range(21, 23)
PINNED_TEXT = 12
ROUTINE_CATEGORY, ROUTINE_TITLE, ROUTINE_SCHEDULE = range(13, 16)
TIME_CUSTOM = 16
INC_AMOUNT, INC_NOTE = range(17, 19)


# ---------------------------------------------------------------------------
# Ma'lumotlar bazasi
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            remind_time TEXT NOT NULL DEFAULT '08:00',
            monthly_budget REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            person TEXT NOT NULL,
            amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            due_day INTEGER,
            note TEXT,
            is_paid INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            task_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            expense_date TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            deadline TEXT,
            target_amount REAL,
            current_amount REAL NOT NULL DEFAULT 0,
            is_achieved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    for ddl in (
        "ALTER TABLE goals ADD COLUMN target_amount REAL",
        "ALTER TABLE goals ADD COLUMN current_amount REAL NOT NULL DEFAULT 0",
    ):
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            pass
    cur.execute(
        """CREATE TABLE IF NOT EXISTS pinned_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            income_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            schedule_info TEXT
        )"""
    )
    conn.commit()
    conn.close()


def ensure_user(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE chat_id = ?", (chat_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (chat_id, remind_time, monthly_budget, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, DEFAULT_REMIND_TIME, 0.0, datetime.now(TIMEZONE).isoformat()),
        )
        conn.commit()
    conn.close()


def set_remind_time(chat_id: int, hhmm: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET remind_time = ? WHERE chat_id = ?", (hhmm, chat_id))
    conn.commit()
    conn.close()


def set_user_budget(chat_id: int, budget: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET monthly_budget = ? WHERE chat_id = ?", (budget, chat_id))
    conn.commit()
    conn.close()


def get_user_info(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id, remind_time FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows


def format_amount(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


# --- Vazifalar ---
def add_task(chat_id, title):
    conn = get_conn()
    cur = conn.cursor()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO tasks (chat_id, title, task_date, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (chat_id, title, today_str, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def get_todays_tasks(chat_id, only_pending=False):
    conn = get_conn()
    cur = conn.cursor()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    cur.execute(
        "UPDATE tasks SET status = 'failed' WHERE chat_id = ? AND task_date < ? AND status = 'pending'",
        (chat_id, today_str),
    )
    conn.commit()
    if only_pending:
        cur.execute(
            "SELECT * FROM tasks WHERE chat_id = ? AND task_date = ? AND status = 'pending' ORDER BY id DESC",
            (chat_id, today_str),
        )
    else:
        cur.execute(
            "SELECT * FROM tasks WHERE chat_id = ? AND task_date = ? ORDER BY id DESC",
            (chat_id, today_str),
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def update_task_status(chat_id, task_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = ? WHERE chat_id = ? AND id = ?", (status, chat_id, task_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def list_failed_tasks(chat_id, limit=30):
    """Muddati o'tib, bajarilmagan deb belgilangan vazifalar (eng yangisi birinchi)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM tasks WHERE chat_id = ? AND status = 'failed' ORDER BY task_date DESC, id DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def clear_failed_task(chat_id, task_id):
    """Bajarilmagan vazifani ro'yxatdan olib tashlash (o'chirish)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE chat_id = ? AND id = ? AND status = 'failed'", (chat_id, task_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# --- Xarajatlar ---
def add_expense(chat_id, category, amount, note):
    conn = get_conn()
    cur = conn.cursor()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO expenses (chat_id, category, amount, note, expense_date) VALUES (?, ?, ?, ?, ?)",
        (chat_id, category, amount, note, today_str),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def get_expenses_summary(chat_id, year=None, month=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(TIMEZONE)
    year = year or now.year
    month = month or now.month
    ym = f"{year:04d}-{month:02d}"
    cur.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE chat_id = ? AND expense_date LIKE ? "
        "GROUP BY category ORDER BY total DESC",
        (chat_id, f"{ym}%"),
    )
    rows = cur.fetchall()
    cur.execute(
        "SELECT SUM(amount) as total_sum FROM expenses WHERE chat_id = ? AND expense_date LIKE ?",
        (chat_id, f"{ym}%"),
    )
    total_row = cur.fetchone()
    conn.close()
    return rows, (total_row["total_sum"] if total_row and total_row["total_sum"] else 0)


# --- Kreditlar ---
def add_debt(chat_id, person, amount, due_day, note):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO debts (chat_id, person, amount, remaining_amount, due_day, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, person, amount, amount, due_day, note, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return qid


def list_debts(chat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM debts WHERE chat_id = ? AND is_paid = 0 ORDER BY due_day ASC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_debt(chat_id, debt_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM debts WHERE chat_id = ? AND id = ?", (chat_id, debt_id))
    row = cur.fetchone()
    conn.close()
    return row


def update_debt_payment(chat_id, debt_id, paid_part):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT remaining_amount FROM debts WHERE chat_id = ? AND id = ?", (chat_id, debt_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None, 0
    rem = row["remaining_amount"] - paid_part
    if rem <= 0:
        cur.execute(
            "UPDATE debts SET remaining_amount = 0, is_paid = 1 WHERE chat_id = ? AND id = ?", (chat_id, debt_id)
        )
        conn.commit()
        conn.close()
        return True, 0
    cur.execute("UPDATE debts SET remaining_amount = ? WHERE chat_id = ? AND id = ?", (rem, chat_id, debt_id))
    conn.commit()
    conn.close()
    return False, rem


# --- Maqsadlar ---
def add_goal(chat_id, title, deadline, target_amount=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO goals (chat_id, title, deadline, target_amount, current_amount, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (chat_id, title, deadline, target_amount, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    gid = cur.lastrowid
    conn.close()
    return gid


def list_goals(chat_id, only_open=False):
    conn = get_conn()
    cur = conn.cursor()
    if only_open:
        cur.execute("SELECT * FROM goals WHERE chat_id = ? AND is_achieved = 0 ORDER BY id DESC", (chat_id,))
    else:
        cur.execute("SELECT * FROM goals WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_savings_goals(chat_id):
    """Faqat jamg'arma (maqsadli summa) belgilangan, hali erishilmagan maqsadlar."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM goals WHERE chat_id = ? AND is_achieved = 0 AND target_amount IS NOT NULL ORDER BY id DESC",
        (chat_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def achieve_goal(chat_id, goal_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE goals SET is_achieved = 1 WHERE chat_id = ? AND id = ?", (chat_id, goal_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def contribute_to_goal(chat_id, goal_id, amount):
    """Jamg'armaga pul qo'shadi. Maqsadga yetsa avtomatik 'erishildi' deb belgilaydi."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT current_amount, target_amount FROM goals WHERE chat_id = ? AND id = ?", (chat_id, goal_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    new_amount = row["current_amount"] + amount
    achieved = row["target_amount"] is not None and new_amount >= row["target_amount"]
    if achieved:
        cur.execute(
            "UPDATE goals SET current_amount = ?, is_achieved = 1 WHERE chat_id = ? AND id = ?",
            (new_amount, chat_id, goal_id),
        )
    else:
        cur.execute("UPDATE goals SET current_amount = ? WHERE chat_id = ? AND id = ?", (new_amount, chat_id, goal_id))
    conn.commit()
    conn.close()
    return {"new_amount": new_amount, "target": row["target_amount"], "achieved": achieved}


def get_goal(chat_id, goal_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM goals WHERE chat_id = ? AND id = ?", (chat_id, goal_id))
    row = cur.fetchone()
    conn.close()
    return row


# --- Muhim eslatmalar ---
def add_pinned(chat_id, text_):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pinned_notes (chat_id, text, created_at) VALUES (?, ?, ?)",
        (chat_id, text_, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def list_pinned(chat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pinned_notes WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_pinned(chat_id, pinned_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM pinned_notes WHERE chat_id = ? AND id = ?", (chat_id, pinned_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# --- Daromadlar ---
def add_income(chat_id, amount, note):
    conn = get_conn()
    cur = conn.cursor()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO incomes (chat_id, amount, note, income_date, created_at) VALUES (?, ?, ?, ?, ?)",
        (chat_id, amount, note, today_str, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return iid


def list_recent_incomes(chat_id, limit=15):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incomes WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def monthly_income_total(chat_id, year=None, month=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(TIMEZONE)
    year = year or now.year
    month = month or now.month
    ym = f"{year:04d}-{month:02d}"
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM incomes WHERE chat_id = ? AND income_date LIKE ?",
        (chat_id, f"{ym}%"),
    )
    total = cur.fetchone()["total"]
    conn.close()
    return total


# --- Haftalik statistika ---
def weekly_stats(chat_id):
    conn = get_conn()
    cur = conn.cursor()
    since = (datetime.now(TIMEZONE).date() - timedelta(days=6)).isoformat()

    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE chat_id = ? AND expense_date >= ?",
        (chat_id, since),
    )
    exp_total = cur.fetchone()["total"]

    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM incomes WHERE chat_id = ? AND income_date >= ?",
        (chat_id, since),
    )
    inc_total = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE chat_id = ? AND task_date >= ? AND status = 'completed'",
        (chat_id, since),
    )
    tasks_done = cur.fetchone()["c"]

    cur.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE chat_id = ? AND task_date >= ? AND status = 'failed'",
        (chat_id, since),
    )
    tasks_failed = cur.fetchone()["c"]

    conn.close()
    return {
        "expense": exp_total,
        "income": inc_total,
        "tasks_done": tasks_done,
        "tasks_failed": tasks_failed,
    }


# --- Eksport (CSV) ---
def export_all_data_csv(chat_id) -> io.BytesIO:
    conn = get_conn()
    cur = conn.cursor()
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["=== XARAJATLAR ==="])
    writer.writerow(["Sana", "Toifa", "Summa", "Izoh"])
    cur.execute("SELECT * FROM expenses WHERE chat_id = ? ORDER BY expense_date", (chat_id,))
    for r in cur.fetchall():
        writer.writerow([r["expense_date"], r["category"], r["amount"], r["note"] or ""])

    writer.writerow([])
    writer.writerow(["=== DAROMADLAR ==="])
    writer.writerow(["Sana", "Summa", "Izoh"])
    cur.execute("SELECT * FROM incomes WHERE chat_id = ? ORDER BY income_date", (chat_id,))
    for r in cur.fetchall():
        writer.writerow([r["income_date"], r["amount"], r["note"] or ""])

    writer.writerow([])
    writer.writerow(["=== KREDITLAR ==="])
    writer.writerow(["Kim", "Boshlang'ich summa", "Qoldiq", "Oyning kuni", "Izoh", "Yopilganmi"])
    cur.execute("SELECT * FROM debts WHERE chat_id = ? ORDER BY id", (chat_id,))
    for r in cur.fetchall():
        writer.writerow([r["person"], r["amount"], r["remaining_amount"], r["due_day"], r["note"] or "", "Ha" if r["is_paid"] else "Yo'q"])

    conn.close()
    data = buf.getvalue().encode("utf-8-sig")
    return io.BytesIO(data)


# --- Rejalar (ish/sog'liq/sport) ---
def add_routine(chat_id, category, title, schedule):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO routines (chat_id, category, title, schedule_info) VALUES (?, ?, ?, ?)",
        (chat_id, category, title, schedule),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def list_routines(chat_id, category):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM routines WHERE chat_id = ? AND category = ? ORDER BY id DESC", (chat_id, category))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Kunlik xabar
# ---------------------------------------------------------------------------

def build_daily_message(chat_id: int) -> str:
    tasks = get_todays_tasks(chat_id)
    debts = list_debts(chat_id)
    _, total_exp = get_expenses_summary(chat_id)
    user = get_user_info(chat_id)
    budget = user["monthly_budget"] if user else 0
    pinned = list_pinned(chat_id)
    ishlar = list_routines(chat_id, "ish")
    soglik = list_routines(chat_id, "soglik")
    sport = list_routines(chat_id, "sport")
    today_day_num = datetime.now(TIMEZONE).day

    lines = ["🌟 <b>Xayrli tong! Bugungi shaxsiy sarhisobingiz:</b>\n"]

    if pinned:
        lines.append("📌 <b>Muhim eslatmalar:</b>")
        for p in pinned:
            lines.append(f"• {p['text']}")
        lines.append("")

    if ishlar:
        lines.append("🏛 <b>Davlat ishi / Vazifalar:</b>")
        for i in ishlar:
            lines.append(f"• {i['title']} ({i['schedule_info']})")
        lines.append("")

    if soglik:
        lines.append("💊 <b>Sog'liq va Vitaminlar:</b>")
        for s in soglik:
            lines.append(f"• {s['title']} ({s['schedule_info']})")
        lines.append("")

    if sport:
        lines.append("⚽ <b>Sport va Jismoniy faollik:</b>")
        for sp in sport:
            lines.append(f"• {sp['title']} ({sp['schedule_info']})")
        lines.append("")

    if tasks:
        lines.append("📋 <b>Kunlik vazifalar:</b>")
        for t in tasks:
            icon = "⏳ Jarayonda"
            if t["status"] == "completed":
                icon = "✅ Bajarildi"
            elif t["status"] == "failed":
                icon = "❌ Bajarilmadi"
            lines.append(f"• {t['title']} — {icon}")
        lines.append("")

    if debts:
        lines.append("💳 <b>Kredit va Oylik To'lovlar:</b>")
        for d in debts:
            alert = ""
            if d["due_day"]:
                if d["due_day"] == today_day_num:
                    alert = " ⚠️ <b>BUGUN TO'LOV KUNI!</b>"
                else:
                    days_left = d["due_day"] - today_day_num
                    if 0 < days_left <= 3:
                        alert = f" ⏰ <b>{days_left} kundan keyin to'lov!</b>"
            lines.append(
                f"• <b>{d['person']}</b>: Qoldiq <b>{format_amount(d['remaining_amount'])} so'm</b> "
                f"(Har oyning {d['due_day']}-kuni){alert}"
            )
        lines.append("")

    total_inc = monthly_income_total(chat_id)
    lines.append(f"💵 <b>Oylik Daromad:</b> {format_amount(total_inc)} so'm")
    lines.append(f"📊 <b>Oylik Xarajatlar:</b> {format_amount(total_exp)} so'm")
    balance = total_inc - total_exp
    lines.append(f"⚖️ <b>Balans:</b> {format_amount(balance)} so'm")
    if budget > 0:
        remainder = budget - total_exp
        lines.append(f"🎯 Oylik limit: {format_amount(budget)} so'm | Qoldi: <b>{format_amount(remainder)} so'm</b>")
        if remainder < 0:
            lines.append("⚠️ <i>Diqqat: Oylik byudjet limiti oshib ketdi!</i>")

    if not any([pinned, ishlar, soglik, sport, tasks, debts]) and total_exp == 0 and total_inc == 0:
        return "Xayrli tong! ☀️\n\nBugun sizda hech qanday ochiq band yo'q. 🎉"

    return "\n".join(lines)


def build_weekly_report(chat_id) -> str:
    stats = weekly_stats(chat_id)
    lines = ["📈 <b>So'nggi 7 kunlik hisobot:</b>\n"]
    lines.append(f"💵 Daromad: {format_amount(stats['income'])} so'm")
    lines.append(f"💸 Xarajat: {format_amount(stats['expense'])} so'm")
    balance = stats["income"] - stats["expense"]
    lines.append(f"⚖️ Balans: {format_amount(balance)} so'm\n")
    lines.append(f"✅ Bajarilgan vazifalar: {stats['tasks_done']}")
    lines.append(f"❌ Bajarilmagan vazifalar: {stats['tasks_failed']}")
    return "\n".join(lines)


def build_monthly_expense_message(chat_id, year, month):
    rows, total = get_expenses_summary(chat_id, year, month)
    title = f"📊 <b>{UZ_MONTHS[month]} {year}</b> oyi xarajatlari\n"
    if not rows:
        return title + "\nBu oyda hali xarajat kiritilmagan."
    lines = [title]
    for r in rows:
        lines.append(f"{r['category']}: {format_amount(r['total'])} so'm")
    lines.append(f"\n<b>Jami: {format_amount(total)} so'm</b>")
    return "\n".join(lines)


def month_nav_keyboard(year, month):
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    today = datetime.now(TIMEZONE).date()
    is_current = (year == today.year and month == today.month)
    buttons = [InlineKeyboardButton("◀️ Oldingi oy", callback_data=f"month:{prev_year}-{prev_month}")]
    if not is_current:
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        buttons.append(InlineKeyboardButton("Keyingi oy ▶️", callback_data=f"month:{next_year}-{next_month}"))
    return InlineKeyboardMarkup([buttons])


# ---------------------------------------------------------------------------
# Menyu navigatsiyasi
# ---------------------------------------------------------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    schedule_user_job(context.application, chat_id, DEFAULT_REMIND_TIME)
    await update.message.reply_text(
        "Assalomu alaykum! Men <b>Sarhisob ULTRA</b> botiman 🤖\n\n"
        "Kreditlaringiz, xarajatlaringiz, vazifalaringiz, maqsadlaringiz va "
        "muhim eslatmalaringizni kuzataman hamda har kuni ertalab (standart 08:00) "
        "to'liq sarhisobni yuboraman.\n\nQuyidagi tugmalar orqali boshqaring 👇",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def bugun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(build_daily_message(chat_id), parse_mode=ParseMode.HTML, reply_markup=MAIN_MENU)


async def to_kredit_menu(update, context):
    await update.message.reply_text("💳 Kreditlar bo'limi:", reply_markup=KREDIT_MENU)


async def to_xarajat_menu(update, context):
    await update.message.reply_text("💸 Xarajatlar bo'limi:", reply_markup=XARAJAT_MENU)


async def to_daromad_menu(update, context):
    await update.message.reply_text("💵 Daromad bo'limi:", reply_markup=DAROMAD_MENU)


async def to_vazifa_menu(update, context):
    await update.message.reply_text("📋 Vazifalar bo'limi:", reply_markup=VAZIFA_MENU)


async def to_maqsad_menu(update, context):
    await update.message.reply_text("🎯 Maqsadlar bo'limi:", reply_markup=MAQSAD_MENU)


async def to_muhim_menu(update, context):
    await update.message.reply_text("📌 Muhimlar bo'limi:", reply_markup=MUHIM_MENU)


async def to_rejalar_menu(update, context):
    await update.message.reply_text("🗓 Rejalar bo'limi:", reply_markup=REJALAR_MENU)


async def to_settings_menu(update, context):
    await update.message.reply_text("⚙️ Sozlamalar:", reply_markup=SETTINGS_MENU)


async def to_main_menu(update, context):
    await update.message.reply_text("Bosh menyu:", reply_markup=MAIN_MENU)


async def cancel_conv(update, context):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Kredit: qo'shish
# ---------------------------------------------------------------------------

async def credit_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Kimga / kimdan kredit? Ismini yozing:", reply_markup=STEP_MENU)
    return CR_PERSON


async def credit_person(update, context):
    context.user_data["cr_person"] = update.message.text.strip()
    await update.message.reply_text("Summasini kiriting (masalan 500000):", reply_markup=STEP_MENU)
    return CR_AMOUNT


async def credit_back_to_person(update, context):
    await update.message.reply_text("Kimga / kimdan kredit? Ismini yozing:", reply_markup=STEP_MENU)
    return CR_PERSON


async def credit_amount(update, context):
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return CR_AMOUNT
    context.user_data["cr_amount"] = amount
    await update.message.reply_text("Har oyning nechinchi kunida to'lanadi?", reply_markup=DUE_DAY_INLINE)
    return CR_DUE_DAY


async def credit_back_to_amount(update, context):
    await update.message.reply_text("Summasini kiriting (masalan 500000):", reply_markup=STEP_MENU)
    return CR_AMOUNT


async def credit_due_day_callback(update, context):
    query = update.callback_query
    await query.answer()
    value = query.data.split(":")[1]
    if value == "custom":
        await query.edit_message_text("Kunni raqamda yozing (1-31):")
        return CR_DUE_DAY
    context.user_data["cr_due_day"] = int(value)
    await query.edit_message_text(f"To'lov kuni: har oyning {value}-kuni\n\nIzoh qo'shasizmi?")
    await context.bot.send_message(chat_id=query.message.chat_id, text="Izoh qo'shasizmi?", reply_markup=YES_NO_INLINE)
    return CR_NOTE


async def credit_due_day_text(update, context):
    raw = update.message.text.strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 31):
        await update.message.reply_text("Iltimos, 1 dan 31 gacha raqam kiriting.")
        return CR_DUE_DAY
    context.user_data["cr_due_day"] = int(raw)
    await update.message.reply_text("Izoh qo'shasizmi?", reply_markup=YES_NO_INLINE)
    return CR_NOTE


async def credit_back_to_due_day(update, context):
    await update.message.reply_text("Har oyning nechinchi kunida to'lanadi?", reply_markup=DUE_DAY_INLINE)
    return CR_DUE_DAY


async def credit_note_choice(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "yn:yes":
        await query.edit_message_text("Izohni yozing:")
        return CR_NOTE
    return await finalize_credit(query.message.chat_id, context, note=None, edit_query=query)


async def credit_note_text(update, context):
    return await finalize_credit(update.effective_chat.id, context, note=update.message.text.strip(), message=update.message)


async def finalize_credit(chat_id, context, note, edit_query=None, message=None):
    person = context.user_data.pop("cr_person")
    amount = context.user_data.pop("cr_amount")
    due_day = context.user_data.pop("cr_due_day")
    add_debt(chat_id, person, amount, due_day, note)
    text = f"💳 Kredit qo'shildi: <b>{person}</b> — {format_amount(amount)} so'm (har oyning {due_day}-kuni)"
    if edit_query:
        await edit_query.edit_message_text(text, parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=chat_id, text="Kreditlar menyusi:", reply_markup=KREDIT_MENU)
    elif message:
        await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=KREDIT_MENU)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Kredit: ro'yxat va to'lov
# ---------------------------------------------------------------------------

async def show_credits_list(update, context):
    chat_id = update.effective_chat.id
    debts = list_debts(chat_id)
    if not debts:
        await update.message.reply_text("Ochiq kreditlar yo'q. 🎉", reply_markup=KREDIT_MENU)
        return
    lines = ["💳 <b>Ochiq kreditlar:</b>\n"]
    total_remaining = 0
    for d in debts:
        lines.append(
            f"• <b>{d['person']}</b>: Qoldiq <b>{format_amount(d['remaining_amount'])} so'm</b> "
            f"— har oyning {d['due_day']}-kuni"
        )
        total_remaining += d["remaining_amount"]
    lines.append(f"\n<b>Jami qoldiq: {format_amount(total_remaining)} so'm</b>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=KREDIT_MENU)


def build_credit_select_keyboard(debts):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"{d['person']} — qoldiq {format_amount(d['remaining_amount'])} so'm", callback_data=f"paycredit:{d['id']}"
            )]
            for d in debts
        ]
    )


async def pay_credit_start(update, context):
    chat_id = update.effective_chat.id
    debts = list_debts(chat_id)
    if not debts:
        await update.message.reply_text("Ochiq kreditlar yo'q.", reply_markup=KREDIT_MENU)
        return ConversationHandler.END
    await update.message.reply_text(
        "Qaysi kredit uchun to'lov kiritamiz?", reply_markup=build_credit_select_keyboard(debts)
    )
    await update.message.reply_text("(Bekor qilish uchun pastdagi tugmadan foydalaning)", reply_markup=STEP_MENU)
    return PAY_SELECT


async def pay_credit_select(update, context):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.split(":")[1])
    context.user_data["pay_debt_id"] = debt_id
    await query.edit_message_text("To'lov summasini kiriting:")
    await context.bot.send_message(chat_id=query.message.chat_id, text="💬 Summani shu yerga yozing:", reply_markup=STEP_MENU)
    return PAY_AMOUNT


async def pay_back_to_select(update, context):
    chat_id = update.effective_chat.id
    debts = list_debts(chat_id)
    if not debts:
        await update.message.reply_text("Ochiq kreditlar yo'q.", reply_markup=KREDIT_MENU)
        return ConversationHandler.END
    await update.message.reply_text(
        "Qaysi kredit uchun to'lov kiritamiz?", reply_markup=build_credit_select_keyboard(debts)
    )
    await update.message.reply_text("(Bekor qilish uchun pastdagi tugmadan foydalaning)", reply_markup=STEP_MENU)
    return PAY_SELECT


async def pay_credit_amount(update, context):
    chat_id = update.effective_chat.id
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        paid = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return PAY_AMOUNT
    debt_id = context.user_data.pop("pay_debt_id")
    is_closed, rem = update_debt_payment(chat_id, debt_id, paid)
    if is_closed is None:
        await update.message.reply_text("Kredit topilmadi.", reply_markup=KREDIT_MENU)
    elif is_closed:
        await update.message.reply_text("🎉 Kredit to'liq yopildi!", reply_markup=KREDIT_MENU)
    else:
        await update.message.reply_text(
            f"✅ To'lov qabul qilindi. Qoldiq: <b>{format_amount(rem)} so'm</b>",
            parse_mode=ParseMode.HTML, reply_markup=KREDIT_MENU,
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Xarajat qo'shish
# ---------------------------------------------------------------------------

async def expense_add_start(update, context):
    ensure_user(update.effective_chat.id)
    context.user_data["exp_step"] = "amount"
    await update.message.reply_text("Xarajat summasini kiriting (masalan 25000):", reply_markup=STEP_MENU)
    return EXP_AMOUNT


def build_category_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(EXPENSE_CATEGORIES[i], callback_data=f"cat:{i}"),
             InlineKeyboardButton(EXPENSE_CATEGORIES[i + 1], callback_data=f"cat:{i + 1}")]
            for i in range(0, len(EXPENSE_CATEGORIES) - 1, 2)
        ]
    )


async def expense_amount(update, context):
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return EXP_AMOUNT
    context.user_data["exp_amount"] = amount
    context.user_data["exp_step"] = "category"
    await update.message.reply_text("Qaysi toifaga tegishli?", reply_markup=build_category_keyboard())
    return EXP_NOTE


async def expense_category(update, context):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    context.user_data["exp_category"] = EXPENSE_CATEGORIES[idx]
    context.user_data["exp_step"] = "note_choice"
    await query.edit_message_text(f"Toifa: {EXPENSE_CATEGORIES[idx]}\n\nIzoh qo'shasizmi?")
    await context.bot.send_message(chat_id=query.message.chat_id, text="Izoh qo'shasizmi?", reply_markup=YES_NO_INLINE)
    return EXP_NOTE


async def expense_back(update, context):
    step = context.user_data.get("exp_step")
    if step in ("note_choice", "note_text"):
        context.user_data.pop("exp_category", None)
        context.user_data["exp_step"] = "category"
        await update.message.reply_text("Qaysi toifaga tegishli?", reply_markup=build_category_keyboard())
        return EXP_NOTE
    context.user_data.pop("exp_amount", None)
    context.user_data["exp_step"] = "amount"
    await update.message.reply_text("Xarajat summasini kiriting (masalan 25000):", reply_markup=STEP_MENU)
    return EXP_AMOUNT


async def expense_note_choice(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "yn:yes":
        context.user_data["exp_step"] = "note_text"
        await query.edit_message_text("Izohni yozing:")
        return EXP_NOTE
    return await finalize_expense(query.message.chat_id, context, note=None, edit_query=query)


async def expense_note_text(update, context):
    return await finalize_expense(update.effective_chat.id, context, note=update.message.text.strip(), message=update.message)


async def finalize_expense(chat_id, context, note, edit_query=None, message=None):
    amount = context.user_data.pop("exp_amount")
    category = context.user_data.pop("exp_category")
    add_expense(chat_id, category, amount, note)
    _, total_exp = get_expenses_summary(chat_id)
    user = get_user_info(chat_id)
    budget = user["monthly_budget"] if user else 0
    text = f"💸 Xarajat qo'shildi: {category} — {format_amount(amount)} so'm"
    if budget > 0 and total_exp > budget:
        text += f"\n\n⚠️ Oylik limit oshib ketdi! (Jami: {format_amount(total_exp)} so'm)"
    if edit_query:
        await edit_query.edit_message_text(text)
        await context.bot.send_message(chat_id=chat_id, text="Xarajatlar menyusi:", reply_markup=XARAJAT_MENU)
    elif message:
        await message.reply_text(text, reply_markup=XARAJAT_MENU)
    return ConversationHandler.END


async def show_monthly_expenses(update, context):
    chat_id = update.effective_chat.id
    today = datetime.now(TIMEZONE).date()
    msg = build_monthly_expense_message(chat_id, today.year, today.month)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=month_nav_keyboard(today.year, today.month))
    await update.message.reply_text("Xarajatlar menyusi:", reply_markup=XARAJAT_MENU)


async def month_nav_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    _, ym = query.data.split(":")
    year, month = map(int, ym.split("-"))
    msg = build_monthly_expense_message(chat_id, year, month)
    await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=month_nav_keyboard(year, month))


async def budget_start(update, context):
    ensure_user(update.effective_chat.id)
    user = get_user_info(update.effective_chat.id)
    current = user["monthly_budget"] if user else 0
    text = "Oylik xarajat limitini kiriting (masalan 3000000):"
    if current:
        text = f"Joriy limit: {format_amount(current)} so'm.\n\n" + text
    await update.message.reply_text(text, reply_markup=CANCEL_MENU)
    return BUDGET_AMOUNT


async def budget_amount(update, context):
    chat_id = update.effective_chat.id
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        budget = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return BUDGET_AMOUNT
    set_user_budget(chat_id, budget)
    await update.message.reply_text(
        f"✅ Oylik limit <b>{format_amount(budget)} so'm</b> qilib belgilandi.",
        parse_mode=ParseMode.HTML, reply_markup=XARAJAT_MENU,
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Daromadlar
# ---------------------------------------------------------------------------

async def income_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Daromad summasini kiriting (masalan 3000000):", reply_markup=STEP_MENU)
    return INC_AMOUNT


async def income_amount(update, context):
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return INC_AMOUNT
    context.user_data["inc_amount"] = amount
    await update.message.reply_text("Izoh qo'shasizmi? (masalan: oylik maosh)", reply_markup=YES_NO_INLINE)
    return INC_NOTE


async def income_back_to_amount(update, context):
    context.user_data.pop("inc_amount", None)
    await update.message.reply_text("Daromad summasini kiriting (masalan 3000000):", reply_markup=STEP_MENU)
    return INC_AMOUNT


async def income_note_choice(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "yn:yes":
        await query.edit_message_text("Izohni yozing:")
        return INC_NOTE
    return await finalize_income(query.message.chat_id, context, note=None, edit_query=query)


async def income_note_text(update, context):
    return await finalize_income(update.effective_chat.id, context, note=update.message.text.strip(), message=update.message)


async def finalize_income(chat_id, context, note, edit_query=None, message=None):
    amount = context.user_data.pop("inc_amount")
    add_income(chat_id, amount, note)
    text = f"✅ Daromad qo'shildi: {format_amount(amount)} so'm" + (f" ({note})" if note else "")
    if edit_query:
        await edit_query.edit_message_text(text)
        await context.bot.send_message(chat_id=chat_id, text="Daromad menyusi:", reply_markup=DAROMAD_MENU)
    elif message:
        await message.reply_text(text, reply_markup=DAROMAD_MENU)
    return ConversationHandler.END


async def show_recent_incomes(update, context):
    chat_id = update.effective_chat.id
    incomes = list_recent_incomes(chat_id)
    if not incomes:
        await update.message.reply_text("Hozircha daromad kiritilmagan.", reply_markup=DAROMAD_MENU)
        return
    lines = ["📋 <b>So'nggi daromadlar:</b>\n"]
    for i in incomes:
        note = f" ({i['note']})" if i["note"] else ""
        lines.append(f"{i['income_date']} | {format_amount(i['amount'])} so'm{note}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=DAROMAD_MENU)


async def show_monthly_balance(update, context):
    chat_id = update.effective_chat.id
    today = datetime.now(TIMEZONE).date()
    total_inc = monthly_income_total(chat_id, today.year, today.month)
    _, total_exp = get_expenses_summary(chat_id, today.year, today.month)
    balance = total_inc - total_exp
    text = (
        f"📊 <b>{UZ_MONTHS[today.month]} {today.year}</b> oyi balansi\n\n"
        f"💵 Daromad: {format_amount(total_inc)} so'm\n"
        f"💸 Xarajat: {format_amount(total_exp)} so'm\n"
        f"⚖️ <b>Balans: {format_amount(balance)} so'm</b>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=DAROMAD_MENU)


# ---------------------------------------------------------------------------
# Haftalik hisobot
# ---------------------------------------------------------------------------

async def show_weekly_report(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text(build_weekly_report(chat_id), parse_mode=ParseMode.HTML, reply_markup=MAIN_MENU)


# ---------------------------------------------------------------------------
# Eksport
# ---------------------------------------------------------------------------

async def export_data(update, context):
    chat_id = update.effective_chat.id
    csv_bytes = export_all_data_csv(chat_id)
    filename = f"sarhisob_{datetime.now(TIMEZONE).strftime('%Y%m%d')}.csv"
    await update.message.reply_document(
        document=csv_bytes, filename=filename, caption="📤 Barcha ma'lumotlaringiz CSV fayl ko'rinishida.",
        reply_markup=SETTINGS_MENU,
    )


# ---------------------------------------------------------------------------
# 🎙 AI: Ovozli xabar orqali xarajat/daromad kiritish
# ---------------------------------------------------------------------------

def _transcribe_and_parse(audio_bytes: bytes):
    """Sinxron (bloklovchi) funksiya — asyncio.to_thread ichida chaqiriladi."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg"
    transcript_resp = client.audio.transcriptions.create(
        model="whisper-1", file=audio_file, language="uz"
    )
    transcript = transcript_resp.text.strip()

    system_prompt = (
        "Foydalanuvchi moliyaviy xarajat yoki daromad haqida gapiradi (o'zbek tilida). "
        "Matndan faqat quyidagi JSON obyektni chiqar, boshqa hech narsa yozma:\n"
        '{"type": "expense" | "income" | "unknown", '
        '"amount": raqam yoki null, '
        '"category": agar type="expense" bo\'lsa quyidagi ro\'yxatdan bittasi yoki null: '
        + ", ".join(EXPENSE_CATEGORIES) + ", "
        '"note": qisqa izoh yoki null}\n'
        "Agar summani aniq bilib bo'lmasa yoki bu xarajat/daromad haqida bo'lmasa, "
        '"type" ni "unknown" qil.'
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    import json
    parsed = json.loads(completion.choices[0].message.content)
    return transcript, parsed


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not OPENAI_API_KEY:
        await update.message.reply_text(
            "🎙 Ovozli xabarni qabul qildim, lekin AI integratsiyasi hali sozlanmagan.\n\n"
            "Administrator Railway'ning \"Variables\" bo'limiga OPENAI_API_KEY "
            "qo'shishi kerak. Hozircha tugmalar orqali kiriting.",
            reply_markup=MAIN_MENU,
        )
        return

    ensure_user(chat_id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        transcript, parsed = await asyncio.to_thread(_transcribe_and_parse, bytes(file_bytes))
    except Exception as e:
        logger.warning("AI ovoz xatosi (chat_id=%s): %s", chat_id, e)
        await update.message.reply_text(
            "😕 Kechirasiz, ovozli xabarni tushuna olmadim. Qaytadan urinib ko'ring "
            "yoki tugmalar orqali kiriting.",
            reply_markup=MAIN_MENU,
        )
        return

    msg_type = parsed.get("type")
    amount = parsed.get("amount")

    if msg_type not in ("expense", "income") or not amount:
        await update.message.reply_text(
            f"🎙 Eshitdim: \"{transcript}\"\n\n"
            "Bu xarajat yoki daromad ekanini va summasini aniq tushuna olmadim. "
            "Iltimos tugmalar orqali kiriting yoki aniqroq gapirib ko'ring "
            "(masalan: \"taksiga 25 ming so'm sarfladim\").",
            reply_markup=MAIN_MENU,
        )
        return

    note = parsed.get("note") or None

    if msg_type == "expense":
        category = parsed.get("category")
        if category not in EXPENSE_CATEGORIES:
            category = "🔧 Boshqa"
        eid = add_expense(chat_id, category, amount, note)
        text = (
            f"🎙 Eshitdim: \"{transcript}\"\n\n"
            f"✅ Xarajat qo'shildi: {category} — {format_amount(amount)} so'm"
            + (f" ({note})" if note else "")
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Noto'g'ri, bekor qilish", callback_data=f"undoexp:{eid}")]])
    else:
        iid = add_income(chat_id, amount, note)
        text = (
            f"🎙 Eshitdim: \"{transcript}\"\n\n"
            f"✅ Daromad qo'shildi: {format_amount(amount)} so'm"
            + (f" ({note})" if note else "")
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Noto'g'ri, bekor qilish", callback_data=f"undoinc:{iid}")]])

    await update.message.reply_text(text, reply_markup=kb)


async def undo_expense_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    eid = int(query.data.split(":")[1])
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE chat_id = ? AND id = ?", (chat_id, eid))
    conn.commit()
    conn.close()
    await query.edit_message_text("🗑 Bekor qilindi, xarajat o'chirildi.")


async def undo_income_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    iid = int(query.data.split(":")[1])
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM incomes WHERE chat_id = ? AND id = ?", (chat_id, iid))
    conn.commit()
    conn.close()
    await query.edit_message_text("🗑 Bekor qilindi, daromad o'chirildi.")


# ---------------------------------------------------------------------------
# Vazifalar
# ---------------------------------------------------------------------------

async def task_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Vazifa matnini yozing:", reply_markup=CANCEL_MENU)
    return TASK_TEXT


async def task_add_text(update, context):
    chat_id = update.effective_chat.id
    add_task(chat_id, update.message.text.strip())
    await update.message.reply_text("✅ Vazifa qo'shildi.", reply_markup=VAZIFA_MENU)
    return ConversationHandler.END


async def show_todays_tasks(update, context):
    chat_id = update.effective_chat.id
    tasks = get_todays_tasks(chat_id)
    if not tasks:
        await update.message.reply_text("Bugungi vazifalar yo'q.", reply_markup=VAZIFA_MENU)
        return
    lines = ["📋 <b>Bugungi vazifalar:</b>\n"]
    for t in tasks:
        icon = "✅ Bajarildi" if t["status"] == "completed" else ("❌ Bajarilmadi" if t["status"] == "failed" else "⏳ Jarayonda")
        lines.append(f"• {t['title']} — {icon}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=VAZIFA_MENU)


async def show_tasks_for_done(update, context):
    chat_id = update.effective_chat.id
    tasks = get_todays_tasks(chat_id, only_pending=True)
    if not tasks:
        await update.message.reply_text("Jarayondagi vazifalar yo'q.", reply_markup=VAZIFA_MENU)
        return
    buttons = [[InlineKeyboardButton(t["title"][:40], callback_data=f"taskdone:{t['id']}")] for t in tasks]
    await update.message.reply_text("Qaysi vazifa bajarildi?", reply_markup=InlineKeyboardMarkup(buttons))


async def task_done_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    tid = int(query.data.split(":")[1])
    if update_task_status(chat_id, tid, "completed"):
        await query.edit_message_text("✅ Vazifa bajarildi deb belgilandi!")
    else:
        await query.edit_message_text("Topilmadi.")


async def show_failed_tasks(update, context):
    chat_id = update.effective_chat.id
    # avvalo bugungi ro'yxatni so'rab, muddati o'tgan vazifalarni "failed"ga o'tkazamiz
    get_todays_tasks(chat_id)
    failed = list_failed_tasks(chat_id)
    if not failed:
        await update.message.reply_text("Bajarilmagan vazifalar yo'q. 🎉", reply_markup=VAZIFA_MENU)
        return
    lines = ["❌ <b>Bajarilmagan vazifalar:</b>\n"]
    for t in failed:
        lines.append(f"• {t['title']} ({t['task_date']})")
    lines.append("\n<i>Tozalash uchun pastdagi tugmalardan foydalaning.</i>")
    buttons = [[InlineKeyboardButton(f"🗑 {t['title'][:35]}", callback_data=f"clearfailed:{t['id']}")] for t in failed]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=VAZIFA_MENU)
    await update.message.reply_text("Ro'yxatdan olib tashlash:", reply_markup=InlineKeyboardMarkup(buttons))


async def clear_failed_task_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    tid = int(query.data.split(":")[1])
    if clear_failed_task(chat_id, tid):
        await query.edit_message_text("🗑 Ro'yxatdan olib tashlandi.")
    else:
        await query.edit_message_text("Topilmadi.")


# ---------------------------------------------------------------------------
# Maqsadlar
# ---------------------------------------------------------------------------

async def goal_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Maqsad sarlavhasini yozing (masalan: Mashina uchun jamg'arish):", reply_markup=STEP_MENU)
    return GOAL_TITLE


async def goal_title(update, context):
    context.user_data["goal_title"] = update.message.text.strip()
    await update.message.reply_text(
        "Bu — pul yig'ish (jamg'arma) maqsadimi? (Ha bo'lsa, necha foiz bajarilganini kuzatib boraman)",
        reply_markup=YES_NO_INLINE,
    )
    return GOAL_SAVINGS_CHOICE


async def goal_back_to_title(update, context):
    context.user_data.pop("goal_title", None)
    await update.message.reply_text("Maqsad sarlavhasini yozing:", reply_markup=STEP_MENU)
    return GOAL_TITLE


async def goal_savings_choice(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "yn:yes":
        await query.edit_message_text("Maqsad summasini kiriting (masalan 5000000):")
        return GOAL_TARGET
    context.user_data["goal_target"] = None
    await query.edit_message_text("Muddat belgilaysizmi?")
    await context.bot.send_message(chat_id=query.message.chat_id, text="Muddat belgilaysizmi?", reply_markup=YES_NO_INLINE)
    return GOAL_DEADLINE


async def goal_target_amount(update, context):
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        target = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return GOAL_TARGET
    context.user_data["goal_target"] = target
    await update.message.reply_text("Muddat belgilaysizmi?", reply_markup=YES_NO_INLINE)
    return GOAL_DEADLINE


async def goal_back_to_savings_choice(update, context):
    context.user_data.pop("goal_target", None)
    await update.message.reply_text(
        "Bu — pul yig'ish (jamg'arma) maqsadimi?", reply_markup=YES_NO_INLINE
    )
    return GOAL_SAVINGS_CHOICE


async def goal_deadline_choice(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "yn:yes":
        await query.edit_message_text("Muddatni yozing (masalan: 2026-yil dekabr):")
        return GOAL_DEADLINE
    return await finalize_goal(query.message.chat_id, context, deadline="Muddatsiz", edit_query=query)


async def goal_deadline_text(update, context):
    return await finalize_goal(update.effective_chat.id, context, deadline=update.message.text.strip(), message=update.message)


async def finalize_goal(chat_id, context, deadline, edit_query=None, message=None):
    title = context.user_data.pop("goal_title")
    target = context.user_data.pop("goal_target", None)
    add_goal(chat_id, title, deadline, target)
    text = f"🎯 Maqsad qo'shildi: <b>{title}</b> ({deadline})"
    if target:
        text += f"\n💰 Maqsad summasi: {format_amount(target)} so'm (hozircha 0%)"
    if edit_query:
        await edit_query.edit_message_text(text, parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=chat_id, text="Maqsadlar menyusi:", reply_markup=MAQSAD_MENU)
    elif message:
        await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAQSAD_MENU)
    return ConversationHandler.END


def _progress_bar(current, target, length=10):
    pct = min(100, int((current / target) * 100)) if target else 0
    filled = int(length * pct / 100)
    return "▓" * filled + "░" * (length - filled) + f" {pct}%"


async def show_goals_list(update, context):
    chat_id = update.effective_chat.id
    goals = list_goals(chat_id)
    if not goals:
        await update.message.reply_text("Maqsadlar yo'q.", reply_markup=MAQSAD_MENU)
        return
    lines = ["🎯 <b>Maqsadlar:</b>\n"]
    for g in goals:
        status = "✅" if g["is_achieved"] else "🎯"
        line = f"• {g['title']} ({g['deadline']}) — {status}"
        if g["target_amount"]:
            bar = _progress_bar(g["current_amount"], g["target_amount"])
            line += f"\n  {format_amount(g['current_amount'])} / {format_amount(g['target_amount'])} so'm\n  {bar}"
        lines.append(line)
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=MAQSAD_MENU)


async def show_goals_for_achieve(update, context):
    chat_id = update.effective_chat.id
    goals = list_goals(chat_id, only_open=True)
    if not goals:
        await update.message.reply_text("Ochiq maqsadlar yo'q.", reply_markup=MAQSAD_MENU)
        return
    buttons = [[InlineKeyboardButton(g["title"][:40], callback_data=f"goalachieve:{g['id']}")] for g in goals]
    await update.message.reply_text("Qaysi maqsadga erishdingiz?", reply_markup=InlineKeyboardMarkup(buttons))


async def goal_achieve_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    gid = int(query.data.split(":")[1])
    if achieve_goal(chat_id, gid):
        await query.edit_message_text("🎉 Tabriklaymiz! Maqsadga erishildi deb belgilandi.")
    else:
        await query.edit_message_text("Topilmadi.")


# --- Maqsadga pul qo'shish (jamg'arma) ---

async def contrib_start(update, context):
    chat_id = update.effective_chat.id
    goals = list_savings_goals(chat_id)
    if not goals:
        await update.message.reply_text(
            "Jamg'arma turidagi (summa belgilangan) ochiq maqsadlaringiz yo'q.\n"
            "Yangi maqsad qo'shganda \"Bu jamg'arma maqsadimi?\" degan savolga \"Ha\" deb javob bering.",
            reply_markup=MAQSAD_MENU,
        )
        return ConversationHandler.END
    buttons = [
        [InlineKeyboardButton(
            f"{g['title']} ({format_amount(g['current_amount'])}/{format_amount(g['target_amount'])})",
            callback_data=f"contrib:{g['id']}",
        )]
        for g in goals
    ]
    await update.message.reply_text("Qaysi maqsadga pul qo'shamiz?", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("(Bekor qilish uchun pastdagi tugmadan foydalaning)", reply_markup=STEP_MENU)
    return CONTRIB_SELECT


async def contrib_select(update, context):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.split(":")[1])
    context.user_data["contrib_goal_id"] = gid
    await query.edit_message_text("Qancha pul qo'shamiz?")
    await context.bot.send_message(chat_id=query.message.chat_id, text="💬 Summani shu yerga yozing:", reply_markup=STEP_MENU)
    return CONTRIB_AMOUNT


async def contrib_back_to_select(update, context):
    return await contrib_start(update, context)


async def contrib_amount(update, context):
    chat_id = update.effective_chat.id
    raw = update.message.text.replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return CONTRIB_AMOUNT
    gid = context.user_data.pop("contrib_goal_id")
    result = contribute_to_goal(chat_id, gid, amount)
    if result is None:
        await update.message.reply_text("Maqsad topilmadi.", reply_markup=MAQSAD_MENU)
        return ConversationHandler.END
    goal = get_goal(chat_id, gid)
    bar = _progress_bar(result["new_amount"], result["target"])
    text = (
        f"✅ {format_amount(amount)} so'm qo'shildi: <b>{goal['title']}</b>\n"
        f"{format_amount(result['new_amount'])} / {format_amount(result['target'])} so'm\n{bar}"
    )
    if result["achieved"]:
        text += "\n\n🎉 Tabriklaymiz! Maqsadga to'liq erishdingiz!"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAQSAD_MENU)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Muhim eslatmalar
# ---------------------------------------------------------------------------

async def pinned_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Muhim eslatma matnini yozing:", reply_markup=CANCEL_MENU)
    return PINNED_TEXT


async def pinned_add_text(update, context):
    chat_id = update.effective_chat.id
    add_pinned(chat_id, update.message.text.strip())
    await update.message.reply_text("📌 Muhimga qo'shildi.", reply_markup=MUHIM_MENU)
    return ConversationHandler.END


async def show_pinned_list(update, context):
    chat_id = update.effective_chat.id
    pinned = list_pinned(chat_id)
    if not pinned:
        await update.message.reply_text("Muhim eslatmalar yo'q.", reply_markup=MUHIM_MENU)
        return
    lines = ["📌 <b>Muhim eslatmalar:</b>\n"] + [f"• {p['text']}" for p in pinned]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=MUHIM_MENU)


async def show_pinned_for_delete(update, context):
    chat_id = update.effective_chat.id
    pinned = list_pinned(chat_id)
    if not pinned:
        await update.message.reply_text("Muhim eslatmalar yo'q.", reply_markup=MUHIM_MENU)
        return
    buttons = [[InlineKeyboardButton(p["text"][:40], callback_data=f"delpinned:{p['id']}")] for p in pinned]
    await update.message.reply_text("Qaysi eslatmani o'chiramiz?", reply_markup=InlineKeyboardMarkup(buttons))


async def pinned_delete_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    pid = int(query.data.split(":")[1])
    if delete_pinned(chat_id, pid):
        await query.edit_message_text("🗑 O'chirildi.")
    else:
        await query.edit_message_text("Topilmadi.")


# ---------------------------------------------------------------------------
# Rejalar (ish/sog'liq/sport)
# ---------------------------------------------------------------------------

async def routine_add_start(update, context):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text("Qaysi turkumga tegishli?", reply_markup=ROUTINE_CAT_INLINE)
    await update.message.reply_text("(Bekor qilish uchun pastdagi tugmadan foydalaning)", reply_markup=STEP_MENU)
    return ROUTINE_CATEGORY


async def routine_category_callback(update, context):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":")[1]
    context.user_data["routine_category"] = category
    await query.edit_message_text(f"Turkum: {ROUTINE_LABELS[category]}\n\nSarlavhasini yozing (masalan: Vitamin D ichish):")
    return ROUTINE_TITLE


async def routine_title(update, context):
    context.user_data["routine_title"] = update.message.text.strip()
    await update.message.reply_text("Qachon / qanday tartibda? (masalan: Har kuni ertalab):", reply_markup=STEP_MENU)
    return ROUTINE_SCHEDULE


async def routine_back_to_category(update, context):
    context.user_data.pop("routine_category", None)
    await update.message.reply_text("Qaysi turkumga tegishli?", reply_markup=ROUTINE_CAT_INLINE)
    await update.message.reply_text("(Bekor qilish uchun pastdagi tugmadan foydalaning)", reply_markup=STEP_MENU)
    return ROUTINE_CATEGORY


async def routine_back_to_title(update, context):
    context.user_data.pop("routine_title", None)
    category = context.user_data.get("routine_category")
    label = ROUTINE_LABELS.get(category, "")
    await update.message.reply_text(
        f"Turkum: {label}\n\nSarlavhasini yozing (masalan: Vitamin D ichish):", reply_markup=STEP_MENU
    )
    return ROUTINE_TITLE


async def routine_schedule(update, context):
    chat_id = update.effective_chat.id
    category = context.user_data.pop("routine_category")
    title = context.user_data.pop("routine_title")
    schedule = update.message.text.strip()
    add_routine(chat_id, category, title, schedule)
    await update.message.reply_text(
        f"✅ {ROUTINE_LABELS[category]} rejasiga qo'shildi: <b>{title}</b> ({schedule})",
        parse_mode=ParseMode.HTML, reply_markup=REJALAR_MENU,
    )
    return ConversationHandler.END


async def show_routines(update, context, category):
    chat_id = update.effective_chat.id
    routines = list_routines(chat_id, category)
    label = ROUTINE_LABELS[category]
    if not routines:
        await update.message.reply_text(f"{label} rejalari yo'q.", reply_markup=REJALAR_MENU)
        return
    lines = [f"{label} <b>rejalari:</b>\n"] + [f"• {r['title']} ({r['schedule_info']})" for r in routines]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=REJALAR_MENU)


async def show_routines_ish(update, context):
    await show_routines(update, context, "ish")


async def show_routines_soglik(update, context):
    await show_routines(update, context, "soglik")


async def show_routines_sport(update, context):
    await show_routines(update, context, "sport")


# ---------------------------------------------------------------------------
# Sozlamalar: vaqt
# ---------------------------------------------------------------------------

async def time_change_start(update, context):
    await update.message.reply_text("Har kuni qaysi vaqtda eslatib turay?", reply_markup=TIME_INLINE)
    return TIME_CUSTOM


async def time_choice_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    value = query.data.split(":", 1)[1]
    if value == "custom":
        await query.edit_message_text("Vaqtni HH:MM formatida yozing (masalan 07:15):")
        return TIME_CUSTOM
    ensure_user(chat_id)
    set_remind_time(chat_id, value)
    schedule_user_job(context.application, chat_id, value)
    await query.edit_message_text(f"✅ Endi har kuni soat {value} da eslatib turaman.")
    await context.bot.send_message(chat_id=chat_id, text="Sozlamalar:", reply_markup=SETTINGS_MENU)
    return ConversationHandler.END


async def time_custom_text(update, context):
    raw = update.message.text.strip()
    chat_id = update.effective_chat.id
    try:
        datetime.strptime(raw, "%H:%M")
    except ValueError:
        await update.message.reply_text("Noto'g'ri format. Masalan: 07:15")
        return TIME_CUSTOM
    ensure_user(chat_id)
    set_remind_time(chat_id, raw)
    schedule_user_job(context.application, chat_id, raw)
    await update.message.reply_text(f"✅ Endi har kuni soat {raw} da eslatib turaman.", reply_markup=SETTINGS_MENU)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Kunlik job
# ---------------------------------------------------------------------------

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    try:
        await context.bot.send_message(chat_id=chat_id, text=build_daily_message(chat_id), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning("Xabar yuborishda xato (chat_id=%s): %s", chat_id, e)


def schedule_user_job(application: Application, chat_id: int, hhmm: str):
    job_name = f"daily_{chat_id}"
    for j in application.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()
    h, m = map(int, hhmm.split(":"))
    application.job_queue.run_daily(
        send_daily_reminder,
        time=time(hour=h, minute=m, tzinfo=TIMEZONE),
        chat_id=chat_id,
        name=job_name,
    )


async def schedule_all_users(application: Application):
    for row in get_all_users():
        schedule_user_job(application, row["chat_id"], row["remind_time"])


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. Muhit o'zgaruvchisida BOT_TOKEN ni belgilang.")

    init_db()
    application = Application.builder().token(BOT_TOKEN).post_init(schedule_all_users).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("bugun", bugun_cmd))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    application.add_handler(MessageHandler(filters.Regex("^💳 Kreditlar$"), to_kredit_menu))
    application.add_handler(MessageHandler(filters.Regex("^💸 Xarajatlar$"), to_xarajat_menu))
    application.add_handler(MessageHandler(filters.Regex("^💵 Daromad$"), to_daromad_menu))
    application.add_handler(MessageHandler(filters.Regex("^📈 Haftalik hisobot$"), show_weekly_report))
    application.add_handler(MessageHandler(filters.Regex("^📋 Vazifalar$"), to_vazifa_menu))
    application.add_handler(MessageHandler(filters.Regex("^🎯 Maqsadlar$"), to_maqsad_menu))
    application.add_handler(MessageHandler(filters.Regex("^📌 Muhimlar$"), to_muhim_menu))
    application.add_handler(MessageHandler(filters.Regex("^🗓 Rejalar$"), to_rejalar_menu))
    application.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"), to_settings_menu))
    application.add_handler(MessageHandler(filters.Regex("^📅 Bugungi holat$"), bugun_cmd))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Orqaga$"), to_main_menu))

    application.add_handler(MessageHandler(filters.Regex("^📋 Kreditlar ro'yxati$"), show_credits_list))
    application.add_handler(MessageHandler(filters.Regex("^📋 Bugungi vazifalar$"), show_todays_tasks))
    application.add_handler(MessageHandler(filters.Regex("^✅ Bajarildi belgilash$"), show_tasks_for_done))
    application.add_handler(MessageHandler(filters.Regex("^❌ Bajarilmagan vazifalar$"), show_failed_tasks))
    application.add_handler(MessageHandler(filters.Regex("^📋 Maqsadlar ro'yxati$"), show_goals_list))
    application.add_handler(MessageHandler(filters.Regex("^✅ Erishildi belgilash$"), show_goals_for_achieve))
    application.add_handler(MessageHandler(filters.Regex("^📋 Muhimlar ro'yxati$"), show_pinned_list))
    application.add_handler(MessageHandler(filters.Regex("^🗑 Muhimni o'chirish$"), show_pinned_for_delete))
    application.add_handler(MessageHandler(filters.Regex("^📊 Oylik xarajatlarim$"), show_monthly_expenses))
    application.add_handler(MessageHandler(filters.Regex("^📋 Daromadlar ro'yxati$"), show_recent_incomes))
    application.add_handler(MessageHandler(filters.Regex("^📊 Oylik balans$"), show_monthly_balance))
    application.add_handler(MessageHandler(filters.Regex("^📤 Ma'lumotlarni eksport qilish$"), export_data))
    application.add_handler(MessageHandler(filters.Regex("^🏛 Ish rejalari$"), show_routines_ish))
    application.add_handler(MessageHandler(filters.Regex("^💊 Sog'liq rejalari$"), show_routines_soglik))
    application.add_handler(MessageHandler(filters.Regex("^⚽ Sport rejalari$"), show_routines_sport))

    BACK_RE = "^◀️ Oldingi qadam$"
    CANCEL_RE = "^❌ Bekor qilish$"

    credit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Kredit qo'shish$"), credit_add_start)],
        states={
            CR_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, credit_person)],
            CR_AMOUNT: [
                MessageHandler(filters.Regex(BACK_RE), credit_back_to_person),
                MessageHandler(filters.TEXT & ~filters.COMMAND, credit_amount),
            ],
            CR_DUE_DAY: [
                MessageHandler(filters.Regex(BACK_RE), credit_back_to_amount),
                CallbackQueryHandler(credit_due_day_callback, pattern="^day:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, credit_due_day_text),
            ],
            CR_NOTE: [
                MessageHandler(filters.Regex(BACK_RE), credit_back_to_due_day),
                CallbackQueryHandler(credit_note_choice, pattern="^yn:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, credit_note_text),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    pay_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💵 To'lov qilish$"), pay_credit_start)],
        states={
            PAY_SELECT: [CallbackQueryHandler(pay_credit_select, pattern="^paycredit:")],
            PAY_AMOUNT: [
                MessageHandler(filters.Regex(BACK_RE), pay_back_to_select),
                MessageHandler(filters.TEXT & ~filters.COMMAND, pay_credit_amount),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Xarajat qo'shish$"), expense_add_start)],
        states={
            EXP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXP_NOTE: [
                MessageHandler(filters.Regex(BACK_RE), expense_back),
                CallbackQueryHandler(expense_category, pattern="^cat:"),
                CallbackQueryHandler(expense_note_choice, pattern="^yn:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_note_text),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    budget_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Limit belgilash$"), budget_start)],
        states={BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_amount)]},
        fallbacks=[MessageHandler(filters.Regex(CANCEL_RE), cancel_conv)],
    )

    income_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Daromad qo'shish$"), income_add_start)],
        states={
            INC_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_amount)],
            INC_NOTE: [
                MessageHandler(filters.Regex(BACK_RE), income_back_to_amount),
                CallbackQueryHandler(income_note_choice, pattern="^yn:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, income_note_text),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    task_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Vazifa qo'shish$"), task_add_start)],
        states={TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_add_text)]},
        fallbacks=[MessageHandler(filters.Regex(CANCEL_RE), cancel_conv)],
    )

    goal_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Maqsad qo'shish$"), goal_add_start)],
        states={
            GOAL_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_title)],
            GOAL_SAVINGS_CHOICE: [
                MessageHandler(filters.Regex(BACK_RE), goal_back_to_title),
                CallbackQueryHandler(goal_savings_choice, pattern="^yn:"),
            ],
            GOAL_TARGET: [
                MessageHandler(filters.Regex(BACK_RE), goal_back_to_savings_choice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_target_amount),
            ],
            GOAL_DEADLINE: [
                MessageHandler(filters.Regex(BACK_RE), goal_back_to_savings_choice),
                CallbackQueryHandler(goal_deadline_choice, pattern="^yn:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_deadline_text),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    contrib_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Pul qo'shish$"), contrib_start)],
        states={
            CONTRIB_SELECT: [CallbackQueryHandler(contrib_select, pattern="^contrib:")],
            CONTRIB_AMOUNT: [
                MessageHandler(filters.Regex(BACK_RE), contrib_back_to_select),
                MessageHandler(filters.TEXT & ~filters.COMMAND, contrib_amount),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    pinned_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Muhim qo'shish$"), pinned_add_start)],
        states={PINNED_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_add_text)]},
        fallbacks=[MessageHandler(filters.Regex(CANCEL_RE), cancel_conv)],
    )

    routine_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Reja qo'shish$"), routine_add_start)],
        states={
            ROUTINE_CATEGORY: [CallbackQueryHandler(routine_category_callback, pattern="^rcat:")],
            ROUTINE_TITLE: [
                MessageHandler(filters.Regex(BACK_RE), routine_back_to_category),
                MessageHandler(filters.TEXT & ~filters.COMMAND, routine_title),
            ],
            ROUTINE_SCHEDULE: [
                MessageHandler(filters.Regex(BACK_RE), routine_back_to_title),
                MessageHandler(filters.TEXT & ~filters.COMMAND, routine_schedule),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f"({BACK_RE}|{CANCEL_RE})"), cancel_conv)],
    )

    time_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⏰ Eslatma vaqtini o'zgartirish$"), time_change_start)],
        states={
            TIME_CUSTOM: [
                CallbackQueryHandler(time_choice_callback, pattern="^time:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_custom_text),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(CANCEL_RE), cancel_conv)],
    )

    for conv in (credit_conv, pay_conv, expense_conv, budget_conv, income_conv, task_conv, goal_conv, contrib_conv, pinned_conv, routine_conv, time_conv):
        application.add_handler(conv)

    application.add_handler(CallbackQueryHandler(task_done_callback, pattern="^taskdone:"))
    application.add_handler(CallbackQueryHandler(clear_failed_task_callback, pattern="^clearfailed:"))
    application.add_handler(CallbackQueryHandler(goal_achieve_callback, pattern="^goalachieve:"))
    application.add_handler(CallbackQueryHandler(pinned_delete_callback, pattern="^delpinned:"))
    application.add_handler(CallbackQueryHandler(month_nav_callback, pattern="^month:"))
    application.add_handler(CallbackQueryHandler(undo_expense_callback, pattern="^undoexp:"))
    application.add_handler(CallbackQueryHandler(undo_income_callback, pattern="^undoinc:"))

    logger.info("Sarhisob ULTRA bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
