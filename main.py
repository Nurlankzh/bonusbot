import asyncio
import logging
from datetime import datetime
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, BufferedInputFile, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
from PIL import Image, ImageDraw

# --- 🔐 CONFIG ---
TOKEN = "5773099087:AAFZcdfKnodG3qnFMH9yAmxCZSFDSt8Btig"
ADMIN_ID = 6303091468
CHANNEL_ID = "@chatsdostat" # Тексерілетін арна

# --- 📊 STATES ---
class BotStates(StatesGroup):
    waiting_for_lang = State()
    waiting_for_broadcast = State()
    waiting_for_content = State()

# --- 🏗️ DATABASE ---
class Database:
    def __init__(self, path):
        self.path = path
        self.pool = None

    async def connect(self):  
        self.pool = await aiosqlite.connect(self.path)  
        self.pool.row_factory = aiosqlite.Row  
        await self.pool.executescript('''  
            CREATE TABLE IF NOT EXISTS users (  
                uid INTEGER PRIMARY KEY, 
                diamonds INTEGER DEFAULT 10,  
                referrals INTEGER DEFAULT 0, 
                lang TEXT DEFAULT 'kk'
            );  
            CREATE TABLE IF NOT EXISTS content (  
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, file_type TEXT  
            );  
            CREATE TABLE IF NOT EXISTS user_progress (uid INTEGER, content_id INTEGER);  
        ''')  
        await self.pool.commit()  

db = Database("ultra_v9_multilang.db")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- 🌍 LOCALIZATION (ТІЛДЕР) ---
TEXTS = {
    'kk': {
        'welcome': "🌟 Қош келдіңіз! Ботты қолдану үшін төмендегі батырмаларды басыңыз.",
        'sub_error': f"❌ Контент көру үшін алдымен арнамызға тіркеліңіз: {CHANNEL_ID}",
        'profile': "👤 Профиліңіз:\n🆔 ID: {uid}\n💎 Алмастар: {diamonds}\n👥 Шақырғандар: {refs}",
        'no_diamonds': "❌ Алмасыңыз жеткіліксіз! Дос шақырып жинаңыз.",
        'content_end': "🏁 Жаңа контент әлі жоқ.",
        'photo_btn': "📸 Фото алу",
        'video_btn': "🎥 Видео алу",
        'profile_btn': "👤 Профиль",
        'bonus_btn': "🎁 Бонус",
        'admin_btn': "⚙️ Админ"
    },
    'ru': {
        'welcome': "🌟 Добро пожаловать! Используйте кнопки ниже для работы с ботом.",
        'sub_error': f"❌ Для просмотра контента подпишитесь на канал: {CHANNEL_ID}",
        'profile': "👤 Ваш профиль:\n🆔 ID: {uid}\n💎 Алмазы: {diamonds}\n👥 Рефералы: {refs}",
        'no_diamonds': "❌ Недостаточно алмазов! Приглашайте друзей.",
        'content_end': "🏁 Контент закончился.",
        'photo_btn': "📸 Получить фото",
        'video_btn': "🎥 Получить видео",
        'profile_btn': "👤 Профиль",
        'bonus_btn': "🎁 Бонус",
        'admin_btn': "⚙️ Админ"
    },
    'en': {
        'welcome': "🌟 Welcome! Use the buttons below to interact with the bot.",
        'sub_error': f"❌ To view content, please subscribe to our channel: {CHANNEL_ID}",
        'profile': "👤 Your Profile:\n🆔 ID: {uid}\n💎 Diamonds: {diamonds}\n👥 Referrals: {refs}",
        'no_diamonds': "❌ Not enough diamonds! Invite friends to get more.",
        'content_end': "🏁 No more content for now.",
        'photo_btn': "📸 Get Photo",
        'video_btn': "🎥 Get Video",
        'profile_btn': "👤 Profile",
        'bonus_btn': "🎁 Bonus",
        'admin_btn': "⚙️ Admin"
    }
}

# --- 🏠 KEYBOARDS ---

def get_lang_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Қазақша 🇰🇿"), KeyboardButton(text="Русский 🇷🇺"), KeyboardButton(text="English 🇺🇸"))
    return builder.as_markup(resize_keyboard=True)

def get_main_kb(uid, lang):
    t = TEXTS[lang]
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=t['photo_btn']), KeyboardButton(text=t['video_btn']))
    builder.row(KeyboardButton(text=t['profile_btn']), KeyboardButton(text=t['bonus_btn']))
    if uid == ADMIN_ID:
        builder.row(KeyboardButton(text=t['admin_btn']))
    return builder.as_markup(resize_keyboard=True)

# --- 🛠️ HELPERS ---
async def check_subscription(uid):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status != 'left'
    except: return True

# --- 🚀 HANDLERS ---

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    # Тіл таңдауды сұрау
    await state.update_data(ref_args=command.args)
    await message.answer("Тіл таңдаңыз / Выберите язык / Select language:", reply_markup=get_lang_kb())
    await state.set_state(BotStates.waiting_for_lang)

@dp.message(BotStates.waiting_for_lang)
async def set_language(message: Message, state: FSMContext):
    lang_map = {"Қазақша 🇰🇿": "kk", "Русский 🇷🇺": "ru", "English 🇺🇸": "en"}
    if message.text not in lang_map:
        return await message.answer("Тізімнен таңдаңыз!")
    
    lang = lang_map[message.text]
    uid = message.from_user.id
    data = await state.get_data()
    ref_args = data.get('ref_args')

    # Базаға сақтау
    async with db.pool.execute("SELECT 1 FROM users WHERE uid = ?", (uid,)) as c:
        if not await c.fetchone():
            await db.pool.execute("INSERT INTO users (uid, lang) VALUES (?, ?)", (uid, lang))
            if ref_args and ref_args.isdigit() and int(ref_args) != uid:
                await db.pool.execute("UPDATE users SET diamonds = diamonds + 5, referrals = referrals + 1 WHERE uid = ?", (int(ref_args),))
        else:
            await db.pool.execute("UPDATE users SET lang = ? WHERE uid = ?", (lang, uid))
    
    await db.pool.commit()
    await message.answer(TEXTS[lang]['welcome'], reply_markup=get_main_kb(uid, lang))
    await state.clear()

@dp.message(F.text.contains("Профиль") | F.text.contains("Profile"))
async def view_profile(message: Message):
    uid = message.from_user.id
    async with db.pool.execute("SELECT * FROM users WHERE uid = ?", (uid,)) as c:
        u = await c.fetchone()
    
    lang = u['lang']
    text = TEXTS[lang]['profile'].format(uid=u['uid'], diamonds=u['diamonds'], refs=u['referrals'])
    await message.answer(text + f"\n\n🔗 Link: `t.me/Tapellotanbot?start={uid}`", parse_mode="Markdown")

@dp.message(F.text.contains("Фото") | F.text.contains("Видео") | F.text.contains("Photo") | F.text.contains("Video"))
async def handle_content(message: Message):
    uid = message.from_user.id
    async with db.pool.execute("SELECT * FROM users WHERE uid = ?", (uid,)) as c:
        user = await c.fetchone()
    
    lang = user['lang']
    t = TEXTS[lang]

    # Арнаға тіркелуді тексеру
    if not await check_subscription(uid):
        return await message.answer(t['sub_error'])

    if user['diamonds'] < 3:
        return await message.answer(t['no_diamonds'])

    c_type = "photo" if ("Фото" in message.text or "Photo" in message.text) else "video"
    
    async with db.pool.execute('''SELECT c.* FROM content c 
                                  LEFT JOIN user_progress p ON c.id = p.content_id AND p.uid = ? 
                                  WHERE c.file_type = ? AND p.content_id IS NULL LIMIT 1''', (uid, c_type)) as c:
        item = await c.fetchone()

    if not item:
        return await message.answer(t['content_end'])

    try:
        if c_type == "photo":
            await message.answer_photo(item['file_id'], protect_content=True)
        else:
            await message.answer_video(item['file_id'], protect_content=True)
        
        await db.pool.execute("INSERT INTO user_progress VALUES (?, ?)", (uid, item['id']))
        await db.pool.execute("UPDATE users SET diamonds = diamonds - 3 WHERE uid = ?", (uid,))
        await db.pool.commit()
    except Exception as e:
        logging.error(e)

# --- ⚙️ ADMIN (ҚЫСҚАША) ---
@dp.message(F.text.contains("Админ") | F.text.contains("Admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="➕ Қосу"), KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🏠 Мәзір"))
    await message.answer("Админ панель:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "➕ Қосу", F.from_user.id == ADMIN_ID)
async def add_start(message: Message, state: FSMContext):
    await message.answer("Медиа жіберіңіз:")
    await state.set_state(BotStates.waiting_for_content)

@dp.message(BotStates.waiting_for_content, F.photo | F.video)
async def add_process(message: Message, state: FSMContext):
    f_type = "photo" if message.photo else "video"
    f_id = message.photo[-1].file_id if message.photo else message.video.file_id
    await db.pool.execute("INSERT INTO content (file_id, file_type) VALUES (?, ?)", (f_id, f_type))
    await db.pool.commit()
    await message.answer("Сақталды!")
    await state.clear()

@dp.message(F.text == "🏠 Мәзір")
async def go_home(message: Message):
    uid = message.from_user.id
    async with db.pool.execute("SELECT lang FROM users WHERE uid = ?", (uid,)) as c:
        row = await c.fetchone()
    await message.answer("Home", reply_markup=get_main_kb(uid, row['lang']))

# --- 🚀 RUN ---
async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
