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


async def send_reminders():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, text, category, streak FROM items WHERE type = 'habit' AND schedule = ? AND is_active = 1",
            (current_time,)
        )
        habits = await cursor.fetchall()

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
        except:
            pass

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
        except:
            pass


# ===================== КОМАНДЫ =====================
@dp.message(CommandStart())
async def start(message: Message):
    text = (
        "👋 <b>Бот Привычек и Задач</b>\n\n"
        "Что я умею:\n"
        "• Добавлять ежедневные привычки (с напоминаниями)\n"
        "• Добавлять разовые задачи с датой\n"
        "• Отправлять напоминания в заданное время\n"
        "• Вести статистику (стрики)\n"
        "• Удалять записи\n\n"
        "<b>Как добавлять:</b>\n"
        "Привычка: <code>Зарядка 07:30</code>\n"
        "Задача: <code>Врач 15.07 14:00</code>\n\n"
        "<b>Команды:</b>\n"
        "/list — список всех дел\n"
        "/today — дела на сегодня\n"
        "/stats — статистика\n"
        "/delete — удалить запись\n\n"
        "Нажми /start чтобы увидеть это сообщение снова."
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_add(message: Message):
    text = message.text.strip()
    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        await message.answer("❌ Неверный формат.\n\nПример:\nЗарядка 07:30\nВрач 15.07 14:00")
        return

    item_text, time_part = parts
    user_id = message.from_user.id
    category = "Другое"

    if "." in time_part:
        try:
            date_part, t = time_part.split(" ", 1) if " " in time_part else (time_part, "09:00")
            day, month = date_part.split(".")
            schedule = f"2026-{month.zfill(2)}-{day.zfill(2)} {t}"
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
    text = "📋 <b>Твои дела:</b>\n\n"
    for _, t, c, txt, s, st in items:
        streak = f" 🔥 {st}" if t == "habit" and st > 0 else ""
        text += f"• [{c}] {txt} — {s}{streak}\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("today"))
async def today(message: Message):
    today_date = datetime.now().strftime("%Y-%m-%d")
    items = await get_user_items(message.from_user.id)
    text = "📅 <b>На сегодня:</b>\n\n"
    found = False
    for _, t, c, txt, s, st in items:
        if t == "task" and today_date in s or t == "habit":
            text += f"• {txt} ({s})\n"
            found = True
    if not found:
        text += "Ничего нет."
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("stats"))
async def stats(message: Message):
    items = await get_user_items(message.from_user.id)
    if not items:
        await message.answer("Статистики пока нет.")
        return
    text = "📊 <b>Статистика привычек:</b>\n\n"
    for _, t, _, txt, _, st in items:
        if t == "habit":
            text += f"• {txt}: {st} дней подряд 🔥\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("delete"))
async def delete_command(message: Message):
    items = await get_user_items(message.from_user.id)
    if not items:
        await message.answer("Нечего удалять.")
        return
    kb = InlineKeyboardBuilder()
    for item_id, _, _, text, _, _ in items:
        kb.button(text=text[:25] + "...", callback_data=f"del_{item_id}")
    kb.adjust(1)
    await message.answer("Выберите, что удалить:", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    await delete_item(item_id)
    await callback.message.edit_text("✅ Запись удалена")


@dp.callback_query(F.data.startswith("done_"))
async def done(callback: CallbackQuery):
    await callback.message.edit_text("✅ Молодец! Продолжай в том же духе!")


@dp.callback_query(F.data.startswith("skip_"))
async def skip(callback: CallbackQuery):
    await callback.message.edit_text("⏭ Пропущено")


async def main():
    await init_db()
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook удалён")
    except:
        pass
    
    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
