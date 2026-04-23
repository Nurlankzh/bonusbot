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
CHANNEL_ID = "@chatsdostat"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= STATES =================
class StateLang(StatesGroup):
    choose = State()

# ================= DB =================
class DB:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect("bot.db")
        self.conn.row_factory = aiosqlite.Row

        await self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'kk',
            diamonds INTEGER DEFAULT 10,
            referrals INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            file_type TEXT
        );

        CREATE TABLE IF NOT EXISTS progress (
            uid INTEGER,
            content_id INTEGER
        );
        """)
        await self.conn.commit()

db = DB()

# ================= TEXT =================
TEXT = {
    "kk": {
        "choose": "🌍 Тілді таңдаңыз",
        "welcome": "🔥 Қош келдіңіз!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "no_diamonds": "❌ Алмас жоқ",
        "no_content": "🏁 Контент жоқ"
    },
    "ru": {
        "choose": "🌍 Выберите язык",
        "welcome": "🔥 Добро пожаловать!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "no_diamonds": "❌ Нет алмазов",
        "no_content": "🏁 Нет контента"
    },
    "en": {
        "choose": "🌍 Choose language",
        "welcome": "🔥 Welcome!",
        "photo": "📸 Photo",
        "video": "🎥 Video",
        "profile": "👤 Profile",
        "no_diamonds": "❌ No diamonds",
        "no_content": "🏁 No content"
    }
}

# ================= KEYBOARDS =================
def lang_kb():
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="Қазақша 🇰🇿"),
        KeyboardButton(text="Русский 🇷🇺"),
        KeyboardButton(text="English 🇺🇸")
    )
    return kb.as_markup(resize_keyboard=True)

def main_kb(lang, uid):
    t = TEXT[lang]
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=t["photo"]), KeyboardButton(text=t["video"]))
    kb.row(KeyboardButton(text=t["profile"]))
    if uid == ADMIN_ID:
        kb.row(KeyboardButton(text="⚙️ Admin"))
    return kb.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext, command: CommandObject):
    await message.answer(TEXT["kk"]["choose"], reply_markup=lang_kb())
    await state.set_state(StateLang.choose)
    await state.update_data(ref=command.args)

# ================= LANGUAGE =================
@dp.message(StateLang.choose)
async def set_lang(message: Message, state: FSMContext):
    map_lang = {
        "Қазақша 🇰🇿": "kk",
        "Русский 🇷🇺": "ru",
        "English 🇺🇸": "en"
    }

    lang = map_lang.get(message.text)
    if not lang:
        return await message.answer("Тілді таңда!")

    uid = message.from_user.id
    data = await state.get_data()
    ref = data.get("ref")

    await db.conn.execute(
        "INSERT OR IGNORE INTO users (id, lang) VALUES (?, ?)",
        (uid, lang)
    )

    await db.conn.execute(
        "UPDATE users SET lang=? WHERE id=?",
        (lang, uid)
    )

    # referral system
    if ref and ref.isdigit():
        ref = int(ref)
        if ref != uid:
            await db.conn.execute(
                "UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE id=?",
                (ref,)
            )

    await db.conn.commit()
    await state.clear()

    await message.answer(TEXT[lang]["welcome"], reply_markup=main_kb(lang, uid))

# ================= PROFILE =================
@dp.message(F.text.contains("Профиль") | F.text.contains("Profile"))
async def profile(message: Message):
    uid = message.from_user.id
    user = await db.conn.execute_fetchone("SELECT * FROM users WHERE id=?", (uid,))

    await message.answer(
        f"👤 ID: {uid}\n💎 Diamonds: {user['diamonds']}\n👥 Ref: {user['referrals']}"
    )

# ================= CONTENT =================
@dp.message(F.text.contains("Фото") | F.text.contains("Video") | F.text.contains("Видео"))
async def content(message: Message):
    uid = message.from_user.id
    user = await db.conn.execute_fetchone("SELECT * FROM users WHERE id=?", (uid,))

    lang = user["lang"]
    t = TEXT[lang]

    c_type = "photo" if "Фото" in message.text else "video"

    if user["diamonds"] < 1:
        return await message.answer(t["no_diamonds"])

    item = await db.conn.execute_fetchone(
        "SELECT * FROM content WHERE file_type=? LIMIT 1",
        (c_type,)
    )

    if not item:
        return await message.answer(t["no_content"])

    if c_type == "photo":
        await message.answer_photo(item["file_id"])
    else:
        await message.answer_video(item["file_id"])

    await db.conn.execute(
        "UPDATE users SET diamonds = diamonds - 1 WHERE id=?",
        (uid,)
    )
    await db.conn.commit()

# ================= ADMIN =================
@dp.message(F.text == "⚙️ Admin", F.from_user.id == ADMIN_ID)
async def admin(message: Message):
    await message.answer("📊 Admin:\n/add - add content")

@dp.message(F.text == "/add", F.from_user.id == ADMIN_ID)
async def add(message: Message):
    await message.answer("Send photo/video")

@dp.message(F.photo | F.video, F.from_user.id == ADMIN_ID)
async def save(message: Message):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    f_type = "photo" if message.photo else "video"

    await db.conn.execute(
        "INSERT INTO content (file_id, file_type) VALUES (?, ?)",
        (file_id, f_type)
    )
    await db.conn.commit()

    await message.answer("✅ Saved")

# ================= RUN =================
async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
