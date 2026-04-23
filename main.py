import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite

# ================= CONFIG =================
TOKEN = os.getenv("5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig")  # қауіпсіздік үшін
ADMIN_ID = 6303091468
CHANNEL_ID = "@chatsdostat"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE =================
class DB:
    def __init__(self):
        self.db = None

    async def connect(self):
        self.db = await aiosqlite.connect("bot.db")
        self.db.row_factory = aiosqlite.Row

        await self.db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            diamonds INTEGER DEFAULT 10,
            referrals INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            joined_at TEXT
        );

        CREATE TABLE IF NOT EXISTS content(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            type TEXT
        );

        CREATE TABLE IF NOT EXISTS progress(
            user_id INTEGER,
            content_id INTEGER
        );
        """)
        await self.db.commit()

db = DB()

# ================= KEYBOARDS =================
def main_kb(uid):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📸 Фото"), KeyboardButton(text="🎥 Видео"))
    kb.row(KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус"))
    if uid == ADMIN_ID:
        kb.row(KeyboardButton(text="🛠 Админ"))
    return kb.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id

    await db.db.execute(
        "INSERT OR IGNORE INTO users(id, joined_at) VALUES(?, ?)",
        (uid, datetime.now().isoformat())
    )
    await db.db.commit()

    # referral
    if command.args and command.args.isdigit():
        ref = int(command.args)
        if ref != uid:
            await db.db.execute(
                "UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE id=?",
                (ref,)
            )
            await db.db.commit()

    await m.answer("🔥 Ботқа қош келдің!", reply_markup=main_kb(uid))

# ================= CHECK USER =================
async def get_user(uid):
    cur = await db.db.execute("SELECT * FROM users WHERE id=?", (uid,))
    return await cur.fetchone()

# ================= CONTENT =================
@dp.message(F.text.in_(["📸 Фото", "🎥 Видео"]))
async def content(m: Message):
    uid = m.from_user.id
    user = await get_user(uid)

    ctype = "photo" if "Фото" in m.text else "video"
    cost = 2

    if user["diamonds"] < cost:
        return await m.answer("❌ Алмас жетпейді")

    cur = await db.db.execute(
        "SELECT * FROM content WHERE type=? ORDER BY id LIMIT 1",
        (ctype,)
    )
    item = await cur.fetchone()

    if not item:
        return await m.answer("❌ Контент жоқ")

    if ctype == "photo":
        await m.answer_photo(item["file_id"], caption="🔥 Premium")
    else:
        await m.answer_video(item["file_id"], caption="🔥 Premium")

    await db.db.execute(
        "UPDATE users SET diamonds = diamonds - ? WHERE id=?",
        (cost, uid)
    )

    await db.db.execute(
        "INSERT INTO progress VALUES (?,?)",
        (uid, item["id"])
    )

    await db.db.commit()

# ================= PROFILE =================
@dp.message(F.text == "👤 Профиль")
async def profile(m: Message):
    user = await get_user(m.from_user.id)

    text = f"""
👤 ID: {m.from_user.id}
💎 Алмас: {user['diamonds']}
👥 Реферал: {user['referrals']}
"""
    await m.answer(text)

# ================= BONUS =================
@dp.message(F.text == "🎁 Бонус")
async def bonus(m: Message):
    uid = m.from_user.id

    await db.db.execute(
        "UPDATE users SET diamonds = diamonds + 1 WHERE id=?",
        (uid,)
    )
    await db.db.commit()

    await m.answer("🎁 +1 алмас алдың!")

# ================= ADMIN =================
@dp.message(F.text == "🛠 Админ")
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Рассылка", callback_data="send")
    await m.answer("Admin panel", reply_markup=kb.as_markup())

# ================= BROADCAST =================
class StateData(StatesGroup):
    wait = State()

@dp.callback_query(F.data == "send")
async def send(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Хабарлама жібер")
    await state.set_state(StateData.wait)

@dp.message(StateData.wait)
async def process(m: Message, state: FSMContext):
    users = await db.db.execute("SELECT id FROM users")
    users = await users.fetchall()

    count = 0

    for u in users:
        try:
            await bot.copy_message(u["id"], m.chat.id, m.message_id)
            count += 1
        except:
            pass

    await m.answer(f"Жіберілді: {count}")
    await state.clear()

# ================= RUN =================
async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
