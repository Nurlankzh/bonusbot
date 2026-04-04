import asyncio
import random
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USERNAME = "Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫ (SQLite) ---
db = sqlite3.connect("bot_logic.db")
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, ref_count INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS content (file_id TEXT PRIMARY KEY, type TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, file_id TEXT)")
db.commit()

# --- ФУНКЦИЯЛАР ---
async def check_sub(user_id):
    try:
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except:
        return False

def main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру"))
    builder.add(KeyboardButton(text="💎 Канал сатып алу"), KeyboardButton(text="👤 Менің кабинетім"))
    if user_id == ADMIN_ID:
        builder.add(KeyboardButton(text="⚙️ Админ Панель"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# --- БОТ ЛОГИКАСЫ ---

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    is_new = cur.fetchone() is None

    if is_new:
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        cur.execute("INSERT INTO users (id, balance) VALUES (?, ?)", (user_id, 0))
        if ref_id and ref_id != user_id:
            cur.execute("UPDATE users SET balance = balance + 10, ref_count = ref_count + 1 WHERE id = ?", (ref_id,))
            try:
                await bot.send_message(ref_id, "🔔 Сүйінші! Досыңыз сіздің сілтемеңізбен кірді. Балансыңызға +10$ қосылды!")
            except: pass
        db.commit()

    if not await check_sub(user_id):
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="📢 Каналға тіркелу", url=CHANNEL_LINK))
        return await message.answer(f"👋 Сәлем! Ботты қолдану үшін алдымен каналға жазылуыңыз керек. \n\nЖазылып болған соң қайтадан /start басыңыз.", reply_markup=kb.as_markup())

    await message.answer("🚀 Қош келдіңіз! Ең эксклюзивті контенттер әлеміне енуге дайынсыз ба? Төмендегі мәзірден таңдау жасаңыз:", reply_markup=main_menu(user_id))

@dp.message(F.text == "👤 Менің кабинетім")
async def profile(message: types.Message):
    cur.execute("SELECT balance, ref_count FROM users WHERE id = ?", (message.from_user.id,))
    res = cur.fetchone()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"👤 **Сіздің профиліңіз**\n\n💰 Баланс: {res[0]}$\n👫 Шақырылған достар: {res[1]}\n\n🔗 Сіздің реферал сілтемеңіз:\n`{ref_link}`\n\n🎁 Досыңызды шақырсаңыз, балансқа 10$ қосылады!")

@dp.message(F.text.in_(["🎥 Видео көру", "🖼 Фото көру"]))
async def view_content(message: types.Message):
    if not await check_sub(message.from_user.id):
        return await message.answer("❌ Каналға жазылмағансыз!")

    c_type = "video" if "Видео" in message.text else "photo"
    user_id = message.from_user.id
    
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = cur.fetchone()[0]

    if balance < 5:
        return await message.answer("💸 Балансыңыз жеткіліксіз. 1 көру құны - 5$.\n\nДостарыңызды шақырып, балансты толтырыңыз!")

    # Көрмеген контентті алу
    cur.execute("SELECT file_id FROM content WHERE type = ? AND file_id NOT IN (SELECT file_id FROM history WHERE user_id = ?)", (c_type, user_id))
    items = cur.fetchall()

    if not items:
        return await message.answer("😔 Әзірге сіз көрмеген жаңа контент жоқ. Сәл күте тұрыңыз!")

    f_id = random.choice(items)[0]
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    caption = f"🎬 Рахаттанып тамашалаңыз!\n\n💸 Көру құны: 5$\n🔗 Достарыңды шақыр: {ref_link}"

    try:
        if c_type == "video":
            await message.answer_video(f_id, caption=caption)
        else:
            await message.answer_photo(f_id, caption=caption)
        
        cur.execute("UPDATE users SET balance = balance - 5 WHERE id = ?", (user_id,))
        cur.execute("INSERT INTO history VALUES (?, ?)", (user_id, f_id))
        db.commit()
    except Exception as e:
        await message.answer("⚠️ Қате орын алды, қайта көріңіз.")

@dp.message(F.text == "💎 Канал сатып алу")
async def buy_channel(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="👨‍💻 Менеджерге жазу", url=f"https://t.me/{MANAGER_USERNAME}"))
    await message.answer("👑 Каналды толықтай иеленгіңіз келе ме?\n\nБарлық құқықтарды сатып алу және толық ақпарат алу үшін менеджерге жазыңыз:", reply_markup=kb.as_markup())

# --- АДМИН ПАНЕЛЬ ---

@dp.message(F.text == "⚙️ Админ Панель", F.from_user.id == ADMIN_ID)
async def admin_main(message: types.Message):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка"))
    kb.row(KeyboardButton(text="👁 Жасырын көру"), KeyboardButton(text="🔙 Артқа"))
    await message.answer("🛠 Админ басқару панелі:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='video'")
    v = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='photo'")
    p = cur.fetchone()[0]
    await message.answer(f"📈 **Жалпы статистика:**\n\n👥 Қолданушылар саны: {u}\n🎥 Видеолар: {v}\n🖼 Фотолар: {p}")

@dp.message(F.from_user.id == ADMIN_ID, (F.video | F.photo))
async def bulk_upload(message: types.Message):
    if message.video:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.video.file_id, "video"))
    elif message.photo:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.photo[-1].file_id, "photo"))
    db.commit()
    await message.answer("✅ Контент сәтті сақталды!")

@dp.message(F.text == "🔙 Артқа")
async def back(message: types.Message):
    await message.answer("Бас мәзірге қайттыңыз.", reply_markup=main_menu(message.from_user.id))

# --- БОТТЫ ІСКЕ ҚОСУ ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
