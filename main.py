import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# =================== НАСТРОЙКАЛАР ===================
API_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo"  # 🔥 Сенің токенің
ADMIN_ID = 6927494520  # 🔥 Сенің админ айдиің
CHANNELS = ["@oqigalaruyatsiz", "@bokseklub", "@Qazhuboyndar"]

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
        except:
            return False
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
        if idx >= total:
            idx = 0
        async with db.execute("SELECT file_id FROM videos ORDER BY id LIMIT 1 OFFSET ?", (idx,)) as c:
            file_id = (await c.fetchone())[0]
        await db.execute("UPDATE users SET last_video_index=? WHERE user_id=?", (idx+1, user_id))
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
        if idx >= total:
            idx = 0
        async with db.execute("SELECT file_id FROM photos ORDER BY id LIMIT 1 OFFSET ?", (idx,)) as c:
            file_id = (await c.fetchone())[0]
        await db.execute("UPDATE users SET last_photo_index=? WHERE user_id=?", (idx+1, user_id))
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

# 🔥 Тек админге арналған меню
def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
            [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="✅ VIP режим")],
            [KeyboardButton(text="➕ 📢 Каналдар"), KeyboardButton(text="☎ Оператор")],
            [KeyboardButton(text="📊 Қолданушылар саны"), KeyboardButton(text="📢 Рассылка")]
        ],
        resize_keyboard=True
    )

# =================== ХЕНДЛЕР ===================
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
                await bot.send_message(ref_id, f"🎉 Сіз жаңа қолданушыны шақырдыңыз! (+2 бонус)")
            except:
                pass
    if msg.from_user.id != ADMIN_ID and not await is_subscribed(msg.from_user.id):
        await msg.answer("Алдымен мына каналдарға тіркеліңіз:\n" + "\n".join(CHANNELS))
    else:
        if msg.from_user.id == ADMIN_ID:
            await msg.answer(f"Қош келдіңіз, Админ! 👑 Сіздің бонусыңыз: {await get_bonus(msg.from_user.id)}", reply_markup=admin_menu())
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
    file_id = await get_next_photo(msg.from_user.id)
    if file_id:
        await change_bonus(msg.from_user.id, -2)
        await bot.send_photo(msg.chat.id, file_id)
    else:
        await msg.answer("Фото жоқ!")

@dp.message(F.text == "⭐ Бонус")
async def bonus_link(msg: Message):
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={msg.from_user.id}"
    await msg.answer(f"⭐ Досыңды шақырып бонус ал!\n👉 Сілтеме: {link}")

@dp.message(F.text == "✅ VIP режим")
async def vip_mode(msg: Message):
    await msg.answer("💎 VIP режим:\n30 бонус – 1000 тг\n50 бонус – 1500 тг\n80 бонус – 2000 тг\n👉 VIP сатып алу үшін: @KazHubALU")

@dp.message(F.text == "➕ 📢 Каналдар")
async def channels_list(msg: Message):
    await msg.answer("🔥 Каналдар:\n" + "\n".join(CHANNELS))

@dp.message(F.text == "☎ Оператор")
async def contact_operator(msg: Message):
    await msg.answer("⚠ Көмек: @Assistedkz_bot")

@dp.message(F.text == "📊 Қолданушылар саны")
async def user_count(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("Бұл ақпарат тек админге арналған.")
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
    await msg.answer(f"👥 Қолданушылар саны: {count}")

# 🔥 ЖАҢА: Рассылка хендлері (тек админ)
@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("✍️ Маған жібергің келетін хабарламаны жаз.")
    # Келесі хабарламаны күтетін ішкі хендлер
    @dp.message()
    async def broadcast_send(m: Message):
        if m.from_user.id != ADMIN_ID:
            return
        text = m.text
        await m.answer("📤 Рассылка басталды...")
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT user_id FROM users") as cur:
                users = await cur.fetchall()
        sent = 0
        for u in users:
            try:
                await bot.send_message(u[0], text)
                sent += 1
            except:
                pass
        await m.answer(f"✅ Рассылка {sent} адамға жіберілді.")
        return

@dp.message(F.video)
async def save_video(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    file_id = msg.video.file_id
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
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

# =================== SCHEDULER ===================
scheduler = AsyncIOScheduler()

async def add_bonus_all():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET bonus = bonus + 5")
        await db.commit()

scheduler.add_job(lambda: asyncio.create_task(add_bonus_all()), 'interval', hours=12)

# =================== MAIN ===================
async def main():
    await init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
