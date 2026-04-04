import asyncio
import logging
import aiosqlite
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link
from aiogram.exceptions import TelegramForbiddenError

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USER = "@Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫ ---
async def init_db():
    async with aiosqlite.connect("bot_main_v3.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 5.0, 
            last_bonus TEXT, referrer_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, 
            file_type TEXT, is_approved INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS views (
            user_id INTEGER, file_id TEXT)''')
        await db.commit()

# --- ПЕРНЕТАҚТАЛАР ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру")],
        [KeyboardButton(text="💎 Канал сатып алу")]
    ], resize_keyboard=True)

def get_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔒 Жасырын"), KeyboardButton(text="💰 Доллар беру")],
        [KeyboardButton(text="🏠 Пайдаланушы мәзірі")]
    ], resize_keyboard=True)

# --- КҮЙЛЕРДІ САҚТАУ ---
broadcast_mode = {}
give_balance_mode = {}

# --- СТАРТ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance, last_bonus) VALUES (?, 5.0, ?)", 
                         (user_id, datetime.now().isoformat()))
        await db.commit()

    if user_id == ADMIN_ID:
        await message.answer("👑 Сәлем, Админ! Басқару панелі қосылды.", reply_markup=get_admin_kb())
    else:
        await message.answer("🌟 Қош келдіңіз!", reply_markup=get_main_kb())

# --- НЕГІЗГІ ХЭНДЛЕР ---
@dp.message()
async def main_handler(message: types.Message):
    user_id = message.from_user.id

    # --- АДМИН ЛОГИКАСЫ ---
    if user_id == ADMIN_ID:
        # Доллар беру режимі қосылған болса
        if user_id in give_balance_mode:
            try:
                target_id, amount = message.text.split()
                target_id = int(target_id)
                amount = float(amount)
                
                async with aiosqlite.connect("bot_main_v3.db") as db:
                    # Юзердің бар-жоғын тексеру
                    curr = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (target_id,))
                    if await curr.fetchone():
                        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                        await db.commit()
                        await message.answer(f"✅ Сәтті берілді!\n🆔 ID: {target_id}\n💵 Сома: {amount}$", reply_markup=get_admin_kb())
                        try:
                            await bot.send_message(target_id, f"🎁 Админ сізге {amount}$ бонус берді!")
                        except: pass
                    else:
                        await message.answer("❌ Қате! Мұндай ID базада табылмады.", reply_markup=get_admin_kb())
                
                del give_balance_mode[user_id]
                return
            except ValueError:
                await message.answer("⚠️ Қате формат! Мысалы: `6303091468 15` (ID бос орын Сома)", reply_markup=get_admin_kb())
                del give_balance_mode[user_id]
                return

        # Рассылка режимі
        if user_id in broadcast_mode:
            del broadcast_mode[user_id]
            async with aiosqlite.connect("bot_main_v3.db") as db:
                users = await (await db.execute("SELECT user_id FROM users")).fetchall()
                count = 0
                for (u_id,) in users:
                    try:
                        await message.copy_to(u_id)
                        count += 1
                        await asyncio.sleep(0.05)
                    except: pass
            await message.answer(f"✅ Рассылка аяқталды! {count} адамға жетті.", reply_markup=get_admin_kb())
            return

        # Батырмаларды өңдеу
        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                m = (await (await db.execute("SELECT COUNT(*) FROM content WHERE is_approved=1")).fetchone())[0]
                await message.answer(f"📊 Статистика:\n\n👥 Юзерлер: {u}\n🎬 Контент: {m}", reply_markup=get_admin_kb())
            return

        elif message.text == "📢 Рассылка":
            broadcast_mode[user_id] = True
            await message.answer("📢 Хабарлама жіберіңіз (мәтін/сурет/видео):", reply_markup=types.ReplyKeyboardRemove())
            return

        elif message.text == "💰 Доллар беру":
            give_balance_mode[user_id] = True
            await message.answer("💵 Доллар беру үшін қолданушының ID-ін және сомасын жазыңыз:\n\nМысалы: `12345678 10`", reply_markup=types.ReplyKeyboardRemove())
            return

        elif message.text == "🔒 Жасырын":
            await show_secret_media(message)
            return

        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Пайдаланушы мәзіріне өттіңіз.", reply_markup=get_main_kb())
            return

    # --- ПАЙДАЛАНУШЫ ЛОГИКАСЫ ---
    if message.text == "🎥 Видео көру":
        await send_random_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_random_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Канал сатып алу үшін менеджерге жазыңыз:", reply_markup=ikb)

    # Контент жүктеу
    if message.video or message.photo:
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, is_a))
            await db.commit()
        await message.answer("✅ Сақталды!" if is_a else "📩 Тексеруге жіберілді.")

# --- ФУНКЦИЯЛАР ---
async def send_random_media(message, m_type):
    u_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (u_id,))).fetchone()
        balance = res[0] if res else 5.0
        if balance < 5:
            link = await create_start_link(bot, str(u_id), encode=True)
            return await message.answer(f"💰 Баланс аз: {balance}$\nДос шақыр: {link}")
        
        query = f"SELECT file_id FROM content WHERE file_type = '{m_type}' AND is_approved = 1 ORDER BY RANDOM() LIMIT 1"
        media = await (await db.execute(query)).fetchone()
        if not media: return await message.answer("😔 Контент жоқ.")
        
        await db.execute("UPDATE users SET balance = balance - 5 WHERE user_id = ?", (u_id,))
        await db.commit()
        if m_type == "video": await bot.send_video(u_id, media[0], caption=f"💰 Қалдық: {balance-5}$", protect_content=True)
        else: await bot.send_photo(u_id, media[0], caption=f"💰 Қалдық: {balance-5}$", protect_content=True)

async def show_secret_media(message):
    async with aiosqlite.connect("bot_main_v3.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Бос.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔥 Қызықты (+8$)", callback_data=f"accept_{item[0]}"), InlineKeyboardButton(text="❌ Жоқ", callback_data=f"reject_{item[0]}")]])
        if item[2] == "video": await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else: await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

@dp.callback_query(F.data.startswith(("accept_", "reject_")))
async def process_approval(call: types.CallbackQuery):
    action, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_main_v3.db") as db:
        if action == "accept":
            await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
            r_u = await (await db.execute("SELECT user_id FROM users ORDER BY RANDOM() LIMIT 1")).fetchone()
            if r_u: 
                await db.execute("UPDATE users SET balance = balance + 8 WHERE user_id = ?", (r_u[0],))
                try: await bot.send_message(r_u[0], "✨ Сәтті күн! +8$ бонус берілді!")
                except: pass
        else: await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    await call.message.delete()
    await show_secret_media(call.message)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
