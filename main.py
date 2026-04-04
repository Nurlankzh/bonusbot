import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USER = "@Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Күйлерді сақтау (Railway қайта қосылғанда тазаланады)
broadcast_mode = {}
give_balance_mode = {}

# --- ДЕРЕКТЕР ҚОРЫ ---
async def init_db():
    async with aiosqlite.connect("bot_main_v3.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
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

# --- СТАРТ ЖӘНЕ ТІРКЕЛУ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    async with aiosqlite.connect("bot_main_v3.db") as db:
        user = await (await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        
        if not user:
            # Жаңа юзерге 5$ бонус (1 видеоға)
            await db.execute("INSERT INTO users (user_id, balance, last_bonus, referrer_id) VALUES (?, 5.0, ?, ?)", 
                             (user_id, datetime.now().isoformat(), ref_id))
            
            # Шақырған адамға +10$
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                try: await bot.send_message(ref_id, "🤝 Досыңыз тіркелді! Сізге +10$ бонус берілді!")
                except: pass
            await db.commit()

    if user_id == ADMIN_ID:
        await message.answer("👑 Қош келдіңіз, Админ!", reply_markup=get_admin_kb())
    else:
        await message.answer("🌟 Ботқа қош келдіңіз! Видео көру үшін балансыңызды толтырыңыз.", reply_markup=get_main_kb())

# --- КОНТЕНТ ШЫҒАРУ ЛОГИКАСЫ ---
async def send_media(message: types.Message, m_type: str):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
        balance = res[0] if res else 0.0

        if balance < 5.0:
            link = await create_start_link(bot, str(user_id), encode=True)
            return await message.answer(
                f"💰 Баланс: {balance}$\n❌ Видео көру үшін кемінде 5$ керек.\n\n"
                f"🔗 Досыңызды шақырып, +10$ бонус алыңыз:\n`{link}`",
                parse_mode="Markdown"
            )

        query = "SELECT file_id FROM content WHERE file_type = ? AND is_approved = 1 ORDER BY RANDOM() LIMIT 1"
        media = await (await db.execute(query, (m_type,))).fetchone()
        
        if not media:
            return await message.answer("😔 Әзірге контент жоқ.")

        # Балансты шегеру
        new_balance = balance - 5.0
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()

        cap = f"💰 Қалған баланс: {new_balance}$"
        if m_type == "video":
            await bot.send_video(user_id, media[0], caption=cap, protect_content=True)
        else:
            await bot.send_photo(user_id, media[0], caption=cap, protect_content=True)

# --- НЕГІЗГІ ӨҢДЕУШІ (ADMIN + USER) ---
@dp.message()
async def handle_all(message: types.Message):
    user_id = message.from_user.id

    # --- АДМИН ПАНЕЛЬ ---
    if user_id == ADMIN_ID:
        if user_id in give_balance_mode:
            try:
                target_id, amount = message.text.split()
                async with aiosqlite.connect("bot_main_v3.db") as db:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(amount), int(target_id)))
                    await db.commit()
                await message.answer(f"✅ ID {target_id} пайдаланушысына {amount}$ берілді!", reply_markup=get_admin_kb())
                try: await bot.send_message(int(target_id), f"🎁 Админ сізге {amount}$ бонус салды!")
                except: pass
                del give_balance_mode[user_id]
                return
            except:
                await message.answer("⚠️ Қате! Формат: `ID сома`", reply_markup=get_admin_kb())
                del give_balance_mode[user_id]
                return

        if user_id in broadcast_mode:
            del broadcast_mode[user_id]
            async with aiosqlite.connect("bot_main_v3.db") as db:
                users = await (await db.execute("SELECT user_id FROM users")).fetchall()
                for (u_id,) in users:
                    try: await message.copy_to(u_id); await asyncio.sleep(0.05)
                    except: pass
            await message.answer("✅ Рассылка аяқталды!", reply_markup=get_admin_kb())
            return

        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                await message.answer(f"📊 Пайдаланушылар саны: {u}")
            return
        elif message.text == "💰 Доллар беру":
            give_balance_mode[user_id] = True
            await message.answer("💵 ID және соманы жазыңыз (Мысалы: 6303091468 50):", reply_markup=types.ReplyKeyboardRemove())
            return
        elif message.text == "📢 Рассылка":
            broadcast_mode[user_id] = True
            await message.answer("📝 Хабарламаны жіберіңіз:", reply_markup=types.ReplyKeyboardRemove())
            return
        elif message.text == "🔒 Жасырын":
            await show_approval(message); return
        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Пайдаланушы режимі.", reply_markup=get_main_kb()); return

    # --- ПАЙДАЛАНУШЫ БӨЛІМІ ---
    if message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Жабық каналға кіру үшін менеджерге жазыңыз:", reply_markup=ikb)

    # Контент қабылдау
    if message.video or message.photo:
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, is_a))
            await db.commit()
        await message.answer("✅ Сақталды!" if is_a else "📩 Тексеруге жіберілді.")

# --- ЖАСЫРЫН БӨЛІМ (APPROVAL) ---
async def show_approval(message):
    async with aiosqlite.connect("bot_main_v3.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Жаңа контент жоқ.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Қос", callback_data=f"ok_{item[0]}"), InlineKeyboardButton(text="❌ Өшір", callback_data=f"no_{item[0]}")]])
        if item[2] == "video": await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else: await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

@dp.callback_query(F.data.startswith(("ok_", "no_")))
async def callback_handler(call: types.CallbackQuery):
    act, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_main_v3.db") as db:
        if act == "ok": await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
        else: await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    await call.message.delete()
    await show_approval(call.message)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
