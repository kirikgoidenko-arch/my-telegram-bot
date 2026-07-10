import asyncio
import os
import random
from datetime import datetime

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ===================== НАСТРОЙКИ =====================
load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ Токен не найден! Создай файл .env и добавь TOKEN=твой_токен")

DB_PATH = "habits_final.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
# ====================================================


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                category TEXT DEFAULT 'Другое',
                text TEXT,
                schedule TEXT,
                streak INTEGER DEFAULT 0,
                last_completed TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.commit()


async def add_item(user_id, item_type, category, text, schedule):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO items (user_id, type, category, text, schedule) VALUES (?, ?, ?, ?, ?)",
            (user_id, item_type, category, text, schedule)
        )
        await db.commit()


async def get_user_items(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, type, category, text, schedule, streak FROM items WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        return await cursor.fetchall()


async def update_streak(item_id, today):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE items SET streak = streak + 1, last_completed = ? WHERE id = ?",
            (today, item_id)
        )
        await db.commit()


async def reset_streak(item_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET streak = 0 WHERE id = ?", (item_id,))
        await db.commit()


async def mark_done(item_id, date):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE items SET last_completed = ? WHERE id = ?",
            (date, item_id)
        )
        await db.commit()


async def send_reminders():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        # Привычки
        cursor = await db.execute(
            "SELECT id, user_id, text, category, streak FROM items WHERE type = 'habit' AND schedule = ? AND is_active = 1",
            (current_time,)
        )
        habits = await cursor.fetchall()

        # Задачи на сегодня
        cursor = await db.execute(
            "SELECT id, user_id, text, category FROM items WHERE type = 'task' AND schedule LIKE ? AND is_active = 1",
            (f"{current_date}%",)
        )
        tasks = await cursor.fetchall()

    for item_id, user_id, text, category, streak in habits:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Сделано", callback_data=f"done_{item_id}")
            kb.button(text="⏭ Пропустить", callback_data=f"skip_{item_id}")
            streak_text = f" 🔥 {streak} дней" if streak > 0 else ""
            await bot.send_message(
                user_id,
                f"⏰ {current_time} | {category}\n\n<b>{text}</b>{streak_text}",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            print(e)

    for item_id, user_id, text, category in tasks:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Сделано", callback_data=f"done_{item_id}")
            await bot.send_message(
                user_id,
                f"📅 Сегодня | {category}\n\n<b>{text}</b>",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            print(e)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Бот для привычек и задач.\n\n"
        "Как добавлять:\n"
        "• Привычка: <b>Зарядка 07:00</b>\n"
        "• Задача: <b>Врач 15.07 10:00</b>\n\n"
        "Команды: /list /today /stats"
    )


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_add(message: Message):
    text = message.text.strip()
    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        await message.answer("❌ Неверный формат.\n\nПример:\nЗарядка 07:00\nВрач 15.07 10:00")
        return

    item_text, time_part = parts
    user_id = message.from_user.id
    category = "Другое"

    if "." in time_part:
        try:
            date_part, time_part = time_part.split(" ", 1) if " " in time_part else (time_part, "09:00")
            day, month = date_part.split(".")
            schedule = f"2026-{month.zfill(2)}-{day.zfill(2)} {time_part}"
            await add_item(user_id, "task", category, item_text, schedule)
            await message.answer(f"✅ Задача добавлена: {item_text}")
        except:
            await message.answer("❌ Неверный формат даты")
    else:
        await add_item(user_id, "habit", category, item_text, time_part)
        await message.answer(f"✅ Привычка добавлена: {item_text} в {time_part}")


@dp.message(Command("list"))
async def list_items(message: Message):
    items = await get_user_items(message.from_user.id)
    if not items:
        await message.answer("У тебя пока ничего нет.")
        return

    text = "📋 Твои дела:\n\n"
    for item_id, item_type, category, item_text, schedule, streak in items:
        streak_text = f" 🔥 {streak}" if item_type == "habit" and streak > 0 else ""
        text += f"• [{category}] {item_text} — {schedule}{streak_text}\n"

    await message.answer(text)


@dp.message(Command("today"))
async def today(message: Message):
    today_date = datetime.now().strftime("%Y-%m-%d")
    items = await get_user_items(message.from_user.id)
    text = "📅 На сегодня:\n\n"
    found = False

    for item_id, item_type, category, item_text, schedule, streak in items:
        if item_type == "task" and today_date in schedule:
            text += f"• {item_text}\n"
            found = True
        elif item_type == "habit":
            text += f"• {item_text} ({schedule})\n"
            found = True

    if not found:
        text += "Ничего нет на сегодня."

    await message.answer(text)


@dp.message(Command("stats"))
async def stats(message: Message):
    items = await get_user_items(message.from_user.id)
    if not items:
        await message.answer("Статистики пока нет.")
        return

    text = "📊 Статистика:\n\n"
    for item_id, item_type, category, item_text, schedule, streak in items:
        if item_type == "habit":
            text += f"• {item_text}: {streak} дней подряд\n"

    await message.answer(text)


@dp.callback_query(F.data.startswith("done_"))
async def done(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    today = datetime.now().strftime("%Y-%m-%d")
    await mark_done(item_id, today)
    await update_streak(item_id, today)
    messages = ["Отлично! 🔥", "Молодец! 👏", "Так держать!", "Красава!"]
    await callback.message.edit_text(f"✅ {random.choice(messages)}")


@dp.callback_query(F.data.startswith("skip_"))
async def skip(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    await reset_streak(item_id)
    await callback.message.edit_text("⏭ Пропущено. Streak сброшен.")


async def main():
    await init_db()
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    
    print("✅ Бот успешно запущен...")
    await on_startup()                    # ← добавь эту строку
    await dp.start_polling(bot)

async def on_startup():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook удалён, бот запущен в режиме polling")
if __name__ == "__main__":
    asyncio.run(main())
