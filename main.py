import asyncio
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USERNAME = "Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler()

# --- ДЕРЕКТЕР ҚОРЫ ---
db = sqlite3.connect("vip_content.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, 
    balance REAL DEFAULT 5, 
    ref_count INTEGER DEFAULT 0,
    last_bonus TEXT)""")
cur.execute("CREATE TABLE IF NOT EXISTS content (file_id TEXT PRIMARY KEY, type TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, file_id TEXT)")
db.commit()

# --- ФУНКЦИЯЛАР ---
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎥 Эксклюзив Видео"), KeyboardButton(text="🖼 Ыстық Фото"))
    builder.row(KeyboardButton(text="💎 Каналды сатып алу"), KeyboardButton(text="👤 Жеке кабинет"))
    if user_id == ADMIN_ID:
        builder.row(KeyboardButton(text="⚙️ Админ Панель"))
    return builder.as_markup(resize_keyboard=True)

# Күнделікті $15 бонус беру (Автоматты түрде)
async def daily_bonus_task():
    cur.execute("UPDATE users SET balance = balance + 15")
    db.commit()
    # Белсенді қолданушыларға хабарлама жіберу (опционально)
    print("Күнделікті бонус үлестірілді!")

# --- ХЭНДЛЕРЛЕР ---

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    user_exists = cur.fetchone()

    if not user_exists:
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        # Жаңа адамға $5 бонус
        cur.execute("INSERT INTO users (id, balance, last_bonus) VALUES (?, ?, ?)", 
                    (user_id, 5, datetime.now().isoformat()))
        if ref_id and ref_id != user_id:
            cur.execute("UPDATE users SET balance = balance + 10, ref_count = ref_count + 1 WHERE id = ?", (ref_id,))
            try:
                await bot.send_message(ref_id, "🎊 Сүйінші! Сіздің сілтемеңізбен жаңа дос қосылды. Сізге +10$ бонус берілді!")
            except: pass
        db.commit()

    if not await check_sub(user_id):
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="📢 Каналға жазылу", url=CHANNEL_LINK))
        return await message.answer(f"⛔️ **Кіру шектелген!**\n\nБоттың барлық мүмкіндігін ашу үшін алдымен ресми каналға жазылыңыз. Содан соң қайта /start басыңыз.", 
                                    reply_markup=kb.as_markup())

    await message.answer("🔥 **Қош келдіңіз!**\n\nМұнда тек ең таңдаулы контенттер жиналған. Күн сайын сізге $15 тегін бонус беріліп тұрады! 🎁", 
                         reply_markup=main_menu(user_id))

@dp.message(F.text == "👤 Жеке кабинет")
async def profile(message: types.Message):
    cur.execute("SELECT balance, ref_count FROM users WHERE id = ?", (message.from_user.id,))
    res = cur.fetchone()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    
    text = (f"👤 **Сіздің профиліңіз**\n\n"
            f"💰 Теңгерім: **{res[0]}$**\n"
            f"👫 Шақырылған достар: {res[1]}\n\n"
            f"🔗 **Реферал сілтемеңіз:**\n`{ref_link}`\n\n"
            f"💡 Дос шақырсаңыз $10 аласыз. Күніне $15 бонус автоматты түрде қосылады!")
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(["🎥 Эксклюзив Видео", "🖼 Ыстық Фото"]))
async def get_content(message: types.Message):
    if not await check_sub(message.from_user.id):
        return await message.answer("❌ Алдымен каналға тіркеліңіз!")

    is_video = "Видео" in message.text
    c_type = "video" if is_video else "photo"
    user_id = message.from_user.id
    
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = cur.fetchone()[0]

    if balance < 5:
        return await message.answer("💸 **Баланс жеткіліксіз!**\n\n1 контент көру құны - $5. Достарыңды шақырып немесе ертеңгі бонусты күтіп баланс толтыр!")

    # Рандом контент (бірақ қайталанбайтын)
    cur.execute("SELECT file_id FROM content WHERE type = ? AND file_id NOT IN (SELECT file_id FROM history WHERE user_id = ?)", (c_type, user_id))
    items = cur.fetchall()

    if not items:
        return await message.answer("✨ Әзірге барлық контентті көрдіңіз! Жаңалары қосылғанша күте тұрыңыз.")

    f_id = random.choice(items)[0]
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    caption = f"🔞 **Эксклюзив контент**\n\n💰 Құны: $5\n🔗 Досыңды шақырып $10 ал:\n{ref_link}"

    try:
        # protect_content=True - бұл видеоны басқа жаққа жібертпейді (private қылады)
        if is_video:
            await message.answer_video(f_id, caption=caption, protect_content=True)
        else:
            await message.answer_photo(f_id, caption=caption, protect_content=True)
        
        cur.execute("UPDATE users SET balance = balance - 5 WHERE id = ?", (user_id,))
        cur.execute("INSERT INTO history VALUES (?, ?)", (user_id, f_id))
        db.commit()
    except:
        await message.answer("⚠️ Қате орын алды.")

@dp.message(F.text == "💎 Каналды сатып алу")
async def buy_channel(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📲 Менеджермен байланыс", url=f"https://t.me/{MANAGER_USERNAME}"))
    await message.answer("👑 **Жеке канал сатып алғыңыз келе ме?**\n\nБарлық контентпен бірге каналды сатып алу үшін тікелей иесіне жазыңыз:", 
                         reply_markup=kb.as_markup())

# --- АДМИН ПАНЕЛЬ ---

@dp.message(F.text == "⚙️ Админ Панель", F.from_user.id == ADMIN_ID)
async def admin_main(message: types.Message):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📊 Толық статистика"), KeyboardButton(text="📢 Жаппай Рассылка"))
    kb.row(KeyboardButton(text="👁 Жасырын контент"), KeyboardButton(text="🔙 Артқа"))
    await message.answer("🛠 Админ басқару панеліне қош келдіңіз!", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "📊 Толық статистика", F.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='video'")
    vids = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='photo'")
    pics = cur.fetchone()[0]
    # Блоктағандарды нақты білу мүмкін емес, бірақ шамамен есептеуге болады
    await message.answer(f"📈 **Статистика:**\n\n👤 Барлық қолданушылар: {users}\n🎥 Видеолар саны: {vids}\n🖼 Фотолар саны: {pics}")

@dp.message(F.from_user.id == ADMIN_ID, (F.video | F.photo))
async def admin_upload(message: types.Message):
    # Бірден көп контент жіберсе де базаға сақтайды
    if message.video:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.video.file_id, "video"))
    elif message.photo:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.photo[-1].file_id, "photo"))
    db.commit()
    await message.answer("📥 Контент базаға сәтті қосылды!")

@dp.message(F.text == "🔙 Артқа")
async def back(message: types.Message):
    await message.answer("Бас мәзірге қайттыңыз.", reply_markup=main_menu(message.from_user.id))

# --- ІСКЕ ҚОСУ ---
async def main():
    # 24 сағат сайын бонус беруді қосу
    scheduler.add_job(daily_bonus_task, 'interval', hours=24)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот тоқтатылды")
