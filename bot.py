import asyncio
import os
import random
from datetime import datetime, timedelta

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ Токен не найден!")

DB_PATH = "habits_final.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


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


# ================== ОСНОВНЫЕ ФУНКЦИИ ==================
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


async def delete_item(item_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET is_active = 0 WHERE id = ?", (item_id,))
        await db.commit()


# ================== НОВЫЕ ФУНКЦИИ ==================
async def get_week_stats(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT text, streak FROM items WHERE user_id = ? AND is_active = 1 AND type = 'habit'",
            (user_id,)
        )
        return await cursor.fetchall()


# ================== ХЕНДЛЕРЫ ==================
@dp.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить привычку", callback_data="add_habit")
    kb.button(text="➕ Добавить задачу", callback_data="add_task")
    kb.adjust(1)
    await message.answer("Добро пожаловать!", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "add_habit")
async def add_habit_callback(callback: CallbackQuery):
    await callback.message.answer("Напиши привычку и время:\nПример: <b>Зарядка 07:30</b>", parse_mode="HTML")


@dp.callback_query(F.data == "add_task")
async def add_task_callback(callback: CallbackQuery):
    await callback.message.answer("Напиши задачу и дату+время:\nПример: <b>Врач 15.07 14:00</b>", parse_mode="HTML")


# (Остальные хендлеры handle_add, list, today, stats, delete — оставь как в предыдущей версии)

@dp.message(Command("stats"))
async def stats(message: Message):
    items = await get_week_stats(message.from_user.id)
    if not items:
        await message.answer("Статистики пока нет.")
        return

    text = "📊 Статистика привычек:\n\n"
    for text_item, streak in items:
        text += f"• {text_item}: {streak} дней подряд 🔥\n"
    await message.answer(text)


async def main():
    await init_db()
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook удалён")
    except:
        pass
    
    print("✅ Бот запущен с новыми функциями...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
