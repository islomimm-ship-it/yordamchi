# -*- coding: utf-8 -*-
"""
Shaxsiy Yordamchi Bot (Telegram)
--------------------------------
Funksiyalar:
- To-do (vazifalar) ro'yxati
- Eslatmalar (bir martalik)
- Yozuvlar (notes)
- Xarajatlar kuzatuvi
- Xarid ro'yxati (shopping list)
- Odatlar kuzatuvi (habit tracker)
- Suv ichish eslatmasi (davriy)

O'rnatish va ishga tushirish uchun README.md faylini o'qing.
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============ SOZLAMALAR ============
# Token endi kodga yozilmaydi — Railway'da "Variables" bo'limidan
# BOT_TOKEN nomli o'zgaruvchi sifatida beriladi.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = "bot.db"

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! Railway'da Variables bo'limiga "
        "BOT_TOKEN nomli environment variable qo'shing."
    )

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============ BAZA (DATABASE) ============
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shopping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            streak INTEGER DEFAULT 0,
            last_done TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS water_settings (
            user_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ============ START / HELP ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Salom! Men sizning shaxsiy yordamchingizman.\n\n"
        "Barcha buyruqlarni ko'rish uchun /help yozing."
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *BUYRUQLAR RO'YXATI*\n\n"
        "*✅ Vazifalar (To-do)*\n"
        "/todo_add <matn> — vazifa qo'shish\n"
        "/todo_list — ro'yxatni ko'rish\n"
        "/todo_done <id> — bajarilgan deb belgilash\n\n"
        "*⏰ Eslatmalar*\n"
        "/remind <daqiqa> <matn> — masalan: /remind 30 Non olish\n\n"
        "*📝 Yozuvlar*\n"
        "/note_add <matn>\n"
        "/note_list\n\n"
        "*💰 Xarajatlar*\n"
        "/expense_add <summa> <kategoriya>\n"
        "/expense_report — oylik hisobot\n\n"
        "*🛒 Xarid ro'yxati*\n"
        "/shopping_add <narsa>\n"
        "/shopping_list\n"
        "/shopping_clear\n\n"
        "*🔥 Odatlar (Habit tracker)*\n"
        "/habit_add <nom>\n"
        "/habit_done <nom>\n"
        "/habit_list\n\n"
        "*💧 Suv ichish eslatmasi*\n"
        "/water_on — har 2 soatda eslatma\n"
        "/water_off — o'chirish"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ============ TO-DO ============
async def todo_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Foydalanish: /todo_add Non sotib olish")
        return
    text = " ".join(context.args)
    conn = get_conn()
    conn.execute(
        "INSERT INTO todos (user_id, text, created_at) VALUES (?, ?, ?)",
        (update.effective_user.id, text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Qo'shildi: {text}")


async def todo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, text, done FROM todos WHERE user_id=? ORDER BY id",
        (update.effective_user.id,),
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Vazifalar ro'yxati bo'sh.")
        return
    lines = []
    for r in rows:
        mark = "✅" if r["done"] else "⬜"
        lines.append(f"{mark} #{r['id']} — {r['text']}")
    await update.message.reply_text("\n".join(lines))


async def todo_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /todo_done 3")
        return
    todo_id = int(context.args[0])
    conn = get_conn()
    conn.execute(
        "UPDATE todos SET done=1 WHERE id=? AND user_id=?",
        (todo_id, update.effective_user.id),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🎉 #{todo_id} bajarildi deb belgilandi.")


# ============ ESLATMALAR (REMINDERS) ============
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(chat_id=job.chat_id, text=f"⏰ Eslatma: {job.data}")


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text("Foydalanish: /remind 30 Non olish")
        return
    minutes = int(context.args[0])
    text = " ".join(context.args[1:])
    context.job_queue.run_once(
        send_reminder,
        when=timedelta(minutes=minutes),
        chat_id=update.effective_chat.id,
        data=text,
    )
    await update.message.reply_text(f"⏰ {minutes} daqiqadan so'ng eslataman: {text}")


# ============ YOZUVLAR (NOTES) ============
async def note_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Foydalanish: /note_add Bugungi fikr...")
        return
    text = " ".join(context.args)
    conn = get_conn()
    conn.execute(
        "INSERT INTO notes (user_id, text, created_at) VALUES (?, ?, ?)",
        (update.effective_user.id, text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("📝 Yozuv saqlandi.")


async def note_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    rows = conn.execute(
        "SELECT text, created_at FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (update.effective_user.id,),
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Hali yozuvlar yo'q.")
        return
    lines = [f"• {r['text']} ({r['created_at'][:10]})" for r in rows]
    await update.message.reply_text("\n".join(lines))


# ============ XARAJATLAR (EXPENSES) ============
async def expense_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Foydalanish: /expense_add 25000 ovqat")
        return
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Summani raqam qilib kiriting.")
        return
    category = " ".join(context.args[1:])
    conn = get_conn()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, created_at) VALUES (?, ?, ?, ?)",
        (update.effective_user.id, amount, category, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"💰 Qo'shildi: {amount:,.0f} so'm — {category}")


async def expense_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses "
        "WHERE user_id=? AND created_at >= ? GROUP BY category ORDER BY total DESC",
        (update.effective_user.id, (datetime.now() - timedelta(days=30)).isoformat()),
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Oxirgi 30 kunda xarajat yozilmagan.")
        return
    total = sum(r["total"] for r in rows)
    lines = [f"• {r['category']}: {r['total']:,.0f} so'm" for r in rows]
    lines.append(f"\n📊 Jami: {total:,.0f} so'm")
    await update.message.reply_text("\n".join(lines))


# ============ XARID RO'YXATI (SHOPPING) ============
async def shopping_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Foydalanish: /shopping_add Sut")
        return
    item = " ".join(context.args)
    conn = get_conn()
    conn.execute(
        "INSERT INTO shopping (user_id, item) VALUES (?, ?)",
        (update.effective_user.id, item),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🛒 Qo'shildi: {item}")


async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    rows = conn.execute(
        "SELECT item FROM shopping WHERE user_id=?", (update.effective_user.id,)
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Xarid ro'yxati bo'sh.")
        return
    lines = [f"• {r['item']}" for r in rows]
    await update.message.reply_text("\n".join(lines))


async def shopping_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    conn.execute("DELETE FROM shopping WHERE user_id=?", (update.effective_user.id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑 Xarid ro'yxati tozalandi.")


# ============ ODATLAR (HABITS) ============
async def habit_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Foydalanish: /habit_add Sport")
        return
    name = " ".join(context.args)
    conn = get_conn()
    conn.execute(
        "INSERT INTO habits (user_id, name, streak, last_done) VALUES (?, ?, 0, '')",
        (update.effective_user.id, name),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🔥 Odat qo'shildi: {name}")


async def habit_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Foydalanish: /habit_done Sport")
        return
    name = " ".join(context.args)
    today = datetime.now().date().isoformat()
    conn = get_conn()
    row = conn.execute(
        "SELECT id, streak, last_done FROM habits WHERE user_id=? AND name=?",
        (update.effective_user.id, name),
    ).fetchone()
    if not row:
        await update.message.reply_text("Bunday odat topilmadi. Avval /habit_add bilan qo'shing.")
        conn.close()
        return
    if row["last_done"] == today:
        await update.message.reply_text("Bugun allaqachon belgilangan. 👍")
        conn.close()
        return
    new_streak = row["streak"] + 1
    conn.execute(
        "UPDATE habits SET streak=?, last_done=? WHERE id=?",
        (new_streak, today, row["id"]),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🔥 {name}: {new_streak} kunlik ketma-ketlik!")


async def habit_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, streak FROM habits WHERE user_id=?", (update.effective_user.id,)
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Hali odatlar qo'shilmagan.")
        return
    lines = [f"• {r['name']}: {r['streak']} kun 🔥" for r in rows]
    await update.message.reply_text("\n".join(lines))


# ============ SUV ICHISH ESLATMASI ============
async def send_water_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id, text="💧 Suv ichishni unutmang!"
    )


async def water_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # avvalgi joblarni tozalash
    current_jobs = context.job_queue.get_jobs_by_name(f"water_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()
    context.job_queue.run_repeating(
        send_water_reminder,
        interval=timedelta(hours=2),
        first=timedelta(seconds=5),
        chat_id=chat_id,
        name=f"water_{chat_id}",
    )
    await update.message.reply_text("💧 Har 2 soatda suv ichish eslatmasi yoqildi.")


async def water_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(f"water_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("💧 Suv ichish eslatmasi o'chirildi.")


# ============ ASOSIY FUNKSIYA ============
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    app.add_handler(CommandHandler("todo_add", todo_add))
    app.add_handler(CommandHandler("todo_list", todo_list))
    app.add_handler(CommandHandler("todo_done", todo_done))

    app.add_handler(CommandHandler("remind", remind))

    app.add_handler(CommandHandler("note_add", note_add))
    app.add_handler(CommandHandler("note_list", note_list))

    app.add_handler(CommandHandler("expense_add", expense_add))
    app.add_handler(CommandHandler("expense_report", expense_report))

    app.add_handler(CommandHandler("shopping_add", shopping_add))
    app.add_handler(CommandHandler("shopping_list", shopping_list))
    app.add_handler(CommandHandler("shopping_clear", shopping_clear))

    app.add_handler(CommandHandler("habit_add", habit_add))
    app.add_handler(CommandHandler("habit_done", habit_done))
    app.add_handler(CommandHandler("habit_list", habit_list))

    app.add_handler(CommandHandler("water_on", water_on))
    app.add_handler(CommandHandler("water_off", water_off))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
