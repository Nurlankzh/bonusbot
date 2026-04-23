import asyncio
import logging
import os
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, CommandObject, StateFilter
from aiogram.types import Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite
from PIL import Image, ImageDraw

# --- 🔐 CONFIG ---
TOKEN = "5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig"
ADMIN_ID = 6303091468
CHANNEL_ID = "@chatsdostat"  # Канал юзернеймі (міндетті түрде @ белгісімен)

# --- 📊 FSM STATES ---
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_content = State()

# --- 🏗️ DATABASE ARCHITECTURE ---
class Database:
    def __init__(self, path):
        self.path = path
        self.pool = None

    async def connect(self):  
        self.pool = await aiosqlite.connect(self.path)  
        self.pool.row_factory = aiosqlite.Row  
        await self._create_tables()  

    async def _create_tables(self):  
        await self.pool.executescript('''  
            CREATE TABLE IF NOT EXISTS users (  
                uid INTEGER PRIMARY KEY, diamonds INTEGER DEFAULT 10,  
                referrals INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0,  
                vip_expire TEXT, is_blocked INTEGER DEFAULT 0, joined_at TEXT  
            );  
            CREATE TABLE IF NOT EXISTS content (  
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT,   
                file_type TEXT, tier INTEGER DEFAULT 0  
            );  
            CREATE TABLE IF NOT EXISTS user_progress (  
                uid INTEGER, content_id INTEGER,  
                PRIMARY KEY (uid, content_id)  
            );  
        ''')  
        await self.pool.commit()  

    async def get_user(self, uid):  
        async with self.pool.execute("SELECT * FROM users WHERE uid = ?", (uid,)) as c:  
            return await c.fetchone()  

    async def get_next_content(self, uid, tier, c_type):  
        query = '''  
            SELECT c.* FROM content c   
            LEFT JOIN user_progress p ON c.id = p.content_id AND p.uid = ?  
            WHERE c.file_type = ? AND c.tier <= ? AND p.content_id IS NULL  
            LIMIT 1  
        '''  
        async with self.pool.execute(query, (uid, c_type, tier)) as c:  
            return await c.fetchone()

db = Database("ultra_pro_v8.db")

# --- 🎨 IMAGE PROTECTION ---
async def add_watermark(bot: Bot, file_id: str, uid: int):
    file = await bot.get_file(file_id)
    photo_bytes = await bot.download_file(file.file_path)
    with Image.open(photo_bytes) as img:
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        text = f"ID: {uid} | @Tapellotanbot"
        # Су таңбасын сол жақ жоғары бұрышқа қою
        draw.text((10, 10), text, fill=(255, 255, 255))
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()

# --- 🚀 BOT INITIALIZATION ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# --- 🛠️ HELPERS ---
async def check_sub(uid):
    if uid == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ['member', 'administrator', 'creator']
    except: return False

def main_kb(uid):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📸 Фото"), KeyboardButton(text="🎥 Видео"))
    kb.row(KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус"))
    if uid == ADMIN_ID: kb.row(KeyboardButton(text="📊 Админ"))
    return kb.as_markup(resize_keyboard=True)

# --- 🏠 HANDLERS ---

@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    uid = message.from_user.id
    
    # Реферал жүйесі
    is_new = False
    async with db.pool.execute("SELECT 1 FROM users WHERE uid = ?", (uid,)) as c:
        if not await c.fetchone():
            is_new = True
            await db.pool.execute("INSERT INTO users (uid, joined_at) VALUES (?, ?)",
                                 (uid, datetime.now().isoformat()))

    if is_new and command.args and command.args.isdigit():
        ref_id = int(command.args)
        if ref_id != uid:
            await db.pool.execute("UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE uid = ?", (ref_id,))
            try: await bot.send_message(ref_id, "🎁 Досыңыз қосылды! +5 💎")
            except: pass
    
    await db.pool.commit()
    await message.answer("🔥 ULTRA BOT-қа қош келдіңіз! Төмендегі батырмаларды қолданыңыз.", reply_markup=main_kb(uid))

@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = await db.get_user(message.from_user.id)
    text = (f"👤 **Сіздің профиліңіз:**\n\n"
            f"🆔 ID: `{user['uid']}`\n"
            f"💎 Алмастар: {user['diamonds']}\n"
            f"👥 Рефералдар: {user['referrals']}\n"
            f"🌟 VIP статус: {'✅ Белсенді' if user['is_vip'] else '❌ Жоқ'}\n\n"
            f"🔗 Реферал сілтеме: `t.me/Tapellotanbot?start={user['uid']}`")
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🎁 Бонус")
async def get_bonus(message: Message):
    await message.answer("🎁 Күнделікті бонус алу үшін каналға тіркелуіңіз керек және достарыңызды шақырыңыз!\n\n"
                         "Әр шақырылған дос үшін 5 💎 аласыз.")

@dp.message(F.text.in_(["📸 Фото", "🎥 Видео"]))
async def content_logic(message: Message):
    uid = message.from_user.id
    if not await check_sub(uid):
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="Тіркелу", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"))
        return await message.answer(f"❌ Контент көру үшін каналға жазылыңыз!", reply_markup=kb.as_markup())

    user = await db.get_user(uid)
    c_type = "photo" if "Фото" in message.text else "video"
    cost = 2 if user['is_vip'] else 3
    
    if user['diamonds'] < cost:
        return await message.answer("❌ Алмас жетпейді! Достарыңды шақырып алмас жина.")

    item = await db.get_next_content(uid, user['is_vip'], c_type)
    if not item:
        return await message.answer("🏁 Әзірге жаңа контент жоқ. Кейінірек тексеріңіз!")

    caption = f"🆔 ID: {uid}\n💎 Қалдық: {user['diamonds']-cost} алмас\n🔥 @Tapellotanbot"
    
    try:
        if c_type == "photo":
            photo_data = await add_watermark(bot, item['file_id'], uid)
            msg = await message.answer_photo(BufferedInputFile(photo_data, filename="photo.jpg"), caption=caption, protect_content=True)
        else:
            msg = await message.answer_video(item['file_id'], caption=caption, protect_content=True)
        
        await db.pool.execute("INSERT INTO user_progress VALUES (?, ?)", (uid, item['id']))
        await db.pool.execute("UPDATE users SET diamonds = diamonds - ? WHERE uid = ?", (cost, uid))
        await db.pool.commit()
        
        # Авто-өшіру (1 сағаттан кейін)
        scheduler.add_job(delete_msg, 'date', run_date=datetime.now() + timedelta(hours=1), args=[message.chat.id, msg.message_id])
    except Exception as e:
        logging.error(e)
        await message.answer("⚠️ Қате шықты, админге хабарласыңыз.")

async def delete_msg(chat_id, message_id):
    try: await bot.delete_message(chat_id, message_id)
    except: pass

# --- 📤 ADMIN PANEL ---

@dp.message(F.text == "📊 Админ", F.from_user.id == ADMIN_ID)
async def admin_menu(message: Message):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📤 Рассылка", callback_data="admin_broadcast"))
    kb.row(InlineKeyboardButton(text="➕ Контент қосу", callback_data="admin_add_content"))
    await message.answer("🛠 Админ панельге қош келдіңіз:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_add_content")
async def add_content_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Фото немесе Видео жіберіңіз (Бот базаға сақтайды):")
    await state.set_state(AdminStates.waiting_for_content)

@dp.message(AdminStates.waiting_for_content, F.photo | F.video)
async def process_content_upload(message: Message, state: FSMContext):
    f_type = "photo" if message.photo else "video"
    f_id = message.photo[-1].file_id if message.photo else message.video.file_id
    
    await db.pool.execute("INSERT INTO content (file_id, file_type) VALUES (?, ?)", (f_id, f_type))
    await db.pool.commit()
    await message.answer(f"✅ {f_type} базаға сәтті қосылды!")
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Рассылка мәтінін немесе медиасын жіберіңіз (Болдырмау үшін /cancel):")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_process(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        return await message.answer("Тоқтатылды.")

    async with db.pool.execute("SELECT uid FROM users WHERE is_blocked = 0") as c:
        users = await c.fetchall()

    sent = 0
    status = await message.answer(f"⌛ Жіберілуде: 0/{len(users)}")
    
    for i, u in enumerate(users):
        try:
            await bot.copy_message(u['uid'], message.chat.id, message.message_id)
            sent += 1
        except TelegramForbiddenError:
            await db.pool.execute("UPDATE users SET is_blocked = 1 WHERE uid = ?", (u['uid'],))
        except Exception: pass
        
        if i % 20 == 0:
            try: await status.edit_text(f"⌛ Жіберілуде: {sent}/{len(users)}")
            except: pass
        await asyncio.sleep(0.05)
    
    await db.pool.commit()
    await status.edit_text(f"✅ Аяқталды! {sent} адамға жетті.")
    await state.clear()

# --- 🛰️ STARTUP ---

async def main():
    await db.connect()
    logging.info("База қосылды")
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот тоқтатылды")

