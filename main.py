import asyncio
import os
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
MY_TOKEN = os.getenv("BOT_KEY", "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo")
ADMIN_ID = 6303091468 
CHANNEL_USERNAME = "@uyatsizoqiga"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=MY_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Күйлері (Рассылка және Бонус үшін)
class AdminStates(StatesGroup):
    broadcast_text = State()
    asking_bonus_all = State()
    asking_user_id = State()
    asking_bonus_single = State()

# =================== МӘЛІМЕТТЕР БАЗАСЫ ===================
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                bonus INTEGER DEFAULT 10,
                ref_id INTEGER,
                last_video_index INTEGER DEFAULT 0,
                last_photo_index INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE)")
        await db.execute("CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                file_type TEXT
            )
        """)
        await db.commit()

async def db_execute(query, params=()):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetch_one(query, params=()):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

async def db_fetch_all(query, params=()):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchall()

# =================== МЕНЮЛАР ===================
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
        [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="📤 ФОТО/ВИДЕО ЖІБЕРУ")],
        [KeyboardButton(text="✅ VIP режим")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👤 Жеке бонус"), KeyboardButton(text="👥 Жалпы бонус")])
        kb.append([KeyboardButton(text="⏳ Pending файлдар"), KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def confirm_pending_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Иә, көрсет (10 файл)", callback_query_data="show_pending_0")],
        [InlineKeyboardButton(text="❌ Жоқ, бәрін өшір", callback_query_data="clear_pending")]
    ])

def pending_item_kb(db_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Мақұлдау", callback_query_data=f"app_{db_id}"),
            InlineKeyboardButton(text="❌ Мақұлдамау", callback_query_data=f"dec_{db_id}")
        ]
    ])

# =================== ХЕНДЛЕРЛЕР ===================

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_id = msg.from_user.id
    user = await db_fetch_one("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if not user:
        await db_execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
    
    u_data = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (user_id,))
    await msg.answer(f"👋 Қош келдіңіз! Балансыңыз: {u_data[0]} бонус", reply_markup=main_menu(user_id))

# --- ПЕНДИНГ СҰРАУ ---
@dp.message(F.text == "⏳ Pending файлдар", F.from_user.id == ADMIN_ID)
async def admin_ask_pending(msg: Message):
    count = await db_fetch_one("SELECT COUNT(*) FROM pending_files")
    if count[0] == 0:
        await msg.answer("📂 Кезекте жаңа файлдар жоқ.")
        return
    await msg.answer(f"📦 Кезекте {count[0]} файл бар.\n\nЖаңа файлдарды көргіңіз келе ме?", reply_markup=confirm_pending_kb())

# --- ПЕНДИНГ ТІЗІМІ (10-НАН КӨРСЕТУ) ---
@dp.callback_query(F.data.startswith("show_pending_"))
async def show_pending_list(call: CallbackQuery):
    offset = int(call.data.split("_")[2])
    files = await db_fetch_all("SELECT id, user_id, file_id, file_type FROM pending_files LIMIT 10 OFFSET ?", (offset,))
    
    if not files:
        await call.message.answer("📂 Кезекте басқа файл жоқ.")
        await call.answer()
        return

    for f in files:
        db_id, u_id, f_id, f_type = f
        cap = f"👤 Қолданушы ID: `{u_id}`\n📂 Түрі: {f_type}"
        try:
            if f_type == "video":
                await call.message.answer_video(f_id, caption=cap, reply_markup=pending_item_kb(db_id), parse_mode="Markdown")
            else:
                await call.message.answer_photo(f_id, caption=cap, reply_markup=pending_item_kb(db_id), parse_mode="Markdown")
        except Exception:
            # Файл ашылмаса, қате туралы хабарлама жіберу (өшіру батырмасымен)
            await call.message.answer(f"⚠️ Файл ашылмады (ID: {u_id}).\nҚолданушы оны өшіріп тастаған немесе формат қате.", reply_markup=pending_item_kb(db_id))

    # "Келесі" батырмасы логикасы
    total = await db_fetch_one("SELECT COUNT(*) FROM pending_files")
    if total[0] > offset + 10:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Келесі 10 файл", callback_query_data=f"show_pending_{offset+10}")]
        ])
        await call.message.answer("Тағы файлдар бар, жалғастырамыз ба? 👇", reply_markup=next_kb)
    
    await call.answer()

# --- БӘРІН ӨШІРУ ---
@dp.callback_query(F.data == "clear_pending")
async def clear_all_pending(call: CallbackQuery):
    await db_execute("DELETE FROM pending_files")
    await call.message.edit_text("🗑 Кезектегі барлық файлдар базадан өшірілді.")
    await call.answer()

# --- МАҚҰЛДАУ / МАҚҰЛДАМАУ (CALLBACK) ---
@dp.callback_query(F.data.startswith("app_") | F.data.startswith("dec_"))
async def handle_decision(call: CallbackQuery):
    action, db_id = call.data.split("_")
    file = await db_fetch_one("SELECT user_id, file_id, file_type FROM pending_files WHERE id=?", (db_id,))
    
    if file:
        u_id, f_id, f_type = file
        if action == "app":
            bonus = 12 if f_type == "video" else 10
            table = "videos" if f_type == "video" else "photos"
            # Негізгі базаға қосу
            await db_execute(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
            # Бонус беру
            await db_execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (bonus, u_id))
            try: await bot.send_message(u_id, f"✅ Файлыңыз мақұлданды! +{bonus} бонус берілді.")
            except: pass
            await call.answer("Мақұлданды ✅")
        else:
            try: await bot.send_message(u_id, "❌ Файлыңыз мақұлданбады.")
            except: pass
            await call.answer("Өшірілді ❌")
        
        await db_execute("DELETE FROM pending_files WHERE id=?", (db_id,))
    
    await call.message.delete()

# --- ФАЙЛ ҚАБЫЛДАУ ---
@dp.message(F.video | F.photo)
async def handle_uploads(msg: Message):
    user_id = msg.from_user.id
    f_type = "video" if msg.video else "photo"
    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id

    if user_id == ADMIN_ID:
        table = "videos" if f_type == "video" else "photos"
        await db_execute(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
        await msg.answer(f"✅ Админ, {f_type} базаға тікелей қосылды.")
    else:
        await db_execute("INSERT INTO pending_files (user_id, file_id, file_type) VALUES (?, ?, ?)", (user_id, f_id, f_type))
        await msg.answer("⏳ Рахмет! Файл админге жіберілді. Тексерістен соң бонус аласыз.")
        try: await bot.send_message(ADMIN_ID, "🔔 Жаңа файл түсті! 'Pending файлдар' бөлімін тексеріңіз.")
        except: pass

# --- СТАТИСТИКА ---
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def adm_stats(msg: Message):
    u = await db_fetch_one("SELECT COUNT(*) FROM users")
    v = await db_fetch_one("SELECT COUNT(*) FROM videos")
    p = await db_fetch_one("SELECT COUNT(*) FROM photos")
    await msg.answer(f"📊 Статистика:\n👥 Қолданушылар: {u[0]}\n🎬 Видеолар: {v[0]}\n🖼 Фотолар: {p[0]}")

# --- БОНУС ---
@dp.message(F.text == "⭐ Бонус")
async def show_bonus(msg: Message):
    u_data = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (msg.from_user.id,))
    me = await bot.get_me()
    ref = f"https://t.me/{me.username}?start={msg.from_user.id}"
    await msg.answer(f"💰 Баланс: {u_data[0]} бонус\n\n🔗 Реферал сілтемеңіз:\n`{ref}`", parse_mode="Markdown")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
