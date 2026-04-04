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

# --- ДЕРЕКТЕР ҚОРЫН ИНИЦИАЛИЗАЦИЯЛАУ ---
async def init_db():
    async with aiosqlite.connect("bot_vip.db") as db:
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
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# --- ПЕРНЕТАҚТАЛАР ---
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

# --- БОТТЫҢ БАСЫ /START ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    async with aiosqlite.connect("bot_vip.db") as db:
        curr = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user_exists = await curr.fetchone()
        
        if not user_exists:
            # НАКРУТКАДАН ҚОРҒАУ
            if not message.from_user.username and not message.from_user.first_name:
                return await message.answer("⚠️ Кешіріңіз, сіздің аккаунтыңыз күмәнді көрінеді. Накрутка жасауға тыйым салынған!")

            ref_id = None
            if len(args) > 1 and args[1].isdigit():
                ref_id = int(args[1])
                if ref_id == user_id: ref_id = None
            
            await db.execute("INSERT INTO users (user_id, balance, last_bonus, referrer_id) VALUES (?, ?, ?, ?)", 
                             (user_id, 5.0, datetime.now().isoformat(), ref_id))
            
            if ref_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                try:
                    await bot.send_message(ref_id, "🤝 Сүйінші! Сіздің сілтемеңізбен жаңа дос қосылды. +10$ бонус берілді!")
                except: pass
            await db.commit()

    if not await is_subscribed(user_id):
        return await message.answer(f"🛑 Толық мүмкіндік алу үшін арнамызға жазылыңыз:\n{CHANNEL_LINK}", disable_web_page_preview=True)

    await message.answer("👋 Қош келдіңіз! Мұнда ең қызықты контенттер жиналған.\n\n🎁 Сізге алғашқы 5$ бонус берілді! Күн сайын кіріп 15$ алып тұрыңыз.", reply_markup=main_kb())

# --- НЕГІЗГІ ЛОГИКА ---
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # КҮНДЕЛІКТІ БОНУСТЫ ТЕКСЕРУ (АВТОМАТТЫ)
    async with aiosqlite.connect("bot_vip.db") as db:
        res = await db.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
        row = await res.fetchone()
        if row:
            last_t = datetime.fromisoformat(row[0])
            if datetime.now() - last_t >= timedelta(hours=24):
                await db.execute("UPDATE users SET balance = balance + 15.0, last_bonus = ? WHERE user_id = ?", 
                                 (datetime.now().isoformat(), user_id))
                await db.commit()
                await message.answer("⭐ Қайырлы күн! Сізге кезекті 15$ бонус қосылды!")

    if message.text == "🎥 Видео көру":
        await send_random_content(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_random_content(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Сатып алу 💳", url=f"https://t.me/{MANAGER[1:]}")]])
        await message.answer(f"💎 Жеке каналға кіру үшін менеджерге жазыңыз. Ең эксклюзивті материалдар сонда!", reply_markup=ikb)
    
    # АДМИН ПАНЕЛЬ БАТЫРМАЛАРЫ
    elif user_id == ADMIN_ID:
        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_vip.db") as db:
                u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                m_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE is_approved=1")).fetchone())[0]
                await message.answer(f"📊 **Бот статистикасы:**\n\n👤 Қолданушылар: {u_count}\n🎬 Дайын контент: {m_count}\n✅ Бот белсенді жұмыс істеп тұр.")
        
        elif message.text == "📢 Рассылка":
            await message.answer("📝 Барлық қолданушыларға жіберілетін мәтінді жазыңыз:")
            dp.message.register(process_broadcast, F.text) # Келесі хабарламаны күту
            
        elif message.text == "🔒 Жасырын":
            await show_admin_approval(message)
        
        elif message.text == "🏠 Басты мәзір":
            await message.answer("Негізгі мәзірге оралдыңыз.", reply_markup=main_kb())

    # МЕДИА ҚАБЫЛДАУ (Админ жіберсе бірден базаға, қолданушы жіберсе тексеріске)
    if (message.video or message.photo) and not message.from_user.is_bot:
        file_id = message.video.file_id if message.video else message.photo[-1].file_id
        file_type = "video" if message.video else "photo"
        is_approved = 1 if user_id == ADMIN_ID else 0
        
        async with aiosqlite.connect("bot_vip.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", 
                             (file_id, file_type, is_approved))
            await db.commit()
        
        if is_approved:
            await message.answer("✅ Контент сәтті қосылды және барлығына қолжетімді!")
        else:
            await message.answer("📩 Рахмет! Сіз жіберген материал тексерістен соң жарияланады.")

# --- КОНТЕНТ ЖІБЕРУ (РАНДОМ ЖӘНЕ ҚАЙТАЛАНБАЙТЫН) ---
async def send_random_content(message, m_type):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_vip.db") as db:
        res = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = (await res.fetchone())[0]
        
        if balance < 5:
            link = await create_start_link(bot, str(user_id), encode=True)
            return await message.answer(f"❌ Балансыңызда қаражат жеткіліксіз (5$ керек).\n💰 Қазіргі баланс: {balance}$\n\n🔗 Дос шақырып бонус алыңыз:\n`{link}`", parse_mode="Markdown")

        query = """SELECT id, file_id FROM content 
                   WHERE file_type = ? AND is_approved = 1 
                   AND file_id NOT IN (SELECT file_id FROM views WHERE user_id = ?) 
                   ORDER BY RANDOM() LIMIT 1"""
        content = await (await db.execute(query, (m_type, user_id))).fetchone()
        
        if not content:
            return await message.answer("🎬 Әзірге сіз көрмеген жаңа контент қалмады. Кейінірек тексеріңіз!")

        await db.execute("UPDATE users SET balance = balance - 5.0 WHERE user_id = ?", (user_id,))
        await db.execute("INSERT INTO views (user_id, file_id) VALUES (?, ?)", (user_id, content[1]))
        await db.commit()
        
        link = await create_start_link(bot, str(user_id), encode=True)
        caption = f"🏷 Баланс: {balance-5}$\n\n🔥 Достарыңды шақырып, көбірек көруге мүмкіндік ал:\n{link}"
        
        if m_type == "video":
            await bot.send_video(user_id, content[1], caption=caption, protect_content=True)
        else:
            await bot.send_photo(user_id, content[1], caption=caption, protect_content=True)

# --- АДМИН ПАНЕЛЬ: ЖАСЫРЫН БӨЛІМ ---
async def show_admin_approval(message):
    async with aiosqlite.connect("bot_vip.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item:
            return await message.answer("📭 Жасырын бөлімде жаңа өтініштер жоқ.")
        
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Қызықты (+8$)", callback_data=f"app_{item[0]}"),
             InlineKeyboardButton(text="❌ Қызық емес", callback_mode=f"rej_{item[0]}")]
        ])
        
        if item[2] == "video":
            await bot.send_video(ADMIN_ID, item[1], caption="Тексеріңіз:", reply_markup=ikb)
        else:
            await bot.send_photo(ADMIN_ID, item[1], caption="Тексеріңіз:", reply_markup=ikb)

@dp.callback_query(F.data.startswith(("app_", "rej_")))
async def admin_callback(call: types.CallbackQuery):
    action, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_vip.db") as db:
        if action == "app":
            await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
            # Кездейсоқ бір қолданушыға бонус (құпия түрде)
            random_user = await (await db.execute("SELECT user_id FROM users ORDER BY RANDOM() LIMIT 1")).fetchone()
            if random_user:
                await db.execute("UPDATE users SET balance = balance + 8 WHERE user_id = ?", (random_user[0],))
                try: await bot.send_message(random_user[0], "✨ Бүгін сіздің сәтті күніңіз! Балансыңызға сыйлық ретінде 8$ қосылды!")
                except: pass
        else:
            await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    
    await call.message.delete()
    await show_admin_approval(call.message)

# --- РАССЫЛКА ФУНКЦИЯСЫ ---
async def process_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID or message.text in ["📊 Статистика", "📢 Рассылка", "🔒 Жасырын"]:
        return

    success, blocked = 0, 0
    async with aiosqlite.connect("bot_vip.db") as db:
        users = await (await db.execute("SELECT user_id FROM users")).fetchall()
        for u in users:
            try:
                await bot.send_message(u[0], message.text)
                success += 1
                await asyncio.sleep(0.05) # Телеграм лимитінен аспау үшін
            except TelegramForbiddenError:
                blocked += 1
            except: pass
    
    await message.answer(f"✅ Хабарлама таратылды!\n\n✔ Жеткізілді: {success}\n🚫 Блоктағандар: {blocked}")

@dp.message(Command("admin"))
async def open_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔧 Админ панельге қош келдіңіз. Төмендегі батырмаларды қолданыңыз:", reply_markup=admin_kb())

# --- БОТТЫ ІСКЕ ҚОСУ ---
async def main():
    await init_db()
    print("Бот іске қосылды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот тоқтатылды.")
