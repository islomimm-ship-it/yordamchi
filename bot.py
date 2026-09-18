"""
MuddatAI Bot — qarzlar va eslatmalarni kuzatuvchi Telegram bot.

Har kuni foydalanuvchi belgilagan vaqtda (standart 08:00, Asia/Tashkent)
bot qolgan qarzlar ro'yxatini avtomatik yuboradi.

Ishga tushirish:
    1. .env faylida yoki muhit o'zgaruvchisida BOT_TOKEN ni belgilang
    2. pip install -r requirements.txt
    3. python bot.py

Kerakli kutubxona: python-telegram-bot[job-queue] >= 21.0
"""

import logging
import os
import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "muddatai.db")
TIMEZONE = ZoneInfo("Asia/Tashkent")
DEFAULT_REMIND_TIME = "08:00"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("muddatai_bot")


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
        """
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            remind_time TEXT NOT NULL DEFAULT '08:00',
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            direction TEXT NOT NULL,       -- 'berdim' (men berdim) yoki 'oldim' (men oldim)
            person TEXT NOT NULL,          -- kimga / kimdan
            amount REAL NOT NULL,
            due_date TEXT,                 -- DD.MM.YYYY yoki NULL
            note TEXT,
            is_paid INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_user(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE chat_id = ?", (chat_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (chat_id, remind_time, created_at) VALUES (?, ?, ?)",
            (chat_id, DEFAULT_REMIND_TIME, datetime.now(TIMEZONE).isoformat()),
        )
        conn.commit()
    conn.close()


def set_remind_time(chat_id: int, hhmm: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET remind_time = ? WHERE chat_id = ?", (hhmm, chat_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id, remind_time FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows


def add_debt(chat_id: int, direction: str, person: str, amount: float, due_date: str, note: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO debts (chat_id, direction, person, amount, due_date, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, direction, person, amount, due_date, note, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    debt_id = cur.lastrowid
    conn.close()
    return debt_id


def list_debts(chat_id: int, only_unpaid: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    if only_unpaid:
        cur.execute(
            "SELECT * FROM debts WHERE chat_id = ? AND is_paid = 0 ORDER BY due_date IS NULL, due_date ASC",
            (chat_id,),
        )
    else:
        cur.execute("SELECT * FROM debts WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_paid(chat_id: int, debt_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE debts SET is_paid = 1 WHERE chat_id = ? AND id = ?", (chat_id, debt_id)
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def delete_debt(chat_id: int, debt_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM debts WHERE chat_id = ? AND id = ?", (chat_id, debt_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def add_reminder(chat_id: int, text: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders (chat_id, text, created_at) VALUES (?, ?, ?)",
        (chat_id, text, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    conn.close()


def list_reminders(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reminders WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_reminder(chat_id: int, reminder_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE chat_id = ? AND id = ?", (chat_id, reminder_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------

def format_amount(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


def build_daily_message(chat_id: int) -> str:
    debts = list_debts(chat_id, only_unpaid=True)
    reminders = list_reminders(chat_id)

    if not debts and not reminders:
        return "Xayrli tong! ☀️\n\nBugun sizda ochiq qarz yoki eslatma yo'q. 🎉"

    lines = ["Xayrli tong! ☀️ Bugungi eslatmalaringiz:\n"]

    if debts:
        lines.append("💰 <b>Qarzlar:</b>")
        total_oldim = 0
        total_berdim = 0
        for d in debts:
            arrow = "🔴 Men qarzdorman →" if d["direction"] == "oldim" else "🟢 Menga qarzdor →"
            due = f" | muddat: {d['due_date']}" if d["due_date"] else ""
            note = f" ({d['note']})" if d["note"] else ""
            lines.append(
                f"{arrow} <b>{d['person']}</b>: {format_amount(d['amount'])} so'm{due}{note} "
                f"[ID: {d['id']}]"
            )
            if d["direction"] == "oldim":
                total_oldim += d["amount"]
            else:
                total_berdim += d["amount"]
        lines.append("")
        if total_oldim:
            lines.append(f"Jami mening qarzim: <b>{format_amount(total_oldim)} so'm</b>")
        if total_berdim:
            lines.append(f"Jami menga qarzdorlar: <b>{format_amount(total_berdim)} so'm</b>")
        lines.append("")

    if reminders:
        lines.append("📝 <b>Eslatmalar:</b>")
        for r in reminders:
            lines.append(f"• {r['text']} [ID: {r['id']}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Buyruqlar (handlers)
# ---------------------------------------------------------------------------

HELP_TEXT = """
<b>MuddatAI — qarz va eslatmalar boti</b>

<b>Qarz qo'shish:</b>
/qarz_oldim Kimdan | Summa | Muddat(DD.MM.YYYY) | Izoh
/qarz_berdim Kimga | Summa | Muddat(DD.MM.YYYY) | Izoh
(Muddat va izoh ixtiyoriy, bo'sh qoldirish mumkin)

Masalan:
<code>/qarz_oldim Aziz | 500000 | 25.09.2026 | mashina uchun</code>

<b>Qarzlarni ko'rish:</b>
/qarzlar — barcha ochiq qarzlar ro'yxati

<b>Qarzni yopish/o'chirish:</b>
/tolandi ID — qarzni "to'landi" deb belgilash
/ochir ID — qarzni butunlay o'chirish

<b>Oddiy eslatma qo'shish:</b>
/eslatma Matn — masalan: "Kommunal to'lovni to'lash"
/eslatmalar — barcha eslatmalar ro'yxati
/eslatma_ochir ID — eslatmani o'chirish

<b>Kunlik xabar vaqti:</b>
/vaqt HH:MM — masalan /vaqt 07:30
(standart: 08:00, Toshkent vaqti)

/bugun — hozir qolgan qarz va eslatmalarni ko'rsatish
"""


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    schedule_user_job(context.application, chat_id, DEFAULT_REMIND_TIME)
    await update.message.reply_text(
        f"Assalomu alaykum! Men <b>MuddatAI</b> botiman 🤖\n"
        f"Har kuni ertalab (standart 08:00) qolgan qarzlaringiz va eslatmalaringizni "
        f"eslatib turaman.\n\n{HELP_TEXT}",
        parse_mode=ParseMode.HTML,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


def _parse_debt_args(raw: str):
    parts = [p.strip() for p in raw.split("|")]
    person = parts[0] if len(parts) > 0 and parts[0] else None
    amount_raw = parts[1] if len(parts) > 1 else None
    due_date = parts[2] if len(parts) > 2 and parts[2] else None
    note = parts[3] if len(parts) > 3 and parts[3] else None

    if not person or not amount_raw:
        return None

    try:
        amount = float(amount_raw.replace(" ", "").replace(",", ""))
    except ValueError:
        return None

    if due_date:
        try:
            datetime.strptime(due_date, "%d.%m.%Y")
        except ValueError:
            return None

    return person, amount, due_date, note


async def qarz_oldim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    raw = " ".join(context.args)
    parsed = _parse_debt_args(raw)
    if not parsed:
        await update.message.reply_text(
            "Format noto'g'ri. Masalan:\n"
            "<code>/qarz_oldim Aziz | 500000 | 25.09.2026 | mashina uchun</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    person, amount, due_date, note = parsed
    debt_id = add_debt(chat_id, "oldim", person, amount, due_date, note)
    await update.message.reply_text(
        f"✅ Qo'shildi [ID: {debt_id}]: <b>{person}</b> dan {format_amount(amount)} so'm oldim."
        + (f" Muddat: {due_date}" if due_date else ""),
        parse_mode=ParseMode.HTML,
    )


async def qarz_berdim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    raw = " ".join(context.args)
    parsed = _parse_debt_args(raw)
    if not parsed:
        await update.message.reply_text(
            "Format noto'g'ri. Masalan:\n"
            "<code>/qarz_berdim Vali | 300000 | 01.10.2026 | </code>",
            parse_mode=ParseMode.HTML,
        )
        return
    person, amount, due_date, note = parsed
    debt_id = add_debt(chat_id, "berdim", person, amount, due_date, note)
    await update.message.reply_text(
        f"✅ Qo'shildi [ID: {debt_id}]: <b>{person}</b> ga {format_amount(amount)} so'm berdim."
        + (f" Muddat: {due_date}" if due_date else ""),
        parse_mode=ParseMode.HTML,
    )


async def qarzlar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    debts = list_debts(chat_id, only_unpaid=True)
    if not debts:
        await update.message.reply_text("Hozircha ochiq qarzlaringiz yo'q. 🎉")
        return
    lines = ["💰 <b>Ochiq qarzlar:</b>\n"]
    for d in debts:
        arrow = "🔴 Men qarzdorman →" if d["direction"] == "oldim" else "🟢 Menga qarzdor →"
        due = f" | muddat: {d['due_date']}" if d["due_date"] else ""
        note = f" ({d['note']})" if d["note"] else ""
        lines.append(f"{arrow} <b>{d['person']}</b>: {format_amount(d['amount'])} so'm{due}{note} [ID: {d['id']}]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def tolandi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /tolandi ID")
        return
    debt_id = int(context.args[0])
    if mark_paid(chat_id, debt_id):
        await update.message.reply_text(f"✅ Qarz [ID: {debt_id}] to'landi deb belgilandi.")
    else:
        await update.message.reply_text("Bunday ID topilmadi.")


async def ochir_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /ochir ID")
        return
    debt_id = int(context.args[0])
    if delete_debt(chat_id, debt_id):
        await update.message.reply_text(f"🗑 Qarz [ID: {debt_id}] o'chirildi.")
    else:
        await update.message.reply_text("Bunday ID topilmadi.")


async def eslatma_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Foydalanish: /eslatma Matn\nMasalan: /eslatma Kommunal to'lovni to'lash")
        return
    add_reminder(chat_id, text)
    await update.message.reply_text(f"✅ Eslatma qo'shildi: {text}")


async def eslatmalar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reminders = list_reminders(chat_id)
    if not reminders:
        await update.message.reply_text("Hozircha eslatmalaringiz yo'q.")
        return
    lines = ["📝 <b>Eslatmalar:</b>\n"]
    for r in reminders:
        lines.append(f"• {r['text']} [ID: {r['id']}]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def eslatma_ochir_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /eslatma_ochir ID")
        return
    reminder_id = int(context.args[0])
    if delete_reminder(chat_id, reminder_id):
        await update.message.reply_text(f"🗑 Eslatma [ID: {reminder_id}] o'chirildi.")
    else:
        await update.message.reply_text("Bunday ID topilmadi.")


async def bugun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = build_daily_message(chat_id)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def vaqt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if not context.args:
        await update.message.reply_text("Foydalanish: /vaqt HH:MM  (masalan: /vaqt 07:30)")
        return
    hhmm = context.args[0]
    try:
        datetime.strptime(hhmm, "%H:%M")
    except ValueError:
        await update.message.reply_text("Noto'g'ri format. Masalan: /vaqt 07:30")
        return

    set_remind_time(chat_id, hhmm)
    schedule_user_job(context.application, chat_id, hhmm)
    await update.message.reply_text(f"✅ Endi har kuni soat {hhmm} da eslatib turaman.")


async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Buyruqni tushunmadim. Yordam uchun /yordam yozing."
    )


# ---------------------------------------------------------------------------
# Kunlik job (rejalashtirilgan xabar)
# ---------------------------------------------------------------------------

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    msg = build_daily_message(chat_id)
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning("Xabar yuborishda xato (chat_id=%s): %s", chat_id, e)


def schedule_user_job(application: Application, chat_id: int, hhmm: str):
    """Foydalanuvchi uchun eski job'ni bekor qilib, yangisini o'rnatadi."""
    job_name = f"daily_{chat_id}"
    current_jobs = application.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    hour, minute = map(int, hhmm.split(":"))
    application.job_queue.run_daily(
        send_daily_reminder,
        time=time(hour=hour, minute=minute, tzinfo=TIMEZONE),
        chat_id=chat_id,
        name=job_name,
    )


async def schedule_all_users(application: Application):
    """Bot qayta ishga tushganda barcha foydalanuvchilar uchun job'larni tiklaydi."""
    for row in get_all_users():
        schedule_user_job(application, row["chat_id"], row["remind_time"])


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. Muhit o'zgaruvchisida BOT_TOKEN ni belgilang "
            "(masalan: export BOT_TOKEN=123456:ABC...)"
        )

    init_db()

    application = Application.builder().token(BOT_TOKEN).post_init(schedule_all_users).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("yordam", help_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("qarz_oldim", qarz_oldim_cmd))
    application.add_handler(CommandHandler("qarz_berdim", qarz_berdim_cmd))
    application.add_handler(CommandHandler("qarzlar", qarzlar_cmd))
    application.add_handler(CommandHandler("tolandi", tolandi_cmd))
    application.add_handler(CommandHandler("ochir", ochir_cmd))
    application.add_handler(CommandHandler("eslatma", eslatma_cmd))
    application.add_handler(CommandHandler("eslatmalar", eslatmalar_cmd))
    application.add_handler(CommandHandler("eslatma_ochir", eslatma_ochir_cmd))
    application.add_handler(CommandHandler("bugun", bugun_cmd))
    application.add_handler(CommandHandler("vaqt", vaqt_cmd))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    logger.info("MuddatAI bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
