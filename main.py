import asyncio
import logging
import aiosqlite
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# =================== НАСТРОЙКАЛАР ===================
# Егер серверде айнымалы орнатылса соны алады, әйтпесе жазылған токенді қолданады
API_TOKEN = os.getenv("API_TOKEN", "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo")
ADMIN_ID = 6303091468 
CHANNEL_USERNAME = "@uyatsizoqiga"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Күйлері (Админ панель үшін)
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

# =================== ТЕКСЕРУ ЖҮЙЕСІ ===================
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

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

def pending_kb(db_id, f_type):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Мақұлдау", callback_query_data=f"app_{f_type}_{db_id}"),
            InlineKeyboardButton(text="❌ Мақұлдамау", callback_query_data=f"dec_{db_id}")
        ]
    ])

# =================== ХЕНДЛЕРЛЕР ===================

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_id = msg.from_user.id
    args = msg.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    user = await db_fetch_one("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if not user:
        await db_execute("INSERT INTO users (user_id, ref_id) VALUES (?, ?)", (user_id, ref_id))
        if ref_id and ref_id != user_id:
            await db_execute("UPDATE users SET bonus = bonus + 2 WHERE user_id=?", (ref_id,))
            try: await bot.send_message(ref_id, "🎁 Реферал үшін +2 бонус берілді!")
            except: pass

    if not await is_subscribed(user_id):
        await msg.answer(f"❌ Ботты қолдану үшін арнаға тіркеліңіз: {CHANNEL_USERNAME}\nТіркелген соң қайта /start басыңыз.")
    else:
        bonus = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (user_id,))
        await msg.answer(f"👋 Қош келдіңіз!\n💰 Баланс: {bonus[0]} бонус", reply_markup=main_menu(user_id))

# --- МЕДИА КӨРУ ЛОГИКАСЫ ---
async def show_media(msg: Message, m_type: str):
    u_id = msg.from_user.id
    if not await is_subscribed(u_id):
        await msg.answer("❌ Арнаға тіркелу қажет!")
        return
    
    cost = 3 if m_type == "videos" else 2
    user_data = await db_fetch_one("SELECT bonus, last_video_index, last_photo_index FROM users WHERE user_id=?", (u_id,))
    
    if user_data[0] < cost and u_id != ADMIN_ID:
        await msg.answer(f"❌ Бонус жеткіліксіз! Керек: {cost}, Сізде: {user_data[0]}")
        return

    idx = user_data[1] if m_type == "videos" else user_data[2]
    table = m_type
    
    media = await db_fetch_one(f"SELECT file_id FROM {table} ORDER BY id LIMIT 1 OFFSET ?", (idx,))
    if not media:
        await msg.answer("⚠️ Базада файлдар таусылды.")
        return

    try:
        if m_type == "videos":
            await msg.answer_video(media[0], caption="🎬 Рахаттанып көріңіз!")
            await db_execute("UPDATE users SET bonus=bonus-?, last_video_index=? WHERE user_id=?", (cost if u_id != ADMIN_ID else 0, idx+1, u_id))
        else:
            await msg.answer_photo(media[0], caption="🖼 Рахаттанып көріңіз!")
            await db_execute("UPDATE users SET bonus=bonus-?, last_photo_index=? WHERE user_id=?", (cost if u_id != ADMIN_ID else 0, idx+1, u_id))
    except:
        await msg.answer("❌ Файлды жіберу мүмкін болмады.")

@dp.message(F.text == "🎥 Видео")
async def btn_video(msg: Message): await show_media(msg, "videos")

@dp.message(F.text == "🖼 Фото")
async def btn_photo(msg: Message): await show_media(msg, "photos")

# --- ФАЙЛ ЖІБЕРУ (PENDING) ---
@dp.message(F.text == "📤 ФОТО/ВИДЕО ЖІБЕРУ")
async def btn_send_info(msg: Message):
    await msg.answer("Ботқа файл жіберіп бонус жинаңыз:\n🎬 1 видео = **12 бонус**\n🖼 1 фото = **10 бонус**\n\nФайлды қазір жіберіңіз (шексіз):", parse_mode="Markdown")

@dp.message(F.video | F.photo)
async def handle_uploads(msg: Message):
    if msg.from_user.id == ADMIN_ID:
        # Админ жіберген файлды бірден базаға қосу
        if msg.video:
            await db_execute("INSERT INTO videos (file_id) VALUES (?)", (msg.video.file_id,))
        else:
            await db_execute("INSERT INTO photos (file_id) VALUES (?)", (msg.photo[-1].file_id,))
        await msg.answer("✅ Админ, файл базаға тікелей қосылды.")
        return

    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id
    f_type = "video" if msg.video else "photo"
    
    await db_execute("INSERT INTO pending_files (user_id, file_id, file_type) VALUES (?, ?, ?)", (msg.from_user.id, f_id, f_type))
    await msg.answer("⏳ Рахмет! Файл админге жіберілді. Тексерілген соң бонус түседі.")

# --- АДМИН ПАНЕЛЬ: PENDING ПАНЕЛЬ ---
@dp.message(F.text == "⏳ Pending файлдар", F.from_user.id == ADMIN_ID)
async def admin_pending(msg: Message):
    file = await db_fetch_one("SELECT id, user_id, file_id, file_type FROM pending_files LIMIT 1")
    if not file:
        await msg.answer("📂 Кезекте жаңа файлдар жоқ.")
        return
    
    db_id, u_id, f_id, f_type = file
    cap = f"👤 Қолданушы: `{u_id}`\n📂 Түрі: {f_type}"
    if f_type == "video":
        await msg.answer_video(f_id, caption=cap, reply_markup=pending_kb(db_id, "video"), parse_mode="Markdown")
    else:
        await msg.answer_photo(f_id, caption=cap, reply_markup=pending_kb(db_id, "photo"), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("app_") | F.data.startswith("dec_"))
async def admin_decision(call: CallbackQuery):
    data = call.data.split("_")
    action, f_type, db_id = data[0], data[1] if len(data)>2 else None, data[-1]
    
    file = await db_fetch_one("SELECT user_id, file_id, file_type FROM pending_files WHERE id=?", (db_id,))
    if not file: 
        await call.answer("Файл табылмады")
        return

    u_id, f_id, f_type = file
    if action == "app":
        bonus = 12 if f_type == "video" else 10
        table = "videos" if f_type == "video" else "photos"
        await db_execute(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
        await db_execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (bonus, u_id))
        try: await bot.send_message(u_id, f"✅ Сіздің файлыңыз мақұлданды! +{bonus} бонус берілді.")
        except: pass
    else:
        try: await bot.send_message(u_id, "❌ Админ сіздің файлыңызды мақұлдамады. Сапалырақ видео/фото жіберіп көріңіз.")
        except: pass

    await db_execute("DELETE FROM pending_files WHERE id=?", (db_id,))
    await call.message.delete()
    await admin_pending(call.message)

# --- АДМИН: БОНУС БЕРУ ЖҮЙЕСІ ---
@dp.message(F.text == "👤 Жеке бонус", F.from_user.id == ADMIN_ID)
async def adm_single(msg: Message, state: FSMContext):
    await msg.answer("Бонус беретін адамның ID-ін жазыңыз:")
    await state.set_state(AdminStates.asking_user_id)

@dp.message(AdminStates.asking_user_id)
async def adm_id_step(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("ID тек сандардан тұруы керек!")
        return
    await state.update_data(uid=msg.text)
    await msg.answer("Қанша бонус бергіңіз келеді?")
    await state.set_state(AdminStates.asking_bonus_single)

@dp.message(AdminStates.asking_bonus_single)
async def adm_final_single(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Тек сан жазыңыз!")
        return
    data = await state.get_data()
    amt, uid = int(msg.text), int(data['uid'])
    await db_execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amt, uid))
    await msg.answer(f"✅ ID {uid} үшін {amt} бонус сәтті қосылды.")
    try: await bot.send_message(uid, f"🎁 Админ сізге {amt} бонус сыйлады!")
    except: pass
    await state.clear()

@dp.message(F.text == "👥 Жалпы бонус", F.from_user.id == ADMIN_ID)
async def adm_all(msg: Message, state: FSMContext):
    await msg.answer("Барлық қолданушыларға қанша бонус береміз? (10-50):")
    await state.set_state(AdminStates.asking_bonus_all)

@dp.message(AdminStates.asking_bonus_all)
async def adm_final_all(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Тек сан жазыңыз!")
        return
    amt = int(msg.text)
    await db_execute("UPDATE users SET bonus = bonus + ?", (amt,))
    await msg.answer(f"✅ Барлық қолданушыларға {amt} бонус берілді!")
    await state.clear()

# --- БАСҚА ФУНКЦИЯЛАР ---
@dp.message(F.text == "⭐ Бонус")
async def btn_bonus(msg: Message):
    me = await bot.get_me()
    await msg.answer(f"🎁 **ТЕГІН БОНУС АЛУ**\n\nДостарыңды шақыр және әрқайсысы үшін 2 бонус ал!\n\nСенің сілтемең:\n`https://t.me/{me.username}?start={msg.from_user.id}`", parse_mode="Markdown")

@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def adm_stats(msg: Message):
    users = await db_fetch_one("SELECT COUNT(*) FROM users")
    vids = await db_fetch_one("SELECT COUNT(*) FROM videos")
    await msg.answer(f"📊 **СТАТИСТИКА**\n\n👥 Пайдаланушылар: {users[0]}\n🎬 Видеолар: {vids[0]}", parse_mode="Markdown")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def adm_broad(msg: Message, state: FSMContext):
    await msg.answer("Рассылка мәтінін жазыңыз:")
    await state.set_state(AdminStates.broadcast_text)

@dp.message(AdminStates.broadcast_text)
async def adm_broad_send(msg: Message, state: FSMContext):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    count = 0
    for u in users:
        try: 
            await bot.send_message(u[0], msg.text)
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await msg.answer(f"✅ Хабарлама {count} адамға жіберілді.")
    await state.clear()

# =================== ІСКЕ ҚОСУ ===================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
