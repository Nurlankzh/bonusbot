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
# Railway-дегі Variables бөліміне BOT_KEY деп токенді қосуды ұмытпаңыз
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

def pending_kb(db_id):
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
        u_data = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (user_id,))
        bonus = u_data[0] if u_data else 10
        await msg.answer(f"👋 Қош келдіңіз!\n💰 Баланс: {bonus} бонус", reply_markup=main_menu(user_id))

# --- МЕДИА КӨРУ ---
@dp.message(F.text.in_({"🎥 Видео", "🖼 Фото"}))
async def handle_media_request(msg: Message):
    u_id = msg.from_user.id
    if not await is_subscribed(u_id):
        await msg.answer("❌ Арнаға тіркелу қажет!")
        return

    m_type = "videos" if msg.text == "🎥 Видео" else "photos"
    cost = 3 if m_type == "videos" else 2
    
    user_data = await db_fetch_one("SELECT bonus, last_video_index, last_photo_index FROM users WHERE user_id=?", (u_id,))
    if not user_data: return

    if user_data[0] < cost and u_id != ADMIN_ID:
        await msg.answer(f"❌ Бонус жеткіліксіз! Керек: {cost}, Сізде: {user_data[0]}")
        return

    idx = user_data[1] if m_type == "videos" else user_data[2]
    media = await db_fetch_one(f"SELECT file_id FROM {m_type} ORDER BY id LIMIT 1 OFFSET ?", (idx,))
    
    if not media:
        await msg.answer("⚠️ Базада жаңа файлдар таусылды.")
        return

    try:
        if m_type == "videos":
            await msg.answer_video(media[0], caption="🎬 Рахаттанып көріңіз!")
            await db_execute("UPDATE users SET bonus=bonus-?, last_video_index=? WHERE user_id=?", (cost if u_id != ADMIN_ID else 0, idx+1, u_id))
        else:
            await msg.answer_photo(media[0], caption="🖼 Рахаттанып көріңіз!")
            await db_execute("UPDATE users SET bonus=bonus-?, last_photo_index=? WHERE user_id=?", (cost if u_id != ADMIN_ID else 0, idx+1, u_id))
    except:
        await msg.answer("❌ Файлды жіберу кезінде қате шықты.")

# --- ФАЙЛ ҚАБЫЛДАУ ---
@dp.message(F.text == "📤 ФОТО/ВИДЕО ЖІБЕРУ")
async def btn_send_info(msg: Message):
    await msg.answer("Ботқа файл жіберіп бонус жинаңыз:\n🎬 1 видео = **12 бонус**\n🖼 1 фото = **10 бонус**\n\nФайлды қазір жіберіңіз:", parse_mode="Markdown")

@dp.message(F.video | F.photo)
async def handle_uploads(msg: Message):
    f_type = "video" if msg.video else "photo"
    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id

    if msg.from_user.id == ADMIN_ID:
        table = "videos" if f_type == "video" else "photos"
        await db_execute(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
        await msg.answer("✅ Админ, файл базаға тікелей қосылды.")
    else:
        await db_execute("INSERT INTO pending_files (user_id, file_id, file_type) VALUES (?, ?, ?)", (msg.from_user.id, f_id, f_type))
        await msg.answer("⏳ Рахмет! Файл админге жіберілді. Тексерілген соң бонус түседі.")

# --- ПЕНДИНГ (ТЕКСЕРУ) ---
@dp.message(F.text == "⏳ Pending файлдар", F.from_user.id == ADMIN_ID)
async def admin_pending(msg: Message):
    file = await db_fetch_one("SELECT id, user_id, file_id, file_type FROM pending_files LIMIT 1")
    if not file:
        await msg.answer("📂 Кезекте жаңа файлдар жоқ.")
        return
    
    db_id, u_id, f_id, f_type = file
    cap = f"👤 Қолданушы: `{u_id}`\n📂 Түрі: {f_type}"
    
    if f_type == "video":
        await msg.answer_video(f_id, caption=cap, reply_markup=pending_kb(db_id), parse_mode="Markdown")
    else:
        await msg.answer_photo(f_id, caption=cap, reply_markup=pending_kb(db_id), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("app_") | F.data.startswith("dec_"))
async def admin_decision(call: CallbackQuery):
    action = call.data.split("_")[0]
    db_id = call.data.split("_")[1]
    
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
        try: await bot.send_message(u_id, "❌ Админ сіздің файлыңызды мақұлдамады.")
        except: pass

    await db_execute("DELETE FROM pending_files WHERE id=?", (db_id,))
    await call.message.delete()
    # Келесі файлды автоматты түрде шығару
    await admin_pending(call.message)

# --- БОНУС БЕРУ ЖҮЙЕСІ ---
@dp.message(F.text == "👤 Жеке бонус", F.from_user.id == ADMIN_ID)
async def adm_single(msg: Message, state: FSMContext):
    await msg.answer("Пайдаланушы ID-ін жазыңыз:")
    await state.set_state(AdminStates.asking_user_id)

@dp.message(AdminStates.asking_user_id)
async def adm_id_step(msg: Message, state: FSMContext):
    await state.update_data(uid=msg.text)
    await msg.answer("Қанша бонус қосу керек?")
    await state.set_state(AdminStates.asking_bonus_single)

@dp.message(AdminStates.asking_bonus_single)
async def adm_final_single(msg: Message, state: FSMContext):
    data = await state.get_data()
    try:
        amt, uid = int(msg.text), int(data['uid'])
        await db_execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amt, uid))
        await msg.answer(f"✅ ID {uid} үшін {amt} бонус қосылды.")
        try:
            await bot.send_message(uid, f"🎁 Менеджер сізге {amt} бонус берді!")
        except:
            await msg.answer("⚠️ Хабарлама жіберілмеді (қолданушы ботты блоктаған).")
    except:
        await msg.answer("Қате! Тек сан жазыңыз.")
    await state.clear()

@dp.message(F.text == "👥 Жалпы бонус", F.from_user.id == ADMIN_ID)
async def adm_all(msg: Message, state: FSMContext):
    await msg.answer("Барлығына қанша бонус қосу керек?")
    await state.set_state(AdminStates.asking_bonus_all)

@dp.message(AdminStates.asking_bonus_all)
async def adm_final_all(msg: Message, state: FSMContext):
    try:
        amt = int(msg.text)
        await db_execute("UPDATE users SET bonus = bonus + ?", (amt,))
        await msg.answer(f"✅ Барлық пайдаланушыларға {amt} бонус берілді!")
        
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT user_id FROM users") as cur:
                users = await cur.fetchall()
                for u in users:
                    try: await bot.send_message(u[0], f"🎁 Сүйінші! Барлық қолданушыларға {amt} бонус берілді!")
                    except: continue
    except:
        await msg.answer("Қате жазылды.")
    await state.clear()

# --- СТАТИСТИКА ЖӘНЕ РАССЫЛКА ---
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def adm_stats(msg: Message):
    users = await db_fetch_one("SELECT COUNT(*) FROM users")
    vids = await db_fetch_one("SELECT COUNT(*) FROM videos")
    pts = await db_fetch_one("SELECT COUNT(*) FROM photos")
    await msg.answer(f"📊 Статистика:\n👥 Пайдаланушылар: {users[0]}\n🎬 Видеолар: {vids[0]}\n🖼 Фотолар: {pts[0]}")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def adm_broad(msg: Message, state: FSMContext):
    await msg.answer("Рассылка мәтінін жіберіңіз:")
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
        except: continue
    await msg.answer(f"✅ Рассылка аяқталды. {count} адамға жетті.")
    await state.clear()

@dp.message(F.text == "⭐ Бонус")
async def show_bonus(msg: Message):
    u_id = msg.from_user.id
    u_data = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (u_id,))
    bonus = u_data[0] if u_data else 0
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={u_id}"
    await msg.answer(f"💰 Сіздің балансыңыз: {bonus} бонус\n\n🔗 Реферал сілтемеңіз:\n`{ref_link}`\n\nӘр шақырылған адам үшін **+2 бонус** беріледі!", parse_mode="Markdown")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Бот тоқтатылды!")
