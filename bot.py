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
    raise ValueError("❌ Токен не найден!")

DB_PATH = "habits_final.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
# ====================================================

# ===================== БАЗА ДАННЫХ =====================
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

# ... (остальные функции add_item, get_user_items и т.д. оставляем как были)

# Добавь эти новые функции в конец файла (перед @dp.message)
async def delete_item(item_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET is_active = 0 WHERE id = ?", (item_id,))
        await db.commit()

async def get_item_by_id(item_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        return await cursor.fetchone()

# ===================== ХЕНДЛЕРЫ =====================
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Бот для привычек и задач.\n\n"
        "Команды:\n"
        "/list — список\n"
        "/today — на сегодня\n"
        "/stats — статистика\n"
        "/delete — удалить"
    )

# ... (остальные хендлеры handle_add, list_items, today, stats оставь как были)

@dp.message(Command("delete"))
async def delete_command(message: Message):
    items = await get_user_items(message.from_user.id)
    if not items:
        await message.answer("Нечего удалять.")
        return

    kb = InlineKeyboardBuilder()
    for item_id, item_type, category, text, schedule, streak in items:
        emoji = "🔄" if item_type == "habit" else "📅"
        kb.button(text=f"{emoji} {text[:25]}...", callback_data=f"del_{item_id}")
    kb.adjust(1)
    await message.answer("Что удалить?", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    item = await get_item_by_id(item_id)
    if item:
        await delete_item(item_id)
        await callback.message.edit_text(f"✅ Удалено: {item[4]}")
    else:
        await callback.message.edit_text("❌ Не найдено.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook удалён")
    except:
        pass
    
    print("✅ Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
