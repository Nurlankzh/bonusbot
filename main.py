import asyncio
import random
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton

# --- БАПТАУЛАР ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USERNAME = "Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗАМЕН ЖҰМЫС ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 5, ref_count INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS content (file_id TEXT PRIMARY KEY, type TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, file_id TEXT)")
    conn.commit()
    return conn, cur

db_conn, cursor = init_db()

# --- АВТОМАТТЫ БОНУС (24 сағат сайын $15) ---
async def auto_bonus_logic():
    while True:
        await asyncio.sleep(86400) # 24 сағат
        try:
            cursor.execute("UPDATE users SET balance = balance + 15")
            db_conn.commit()
            logging.info("Күнделікті бонус үлестірілді!")
        except Exception as e:
            logging.error(f"Бонус қатесі: {e}")

# --- МӘЗІР ---
def get_main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру"))
    builder.row(KeyboardButton(text="💎 Канал сатып алу"), KeyboardButton(text="👤 Профиль"))
    if user_id == ADMIN_ID:
        builder.row(KeyboardButton(text="⚙️ Админ Панель"))
    return builder.as_markup(resize_keyboard=True)

# --- НЕГІЗГІ ЛОГИКА ---
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        cursor.execute("INSERT INTO users (id, balance) VALUES (?, ?)", (user_id, 5))
        if ref_id and ref_id != user_id:
            cursor.execute("UPDATE users SET balance = balance + 10, ref_count = ref_count + 1 WHERE id = ?", (ref_id,))
            try: await bot.send_message(ref_id, "🤝 Құттықтаймыз! Досыңыз қосылды, сізге +$10 берілді!")
            except: pass
        db_conn.commit()

    if not await is_subscribed(user_id):
        kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="📢 Каналға жазылу", url=CHANNEL_LINK))
        return await message.answer("⚠️ Ботты қолдану үшін каналға жазылыңыз!", reply_markup=kb.as_markup())

    await message.answer("👋 Қош келдіңіз! Сізге бастапқы $5 сыйлық берілді. Күн сайын $15 бонус қосылып тұрады.", 
                         reply_markup=get_main_menu(user_id))

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    cursor.execute("SELECT balance, ref_count FROM users WHERE id = ?", (message.from_user.id,))
    data = cursor.fetchone()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"💰 Баланс: {data[0]}$\n👥 Достар: {data[1]}\n🔗 Сілтеме: `{ref_link}`", parse_mode="Markdown")

@dp.message(F.text.in_(["🎥 Видео көру", "🖼 Фото көру"]))
async def send_content(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    
    user_id = message.from_user.id
    c_type = "video" if "Видео" in message.text else "photo"
    
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    if cursor.fetchone()[0] < 5:
        return await message.answer("💸 Баланс жеткіліксіз ($5 қажет). Дос шақырыңыз немесе ертеңді күтіңіз.")

    cursor.execute("SELECT file_id FROM content WHERE type = ? AND file_id NOT IN (SELECT file_id FROM history WHERE user_id = ?)", (c_type, user_id))
    rows = cursor.fetchall()
    if not rows: return await message.answer("✨ Барлық контентті көрдіңіз!")

    f_id = random.choice(rows)[0]
    try:
        # protect_content=True - Видеоны басқаға жіберуге тыйым салады
        if c_type == "video": await message.answer_video(f_id, protect_content=True)
        else: await message.answer_photo(f_id, protect_content=True)
        
        cursor.execute("UPDATE users SET balance = balance - 5 WHERE id = ?", (user_id,))
        cursor.execute("INSERT INTO history VALUES (?, ?)", (user_id, f_id))
        db_conn.commit()
    except: await message.answer("❌ Жіберу кезінде қате шықты.")

@dp.message(F.text == "💎 Канал сатып алу")
async def buy_info(message: types.Message):
    kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="👨‍💻 Менеджерге жазу", url=f"https://t.me/{MANAGER_USERNAME}"))
    await message.answer("👑 Каналды сатып алу үшін менеджерге хабарласыңыз:", reply_markup=kb.as_markup())

# --- АДМИН БӨЛІМІ ---
@dp.message(F.from_user.id == ADMIN_ID, (F.video | F.photo))
async def admin_upload(message: types.Message):
    f_id = message.video.file_id if message.video else message.photo[-1].file_id
    cursor.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (f_id, "video" if message.video else "photo"))
    db_conn.commit()
    await message.answer("📥 Контент базаға сақталды!")

@dp.message(F.text == "⚙️ Админ Панель", F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    u = cursor.fetchone()[0]
    await message.answer(f"📊 Статистика:\n👤 Қолданушылар: {u}\n\nРассылка жіберу үшін жай ғана текст жазыңыз.")

# --- БОТТЫ ІСКЕ ҚОСУ ---
async def main():
    asyncio.create_task(auto_bonus_logic()) # Бонус беруді іске қосу
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
