import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite

# ================= CONFIG =================
TOKEN = "5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig"
ADMIN_ID = 6303091468
CHANNEL = "@chatsdostat"

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= TEXT =================
TEXT = {
    "kk": {
        "start": "🔥 Қош келдіңіз!",
        "sub": "❌ Каналға жазылыңыз",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "bonus": "🎁 Бонус",
        "admin": "⚙️ Админ",
        "no_diamonds": "❌ Алмас жоқ"
    },
    "ru": {
        "start": "🔥 Добро пожаловать!",
        "sub": "❌ Подпишитесь на канал",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "bonus": "🎁 Бонус",
        "admin": "⚙️ Админ",
        "no_diamonds": "❌ Нет алмазов"
    },
    "en": {
        "start": "🔥 Welcome!",
        "sub": "❌ Subscribe to channel",
        "photo": "📸 Photo",
        "video": "🎥 Video",
        "profile": "👤 Profile",
        "bonus": "🎁 Bonus",
        "admin": "⚙️ Admin",
        "no_diamonds": "❌ No diamonds"
    }
}

# ================= DB =================
async def db():
    conn = await aiosqlite.connect("bot.db")
    await conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'kk',
        diamonds INTEGER DEFAULT 10
    );

    CREATE TABLE IF NOT EXISTS content(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT,
        type TEXT
    );

    CREATE TABLE IF NOT EXISTS progress(
        uid INTEGER,
        cid INTEGER
    );
    """)
    await conn.commit()
    return conn

# ================= HELPERS =================
async def get_user(conn, uid):
    cur = await conn.execute("SELECT * FROM users WHERE id=?", (uid,))
    return await cur.fetchone()

def kb(lang, uid):
    t = TEXT[lang]
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t["photo"]), KeyboardButton(text=t["video"]))
    b.row(KeyboardButton(text=t["profile"]), KeyboardButton(text=t["bonus"]))
    if uid == ADMIN_ID:
        b.row(KeyboardButton(text=t["admin"]))
    return b.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    conn = await db()
    uid = m.from_user.id

    await conn.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))
    await conn.commit()

    lang = (await get_user(conn, uid))[1]

    await m.answer(TEXT[lang]["start"], reply_markup=kb(lang, uid))

# ================= CONTENT =================
@dp.message(F.text.in_(["📸 Фото", "🎥 Видео", "📸 Photo", "🎥 Video"]))
async def content(m: Message):
    conn = await db()
    uid = m.from_user.id

    user = await get_user(conn, uid)
    lang = user[1]
    diamonds = user[2]

    if diamonds <= 0:
        return await m.answer(TEXT[lang]["no_diamonds"])

    ctype = "photo" if "Фото" in m.text or "Photo" in m.text else "video"

    cur = await conn.execute("""
        SELECT * FROM content 
        WHERE type=? 
        AND id NOT IN (SELECT cid FROM progress WHERE uid=?)
        LIMIT 1
    """, (ctype, uid))

    item = await cur.fetchone()

    if not item:
        return await m.answer("🏁 Бітті")

    if ctype == "photo":
        await m.answer_photo(item[1])
    else:
        await m.answer_video(item[1])

    await conn.execute("INSERT INTO progress VALUES(?,?)", (uid, item[0]))
    await conn.execute("UPDATE users SET diamonds=diamonds-1 WHERE id=?", (uid,))
    await conn.commit()

# ================= PROFILE =================
@dp.message(F.text.in_(["👤 Профиль", "👤 Profile"]))
async def profile(m: Message):
    conn = await db()
    user = await get_user(conn, m.from_user.id)

    await m.answer(f"""
👤 ID: {user[0]}
💎 Diamonds: {user[2]}
🌍 Lang: {user[1]}
""")

# ================= ADMIN =================
@dp.message(F.text.in_(["⚙️ Админ", "⚙️ Admin"]))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("📢 Admin panel:\n/broadcast")

# ================= BROADCAST =================
@dp.message(F.text == "/broadcast")
async def bc(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    conn = await db()
    users = await conn.execute("SELECT id FROM users")
    users = await users.fetchall()

    for u in users:
        try:
            await bot.send_message(u[0], "📢 Broadcast message")
        except:
            pass

# ================= RUN =================
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
