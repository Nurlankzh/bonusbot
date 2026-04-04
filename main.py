import logging
import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link

# --- БАПТАУЛАР ---
API_TOKEN = '8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs'
ADMIN_ID = 6303091468
CHANNEL_URL = 'https://t.me/uyatsizoqiga'
CHANNEL_ID = '@uyatsizoqiga'  # Каналдың username-і немесе ID-і
MANAGER_USERNAME = '@Kazhabs'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ДЕРЕКТЕР ҚОРЫ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, balance REAL, last_bonus TEXT, referrer_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS media 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, type TEXT, is_hidden INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS views 
                      (user_id INTEGER, file_id TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- КӨМЕКШІ ФУНКЦИЯЛАР ---
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_db():
    return sqlite3.connect('bot_data.db')

# --- МЕНЮЛАР ---
def main_menu():
    kb = [
        [KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру")],
        [KeyboardButton(text="💎 Канал сатып алу")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔒 Жасырын"), KeyboardButton(text="🏠 Бас мәзір")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ХЭНДЛЕРЛЕР ---
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()

    if not user_exists:
        referrer_id = None
        # Рефералды тексеру және Анти-фрод (өзін-өзі шақырмау)
        if len(args) > 1 and args[1].isdigit():
            ref_candidate = int(args[1])
            if ref_candidate != user_id:
                # Накруткадан қорғау: егер рефералдың аккаунтында фото/есім болмаса бонус бермеуге болады
                if message.from_user.has_main_web_app: # Қарапайым фильтр
                    referrer_id = ref_candidate
        
        cursor.execute("INSERT INTO users (user_id, balance, last_bonus, referrer_id) VALUES (?, ?, ?, ?)",
                       (user_id, 5.0, datetime.now().isoformat(), referrer_id))
        
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (referrer_id,))
            try:
                await bot.send_message(referrer_id, f"✅ Сіздің сілтемеңізбен жаңа дос қосылды! +10$ бонус берілді.")
            except: pass

    conn.commit()
    conn.close()

    if not await check_sub(user_id):
        return await message.answer(f"❌ Ботты қолдану үшін каналға тіркеліңіз:\n{CHANNEL_URL}", 
                                    disable_web_page_preview=True)

    welcome_text = "🌟 Қош келдіңіз! Мұнда сіз эксклюзивті контент көріп, бонус жинай аласыз.\n\nКүнделікті 15$ бонус автоматты түрде қосылып тұрады!"
    await message.answer(welcome_text, reply_markup=main_menu())

# Автоматты бонус тексеру (күн сайын 15$)
@dp.message()
async def auto_bonus_check(message: types.Message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT last_bonus, balance FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    
    if data:
        last_time = datetime.fromisoformat(data[0])
        if datetime.now() - last_time >= timedelta(hours=24):
            new_balance = data[1] + 15.0
            cursor.execute("UPDATE users SET balance = ?, last_bonus = ? WHERE user_id = ?", 
                           (new_balance, datetime.now().isoformat(), user_id))
            conn.commit()
            await message.answer(f"🎁 Күнделікті бонус: +15$ есептелді!")
    conn.close()

# Медиа көрсету функциясы
@dp.message(F.text.in_(["🎥 Видео көру", "🖼 Фото көру"]))
async def show_media(message: types.Message):
    m_type = 'video' if "Видео" in message.text else 'photo'
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < 5.0:
        link = await create_start_link(bot, str(user_id), encode=True)
        return await message.answer(f"💰 Баланс жеткіліксіз (5$ керек). \nДосыңды шақырып 10$ ал: `{link}`", parse_mode="Markdown")

    # Рандом және қайталанбайтын медиа
    cursor.execute("""SELECT file_id FROM media WHERE type = ? AND is_hidden = 0 
                      AND file_id NOT IN (SELECT file_id FROM views WHERE user_id = ?) 
                      ORDER BY RANDOM() LIMIT 1""", (m_type, user_id))
    media_item = cursor.fetchone()

    if not media_item:
        return await message.answer("😔 Әзірге жаңа контент жоқ. Кейінірек көріңіз.")

    file_id = media_item[0]
    cursor.execute("UPDATE users SET balance = balance - 5.0 WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO views (user_id, file_id) VALUES (?, ?)", (user_id, file_id))
    conn.commit()

    caption = f"💎 Көру құны: 5$\n💰 Қалған баланс: {balance - 5}$"
    
    if m_type == 'video':
        await message.answer_video(file_id, caption=caption, protect_content=True) # Приватты қылу
    else:
        await message.answer_photo(file_id, caption=caption)
    conn.close()

@dp.message(F.text == "💎 Канал сатып алу")
async def buy_channel(message: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Менеджерге жазу ✍️", url=f"https://t.me/{MANAGER_USERNAME.replace('@','')}")]
    ])
    await message.answer(f"📢 Канал сатып алу немесе жарнама бойынша менеджерге хабарласыңыз:", reply_markup=ikb)

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Админ панеліне қош келдіңіз", reply_markup=admin_menu())

@dp.message(F.text == "📊 Статистика")
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = get_db()
    cursor = conn.cursor()
    users_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    media_count = cursor.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    await message.answer(f"👥 Пайдаланушылар: {users_count}\n🎥 Жалпы медиа: {media_count}")
    conn.close()

@dp.message(F.text == "🔒 Жасырын")
async def secret_media(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_id, type FROM media WHERE is_hidden = 1 LIMIT 1")
    item = cursor.fetchone()
    
    if not item:
        return await message.answer("Жасырын контент бос.")

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Қызықты (+8$)", callback_data=f"cool_{item[0]}")],
        [InlineKeyboardButton(text="❌ Қызық емес", callback_data=f"bad_{item[0]}")]
    ])

    if item[2] == 'video':
        await message.answer_video(item[1], caption="Жасырын видео", reply_markup=ikb)
    else:
        await message.answer_photo(item[1], caption="Жасырын фото", reply_markup=ikb)
    conn.close()

@dp.callback_query(F.data.startswith("cool_") | F.data.startswith("bad_"))
async def admin_decision(callback: types.CallbackQuery):
    action, m_id = callback.data.split('_')
    conn = get_db()
    cursor = conn.cursor()
    
    if action == "cool":
        # Кездейсоқ қолданушыға 8$ бонус беру (тіпті ол жүктемесе де, жасырын түрде)
        cursor.execute("SELECT user_id FROM users ORDER BY RANDOM() LIMIT 1")
        lucky_user = cursor.fetchone()[0]
        cursor.execute("UPDATE users SET balance = balance + 8.0 WHERE user_id = ?", (lucky_user,))
        await bot.send_message(lucky_user, "✨ Бүгін сіздің сәтті күніңіз! Балансыңызға 8$ сыйлық қосылды!")
    
    cursor.execute("DELETE FROM media WHERE id = ?", (m_id,))
    conn.commit()
    conn.close()
    await callback.message.delete()
    await secret_media(callback.message)

# Админ медиа қосу (кез келген видео/фото жіберсе сақталады)
@dp.message(F.video | F.photo)
async def collect_media(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        # Егер админ емес адам жіберсе, ол "Жасырын" бөліміне түседі
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        m_type = 'video' if message.video else 'photo'
        conn = get_db()
        conn.execute("INSERT INTO media (file_id, type, is_hidden) VALUES (?, ?, 1)", (f_id, m_type))
        conn.commit()
        conn.close()
        return

    # Админ жібергендер негізгі базаға
    f_id = message.video.file_id if message.video else message.photo[-1].file_id
    m_type = 'video' if message.video else 'photo'
    conn = get_db()
    conn.execute("INSERT INTO media (file_id, type, is_hidden) VALUES (?, ?, 0)", (f_id, m_type))
    conn.commit()
    conn.close()
    await message.reply("✅ Медиа базаға қосылды!")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
