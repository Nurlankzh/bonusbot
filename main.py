import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# =================== НАСТРОЙКАЛАР ===================
API_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo" 
ADMIN_ID = 6303091468  # 🔥 Жаңа Админ ID орнатылды
# Жаңа канал тізімі
CHANNELS = ["@uyatsizoqiga"] 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# =================== БАЗА ===================
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                bonus INTEGER DEFAULT 10,
                ref TEXT,
                last_video_index INTEGER DEFAULT 0,
                last_photo_index INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT)")
        await db.commit()

async def add_user(user_id, ref=None):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, bonus, ref, last_video_index, last_photo_index)
            VALUES (?,?,?,?,?)
        """, (user_id, 10, ref, 0, 0))
        await db.commit()

async def get_bonus(user_id):
    if user_id == ADMIN_ID:
        return 999999
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT bonus FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def change_bonus(user_id, amount):
    if user_id == ADMIN_ID:
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

async def is_subscribed(user_id):
    if user_id == ADMIN_ID:
        return True
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ("left", "kicked"):
                return False
        except Exception as e:
            # Егер канал бан алса немесе бот ол жерде админ болмаса, тексеруді өткізіп жібереді
            logging.error(f"Каналды тексеру мүмкін болмады {ch}: {e}")
            continue 
    return True

# =================== ВИДЕО/ФОТО ===================
async def get_next_video(user_id):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM videos") as c:
            total = (await c.fetchone())[0]
        if total == 0:
            return None
        async with db.execute("SELECT last_video_index FROM users WHERE user_id=?", (user_id,)) as c:
            idx = (await c.fetchone())[0]
        
        # Егер видеолар таусылса, басынан бастайды
        current_idx = idx if idx < total else 0
        
        async with db.execute("SELECT file_id FROM videos ORDER BY id LIMIT 1 OFFSET ?", (current_idx,)) as c:
            result = await c.fetchone()
            if not result: return None
            file_id = result[0]
            
        await db.execute("UPDATE users SET last_video_index=? WHERE user_id=?", (current_idx + 1, user_id))
        await db.commit()
        return file_id

async def get_next_photo(user_id):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM photos") as c:
            total = (await c.fetchone())[0]
        if total == 0:
            return None
        async with db.execute("SELECT last_photo_index FROM users WHERE user_id=?", (user_id,)) as c:
            idx = (await c.fetchone())[0]
            
        current_idx = idx if idx < total else 0
            
        async with db.execute("SELECT file_id FROM photos ORDER BY id LIMIT 1 OFFSET ?", (current_idx,)) as c:
            result = await c.fetchone()
            if not result: return None
            file_id = result[0]
            
        await db.execute("UPDATE users SET last_photo_index=? WHERE user_id=?", (current_idx + 1, user_id))
        await db.commit()
        return file_id

# =================== МЕНЮ ===================
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
            [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="✅ VIP режим")],
            [KeyboardButton(text="➕ 📢 Каналдар"), KeyboardButton(text="☎ Оператор")],
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
            [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="✅ VIP режим")],
            [KeyboardButton(text="📊 Қолданушылар саны"), KeyboardButton(text="📢 Рассылка")]
        ],
        resize_keyboard=True
    )

# =================== ХЕНДЛЕР ===================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    if msg.chat.type != "private":
        return
    ref = msg.text.split()[1] if len(msg.text.split()) > 1 else None
    await add_user(msg.from_user.id, ref)
    
    if ref and ref.isdigit():
        ref_id = int(ref)
        if ref_id != msg.from_user.id:
            await change_bonus(ref_id, 2)
            try:
                await bot.send_message(ref_id, f"🎉 Сіз жаңа қолданушыны шақырдыңыз! (+2 бонус)")
            except:
                pass

    if not await is_subscribed(msg.from_user.id):
        await msg.answer(f"❌ Ботты қолдану үшін мына каналға тіркеліңіз:\n{CHANNELS[0]}")
    else:
        markup = admin_menu() if msg.from_user.id == ADMIN_ID else main_menu()
        await msg.answer(f"Қош келдіңіз! Сіздің бонусыңыз: {await get_bonus(msg.from_user.id)}", reply_markup=markup)

@dp.message(F.text == "🎥 Видео")
async def get_video(msg: Message):
    if not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен каналға тіркеліңіз!")
        return
    
    b = await get_bonus(msg.from_user.id)
    if msg.from_user.id != ADMIN_ID and b < 3:
        await msg.answer("Бонус жеткіліксіз (3 бонус керек)")
        return
        
    file_id = await get_next_video(msg.from_user.id)
    if file_id:
        try:
            await bot.send_video(msg.chat.id, file_id)
            await change_bonus(msg.from_user.id, -3)
        except:
            await msg.answer("Видеоны жіберу мүмкін болмады (өшірілген болуы мүмкін)")
    else:
        await msg.answer("Видео базасы бос!")

@dp.message(F.text == "🖼 Фото")
async def get_photo(msg: Message):
    if not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен каналға тіркеліңіз!")
        return
        
    b = await get_bonus(msg.from_user.id)
    if msg.from_user.id != ADMIN_ID and b < 2:
        await msg.answer("Бонус жеткіліксіз (2 бонус керек)")
        return
        
    file_id = await get_next_photo(msg.from_user.id)
    if file_id:
        try:
            await bot.send_photo(msg.chat.id, file_id)
            await change_bonus(msg.from_user.id, -2)
        except:
            await msg.answer("Фотоны жіберу мүмкін болмады.")
    else:
        await msg.answer("Фото базасы бос!")

@dp.message(F.text == "⭐ Бонус")
async def bonus_link(msg: Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={msg.from_user.id}"
    await msg.answer(f"⭐ Досыңды шақырып бонус ал!\n👉 Сілтеме: {link}")

@dp.message(F.text == "📊 Қолданушылар саны")
async def user_count(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
    await msg.answer(f"👥 Қолданушылар саны: {count}")

@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("✍️ Маған жібергің келетін хабарламаны жаз.")

@dp.message(F.text, F.from_user.id == ADMIN_ID)
async def admin_text_handler(msg: Message):
    # Егер админ жай мәтін жазса, оны рассылка деп қабылдау (бұл жерде логиканы шектеуге болады)
    if msg.text in ["🎥 Видео", "🖼 Фото", "⭐ Бонус", "📊 Қолданушылар саны"]: return
    
    await msg.answer("📤 Рассылка басталды...")
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    
    sent = 0
    for u in users:
        try:
            await bot.send_message(u[0], msg.text)
            sent += 1
            await asyncio.sleep(0.05) # Блокқа түспеу үшін кішкене кідіріс
        except:
            continue
    await msg.answer(f"✅ Рассылка {sent} адамға жіберілді.")

@dp.message(F.video)
async def save_video(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO videos (file_id) VALUES (?)", (msg.video.file_id,))
        await db.commit()
    await msg.answer("✅ Видео базаға сақталды!")

@dp.message(F.photo)
async def save_photo(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO photos (file_id) VALUES (?)", (msg.photo[-1].file_id,))
        await db.commit()
    await msg.answer("✅ Фото базаға сақталды!")

# =================== SCHEDULER ===================
async def add_bonus_all():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + 5")
        await db.commit()

# =================== MAIN ===================
async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(add_bonus_all, 'interval', hours=12)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

