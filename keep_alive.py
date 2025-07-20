import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite

# 👉 Мұнда өзіңнің токеніңді қой
API_TOKEN = "7539520982:AAHG6Oq8QkLmKgV9E8X0PIhVoA3aQwmaEek"
# 👉 Мұнда админнің ID нөмірін қой
ADMIN_ID = 7047272652
# 👉 Қажетті каналдар
CHANNELS = ["@oqigalaruyatsiz", "@bokseklub", "@Qazhuboyndar"]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# -------------------- DATABASE --------------------
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, bonus INTEGER DEFAULT 10, ref TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, timestamp INTEGER)")
        await db.commit()

# -------------------- UTILS --------------------
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
        await db.execute("INSERT OR IGNORE INTO users (user_id, bonus, ref) VALUES (?,?,?)", (user_id,10,ref))
        await db.commit()

async def change_bonus(user_id, amount):
    if user_id == ADMIN_ID:
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus=bonus+? WHERE user_id=?", (amount,user_id))
        await db.commit()

# -------------------- MENUS --------------------
def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
            [KeyboardButton(text="⭐ Бонус")]
        ],
        resize_keyboard=True
    )
    return keyboard

# -------------------- HANDLERS --------------------
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    if msg.chat.type != "private":
        return
    ref = None
    if len(msg.text.split()) > 1:
        ref = msg.text.split()[1]
    await add_user(msg.from_user.id, ref)
    if msg.from_user.id != ADMIN_ID and not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен мына каналдарға тіркеліңіз:\n" + "\n".join(CHANNELS))
    else:
        await msg.answer(
            f"Қош келдіңіз! Сіздің бонусыңыз: {await get_bonus(msg.from_user.id)}",
            reply_markup=main_menu()
        )

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
    else:
        await change_bonus(msg.from_user.id, -3)
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT file_id FROM videos ORDER BY id DESC LIMIT 1") as cur:
                row = await cur.fetchone()
                if row:
                    await bot.send_video(msg.from_user.id, row[0])
                else:
                    await msg.answer("Видео жоқ")

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
    else:
        await change_bonus(msg.from_user.id, -2)
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT file_id FROM photos ORDER BY id DESC LIMIT 1") as cur:
                row = await cur.fetchone()
                if row:
                    await bot.send_photo(msg.from_user.id, row[0])
                else:
                    await msg.answer("Фото жоқ")

@dp.message(F.text == "⭐ Бонус")
async def get_bonus_link(msg: Message):
    if msg.chat.type != "private":
        return
    link = f"https://t.me/vipkazaktarbot?start={msg.from_user.id}"
    await msg.answer(f"Сіздің рефераль сілтемеңіз: {link}")

@dp.message()
async def delete_anything(msg: Message):
    if msg.chat.type != "private":
        return
    if msg.from_user.id != ADMIN_ID and msg.text not in ["🎥 Видео", "🖼 Фото", "⭐ Бонус"]:
        try:
            await bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass

# -------------------- SCHEDULED TASKS --------------------
scheduler = AsyncIOScheduler()

async def add_bonus_all():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + 5")
        await db.commit()

async def clear_videos():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM videos")
        await db.commit()

scheduler.add_job(lambda: asyncio.create_task(add_bonus_all()), 'interval', hours=12)
scheduler.add_job(lambda: asyncio.create_task(clear_videos()), 'interval', hours=2)

# -------------------- ADMIN HANDLERS --------------------
@dp.message(F.video)
async def save_video(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    file_id = msg.video.file_id
    print(f"[TEST] Видео file_id: {file_id}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT INTO videos (file_id, timestamp) VALUES (?, ?)",
            (file_id, int(time.time()))
        )
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

# -------------------- START --------------------
from keep_alive import keep_alive  # 👈 keep_alive импорт

async def main():
    await init_db()
    scheduler.start(paused=True)
    scheduler.resume()
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()  # 👈 Flask серверін қосу
    asyncio.run(main())
