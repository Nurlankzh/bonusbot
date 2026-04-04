import asyncio
import logging
import aiosqlite
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
MANAGER = "@Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫ ---
async def init_db():
    async with aiosqlite.connect("bot_base.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 5.0, 
            last_bonus TEXT, referrer_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, 
            file_type TEXT, is_approved INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS views (
            user_id INTEGER, file_id TEXT)''')
        await db.commit()

async def is_subscribed(user_id):
    try:
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except: return False

# --- МӘЗІРЛЕР ---
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

# --- БОТТЫҢ БАСЫ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = await curr.fetchone()
        
        if not user:
            # НАКРУТКАДАН ҚОРҒАУ
            if not message.from_user.username and not message.from_user.first_name:
                return await message.answer("⚠️ Аккаунтыңыз тексерістен өтпеді. Накрутка жасауға тыйым салынады!")

            ref_id = None
            if len(args) > 1 and args[1].isdigit():
                ref_candidate = int(args[1])
                if ref_candidate != user_id:
                    ref_id = ref_candidate
            
            await db.execute("INSERT INTO users (user_id, balance, last_bonus, referrer_id) VALUES (?, ?, ?, ?)", 
                             (user_id, 5.0, datetime.now().isoformat(), ref_id))
            
            if ref_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                try: await bot.send_message(ref_id, "🤝 Жаңа дос қосылды! Балансыңызға +10$ түсті.")
                except: pass
            await db.commit()

    if not await is_subscribed(user_id):
        return await message.answer(f"⛔️ Ботты қолдану үшін каналға жазылыңыз:\n{CHANNEL_LINK}", disable_web_page_preview=True)

    await message.answer("🌟 Қош келдіңіз! Күнделікті 15$ бонус автоматты түрде қосылады.", reply_markup=main_kb())

# --- НЕГІЗГІ ХЭНДЛЕР ---
@dp.message()
async def main_handler(message: types.Message):
    user_id = message.from_user.id
    
    # АВТО БОНУС (24 САҒАТ)
    async with aiosqlite.connect("bot_base.db") as db:
        curr = await db.execute("SELECT last_bonus, balance FROM users WHERE user_id = ?", (user_id,))
        row = await curr.fetchone()
        if row:
            last_t = datetime.fromisoformat(row[0])
            if datetime.now() - last_t >= timedelta(hours=24):
                await db.execute("UPDATE users SET balance = balance + 15.0, last_bonus = ? WHERE user_id = ?", 
                                 (datetime.now().isoformat(), user_id))
                await db.commit()
                await message.answer("🎁 Күнделікті 15$ бонус берілді!")

    if message.text == "🎥 Видео көру": await send_content(message, "video")
    elif message.text == "🖼 Фото көру": await send_content(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER[1:]}")]])
        await message.answer(f"💎 Каналды осы жерден сатып аласыз:", reply_markup=ikb)
    elif message.text == "🏠 Басты мәзір": await message.answer("Негізгі мәзір", reply_markup=main_kb())
    
    # АДМИН БӨЛІМІ
    elif user_id == ADMIN_ID:
        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_base.db") as db:
                users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                media = (await (await db.execute("SELECT COUNT(*) FROM content WHERE is_approved=1")).fetchone())[0]
                await message.answer(f"📊 Статистика:\n👤 Пайдаланушылар: {users}\n🎥 Видео/Фото: {media}\n🚫 Блокталғандар: Тексерілуде...")
        
        elif message.text == "📢 Рассылка":
            await message.answer("📣 Рассылка мәтінін жіберіңіз:")
            @dp.message()
            async def process_broadcast(msg: types.Message):
                if msg.from_user.id != ADMIN_ID: return
                count = 0
                blocked = 0
                async with aiosqlite.connect("bot_base.db") as db:
                    curr = await db.execute("SELECT user_id FROM users")
                    all_users = await curr.fetchall()
                    for u in all_users:
                        try:
                            await bot.send_message(u[0], msg.text)
                            count += 1
                        except TelegramForbiddenError: blocked += 1
                        except: pass
                await msg.answer(f"✅ Аяқталды!\nЖетті: {count}\nБлоктаған: {blocked}")
        
        elif message.text == "🔒 Жасырын": await show_secret(message)

    # МЕДИА ЖҮКТЕУ (ПРИВАТТЫ)
    if (message.video or message.photo) and not message.from_user.is_bot:
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_t = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_base.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_t, is_a))
            await db.commit()
        await message.answer("✅ Базаға қосылды!" if is_a else "📩 Админге жіберілді!")

# --- МЕДИА ЖІБЕРУ ЛОГИКАСЫ ---
async def send_content(message, m_type):
    u_id = message.from_user.id
    async with aiosqlite.connect("bot_base.db") as db:
        balance = (await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (u_id,))).fetchone())[0]
        if balance < 5:
            link = await create_start_link(bot, str(u_id), encode=True)
            return await message.answer(f"💰 Баланс: {balance}$\n❌ Кемі 5$ керек.\n🔗 Дос шақыр: {link}")

        query = "SELECT file_id FROM content WHERE file_type = ? AND is_approved = 1 AND file_id NOT IN (SELECT file_id FROM views WHERE user_id = ?) ORDER BY RANDOM() LIMIT 1"
        res = await (await db.execute(query, (m_type, u_id))).fetchone()
        if not res: return await message.answer("😔 Әзірге жаңа зат жоқ.")

        await db.execute("UPDATE users SET balance = balance - 5 WHERE user_id = ?", (u_id,))
        await db.execute("INSERT INTO views (user_id, file_id) VALUES (?, ?)", (u_id, res[0]))
        await db.commit()
        
        link = await create_start_link(bot, str(u_id), encode=True)
        cap = f"💰 Қалдық: {balance-5}$\n🔗 Реферал сілтемеңіз: {link}"
        if m_type == "video": await bot.send_video(u_id, res[0], caption=cap, protect_content=True)
        else: await bot.send_photo(u_id, res[0], caption=cap, protect_content=True)

# --- АДМИН ЖАСЫРЫН ---
async def show_secret(message):
    async with aiosqlite.connect("bot_base.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Жасырын бөлім бос.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Қызықты (+8$)", callback_data=f"ok_{item[0]}"),
             InlineKeyboardButton(text="❌ Қызық емес", callback_data=f"no_{item[0]}")]
        ])
        if item[2] == "video": await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else: await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

@dp.callback_query(F.data.startswith(("ok_", "no_")))
async def admin_decision(call: types.CallbackQuery):
    act, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_base.db") as db:
        if act == "ok":
            await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
            lucky = (await (await db.execute("SELECT user_id FROM users ORDER BY RANDOM() LIMIT 1")).fetchone())[0]
            await db.execute("UPDATE users SET balance = balance + 8 WHERE user_id = ?", (lucky,))
            try: await bot.send_message(lucky, "✨ Бүгін сіздің сәтті күніңіз! Балансыңызға 8$ бонус қосылды!")
            except: pass
        else: await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    await call.message.delete()
    await show_secret(call.message)

@dp.message(Command("admin"))
async def open_adm(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔧 Админ панель ашылды", reply_markup=admin_kb())

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
