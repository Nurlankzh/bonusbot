import asyncio
import random
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USERNAME = "Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫ ---
conn = sqlite3.connect("bonus_bot.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 5, ref_count INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS content (file_id TEXT PRIMARY KEY, type TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, file_id TEXT)")
conn.commit()

# --- АВТО-БОНУС (24 сағат сайын $15) ---
async def auto_bonus():
    while True:
        await asyncio.sleep(86400) # Күніне бір рет
        cur.execute("UPDATE users SET balance = balance + 15")
        conn.commit()

# --- МӘЗІРЛЕР ---
def main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру"))
    builder.row(KeyboardButton(text="💎 Канал сатып алу"), KeyboardButton(text="👤 Профиль"))
    if user_id == ADMIN_ID:
        builder.row(KeyboardButton(text="⚙️ Админ Панель"))
    return builder.as_markup(resize_keyboard=True)

def admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка"))
    builder.row(KeyboardButton(text="🕵️ Жасырын"), KeyboardButton(text="🔙 Артқа"))
    return builder.as_markup(resize_keyboard=True)

# --- ЛОГИКА ---
async def check_sub(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ["member", "administrator", "creator"]
    except: return False

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cur.fetchone():
        # Жаңа адамға $5
        cur.execute("INSERT INTO users (id, balance) VALUES (?, 5)")
        # Реферал бонус ($10)
        if len(args) > 1 and args[1].isdigit():
            inviter = int(args[1])
            if inviter != user_id:
                cur.execute("UPDATE users SET balance = balance + 10, ref_count = ref_count + 1 WHERE id = ?", (inviter,))
                try: await bot.send_message(inviter, "🎊 Дос шақырғаныңыз үшін **+$10** бонус берілді!")
                except: pass
        conn.commit()

    if not await check_sub(user_id):
        kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="📢 Тіркелу", url=CHANNEL_LINK))
        return await message.answer("⛔ Ботты қолдану үшін каналға жазылыңыз!", reply_markup=kb.as_markup())

    await message.answer("🔥 Қош келдіңіз! Сізге бастапқы **$5** берілді. Күн сайын **$15** бонус қосылып тұрады.", reply_markup=main_menu(user_id))

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    cur.execute("SELECT balance, ref_count FROM users WHERE id = ?", (message.from_user.id,))
    res = cur.fetchone()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"💰 Баланс: **{res[0]}$**\n👥 Достар: **{res[1]}**\n🔗 Сілтеме: `{ref_link}`")

@dp.message(F.text.in_(["🎥 Видео көру", "🖼 Фото көру"]))
async def view(message: types.Message):
    if not await check_sub(message.from_user.id): return
    user_id = message.from_user.id
    c_type = "video" if "Видео" in message.text else "photo"
    
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    if cur.fetchone()[0] < 5:
        return await message.answer("💸 Баланс жеткіліксіз ($5 қажет).")

    cur.execute("SELECT file_id FROM content WHERE type = ? AND file_id NOT IN (SELECT file_id FROM history WHERE user_id = ?)", (c_type, user_id))
    rows = cur.fetchall()
    if not rows: return await message.answer("✨ Барлығын көрдіңіз!")

    f_id = random.choice(rows)[0]
    try:
        if c_type == "video": await message.answer_video(f_id, protect_content=True)
        else: await message.answer_photo(f_id, protect_content=True)
        cur.execute("UPDATE users SET balance = balance - 5 WHERE id = ?", (user_id,))
        cur.execute("INSERT INTO history VALUES (?, ?)", (user_id, f_id))
        conn.commit()
    except: await message.answer("❌ Қате.")

@dp.message(F.text == "💎 Канал сатып алу")
async def buy(message: types.Message):
    kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="📲 Жазу", url=f"https://t.me/{MANAGER_USERNAME}"))
    await message.answer("👑 Канал сатып алу үшін менеджерге жазыңыз:", reply_markup=kb.as_markup())

# --- АДМИН ПАНЕЛЬ ---
@dp.message(F.text == "⚙️ Админ Панель", F.from_user.id == ADMIN_ID)
async def admin(message: types.Message):
    await message.answer("🛠 Басқару:", reply_markup=admin_menu())

@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    await message.answer(f"📈 Пайдаланушылар: {u}")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def broadcast(message: types.Message):
    await message.answer("Рассылка үшін текст жіберіңіз.")

@dp.message(F.text == "🔙 Артқа")
async def back(message: types.Message):
    await message.answer("Мәзір", reply_markup=main_menu(message.from_user.id))

@dp.message(F.from_user.id == ADMIN_ID, (F.video | F.photo))
async def save(message: types.Message):
    f_id = message.video.file_id if message.video else message.photo[-1].file_id
    cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (f_id, "video" if message.video else "photo"))
    conn.commit()
    await message.answer("✅ Сақталды.")

# --- ІСКЕ ҚОСУ ---
async def main():
    asyncio.create_task(auto_bonus())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
