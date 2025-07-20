import asyncio
import logging
import time
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask
from threading import Thread

# ====== ТВОЙ ТОКЕН МЕН АДМИН АЙДИ ======
API_TOKEN = "7748542247:AAGVgKPaOvHH7iDL4Uei2hM_zsI_6gCowkM"  # ← сенің токенің
ADMIN_ID = 6927494520  # ← сенің админ айдиң
CHANNELS = ["@oqigalaruyatsiz", "@bokseklub", "@Qazhuboyndar"]
# =======================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ======== KEEP ALIVE ========
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ======== БАЗА ИНИЦИАЛИЗАЦИЯ ========
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                bonus INTEGER DEFAULT 10,
                ref TEXT,
                last_video_index INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, timestamp INTEGER)")
        await db.commit()
    try:
        async with aiosqlite.connect("bot.db") as db:
            await db.execute("ALTER TABLE users ADD COLUMN last_video_index INTEGER DEFAULT 0")
            await db.commit()
    except:
        pass

# ======== КӨМЕКШІ ФУНКЦИЯЛАР ========
async def is_subscribed(user_id):
    if user_id == ADMIN_ID:
        return True
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

async def get_bonus(user_id):
    if user_id == ADMIN_ID:
        return 999999
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT bonus FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def add_user(user_id, ref=None):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, bonus, ref, last_video_index) VALUES (?,?,?,?)",
                         (user_id, 10, ref, 0))
        await db.commit()

async def change_bonus(user_id, amount):
    if user_id == ADMIN_ID:
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_next_video(user_id: int):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM videos") as cur:
            row = await cur.fetchone()
            total_videos = row[0] if row else 0
        if total_videos == 0:
            return None
        async with db.execute("SELECT last_video_index FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            index = row[0] if row and row[0] is not None else 0
        if index >= total_videos:
            index = 0
        async with db.execute("SELECT file_id FROM videos ORDER BY id LIMIT 1 OFFSET ?", (index,)) as cur:
            row = await cur.fetchone()
            file_id = row[0] if row else None
        await db.execute("UPDATE users SET last_video_index=? WHERE user_id=?", (index + 1, user_id))
        await db.commit()
        return file_id

# ======== МЕНЮ ========
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
            [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="✅ VIP режим")],
            [KeyboardButton(text="➕ 📢 Каналдар"), KeyboardButton(text="☎ Оператор")],
            [KeyboardButton(text="📊 Қолданушылар саны")]
        ],
        resize_keyboard=True
    )

# ======== ХЕНДЛЕР ========
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    if msg.chat.type != "private":
        return
    ref = None
    if len(msg.text.split()) > 1:
        ref = msg.text.split()[1]
    await add_user(msg.from_user.id, ref)
    if ref and ref.isdigit():
        ref_id = int(ref)
        if ref_id != msg.from_user.id:
            await change_bonus(ref_id, 2)
            try:
                await bot.send_message(ref_id, f"🎉 Сіз жаңа қолданушыны шақырдыңыз! (+2 бонус)\n👉 @{msg.from_user.username or msg.from_user.first_name}")
            except Exception as e:
                print("[DEBUG] Хабарлама жіберу қатесі:", e)
    if msg.from_user.id != ADMIN_ID and not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен мына каналдарға тіркеліңіз:\n" + "\n".join(CHANNELS))
    else:
        await msg.answer(f"Қош келдіңіз! Сіздің бонусыңыз: {await get_bonus(msg.from_user.id)}", reply_markup=main_menu())

@dp.message(F.text == "🎥 Видео")
async def get_video(msg: Message):
    if msg.chat.type != "private":
        return
    if msg.from_user.id != ADMIN_ID and not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен каналдарға тіркеліңіз!")
        return
    b = await get_bonus(msg.from_user.id)
    if msg.from_user.id != ADMIN_ID and b < 3:
        await msg.answer("Бонус жеткіліксіз")
        return
    file_id = await get_next_video(msg.from_user.id)
    if file_id:
        await change_bonus(msg.from_user.id, -3)
        await bot.send_video(msg.chat.id, file_id)
    else:
        await msg.answer("Видео жоқ!")

@dp.message(F.text == "🖼 Фото")
async def get_photo(msg: Message):
    if msg.chat.type != "private":
        return
    if msg.from_user.id != ADMIN_ID and not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен каналдарға тіркеліңіз!")
        return
    b = await get_bonus(msg.from_user.id)
    if msg.from_user.id != ADMIN_ID and b < 2:
        await msg.answer("Бонус жеткіліксіз")
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT file_id FROM photos ORDER BY id DESC LIMIT 1") as cur:
            row = await cur.fetchone()
            if row:
                await change_bonus(msg.from_user.id, -2)
                await bot.send_photo(msg.chat.id, row[0])
            else:
                await msg.answer("Фото жоқ!")

# Мына жерде бонус батырмасының мәтіні сен сұрағандай етіп ауыстырылды 👇👇👇
@dp.message(F.text == "⭐ Бонус")
async def get_bonus_link(msg: Message):
    if msg.chat.type != "private":
        return
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={msg.from_user.id}"
    await msg.answer(
        f"⭐ Бонус жинау үшін достарыңды шақыр!\n"
        f"Әр тіркелген досың үшін +2 бонус аласыз ✅\n\n"
        f"👉 Сіздің сілтемеңіз:\n{link}"
    )

@dp.message(F.text == "✅ VIP режим")
async def vip_mode(msg: Message):
    if msg.chat.type != "private":
        return
    await msg.answer(
        "💎 VIP режим:\n"
        "30 бонус – 1000 тг\n"
        "50 бонус – 1500 тг\n"
        "80 бонус – 2000 тг\n\n"
        "👉 VIP сатып алу үшін: @KazHubALU жаз!\n\n"
        "⚡ Қосымша ақпарат алу үшін админге жазыңыз.",
        reply_markup=main_menu()
    )

@dp.message(F.text == "➕ 📢 Каналдар")
async def channels_list(msg: Message):
    if msg.chat.type != "private":
        return
    text = "🔥 Біздің каналдарға жазылыңыз:\n"
    for ch in CHANNELS:
        text += f"{ch}\n"
    await msg.answer(text)

@dp.message(F.text == "☎ Оператор")
async def contact_operator(msg: Message):
    if msg.chat.type != "private":
        return
    await msg.answer("⚠ Егер ботта ақау болса, операторға жазыңыз: http://t.me/Assistedkz_bot")

@dp.message(F.text == "📊 Қолданушылар саны")
async def user_count(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("Бұл ақпарат тек админге арналған.")
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
    await msg.answer(f"👥 Боттағы қолданушылар саны: {count}")

# ======== АДМИН ФОТО/ВИДЕО САҚТАУ ========
@dp.message(F.video)
async def save_video(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    file_id = msg.video.file_id
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO videos (file_id, timestamp) VALUES (?,?)", (file_id, int(time.time())))
        await db.commit()
    await msg.answer("✅ Видео сақталды!")

@dp.message(F.photo)
async def save_photo(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    file_id = msg.photo[-1].file_id
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO photos (file_id) VALUES (?)", (file_id,))
        await db.commit()
    await msg.answer("✅ Фото сақталды!")

# ======== БАСҚА ХАБАРЛАМАНЫ ӨШІРУ ========
@dp.message()
async def delete_any_text(msg: Message):
    if msg.chat.type != "private":
        return
    if msg.from_user.id == ADMIN_ID:
        return
    allowed_texts = ["🎥 Видео", "🖼 Фото", "⭐ Бонус", "✅ VIP режим", "➕ 📢 Каналдар", "☎ Оператор", "📊 Қолданушылар саны"]
    if msg.text not in allowed_texts:
        try:
            await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
        except Exception as e:
            print("[DEBUG] Хабарламаны өшіре алмадым:", e)

# ======== SCHEDULER ========
scheduler = AsyncIOScheduler()

async def add_bonus_all():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + 5")
        await db.commit()

scheduler.add_job(lambda: asyncio.create_task(add_bonus_all()), 'interval', hours=12)

# ======== СТАРТ ========
async def main():
    await init_db()
    scheduler.start()
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
