import asyncio
import os
import random
from datetime import datetime

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
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


# ===================== НАПОМИНАНИЯ =====================
async def send_reminders():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        # Привычки (по времени)
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

    # Отправляем привычки
    for item_id, user_id, text, category, streak in habits:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Сделано", callback_data=f"done_{item_id}")
            kb.button(text="⏭ Пропустить", callback_data=f"skip_{item_id}")
            streak_text = f" 🔥 {streak} дней" if streak > 0 else ""
            await bot.send_message(
                user_id,
                f"⏰ <b>Напоминание!</b>\n\n{current_time} | {category}\n\n{text}{streak_text}",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except:
            pass

    # Отправляем задачи
    for item_id, user_id, text, category in tasks:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Сделано", callback_data=f"done_{item_id}")
            await bot.send_message(
                user_id,
                f"📅 <b>Задача на сегодня!</b>\n\n{category}\n\n{text}",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except:
            pass


# ===================== КНОПКИ =====================
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Мои дела", callback_data="show_list")
    kb.button(text="📅 На сегодня", callback_data="show_today")
    kb.button(text="📊 Статистика", callback_data="show_stats")
    kb.button(text="🗑 Удалить", callback_data="show_delete")
    kb.button(text="➕ Привычка", callback_data="add_habit")
    kb.button(text="➕ Задача", callback_data="add_task")
    kb.adjust(2)
    return kb.as_markup()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>Бот Привычек и Задач</b>\n\n"
        "Бот будет присылать уведомления автоматически в заданное время.\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.in_(["add_habit", "add_task"]))
async def add_callback(callback: CallbackQuery):
    if callback.data == "add_habit":
        await callback.message.edit_text("Напиши: <b>Название привычки ЧЧ:ММ</b>\nПример: Зарядка 07:30", parse_mode="HTML")
    else:
        await callback.message.edit_text("Напиши: <b>Название задачи ДД.ММ ЧЧ:ММ</b>\nПример: Врач 15.07 14:00", parse_mode="HTML")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_add(message: Message):
    # ... (логика добавления как раньше)
    text = message.text.strip()
    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        await message.answer("❌ Неверный формат.")
        return

    item_text, time_part = parts
    user_id = message.from_user.id

    if "." in time_part:
        try:
            date_part, t = time_part.split(" ", 1) if " " in time_part else (time_part, "09:00")
            day, month = date_part.split(".")
            schedule = f"2026-{month.zfill(2)}-{day.zfill(2)} {t}"
            await add_item(user_id, "task", "Другое", item_text, schedule)
            await message.answer("✅ Задача добавлена!", reply_markup=main_menu())
        except:
            await message.answer("❌ Неверный формат даты")
    else:
        await add_item(user_id, "habit", "Другое", item_text, time_part)
        await message.answer("✅ Привычка добавлена! Напоминание будет приходить ежедневно.", reply_markup=main_menu())


# Callback для кнопок "Сделано" и "Пропустить"
@dp.callback_query(F.data.startswith("done_"))
async def done(callback: CallbackQuery):
    await callback.message.edit_text("✅ Отлично! Продолжай в том же духе 🔥")


@dp.callback_query(F.data.startswith("skip_"))
async def skip(callback: CallbackQuery):
    await callback.message.edit_text("⏭ Пропущено")


async def main():
    await init_db()
    scheduler.add_job(send_reminders, "interval", minutes=1)   # проверка каждую минуту
    scheduler.start()
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    
    print("✅ Бот запущен с напоминаниями!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
