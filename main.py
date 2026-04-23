import asyncio
import logging
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ================= CONFIG =================
TOKEN = "5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig"
ADMIN_ID = 6303091468
CHANNEL = "@chatsdostat"

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= STATES =================
class AdminState(StatesGroup):
    broadcast = State()
    add_content = State()

# ================= DB =================
class DB:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect("bot.db")
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'kk',
            diamonds INTEGER DEFAULT 10,
            referrals INTEGER DEFAULT 0,
            vip INTEGER DEFAULT 0
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
        await self.conn.commit()

db = DB()

# ================= TEXT =================
TEXT = {
    "kk": {"start": "🔥 Қош келдіңіз", "no_d": "❌ Алмас жоқ"},
    "ru": {"start": "🔥 Добро пожаловать", "no_d": "❌ Нет алмазов"},
    "en": {"start": "🔥 Welcome", "no_d": "❌ No diamonds"},
}

# ================= HELPERS =================
async def get_user(uid):
    cur = await db.conn.execute("SELECT * FROM users WHERE id=?", (uid,))
    return await cur.fetchone()

def kb(lang, uid):
    t = TEXT[lang]
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📸 Фото"), KeyboardButton(text="🎥 Видео"))
    b.row(KeyboardButton(text="👤 Профиль"))
    if uid == ADMIN_ID:
        b.row(KeyboardButton(text="⚙️ Admin"))
    return b.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id

    await db.conn.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))

    # referral
    if command.args and command.args.isdigit():
        ref = int(command.args)
        if ref != uid:
            await db.conn.execute(
                "UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE id=?",
                (ref,)
            )

    await db.conn.commit()

    user = await get_user(uid)

    await m.answer(TEXT[user["lang"]]["start"], reply_markup=kb(user["lang"], uid))

# ================= CONTENT =================
@dp.message(F.text.in_(["📸 Фото", "🎥 Видео"]))
async def content(m: Message):
    uid = m.from_user.id
    user = await get_user(uid)

    ctype = "photo" if "Фото" in m.text else "video"

    if user["diamonds"] <= 0:
        return await m.answer(TEXT[user["lang"]]["no_d"])

    cur = await db.conn.execute("""
        SELECT * FROM content
        WHERE type=?
        AND id NOT IN (SELECT cid FROM progress WHERE uid=?)
        LIMIT 1
    """, (ctype, uid))

    item = await cur.fetchone()

    if not item:
        return await m.answer("🏁 Бітті")

    if ctype == "photo":
        await m.answer_photo(item["file_id"])
    else:
        await m.answer_video(item["file_id"])

    await db.conn.execute("INSERT INTO progress VALUES(?,?)", (uid, item["id"]))
    await db.conn.execute("UPDATE users SET diamonds = diamonds - 1 WHERE id=?", (uid,))
    await db.conn.commit()

# ================= PROFILE =================
@dp.message(F.text == "👤 Профиль")
async def profile(m: Message):
    user = await get_user(m.from_user.id)

    await m.answer(
        f"👤 ID: {user['id']}\n💎 {user['diamonds']}\n👥 {user['referrals']}\n🌍 {user['lang']}"
    )

# ================= ADMIN =================
@dp.message(F.text == "⚙️ Admin", F.from_user.id == ADMIN_ID)
async def admin(m: Message):
    await m.answer("📢 /broadcast\n➕ /add\n📊 /stats")

# ================= BROADCAST =================
@dp.message(F.text == "/broadcast", F.from_user.id == ADMIN_ID)
async def bc(m: Message, state: FSMContext):
    await m.answer("Жібер хабарламаны")
    await state.set_state(AdminState.broadcast)

@dp.message(AdminState.broadcast)
async def bc_send(m: Message, state: FSMContext):
    users = await db.conn.execute("SELECT id FROM users")
    users = await users.fetchall()

    for u in users:
        try:
            await bot.copy_message(u["id"], m.chat.id, m.message_id)
        except:
            pass

    await m.answer("✅ Жіберілді")
    await state.clear()

# ================= ADD CONTENT =================
@dp.message(F.text == "/add", F.from_user.id == ADMIN_ID)
async def add(m: Message, state: FSMContext):
    await m.answer("Фото/видео жібер")
    await state.set_state(AdminState.add_content)

@dp.message(AdminState.add_content)
async def save(m: Message, state: FSMContext):
    if m.photo:
        fid = m.photo[-1].file_id
        t = "photo"
    else:
        fid = m.video.file_id
        t = "video"

    await db.conn.execute("INSERT INTO content(file_id,type) VALUES(?,?)", (fid, t))
    await db.conn.commit()

    await m.answer("Сақталды")
    await state.clear()

# ================= RUN =================
async def main():
    await db.connect()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
