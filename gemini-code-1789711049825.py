import logging
import os
import sqlite3
from datetime import datetime, time, date
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "810386570:AAGWl5ylbtWdxVf8vSKonRvvzBxpy8FgidU")
DB_PATH = os.environ.get("DB_PATH", "sarhisob_pro.db")
TIMEZONE = ZoneInfo("Asia/Tashkent")
DEFAULT_REMIND_TIME = "08:00"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("sarhisob_pro_bot")


# ---------------------------------------------------------------------------
# Ma'lumotlar bazasi (SQLite)
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
            monthly_budget REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            direction TEXT NOT NULL,
            person TEXT NOT NULL,
            amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            due_day INTEGER,
            note TEXT,
            is_paid INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            task_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            expense_date TEXT NOT NULL
        )
        """
    )
    
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            deadline TEXT,
            is_achieved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pinned_notes (
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


def add_task(chat_id: int, title: str):
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


def get_todays_tasks(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    cur.execute(
        "UPDATE tasks SET status = 'failed' WHERE chat_id = ? AND task_date < ? AND status = 'pending'",
        (chat_id, today_str)
    )
    conn.commit()
    cur.execute(
        "SELECT * FROM tasks WHERE chat_id = ? AND task_date = ? ORDER BY id DESC",
        (chat_id, today_str),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def update_task_status(chat_id: int, task_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = ? WHERE chat_id = ? AND id = ?", (status, chat_id, task_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def add_expense(chat_id: int, category: str, amount: float, note: str):
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


def get_expenses_summary(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    current_month = datetime.now(TIMEZONE).strftime("%Y-%m")
    cur.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE chat_id = ? AND expense_date LIKE ? GROUP BY category",
        (chat_id, f"{current_month}%")
    )
    rows = cur.fetchall()
    cur.execute(
        "SELECT SUM(amount) as total_sum FROM expenses WHERE chat_id = ? AND expense_date LIKE ?",
        (chat_id, f"{current_month}%")
    )
    total_row = cur.fetchone()
    conn.close()
    return rows, total_row["total_sum"] if total_row and total_row["total_sum"] else 0


def add_debt(chat_id: int, direction: str, person: str, amount: float, due_day: int, note: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO debts (chat_id, direction, person, amount, remaining_amount, due_day, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, direction, person, amount, amount, due_day, note, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return qid


def list_debts(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM debts WHERE chat_id = ? AND is_paid = 0 ORDER BY due_day ASC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_debt_payment(chat_id: int, debt_id: int, paid_part: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT remaining_amount FROM debts WHERE chat_id = ? AND id = ?", (chat_id, debt_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, 0
    rem = row["remaining_amount"] - paid_part
    if rem <= 0:
        cur.execute("UPDATE debts SET remaining_amount = 0, is_paid = 1 WHERE chat_id = ? AND id = ?", (chat_id, debt_id))
        conn.commit()
        conn.close()
        return True, 0
    else:
        cur.execute("UPDATE debts SET remaining_amount = ? WHERE chat_id = ? AND id = ?", (rem, chat_id, debt_id))
        conn.commit()
        conn.close()
        return False, rem


def add_goal(chat_id: int, title: str, deadline: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO goals (chat_id, title, deadline, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, title, deadline, datetime.now(TIMEZONE).isoformat()),
    )
    conn.commit()
    gid = cur.lastrowid
    conn.close()
    return gid


def list_goals(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM goals WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def achieve_goal(chat_id: int, goal_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE goals SET is_achieved = 1 WHERE chat_id = ? AND id = ?", (chat_id, goal_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def add_pinned(chat_id: int, text: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO pinned_notes (chat_id, text, created_at) VALUES (?, ?, ?)", (chat_id, text, datetime.now(TIMEZONE).isoformat()))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def list_pinned(chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pinned_notes WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def build_daily_message(chat_id: int) -> str:
    tasks = get_todays_tasks(chat_id)
    debts = list_debts(chat_id)
    exp_rows, total_exp = get_expenses_summary(chat_id)
    user = get_user_info(chat_id)
    budget = user["monthly_budget"] if user else 0
    pinned = list_pinned(chat_id)
    today_day_num = datetime.now(TIMEZONE).day

    lines = ["🌟 <b>Xayrli tong! Bugungi shaxsiy sarhisobingiz:</b>\n"]

    if pinned:
        lines.append("📌 <b>Muhim eslatmalar:</b>")
        for p in pinned:
            lines.append(f"• {p['text']}")
        lines.append("")

    if tasks:
        lines.append("📋 <b>Bugungi vazifalar:</b>")
        for t in tasks:
            icon = "⏳ Jarayonda"
            if t["status"] == "completed":
                icon = "✅ Bajarildi"
            elif t["status"] == "failed":
                icon = "❌ Bajarilmadi"
            lines.append(f"• {t['title']} — {icon} [ID: {t['id']}]")
        lines.append("")

    if debts:
        lines.append("💳 <b>Kredit va Oylik To'lovlar (Grafik):</b>")
        for d in debts:
            alert = ""
            if d["due_day"] and d["due_day"] == today_day_num:
                alert = " ⚠️ <b>BUGUN TO'LOV KUNI!</b>"
            due_str = f" (Har oyning {d['due_day']}-kuni)" if d["due_day"] else ""
            lines.append(f"• <b>{d['person']}</b>: Qoldiq <b>{format_amount(d['remaining_amount'])} so'm</b>{due_str}{alert} [ID: {d['id']}]")
        lines.append("")

    lines.append(f"📊 <b>Oylik Xarajatlar:</b> {format_amount(total_exp)} so'm")
    if budget > 0:
        remainder = budget - total_exp
        lines.append(f"🎯 Oylik limit: {format_amount(budget)} so'm | Qoldi: <b>{format_amount(remainder)} so'm</b>")
        if remainder < 0:
            lines.append("⚠️ <i>Diqqat: Oylik byudjet limiti oshib ketdi!</i>")

    return "\n".join(lines)


HELP_TEXT = """
<b>🤖 Sarhisob PRO - To'liq Qo'llanma</b>

<b>1. Kunlik Vazifalar:</b>
/vazifa [Matn] — bugungi vazifa qo'shish
/vazifalar — ro'yxatni ko'rish
/bajar [ID] — bajarildi deb belgilash

<b>2. Kredit va Oylik To'lovlar:</b>
/kredit [Nomi] | [Summa] | [Kun] | [Izoh]
/kreditlar — qoldiqni ko'rish
/tolash [ID] | [Summa] — to'lov qilish

<b>3. Xarajatlar va Byudjet:</b>
/xarajat [Kategoriya] | [Summa] | [Izoh]
/limit [Summa] — oylik limit
/xarajatlar — statistika

<b>4. Maqsadlar:</b>
/maqsad [Sarlavha] | [Muddat]
/maqsadlar — ro'yxat
/maqsad_bajar [ID]

<b>5. Muhim Eslatmalar:</b>
/muhim [Matn]
/muhimlar

<b>6. Boshqaruv:</b>
/vaqt [HH:MM]
/bugun
"""


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    schedule_user_job(context.application, chat_id, DEFAULT_REMIND_TIME)
    await update.message.reply_text(f"Assalomu alaykum! <b>Sarhisob PRO</b> botiga xush kelibsiz.\n\n{HELP_TEXT}", parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def vazifa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Foydalanish: /vazifa [Matn]")
        return
    tid = add_task(chat_id, text)
    await update.message.reply_text(f"✅ Vazifa qo'shildi [ID: {tid}]: <b>{text}</b>", parse_mode=ParseMode.HTML)


async def vazifalar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    tasks = get_todays_tasks(chat_id)
    if not tasks:
        await update.message.reply_text("Bugungi vazifalar yo'q.")
        return
    lines = ["📋 <b>Bugungi vazifalar:</b>\n"]
    for t in tasks:
        icon = "⏳ Jarayonda"
        if t["status"] == "completed":
            icon = "✅ Bajarildi"
        elif t["status"] == "failed":
            icon = "❌ Bajarilmadi"
        lines.append(f"• {t['title']} — {icon} [ID: {t['id']}]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def bajar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /bajar [ID]")
        return
    tid = int(context.args[0])
    if update_task_status(chat_id, tid, "completed"):
        await update.message.reply_text(f"✅ Vazifa [ID: {tid}] bajarildi!")
    else:
        await update.message.reply_text("ID topilmadi.")


async def kredit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("Format xato. Masalan:\n<code>/kredit Ipoteka | 15000000 | 20 | Uy krediti</code>", parse_mode=ParseMode.HTML)
        return
    person = parts[0]
    try:
        amount = float(parts[1].replace(" ", "").replace(",", ""))
        due_day = int(parts[2])
    except ValueError:
        await update.message.reply_text("Summa yoki sana raqam bo'lishi kerak.")
        return
    note = parts[3] if len(parts) > 3 else ""
    qid = add_debt(chat_id, "oldim", person, amount, due_day, note)
    await update.message.reply_text(f"💳 Kredit qo'shildi [ID: {qid}]: <b>{person}</b> - {format_amount(amount)} so'm", parse_mode=ParseMode.HTML)


async def kreditlar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    debts = list_debts(chat_id)
    if not debts:
        await update.message.reply_text("Ochiq kreditlar va to'lovlar yo'q.")
        return
    lines = ["💳 <b>Ochiq kreditlar:</b>\n"]
    for d in debts:
        lines.append(f"• <b>{d['person']}</b>: Qoldiq <b>{format_amount(d['remaining_amount'])} so'm</b> — Har oyning {d['due_day']}-kuni [ID: {d['id']}]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def tolash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2 or not parts[0].isdigit():
        await update.message.reply_text("Foydalanish: /tolash [ID] | [Summa]")
        return
    qid = int(parts[0])
    try:
        paid_part = float(parts[1].replace(" ", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("Summa xato.")
        return
    is_closed, rem = update_debt_payment(chat_id, qid, paid_part)
    if is_closed:
        await update.message.reply_text(f"🎉 Kredit [ID: {qid}] yopildi!")
    else:
        await update.message.reply_text(f"✅ Qoldiq qarz: <b>{format_amount(rem)} so'm</b>", parse_mode=ParseMode.HTML)


async def xarajat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2:
        await update.message.reply_text("Format xato. Masalan:\n<code>/xarajat Bog'cha | 300000</code>", parse_mode=ParseMode.HTML)
        return
    cat = parts[0]
    try:
        amount = float(parts[1].replace(" ", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("Summa xato.")
        return
    note = parts[2] if len(parts) > 2 else ""
    add_expense(chat_id, cat, amount, note)
    _, total_exp = get_expenses_summary(chat_id)
    user = get_user_info(chat_id)
    budget = user["monthly_budget"] if user else 0
    msg = f"💸 Xarajat qo'shildi: <b>{cat}</b> - {format_amount(amount)} so'm"
    if budget > 0 and total_exp > budget:
        msg += f"\n\n⚠️ Oylik limit oshib ketdi! (Jami: {format_amount(total_exp)} so'm)"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if not context.args:
        user = get_user_info(chat_id)
        b = user["monthly_budget"] if user else 0
        await update.message.reply_text(f"Joriy limit: <b>{format_amount(b)} so'm</b>", parse_mode=ParseMode.HTML)
        return
    try:
        b = float(context.args[0].replace(" ", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("Summa xato.")
        return
    set_user_budget(chat_id, b)
    await update.message.reply_text(f"✅ Limit <b>{format_amount(b)} so'm</b> qilindi.", parse_mode=ParseMode.HTML)


async def xarajatlar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows, total = get_expenses_summary(chat_id)
    if not rows:
        await update.message.reply_text("Xarajatlar yo'q.")
        return
    lines = ["📊 <b>Xarajatlar:</b>\n"]
    for r in rows:
        lines.append(f"• <b>{r['category']}</b>: {format_amount(r['total'])} so'm")
    lines.append(f"\n<b>Jami:</b> {format_amount(total)} so'm")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def maqsad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if not parts[0]:
        await update.message.reply_text("Format xato.")
        return
    title = parts[0]
    deadline = parts[1] if len(parts) > 1 and parts[1] else "Muddatsiz"
    gid = add_goal(chat_id, title, deadline)
    await update.message.reply_text(f"🎯 Maqsad qo'shildi [ID: {gid}]: {title}", parse_mode=ParseMode.HTML)


async def maqsadlar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    goals = list_goals(chat_id)
    if not goals:
        await update.message.reply_text("Maqsadlar yo'q.")
        return
    lines = ["🎯 <b>Maqsadlar:</b>\n"]
    for g in goals:
        status = "✅" if g["is_achieved"] else "🎯"
        lines.append(f"• {g['title']} — {status} [ID: {g['id']}]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def maqsad_bajar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /maqsad_bajar [ID]")
        return
    gid = int(context.args[0])
    if achieve_goal(chat_id, gid):
        await update.message.reply_text(f"🎉 Maqsad [ID: {gid}] bajarildi!")
    else:
        await update.message.reply_text("Topilmadi.")


async def muhim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Foydalanish: /muhim [Matn]")
        return
    add_pinned(chat_id, text)
    await update.message.reply_text(f"📌 Qo'shildi: {text}")


async def muhimlar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pinned = list_pinned(chat_id)
    if not pinned:
        await update.message.reply_text("Muhimlar yo'q.")
        return
    lines = ["📌 <b>Muhim eslatmalar:</b>\n"]
    for p in pinned:
        lines.append(f"• {p['text']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙 Ovozli xabar qabul qilindi!")


async def bugun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = build_daily_message(chat_id)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def vaqt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if not context.args:
        await update.message.reply_text("Foydalanish: /vaqt 08:00")
        return
    hhmm = context.args[0]
    try:
        datetime.strptime(hhmm, "%H:%M")
    except ValueError:
        await update.message.reply_text("Format xato.")
        return
    set_remind_time(chat_id, hhmm)
    schedule_user_job(context.application, chat_id, hhmm)
    await update.message.reply_text(f"✅ Vaqt {hhmm} ga o'zgartirildi.")


async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    msg = build_daily_message(chat_id)
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning("Xato: %s", e)


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


def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).post_init(schedule_all_users).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("yordam", help_cmd))
    
    application.add_handler(CommandHandler("vazifa", vazifa_cmd))
    application.add_handler(CommandHandler("vazifalar", vazifalar_cmd))
    application.add_handler(CommandHandler("bajar", bajar_cmd))

    application.add_handler(CommandHandler("kredit", kredit_cmd))
    application.add_handler(CommandHandler("kreditlar", kreditlar_cmd))
    application.add_handler(CommandHandler("tolash", tolash_cmd))

    application.add_handler(CommandHandler("xarajat", xarajat_cmd))
    application.add_handler(CommandHandler("limit", limit_cmd))
    application.add_handler(CommandHandler("xarajatlar", xarajatlar_cmd))

    application.add_handler(CommandHandler("maqsad", maqsad_cmd))
    application.add_handler(CommandHandler("maqsadlar", maqsadlar_cmd))
    application.add_handler(CommandHandler("maqsad_bajar", maqsad_bajar_cmd))

    application.add_handler(CommandHandler("muhim", muhim_cmd))
    application.add_handler(CommandHandler("muhimlar", muhimlar_cmd))

    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))

    application.add_handler(CommandHandler("bugun", bugun_cmd))
    application.add_handler(CommandHandler("vaqt", vaqt_cmd))

    logger.info("Sarhisob PRO bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()