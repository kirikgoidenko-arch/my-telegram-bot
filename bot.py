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
                type TEXT,                    # 'habit' или 'task'
                type TEXT,                    -- 'habit' или 'task'
               category TEXT DEFAULT 'Другое',
               text TEXT,
                schedule TEXT,                # для привычки: "07:30", для задачи: "2026-07-15 14:00"
                schedule TEXT,                -- для привычки: "07:30", для задачи: "2026-07-15 14:00"
               streak INTEGER DEFAULT 0,
               last_completed TEXT,
               is_active INTEGER DEFAULT 1
@@ -73,20 +73,24 @@
current_time = now.strftime("%H:%M")
current_date = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        # Привычки (ежедневно)
        cursor = await db.execute(
            "SELECT id, user_id, text, category, streak FROM items WHERE type = 'habit' AND schedule = ? AND is_active = 1",
            (current_time,)
        )
        habits = await cursor.fetchall()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Привычки (ежедневно)
            cursor = await db.execute(
                "SELECT id, user_id, text, category, streak FROM items WHERE type = 'habit' AND schedule = ? AND is_active = 1",
                (current_time,)
            )
            habits = await cursor.fetchall()

        # Задачи (только сегодня)
        cursor = await db.execute(
            "SELECT id, user_id, text, category FROM items WHERE type = 'task' AND schedule LIKE ? AND is_active = 1",
            (f"{current_date}%",)
        )
        tasks = await cursor.fetchall()
            # Задачи (только сегодня)
            cursor = await db.execute(
                "SELECT id, user_id, text, category FROM items WHERE type = 'task' AND schedule LIKE ? AND is_active = 1",
                (f"{current_date}%",)
            )
            tasks = await cursor.fetchall()
    except Exception:
        # Если ошибка БД — просто пропускаем этот запуск напоминаний
        return

# Отправка привычек
for item_id, user_id, text, category, streak in habits:
@@ -101,7 +105,7 @@
reply_markup=kb.as_markup(),
parse_mode="HTML"
)
        except:
        except Exception:
pass

# Отправка задач
@@ -115,7 +119,7 @@
reply_markup=kb.as_markup(),
parse_mode="HTML"
)
        except:
        except Exception:
pass


@@ -157,22 +161,32 @@
text = message.text.strip()
parts = text.rsplit(" ", 1)
if len(parts) != 2:
        await message.answer("❌ Неверный формат.")
        await message.answer("❌ Неверный формат. Нужно: <текст> <время или дата.время>")
return

item_text, time_part = parts
user_id = message.from_user.id

if "." in time_part:  # Это задача
try:
            date_part, t = time_part.split(" ", 1) if " " in time_part else (time_part, "09:00")
            # Поддерживаем оба варианта: "15.07" и "15.07 14:00"
            if " " in time_part:
                date_part, t = time_part.split(" ", 1)
            else:
                date_part = time_part
                t = "09:00"  # время по умолчанию, если не указано

day, month = date_part.split(".")
schedule = f"2026-{month.zfill(2)}-{day.zfill(2)} {t}"
await add_item(user_id, "task", "Другое", item_text, schedule)
await message.answer("✅ Задача добавлена! Напоминание придёт только в этот день.", reply_markup=main_menu())
        except:
            await message.answer("❌ Неверный формат даты (ДД.ММ ЧЧ:ММ)")
        except Exception:
            await message.answer("❌ Неверный формат даты. Пример: 15.07 или 15.07 14:00")
else:  # Это привычка
        # Простая валидация времени для привычки
        if len(time_part) != 5 or time_part[2] != ":":
            await message.answer("❌ Время привычки должно быть в формате ЧЧ:ММ (например, 07:30)")
            return
await add_item(user_id, "habit", "Другое", item_text, time_part)
await message.answer("✅ Привычка добавлена! Будет напоминать каждый день.", reply_markup=main_menu())

@@ -192,12 +206,12 @@
await init_db()
scheduler.add_job(send_reminders, "interval", minutes=1)
scheduler.start()
    

try:
await bot.delete_webhook(drop_pending_updates=True)
    except:
    except Exception:
pass
    

print("✅ Бот запущен! Задачи и привычки разделены.")
await dp.start_polling(bot)
