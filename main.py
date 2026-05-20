import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE =================

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    name TEXT,
    gender TEXT,
    size TEXT,
    quantity INTEGER,
    price REAL,
    comment TEXT,
    photos TEXT,
    status TEXT DEFAULT 'В обработке'
)
""")
conn.commit()

# ================= KEYBOARDS =================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="ℹ️ О нас")],
        [KeyboardButton(text="📦 Мои лоты")],
        [KeyboardButton(text="➕ Выставить лот")]
    ],
    resize_keyboard=True
)

def admin_kb(lot_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{lot_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{lot_id}")
        ]
    ])

# ================= STATES =================

class LotForm(StatesGroup):
    name = State()
    gender = State()
    size = State()
    quantity = State()
    price = State()
    comment = State()
    photos = State()

# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Добро пожаловать в Ликвид База!!🔥",
        reply_markup=main_kb
    )

# ================= ABOUT =================

@dp.message(F.text == "ℹ️ О нас")
async def about(message: Message):
    await message.answer(
        "🔥 Ликвид База — площадка для продажи товаров.\n\n"
        "Поддержка: @your_telegram"
    )

# ================= PROFILE =================

@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    cursor.execute("SELECT name FROM lots WHERE user_id=?", (user_id,))
    lots = cursor.fetchall()

    lot_list = "\n".join([f"- {lot[0]}" for lot in lots]) if lots else "Нет лотов"

    await message.answer(
        f"👤 Имя: {message.from_user.full_name}\n"
        f"@{username}\n\n"
        f"📦 Ваши лоты:\n{lot_list}"
    )

# ================= MY LOTS =================

@dp.message(F.text == "📦 Мои лоты")
async def my_lots(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT id, name, price, quantity, status FROM lots WHERE user_id=?", (user_id,))
    lots = cursor.fetchall()

    if not lots:
        await message.answer("У вас пока нет лотов.")
        return

    for lot in lots:
        await message.answer(
            f"📌 Лот #{lot[0]}\n"
            f"Название: {lot[1]}\n"
            f"ID пользователя: {user_id}\n"
            f"Цена: {lot[2]}\n"
            f"Количество: {lot[3]}\n"
            f"Статус: {lot[4]}"
        )

# ================= CREATE LOT =================

@dp.message(F.text == "➕ Выставить лот")
async def create_lot(message: Message, state: FSMContext):
    await message.answer("Введите наименование товара:")
    await state.set_state(LotForm.name)

@dp.message(LotForm.name)
async def lot_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Мужское / Женское / Смешанное?")
    await state.set_state(LotForm.gender)

@dp.message(LotForm.gender)
async def lot_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Введите размер:")
    await state.set_state(LotForm.size)

@dp.message(LotForm.size)
async def lot_size(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Введите количество:")
    await state.set_state(LotForm.quantity)

@dp.message(LotForm.quantity)
async def lot_quantity(message: Message, state: FSMContext):
    await state.update_data(quantity=message.text)
    await message.answer("Введите цену за единицу:")
    await state.set_state(LotForm.price)

@dp.message(LotForm.price)
async def lot_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Дополнительный комментарий:")
    await state.set_state(LotForm.comment)

@dp.message(LotForm.comment)
async def lot_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await message.answer("Отправьте от 3 до 5 фото (по одному). Когда закончите напишите: Готово")
    await state.update_data(photos=[])
    await state.set_state(LotForm.photos)

@dp.message(LotForm.photos, F.photo)
async def lot_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото добавлено ({len(photos)}/5)")

@dp.message(LotForm.photos, F.text.lower() == "готово")
async def lot_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) < 3:
        await message.answer("Нужно минимум 3 фото.")
        return

    cursor.execute("""
    INSERT INTO lots (user_id, username, name, gender, size, quantity, price, comment, photos)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        message.from_user.username,
        data["name"],
        data["gender"],
        data["size"],
        data["quantity"],
        data["price"],
        data["comment"],
        ",".join(photos)
    ))
    conn.commit()

    lot_id = cursor.lastrowid

    await message.answer("✅ Ваш лот успешно выставлен и отправлен на модерацию!", reply_markup=main_kb)

    # уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🆕 Новый лот #{lot_id}\n"
        f"Название: {data['name']}\n"
        f"Пользователь: @{message.from_user.username}\n"
        f"Цена: {data['price']}\n"
        f"Количество: {data['quantity']}",
        reply_markup=admin_kb(lot_id)
    )

    await state.clear()

# ================= ADMIN ACTIONS =================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    lot_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE lots SET status='Принят' WHERE id=?", (lot_id,))
    conn.commit()

    cursor.execute("SELECT user_id FROM lots WHERE id=?", (lot_id,))
    user_id = cursor.fetchone()[0]

    await bot.send_message(user_id, f"✅ Ваш лот #{lot_id} принят!")
    await callback.message.edit_text("✅ Лот принят")

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    lot_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE lots SET status='Отклонён' WHERE id=?", (lot_id,))
    conn.commit()

    cursor.execute("SELECT user_id FROM lots WHERE id=?", (lot_id,))
    user_id = cursor.fetchone()[0]

    await bot.send_message(user_id, f"❌ Ваш лот #{lot_id} отклонён.")
    await callback.message.edit_text("❌ Лот отклонён")

# ================= RUN =================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
