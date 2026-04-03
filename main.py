import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# =================== НАСТРОЙКАЛАР (SETTINGS) ===================
API_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo" 
ADMIN_ID = 6303091468 
CHANNEL_USERNAME = "@uyatsizoqiga"  # Тексерілетін арна

# Логтарды баптау
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# =================== МӘЛІМЕТТЕР БАЗАСЫ (DATABASE) ===================
async def init_db():
    """Базаны және кестелерді құру"""
    async with aiosqlite.connect("bot.db") as db:
        # Пайдаланушылар кестесі
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                bonus INTEGER DEFAULT 10,
                ref_id INTEGER,
                last_video_index INTEGER DEFAULT 0,
                last_photo_index INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Видеолар кестесі
        await db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE
            )
        """)
        # Фотолар кестесі
        await db.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE
            )
        """)
        await db.commit()
        logger.info("Мәліметтер базасы сәтті іске қосылды.")

# Базамен жұмыс істеу функциялары
async def db_execute(query, params=()):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetch_one(query, params=()):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

# =================== ТЕКСЕРУ ЖҮЙЕСІ (CHECKS) ===================
async def is_subscribed(user_id):
    """Арнаға тіркелуді қатаң тексеру"""
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception as e:
        logger.error(f"Тексеру қатесі ({user_id}): {e}")
        return False

# =================== МЕНЮЛАР (KEYBOARDS) ===================
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото")],
        [KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="✅ VIP режим")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")])
    
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# =================== НЕГІЗГІ ЛОГИКА (MEDIA HANDLERS) ===================
async def send_media_sequentially(msg: Message, media_type: str):
    """Медианы кезегімен жіберу функциясы"""
    user_id = msg.from_user.id
    
    # 1. Тіркелуді тексеру
    if not await is_subscribed(user_id):
        await msg.answer(f"❌ Ботты қолдану үшін алдымен арнаға тіркеліңіз:\n{CHANNEL_USERNAME}")
        return

    # 2. Бонусты тексеру
    bonus_needed = 3 if media_type == "videos" else 2
    user_data = await db_fetch_one("SELECT bonus, last_video_index, last_photo_index FROM users WHERE user_id=?", (user_id,))
    
    if not user_data:
        await msg.answer("Қателік: Пайдаланушы табылмады. /start басыңыз.")
        return
    
    current_bonus = user_data[0]
    if current_bonus < bonus_needed and user_id != ADMIN_ID:
        await msg.answer(f"❌ Бонус жеткіліксіз!\nСізге: {bonus_needed} бонус керек.\nҚазіргі баланс: {current_bonus}")
        return

    # 3. Кезекті анықтау
    table = media_type
    idx_column = "last_video_index" if media_type == "videos" else "last_photo_index"
    current_idx = user_data[1] if media_type == "videos" else user_data[2]

    # Жалпы санын алу
    total_count_row = await db_fetch_one(f"SELECT COUNT(*) FROM {table}")
    total_count = total_count_row[0]

    if total_count == 0:
        await msg.answer(f"⚠️ {media_type} базасы әзірге бос. Админ жақында қосады!")
        return

    # Егер қолданушы бәрін көріп бітірсе, басынан бастайды
    if current_idx >= total_count:
        current_idx = 0

    # Файлды алу
    media_row = await db_fetch_one(f"SELECT file_id FROM {table} ORDER BY id LIMIT 1 OFFSET ?", (current_idx,))
    
    if media_row:
        file_id = media_row[0]
        try:
            if media_type == "videos":
                await bot.send_video(msg.chat.id, file_id, caption="✅ Тамашалаңыз!")
            else:
                await bot.send_photo(msg.chat.id, file_id, caption="✅ Тамашалаңыз!")
            
            # 4. Бонусты шегеріп, индексті жаңарту
            new_idx = current_idx + 1
            await db_execute(f"UPDATE users SET bonus = bonus - ?, {idx_column} = ? WHERE user_id = ?", 
                           (bonus_needed if user_id != ADMIN_ID else 0, new_idx, user_id))
            
        except Exception as e:
            logger.error(f"Медиа жіберу қатесі: {e}")
            await msg.answer("❌ Файлды жіберу кезінде қате шықты. Базадағы файл өшірілген болуы мүмкін.")
    else:
        await msg.answer("❌ Кезекті анықтау мүмкін болмады.")

# =================== ХЕНДЛЕРЛЕР (HANDLERS) ===================

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_id = msg.from_user.id
    
    # Реферал жүйесі
    args = msg.text.split()
    ref_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])

    # Пайдаланушыны базаға қосу
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)) as cur:
            exists = await cur.fetchone()
            
            if not exists:
                await db.execute("INSERT INTO users (user_id, ref_id) VALUES (?, ?)", (user_id, ref_id))
                await db.commit()
                # Шақырған адамға бонус беру
                if ref_id and ref_id != user_id:
                    await db.execute("UPDATE users SET bonus = bonus + 2 WHERE user_id = ?", (ref_id,))
                    await db.commit()
                    try:
                        await bot.send_message(ref_id, "🎉 Сіздің сілтемеңізбен жаңа қолданушы тіркелді! +2 бонус берілді.")
                    except: pass

    if not await is_subscribed(user_id):
        await msg.answer(f"👋 Сәлем! Ботты іске қосу үшін арнаға тіркелуіңіз керек:\n{CHANNEL_USERNAME}\n\nТіркелген соң қайта /start басыңыз.")
    else:
        bonus = await db_fetch_one("SELECT bonus FROM users WHERE user_id=?", (user_id,))
        await msg.answer(f"👋 Қайта қош келдіңіз!\n💰 Сіздің бонусыңыз: {bonus[0]}", 
                         reply_markup=main_menu(user_id))

@dp.message(F.text == "🎥 Видео")
async def handle_video(msg: Message):
    await send_media_sequentially(msg, "videos")

@dp.message(F.text == "🖼 Фото")
async def handle_photo(msg: Message):
    await send_media_sequentially(msg, "photos")

@dp.message(F.text == "✅ VIP режим")
async def handle_vip(msg: Message):
    await msg.answer("💎 **VIP РЕЖИМ**\n\nБонустар сатып алу немесе VIP статус алу үшін біздің менеджерге жазыңыз:\n\n👉 @Kazhabs\n\nТөлем қабылдаған соң бонустар 5 минут ішінде салынады.")

@dp.message(F.text == "⭐ Бонус")
async def handle_bonus(msg: Message):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={msg.from_user.id}"
    await msg.answer(f"🎁 **ТЕГІН БОНУС АЛУ**\n\nТөмендегі сілтемені достарыңызға жіберіңіз. Әр тіркелген дос үшін сізге +2 бонус беріледі!\n\n🔗 Сілтеме:\n`{link}`", parse_mode="Markdown")

# =================== АДМИН ПАНЕЛЬ (ADMIN) ===================

@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def admin_stats(msg: Message):
    user_count = await db_fetch_one("SELECT COUNT(*) FROM users")
    video_count = await db_fetch_one("SELECT COUNT(*) FROM videos")
    photo_count = await db_fetch_one("SELECT COUNT(*) FROM photos")
    
    text = (f"📊 **БОТ СТАТИСТИКАСЫ**\n\n"
            f"👥 Қолданушылар: {user_count[0]}\n"
            f"🎥 Видеолар саны: {video_count[0]}\n"
            f"🖼 Фотолар саны: {photo_count[0]}")
    await msg.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def admin_broadcast_prompt(msg: Message):
    await msg.answer("📢 Рассылка мәтінін жазыңыз. Барлық пайдаланушыларға жіберіледі:")

@dp.message(F.from_user.id == ADMIN_ID, F.text)
async def process_admin_text(msg: Message):
    # Мәзір батырмалары болса тоқтату
    if msg.text in ["🎥 Видео", "🖼 Фото", "⭐ Бонус", "✅ VIP режим", "📊 Статистика", "📢 Рассылка"]:
        return

    await msg.answer("📤 Тарату басталды...")
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    
    count = 0
    for user in users:
        try:
            await bot.send_message(user[0], msg.text)
            count += 1
            await asyncio.sleep(0.05) # Серверге күш түсірмеу үшін
        except (TelegramForbiddenError, Exception):
            continue
            
    await msg.answer(f"✅ Рассылка аяқталды. {count} адамға жіберілді.")

# Видео сақтау (Админ видео жібергенде)
@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def admin_save_video(msg: Message):
    try:
        await db_execute("INSERT INTO videos (file_id) VALUES (?)", (msg.video.file_id,))
        await msg.answer("✅ Видео базаға сәтті қосылды және кезекке тұрды.")
    except aiosqlite.IntegrityError:
        await msg.answer("❌ Бұл видео базада бар!")

# Фото сақтау (Админ фото жібергенде)
@dp.message(F.photo, F.from_user.id == ADMIN_ID)
async def admin_save_photo(msg: Message):
    try:
        # Ең жоғарғы сападағы фотоны алу
        file_id = msg.photo[-1].file_id
        await db_execute("INSERT INTO photos (file_id) VALUES (?)", (file_id,))
        await msg.answer("✅ Фото базаға сәтті қосылды және кезекке тұрды.")
    except aiosqlite.IntegrityError:
        await msg.answer("❌ Бұл фото базада бар!")

# =================== SCHEDULER (АВТО БОНУС) ===================
async def daily_bonus_job():
    """Әр 12 сағат сайын барлығына 5 бонус беру"""
    await db_execute("UPDATE users SET bonus = bonus + 5")
    logger.info("Автоматты бонустар үлестірілді.")

# =================== MAIN (STARTUP) ===================
async def main():
    # Базаны дайындау
    await init_db()
    
    # Шедулерді іске қосу
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_bonus_job, 'interval', hours=12)
    scheduler.start()
    
    logger.info("Бот қосылды!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот тоқтатылды.")
