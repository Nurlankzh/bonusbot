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
BOT_USERNAME = "@Tapellotanbot"

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= STATES =================
class States(StatesGroup):
    lang = State()
    broadcast = State()
    add_content = State()

# ================= TEXT =================
TEXT = {
    "kk": {
        "choose": "🌍 Тілді таңдаңыз",
        "start": "🔥 Қош келдіңіз!",
        "sub": "❌ Каналға тіркеліңіз!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "admin": "⚙️ Админ",
        "no_d": "❌ Алмас жетіспейді",
    },
    "ru": {
        "choose": "🌍 Выберите язык",
        "start": "🔥 Добро пожаловать!",
        "sub": "❌ Подпишитесь на канал!",
        "photo": "📸 Фото",
        "video": "🎥 Видео",
        "profile": "👤 Профиль",
        "admin": "⚙️ Админ",
        "no_d": "❌ Недостаточно алмазов",
    },
    "en": {
        "choose": "🌍 Choose language",
        "start": "🔥 Welcome!",
        "sub": "❌ Subscribe to channel!",
        "photo": "📸 Photo",
        "video": "🎥 Video",
        "profile": "👤 Profile",
        "admin": "⚙️ Admin",
        "no_d": "❌ Not enough diamonds",
    }
}

# ================= DB =================
async def db():
    conn = await aiosqlite.connect("bot.db")
    conn.row_factory = aiosqlite.Row

    await conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        lang TEXT,
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
        referrer INTEGER,
        user INTEGER UNIQUE
    );

    CREATE TABLE IF NOT EXISTS stats(
        date TEXT PRIMARY KEY,
        users INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0
    );
    """)
    await conn.commit()
    return conn

# ================= KEYBOARDS =================
def lang_kb():
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="Қазақша"),
        KeyboardButton(text="Русский"),
        KeyboardButton(text="English")
    )
    return kb.as_markup(resize_keyboard=True)

def main_kb(lang, uid):
    t = TEXT[lang]
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=t["photo"]), KeyboardButton(text=t["video"]))
    kb.row(KeyboardButton(text=t["profile"]))
    if uid == ADMIN_ID:
        kb.row(KeyboardButton(text=t["admin"]))
    return kb.as_markup(resize_keyboard=True)

def admin_kb():
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📢 Рассылка"))
    kb.row(KeyboardButton(text="➕ Контент"))
    kb.row(KeyboardButton(text="📊 Статистика"))
    kb.row(KeyboardButton(text="🏠 Мәзір"))
    return kb.as_markup(resize_keyboard=True)

# ================= HELPERS =================
async def get_user(conn, uid):
    cur = await conn.execute("SELECT * FROM users WHERE id=?", (uid,))
    return await cur.fetchone()

async def check_sub(uid):
    try:
        m = await bot.get_chat_member(CHANNEL, uid)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext, command: CommandObject):
    await state.update_data(ref=command.args)
    await m.answer("🌍 Тілді таңдаңыз", reply_markup=lang_kb())
    await state.set_state(States.lang)

# ================= LANGUAGE =================
@dp.message(States.lang)
async def set_lang(m: Message, state: FSMContext):
    lang_map = {"Қазақша": "kk", "Русский": "ru", "English": "en"}

    if m.text not in lang_map:
        return

    lang = lang_map[m.text]
    uid = m.from_user.id
    conn = await db()

    data = await state.get_data()
    ref = data.get("ref")

    # жаңа user тексеру
    user_exists = await get_user(conn, uid)

    await conn.execute("INSERT OR IGNORE INTO users(id, lang) VALUES(?,?)", (uid, lang))

    # статистика (жаңа user)
    if not user_exists:
        today = datetime.now().strftime("%Y-%m-%d")
        await conn.execute("""
        INSERT INTO stats(date, users) VALUES(?,1)
        ON CONFLICT(date) DO UPDATE SET users = users + 1
        """, (today,))

    # ===== REFERRAL =====
    if ref and ref.isdigit():
        ref = int(ref)
        if ref != uid:
            try:
                await conn.execute("INSERT INTO refs(referrer,user) VALUES(?,?)", (ref, uid))
                await conn.execute("UPDATE users SET diamonds=diamonds+5, referrals=referrals+1 WHERE id=?", (ref,))
                await bot.send_message(ref, "🎁 +5 💎 Жаңа реферал!")
            except:
                pass

    await conn.commit()

    await m.answer(TEXT[lang]["start"], reply_markup=main_kb(lang, uid))
    await state.clear()

# ================= CONTENT =================
@dp.message(F.text.contains("Фото") | F.text.contains("Video") | F.text.contains("Видео") | F.text.contains("Photo"))
async def content(m: Message):
    conn = await db()
    uid = m.from_user.id

    user = await get_user(conn, uid)
    lang = user["lang"]

    if not await check_sub(uid):
        return await m.answer(TEXT[lang]["sub"])

    if user["diamonds"] <= 0:
        return await m.answer(TEXT[lang]["no_d"])

    ctype = "photo" if "Фото" in m.text or "Photo" in m.text else "video"

    cur = await conn.execute("""
    SELECT * FROM content
    WHERE type=?
    AND id NOT IN (SELECT cid FROM progress WHERE uid=?)
    LIMIT 1
    """, (ctype, uid))

    item = await cur.fetchone()

    if not item:
        return await m.answer("🏁 Контент бітті")

    if ctype == "photo":
        await m.answer_photo(item["file_id"])
    else:
        await m.answer_video(item["file_id"])

    await conn.execute("INSERT INTO progress VALUES(?,?)", (uid, item["id"]))
    await conn.execute("UPDATE users SET diamonds=diamonds-1 WHERE id=?", (uid,))

    # статистика views
    today = datetime.now().strftime("%Y-%m-%d")
    await conn.execute("""
    INSERT INTO stats(date, views) VALUES(?,1)
    ON CONFLICT(date) DO UPDATE SET views = views + 1
    """, (today,))

    await conn.commit()

# ================= PROFILE =================
@dp.message(F.text.contains("Профиль") | F.text.contains("Profile"))
async def profile(m: Message):
    conn = await db()
    user = await get_user(conn, m.from_user.id)

    link = f"https://t.me/{BOT_USERNAME}?start={user['id']}"

    text = f"""
👤 <b>ПРОФИЛЬ</b>

🆔 ID: <code>{user['id']}</code>
💎 Алмас: <b>{user['diamonds']}</b>
👥 Шақырғандар: <b>{user['referrals']}</b>

🔗 <b>Сенің ссылкаң:</b>
{link}

🚀 Дос шақыр → +5 💎 ал
"""

    await m.answer(text, parse_mode="HTML")

# ================= ADMIN =================
@dp.message(F.text.contains("Админ") | F.text.contains("Admin"), F.from_user.id == ADMIN_ID)
async def admin(m: Message):
    await m.answer("⚙️ Админ панель", reply_markup=admin_kb())

# ================= ADD CONTENT =================
@dp.message(F.text == "➕ Контент", F.from_user.id == ADMIN_ID)
async def add(m: Message, state: FSMContext):
    await m.answer("Фото немесе видео жібер")
    await state.set_state(States.add_content)

@dp.message(States.add_content)
async def save(m: Message, state: FSMContext):
    conn = await db()

    if m.photo:
        fid = m.photo[-1].file_id
        t = "photo"
    elif m.video:
        fid = m.video.file_id
        t = "video"
    else:
        return

    await conn.execute("INSERT INTO content(file_id,type) VALUES(?,?)", (fid, t))
    await conn.commit()

    await m.answer("✅ Сақталды")
    await state.clear()

# ================= BROADCAST =================
@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def bc_start(m: Message, state: FSMContext):
    await m.answer("Жіберетін хабарды жібер")
    await state.set_state(States.broadcast)

@dp.message(States.broadcast)
async def bc_send(m: Message, state: FSMContext):
    conn = await db()

    users = await conn.execute("SELECT id FROM users")
    users = await users.fetchall()

    sent = 0

    for u in users:
        try:
            await bot.copy_message(u["id"], m.chat.id, m.message_id)
            sent += 1
        except:
            pass

    await m.answer(f"✅ Жіберілді: {sent}")
    await state.clear()

# ================= STATS =================
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(m: Message):
    conn = await db()

    rows = await conn.execute("SELECT * FROM stats ORDER BY date DESC LIMIT 7")
    rows = await rows.fetchall()

    text = "📊 Соңғы 7 күн:\n\n"

    for r in rows:
        text += f"{r['date']}\n👤 Users: {r['users']} | 👁 Views: {r['views']}\n\n"

    await m.answer(text)

# ================= HOME =================
@dp.message(F.text == "🏠 Мәзір")
async def home(m: Message):
    conn = await db()
    user = await get_user(conn, m.from_user.id)
    await m.answer("🏠", reply_markup=main_kb(user["lang"], user["id"]))

# ================= RUN =================
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
