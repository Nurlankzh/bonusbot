import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite

# ================= CONFIG =================
TOKEN = "5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig"
ADMIN_ID = 6303091468
CHANNEL = "@chatsdostat"

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= TEXTS =================
TEXT = {
    "kk": {
        "start": "🔥 Қош келдіңіз!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "admin": "⚙️ Админ",
        "no_diamonds": "❌ Алмас жетпейді"
    },
    "ru": {
        "start": "🔥 Добро пожаловать!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "admin": "⚙️ Админ",
        "no_diamonds": "❌ Нет алмазов"
    },
    "en": {
        "start": "🔥 Welcome!",
        "photo": "📸 Photo",
        "video": "🎥 Video",
        "profile": "👤 Profile",
        "admin": "⚙️ Admin",
        "no_diamonds": "❌ No diamonds"
    }
}

# ================= DB =================
db = None

async def init_db():
    global db
    db = await aiosqlite.connect("bot.db")
    db.row_factory = aiosqlite.Row

    await db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'kk',
        diamonds INTEGER DEFAULT 10,
        referrals INTEGER DEFAULT 0
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

    CREATE TABLE IF NOT EXISTS refs(
        owner INTEGER,
        guest INTEGER
    );
    """)
    await db.commit()

# ================= HELPERS =================
async def get_user(uid):
    cur = await db.execute("SELECT * FROM users WHERE id=?", (uid,))
    return await cur.fetchone()

def kb(lang, uid):
    t = TEXT[lang]
    b = ReplyKeyboardBuilder()

    b.row(
        KeyboardButton(text=t["photo"]),
        KeyboardButton(text=t["video"])
    )

    b.row(KeyboardButton(text=t["profile"]))

    if uid == ADMIN_ID:
        b.row(KeyboardButton(text=t["admin"]))

    return b.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id

    await db.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))
    await db.commit()

    user = await get_user(uid)
    lang = user["lang"]

    # referral
    if command.args and command.args.isdigit():
        ref = int(command.args)
        if ref != uid:
            await db.execute("UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE id=?", (ref,))
            await db.execute("INSERT INTO refs VALUES(?,?)", (ref, uid))

    await db.commit()

    await m.answer(TEXT[lang]["start"], reply_markup=kb(lang, uid))

# ================= CONTENT =================
@dp.message(F.text.in_(["📸 Фото", "📸 Photo", "🎥 Видео", "🎥 Video"]))
async def content(m: Message):
    uid = m.from_user.id
    user = await get_user(uid)

    lang = user["lang"]
    cost = 1

    if user["diamonds"] < cost:
        return await m.answer(TEXT[lang]["no_diamonds"])

    ctype = "photo" if "Фото" in m.text or "Photo" in m.text else "video"

    cur = await db.execute("""
        SELECT * FROM content
        WHERE type=?
        AND id NOT IN (SELECT cid FROM progress WHERE uid=?)
        LIMIT 1
    """, (ctype, uid))

    item = await cur.fetchone()

    if not item:
        return await m.answer("🏁 Контент жоқ")

    if ctype == "photo":
        await m.answer_photo(item["file_id"])
    else:
        await m.answer_video(item["file_id"])

    await db.execute("INSERT INTO progress VALUES(?,?)", (uid, item["id"]))
    await db.execute("UPDATE users SET diamonds = diamonds - ? WHERE id=?", (cost, uid))
    await db.commit()

# ================= PROFILE =================
@dp.message(F.text.in_(["👤 Профиль", "👤 Profile"]))
async def profile(m: Message):
    user = await get_user(m.from_user.id)

    await m.answer(
        f"👤 ID: {user['id']}\n"
        f"💎 Diamonds: {user['diamonds']}\n"
        f"👥 Referrals: {user['referrals']}"
    )

# ================= ADMIN =================
@dp.message(F.text.in_(["⚙️ Админ", "⚙️ Admin"]))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    await m.answer("⚙️ Admin:\n/add - add content\n/bc - broadcast")

# ================= ADD CONTENT =================
@dp.message(F.photo | F.video, F.from_user.id == ADMIN_ID)
async def add(m: Message):
    if m.photo:
        file_id = m.photo[-1].file_id
        ctype = "photo"
    else:
        file_id = m.video.file_id
        ctype = "video"

    await db.execute("INSERT INTO content(file_id,type) VALUES(?,?)", (file_id, ctype))
    await db.commit()

    await m.answer("✅ Added")

# ================= BROADCAST =================
@dp.message(F.text == "/bc")
async def bc(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    users = await db.execute("SELECT id FROM users")
    users = await users.fetchall()

    for u in users:
        try:
            await bot.send_message(u["id"], "📢 Broadcast")
        except:
            pass

# ================= RUN =================
async def main():
    await init_db()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
