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

# FSM Күйлері
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
                is_vip INTEGER DEFAULT 0,
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
        [InlineKeyboardButton(text="✅ Иә, көрсет", callback_query_data="show_pending_0")],
        [InlineKeyboardButton(text="❌ Жоқ, бәрін өшір", callback_query_data="clear_pending")]
    ])

def pending_item_kb(db_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Мақұлдау", callback_query_data=f"app_{db_id}"),
            InlineKeyboardButton(text="❌ Мақұлдамау", callback_query_data=f"dec_{db_id}")
        ]
    ])

# =================== НЕГІЗГІ ЛОГИКА ===================

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_id = msg.from_user.id
    user = await db_fetch_one("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if not user:
        await db_execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
    
    u_data = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (user_id,))
    await msg.answer(f"👋 Қош келдіңіз!\n💰 Баланс: {u_data[0]} бонус", reply_markup=main_menu(user_id))

# --- МЕДИА КӨРУ (ВИДЕО/ФОТО) ---
@dp.message(F.text.in_({"🎥 Видео", "🖼 Фото"}))
async def handle_media(msg: Message):
    u_id = msg.from_user.id
    m_type = "videos" if msg.text == "🎥 Видео" else "photos"
    cost = 3 if m_type == "videos" else 2
    
    user_data = await db_fetch_one("SELECT bonus, last_video_index, last_photo_index, is_vip FROM users WHERE user_id=?", (u_id,))
    
    if not user_data[3] and user_data[0] < cost and u_id != ADMIN_ID:
        await msg.answer(f"❌ Бонус жеткіліксіз! Керек: {cost}")
        return

    idx = user_data[1] if m_type == "videos" else user_data[2]
    media = await db_fetch_one(f"SELECT file_id FROM {m_type} ORDER BY id LIMIT 1 OFFSET ?", (idx,))
    
    if not media:
        await msg.answer("⚠️ Жаңа файлдар таусылды.")
        return

    try:
        if m_type == "videos":
            await msg.answer_video(media[0])
            await db_execute("UPDATE users SET bonus=bonus-?, last_video_index=? WHERE user_id=?", (0 if user_data[3] or u_id==ADMIN_ID else cost, idx+1, u_id))
        else:
            await msg.answer_photo(media[0])
            await db_execute("UPDATE users SET bonus=bonus-?, last_photo_index=? WHERE user_id=?", (0 if user_data[3] or u_id==ADMIN_ID else cost, idx+1, u_id))
    except:
        await msg.answer("❌ Файл ашылмады.")

# --- VIP РЕЖИМ ---
@dp.message(F.text == "✅ VIP режим")
async def vip_info(msg: Message):
    await msg.answer("💎 **VIP режим артықшылықтары:**\n- Барлық видео/фото тегін\n- Шектеусіз көру\n\nСатып алу үшін админге жазыңыз: @admin_username", parse_mode="Markdown")

# --- ПЕНДИНГ (10-НАН КӨРСЕТУ) ---
@dp.message(F.text == "⏳ Pending файлдар", F.from_user.id == ADMIN_ID)
async def admin_pending_start(msg: Message):
    count = await db_fetch_one("SELECT COUNT(*) FROM pending_files")
    if count[0] == 0:
        await msg.answer("📂 Кезек бос.")
        return
    await msg.answer(f"📦 Кезекте {count[0]} файл бар. Көресіз бе?", reply_markup=confirm_pending_kb())

@dp.callback_query(F.data.startswith("show_pending_"))
async def show_pending(call: CallbackQuery):
    offset = int(call.data.split("_")[2])
    files = await db_fetch_all("SELECT id, user_id, file_id, file_type FROM pending_files LIMIT 10 OFFSET ?", (offset,))
    
    for f in files:
        db_id, u_id, f_id, f_type = f
        cap = f"👤 ID: `{u_id}`"
        try:
            if f_type == "video": await call.message.answer_video(f_id, caption=cap, reply_markup=pending_item_kb(db_id))
            else: await call.message.answer_photo(f_id, caption=cap, reply_markup=pending_item_kb(db_id))
        except:
            await call.message.answer(f"❌ Қате файл {u_id}", reply_markup=pending_item_kb(db_id))

    total = await db_fetch_one("SELECT COUNT(*) FROM pending_files")
    if total[0] > offset + 10:
        await call.message.answer("Тағы бар 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Келесі 10", callback_query_data=f"show_pending_{offset+10}")]
        ]))
    await call.answer()

@dp.callback_query(F.data == "clear_pending")
async def clear_pending(call: CallbackQuery):
    await db_execute("DELETE FROM pending_files")
    await call.message.edit_text("🗑 Тазаланды.")

@dp.callback_query(F.data.startswith("app_") | F.data.startswith("dec_"))
async def decision(call: CallbackQuery):
    act, db_id = call.data.split("_")
    file = await db_fetch_one("SELECT user_id, file_id, file_type FROM pending_files WHERE id=?", (db_id,))
    if file:
        u_id, f_id, f_type = file
        if act == "app":
            table = "videos" if f_type == "video" else "photos"
            await db_execute(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
            await db_execute("UPDATE users SET bonus=bonus+? WHERE user_id=?", (12 if f_type=="video" else 10, u_id))
            try: await bot.send_message(u_id, "✅ Мақұлданды!")
            except: pass
        await db_execute("DELETE FROM pending_files WHERE id=?", (db_id,))
    await call.message.delete()

# --- АДМИН ПАНЕЛЬ (БОНУС/РАССЫЛКА) ---
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(msg: Message):
    u = await db_fetch_one("SELECT COUNT(*) FROM users")
    await msg.answer(f"👥 Пайдаланушылар: {u[0]}")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def broad(msg: Message, state: FSMContext):
    await msg.answer("Мәтін:")
    await state.set_state(AdminStates.broadcast_text)

@dp.message(AdminStates.broadcast_text)
async def broad_send(msg: Message, state: FSMContext):
    users = await db_fetch_all("SELECT user_id FROM users")
    for u in users:
        try: await bot.send_message(u[0], msg.text)
        except: pass
    await msg.answer("✅ Жіберілді.")
    await state.clear()

@dp.message(F.text == "👥 Жалпы бонус", F.from_user.id == ADMIN_ID)
async def bonus_all(msg: Message, state: FSMContext):
    await msg.answer("Қанша бонус?")
    await state.set_state(AdminStates.asking_bonus_all)

@dp.message(AdminStates.asking_bonus_all)
async def bonus_all_send(msg: Message, state: FSMContext):
    await db_execute("UPDATE users SET bonus=bonus+?", (int(msg.text),))
    await msg.answer("✅ Орындалды.")
    await state.clear()

# --- ФАЙЛ ҚАБЫЛДАУ ---
@dp.message(F.video | F.photo)
async def uploads(msg: Message):
    f_type = "video" if msg.video else "photo"
    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id
    if msg.from_user.id == ADMIN_ID:
        await db_execute(f"INSERT OR IGNORE INTO {'videos' if f_type=='video' else 'photos'} (file_id) VALUES (?)", (f_id,))
        await msg.answer("✅ Базаға қосылды.")
    else:
        await db_execute("INSERT INTO pending_files (user_id, file_id, file_type) VALUES (?, ?, ?)", (msg.from_user.id, f_id, f_type))
        await msg.answer("⏳ Тексеруге жіберілді.")

@dp.message(F.text == "⭐ Бонус")
async def bonus_view(msg: Message):
    u = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (msg.from_user.id,))
    await msg.answer(f"💰 Бонус: {u[0]}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
