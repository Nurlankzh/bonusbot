import asyncio
import random
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USERNAME = "Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗАМЕН ЖҰМЫС ---
conn = sqlite3.connect("bot_base.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 5, ref_count INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS content (file_id TEXT PRIMARY KEY, type TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, file_id TEXT)")
conn.commit()

# --- КҮНДЕЛІКТІ БОНУС ($15) ---
async def daily_bonus_checker():
    while True:
        await asyncio.sleep(86400) # 24 сағат сайын
        cur.execute("UPDATE users SET balance = balance + 15")
        conn.commit()
        logging.info("Барлық қолданушыға $15 бонус берілді.")

# --- МӘЗІРЛЕР ---
def main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру"))
    builder.row(KeyboardButton(text="💎 Канал сатып алу"), KeyboardButton(text="👤 Профиль"))
    if user_id == ADMIN_ID:
        builder.row(KeyboardButton(text="⚙️ Админ Панель"))
    return builder.as_markup(resize_keyboard=True)

def admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка"))
    builder.row(KeyboardButton(text="🕵️ Жасырын"), KeyboardButton(text="🔙 Артқа"))
    return builder.as_markup(resize_keyboard=True)

# --- ТЕКСЕРУ ---
async def is_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

# --- ХЭНДЛЕРЛЕР ---

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cur.fetchone():
        # Жаңа қолданушы тіркеу
        cur.execute("INSERT INTO users (id, balance) VALUES (?, 5)")
        # Реферал тексеру
        if len(args) > 1 and args[1].isdigit():
            inviter_id = int(args[1])
            if inviter_id != user_id:
                cur.execute("UPDATE users SET balance = balance + 10, ref_count = ref_count + 1 WHERE id = ?", (inviter_id,))
                try:
                    await bot.send_message(inviter_id, "🎊 Құттықтаймыз! Сіздің сілтемеңізбен жаңа дос қосылды. Сізге **+$10** бонус берілді!")
                except: pass
        conn.commit()

    if not await is_sub(user_id):
        kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="📢 Каналға тіркелу", url=CHANNEL_LINK))
        return await message.answer(f"👋 Сәлем! Ботты қолдану үшін алдымен ресми каналға жазылыңыз.\n\nЖазылып болған соң қайта /start басыңыз.", reply_markup=kb.as_markup())

    await message.answer("🔞 **Ең ыстық контенттер әлеміне қош келдіңіз!**\n\nСізге бастапқы **$5** сыйлық берілді. Күн сайын балансыңызға автоматты түрде **$15** қосылып тұрады! 🎁", reply_markup=main_menu(user_id))

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    cur.execute("SELECT balance, ref_count FROM users WHERE id = ?", (message.from_user.id,))
    res = cur.fetchone()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"👤 **Сіздің жеке кабинетіңіз**\n\n💰 Баланс: **{res[0]}$**\n👥 Шақырылған достар: **{res[1]}**\n\n🔗 **Реферал сілтемеңіз:**\n`{ref_link}`\n\n💡 Әр дос үшін $10 бонус беріледі!")

@dp.message(F.text.in_(["🎥 Видео көру", "🖼 Фото көру"]))
async def show_content(message: types.Message):
    if not await is_sub(message.from_user.id): return
    
    user_id = message.from_user.id
    c_type = "video" if "Видео" in message.text else "photo"
    
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    if cur.fetchone()[0] < 5:
        return await message.answer("💸 **Баланс жеткіліксіз!**\n\n1 контент көру - $5 тұрады. Достарыңды шақырып немесе ертеңгі бонусты күтіп баланс толтырыңыз.")

    cur.execute("SELECT file_id FROM content WHERE type = ? AND file_id NOT IN (SELECT file_id FROM history WHERE user_id = ?)", (c_type, user_id))
    rows = cur.fetchall()
    if not rows: return await message.answer("✨ Сіз барлық қолжетімді контентті көрдіңіз. Жаңа контент қосылғанша күтіңіз!")

    f_id = random.choice(rows)[0]
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    caption = f"🔞 **Эксклюзив**\n\n💸 Құны: $5\n🔗 Досыңды шақыр: {ref_link}"

    try:
        if c_type == "video":
            await message.answer_video(f_id, caption=caption, protect_content=True)
        else:
            await message.answer_photo(f_id, caption=caption, protect_content=True)
        
        cur.execute("UPDATE users SET balance = balance - 5 WHERE id = ?", (user_id,))
        cur.execute("INSERT INTO history VALUES (?, ?)", (user_id, f_id))
        conn.commit()
    except: await message.answer("⚠️ Қате орын алды.")

@dp.message(F.text == "💎 Канал сатып алу")
async def buy(message: types.Message):
    kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="📲 Иесіне жазу", url=f"https://t.me/{MANAGER_USERNAME}"))
    await message.answer("👑 **Жеке канал сатып алғыңыз келе ме?**\n\nБарлық контентпен бірге каналды иелену үшін менеджерге хабарласыңыз:", reply_markup=kb.as_markup())

# --- АДМИН ПАНЕЛЬ ---

@dp.message(F.text == "⚙️ Админ Панель", F.from_user.id == ADMIN_ID)
async def admin_main(message: types.Message):
    await message.answer("🛠 Админ басқару бөлімі:", reply_markup=admin_menu())

@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def admin_stats(message: types.Message):
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='video'")
    v = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content WHERE type='photo'")
    p = cur.fetchone()[0]
    await message.answer(f"📈 **Бот статистикасы:**\n\n👤 Қолданушылар: {u}\n🎥 Видеолар: {v}\n🖼 Фотолар: {p}")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def admin_broadcast_info(message: types.Message):
    await message.answer("Жіберілетін текстті жазыңыз. Ол барлық қолданушыға барады.")

@dp.message(F.text == "🕵️ Жасырын", F.from_user.id == ADMIN_ID)
async def admin_hidden(message: types.Message):
    await message.answer("Бұл бөлімде сіз жүктелген барлық контентті көре аласыз.")

@dp.message(F.text == "🔙 Артқа")
async def back(message: types.Message):
    await message.answer("Бас мәзір", reply_markup=main_menu(message.from_user.id))

# Контентті жаппай жүктеу
@dp.message(F.from_user.id == ADMIN_ID, (F.video | F.photo))
async def bulk_save(message: types.Message):
    if message.video:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.video.file_id, "video"))
    elif message.photo:
        cur.execute("INSERT OR IGNORE INTO content VALUES (?, ?)", (message.photo[-1].file_id, "photo"))
    conn.commit()
    await message.answer("📥 Контент сақталды!")

# --- ІСКЕ ҚОСУ ---
async def main():
    asyncio.create_task(daily_bonus_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
