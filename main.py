import asyncio
import logging
import random
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link

# --- БАПТАУЛАР ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" # Каналдың юзернеймі
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER = "@Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫН ДАЙЫНДАУ ---
async def init_db():
    async with aiosqlite.connect("bot_base.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 5.0, 
            last_bonus TEXT, 
            referrer_id INTEGER,
            is_banned INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            file_id TEXT, 
            file_type TEXT, 
            is_approved INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS views (
            user_id INTEGER, 
            file_id TEXT)''')
        await db.commit()

# --- ТЕКСЕРУ ФУНКЦИЯЛАРЫ ---
async def is_subscribed(user_id):
    try:
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except:
        return False

# --- МӘЗІРЛЕР (REPLY КНОПКАЛАР) ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру")],
        [KeyboardButton(text="💎 Канал сатып алу")]
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔒 Жасырын"), KeyboardButton(text="🏠 Басты мәзір")]
    ], resize_keyboard=True)

# --- БОТТЫҢ ЖҰМЫСЫ ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = await curr.fetchone()
        
        if not user:
            # Накруткадан қорғау: Егер профильде фото немесе юзернейм болмаса (бот болуы мүмкін)
            if not message.from_user.username and not message.from_user.last_name:
                return await message.answer("⚠️ Кешіріңіз, сіздің аккаунтыңыз күдікті көрінеді. Накруткаға жол берілмейді!")

            ref_id = None
            if len(args) > 1 and args[1].isdigit():
                ref_candidate = int(args[1])
                if ref_candidate != user_id:
                    ref_id = ref_candidate
            
            now = datetime.now().isoformat()
            await db.execute("INSERT INTO users (user_id, last_bonus, referrer_id) VALUES (?, ?, ?)", 
                             (user_id, now, ref_id))
            
            if ref_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                try:
                    await bot.send_message(ref_id, "🤝 Құттықтаймыз! Досыңыз тіркелді, сізге 10$ бонус берілді!")
                except: pass
            await db.commit()

    if not await is_subscribed(user_id):
        return await message.answer(f"👋 Сәлем! Жұмысты бастау үшін каналға тіркел:\n{CHANNEL_LINK}", 
                                    disable_web_page_preview=True)

    await message.answer("🔥 Қош келдіңіз! Күнделікті 15$ бонус автоматты түрде қосылып тұрады.", 
                         reply_markup=main_kb())

# Автоматты бонус тексеру (хабарлама жіберген сайын)
@dp.message()
async def global_handler(message: types.Message):
    user_id = message.from_user.id
    
    # 24 сағаттық бонус логикасы
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT last_bonus, balance FROM users WHERE user_id = ?", (user_id,))
        row = await curr.fetchone()
        if row:
            last_time = datetime.fromisoformat(row[0])
            if datetime.now() - last_time >= timedelta(hours=24):
                await db.execute("UPDATE users SET balance = balance + 15.0, last_bonus = ? WHERE user_id = ?", 
                                 (datetime.now().isoformat(), user_id))
                await db.commit()
                await message.answer("🎁 Сүйінші! 24 сағат өтті, балансыңызға 15$ сыйлық қосылды!")

    # Кнопкаларды өңдеу
    if message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Сатып алу 💸", url=f"https://t.me/{MANAGER[1:]}")]])
        await message.answer(f"💎 Канал сатып алу үшін менеджерге жазыңыз: {MANAGER}", reply_markup=ikb)
    elif message.text == "🏠 Басты мәзір":
        await message.answer("Не істейміз?", reply_markup=main_kb())
    
    # Админ бөлімі
    elif message.text == "📊 Статистика" and user_id == ADMIN_ID:
        async with aiosqlite.connect("bot_base.db") as db:
            c = await db.execute("SELECT COUNT(*) FROM users")
            u_cnt = (await c.fetchone())[0]
            m = await db.execute("SELECT COUNT(*) FROM content WHERE is_approved=1")
            m_cnt = (await m.fetchone())[0]
            await message.answer(f"📊 Статистика:\n👤 Адам саны: {u_cnt}\n📥 Базадағы медиа: {m_cnt}")
    
    elif message.text == "🔒 Жасырын" and user_id == ADMIN_ID:
        await show_secret_media(message)

    # Медиа қабылдау (Админ жіберсе базаға, басқалар жіберсе жасырынға)
    if message.video or message.photo:
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_app = 1 if user_id == ADMIN_ID else 0
        
        async with aiosqlite.connect("bot_base.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", 
                             (f_id, f_type, is_app))
            await db.commit()
        
        text = "✅ Базаға сақталды!" if user_id == ADMIN_ID else "📩 Сіздің затыңыз админге тексеруге жіберілді!"
        await message.answer(text)

# --- МЕДИА ЖІБЕРУ ---
async def send_media(message, m_type):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = (await curr.fetchone())[0]
        
        if balance < 5:
            link = await create_start_link(bot, str(user_id), encode=True)
            return await message.answer(f"❌ Баланс жеткіліксіз (5$ керек).\n🔗 Дос шақыру үшін сілтеме: {link}")

        # Рандом және қайталанбайтын медиа
        query = """SELECT file_id FROM content WHERE file_type = ? AND is_approved = 1 
                   AND file_id NOT IN (SELECT file_id FROM views WHERE user_id = ?) 
                   ORDER BY RANDOM() LIMIT 1"""
        curr = await db.execute(query, (m_type, user_id))
        media = await curr.fetchone()

        if not media:
            return await message.answer("😔 Әзірге жаңа зат жоқ. Кейінірек көріңіз!")

        f_id = media[0]
        await db.execute("UPDATE users SET balance = balance - 5 WHERE user_id = ?", (user_id,))
        await db.execute("INSERT INTO views (user_id, file_id) VALUES (?, ?)", (user_id, f_id))
        await db.commit()

        link = await create_start_link(bot, str(user_id), encode=True)
        caption = f"💰 Көру құны: 5$\n💳 Баланс: {balance-5}$\n\n🔗 Реферал сілтемең: {link}"
        
        if m_type == "video":
            await bot.send_video(user_id, f_id, caption=caption, protect_content=True)
        else:
            await bot.send_photo(user_id, f_id, caption=caption, protect_content=True)

# --- АДМИН ЖАСЫРЫН БӨЛІМІ ---
async def show_secret_media(message):
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")
        item = await curr.fetchone()
        
        if not item:
            return await message.answer("📭 Жасырын бөлім бос.")

        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Қызықты (+8$)", callback_data=f"app_{item[0]}")],
            [InlineKeyboardButton(text="❌ Қызық емес", callback_data=f"del_{item[0]}")]
        ])
        
        if item[2] == "video":
            await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else:
            await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

@dp.callback_query(F.data.startswith(("app_", "del_")))
async def admin_callback(call: types.CallbackQuery):
    action, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_base.db") as db:
        if action == "app":
            await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
            # Кездейсоқ қолданушыға 8$ бонус (сезіндірмей)
            curr = await db.execute("SELECT user_id FROM users ORDER BY RANDOM() LIMIT 1")
            lucky_id = (await curr.fetchone())[0]
            await db.execute("UPDATE users SET balance = balance + 8 WHERE user_id = ?", (lucky_id,))
            try:
                await bot.send_message(lucky_id, "✨ Бүгін сіздің сәтті күніңіз! Балансыңызға 8$ бонус қосылды!")
            except: pass
        else:
            await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    
    await call.message.delete()
    await show_secret_media(call.message)

# Рассылка функциясы
@dp.message(F.text == "📢 Рассылка")
async def broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Рассылка мәтінін жіберіңіз (немесе 'отмена'):")
    
    @dp.message()
    async def get_text(msg: types.Message):
        if msg.text == "отмена": return
        async with aiosqlite.connect("bot_base.db") as db:
            curr = await db.execute("SELECT user_id FROM users")
            users = await curr.fetchall()
            for u in users:
                try: await bot.send_message(u[0], msg.text)
                except: pass
        await msg.answer("✅ Рассылка аяқталды!")

@dp.message(Command("admin"))
async def open_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Админ панель ашылды", reply_markup=admin_kb())

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
