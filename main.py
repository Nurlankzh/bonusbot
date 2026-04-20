import asyncio
import logging
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link, decode_payload
from aiogram.exceptions import TelegramForbiddenError

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8576637032:AAEF5DhrNNUkRKoEtJ0Qg3D0q7v5_Zhp-hw"
ADMIN_ID = 6303091468
MANAGER_USER = "@QAZAQSHACONTENT18"
BOT_USERNAME = "qozu_bot"
TARGET_CHANNEL_ID = "@videoskazak" # Канал ID-і немесе юзернеймі
CHANNEL_URL = "https://t.me/videoskazak"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Күйлерді сақтау
broadcast_mode = set()
give_balance_mode = set()

# --- ДЕРЕКТЕР ҚОРЫ ---
async def init_db():
    async with aiosqlite.connect("bot_main_v3.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 5.0, 
            referrer_id INTEGER,
            last_video_id INTEGER DEFAULT 0,
            last_photo_id INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            task_completed INTEGER DEFAULT 0)''') # 0: істемеген, 1: тексерілуде, 2: аяқталды
        
        await db.execute('''CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            file_id TEXT, 
            file_type TEXT, 
            is_approved INTEGER DEFAULT 0)''')
        await db.commit()

# --- ПЕРНЕТАҚТАЛАР ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎥 Видео көру"), KeyboardButton(text="🖼 Фото көру")],
        [KeyboardButton(text="🎁 Задания"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="💎 Канал сатып алу")]
    ], resize_keyboard=True)

def get_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔒 Жасырын"), KeyboardButton(text="💰 Доллар беру")],
        [KeyboardButton(text="🏠 Пайдаланушы мәзірі")]
    ], resize_keyboard=True)

# --- ФУНКЦИЯЛАР ---
async def delete_message_after_delay(chat_id: int, message_id: int, delay: int = 7200):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

async def check_sub(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=TARGET_CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except:
        return False

# Тапсырманы 10 минуттан кейін тексеру
async def wait_and_verify_task(user_id: int):
    await asyncio.sleep(600) # 10 минут
    if await check_sub(user_id):
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET balance = balance + 25.0, task_completed = 2 WHERE user_id = ?", (user_id,))
            await db.commit()
        try:
            await bot.send_message(user_id, "✅ Құттықтаймыз! Сіз шартты толық орындадыңыз. Балансыңызға 25$ қосылды!")
        except:
            pass
    else:
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET task_completed = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        try:
            await bot.send_message(user_id, "❌ Өкінішке орай, сіз каналдан шығып кеттіңіз немесе тіркелмедіңіз. Бонус берілмеді. Қайта көріңіз.")
        except:
            pass

# --- СТАРТ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    payload = message.text.split()
    ref_id = None

    if len(payload) > 1 and payload[1].isdigit():
        ref_id = int(payload[1])

    async with aiosqlite.connect("bot_main_v3.db") as db:
        user = await (await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, balance, referrer_id) VALUES (?, ?, ?)", 
                             (user_id, 5.0, ref_id))
            await db.commit()
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                await db.commit()
                try:
                    await bot.send_message(ref_id, "🤝 Сүйінші! Сіздің сілтемеңізбен жаңа дос қосылды: +10$ бонус берілді!")
                except:
                    pass

    if user_id == ADMIN_ID:
        await message.answer("👑 Админ панеліне қош келдіңіз!", reply_markup=get_admin_kb())
    else:
        await message.answer("🌟 Қош келдіңіз! Мәзірді таңдаңыз:", reply_markup=get_main_kb())

# --- ХЭНДЛЕРЛЕР ---
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # Админ бөлімі
    if user_id == ADMIN_ID:
        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                v_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE file_type = 'video' AND is_approved = 1")).fetchone())[0]
                p_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE file_type = 'photo' AND is_approved = 1")).fetchone())[0]
                b_count = (await (await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")).fetchone())[0]
                
                await message.answer(
                    f"📊 **Бот статистикасы:**\n\n"
                    f"👥 Барлық пайдаланушылар: {u_count}\n"
                    f"🎥 Мақұлданған видеолар: {v_count}\n"
                    f"🖼 Мақұлданған фотолар: {p_count}\n"
                    f"🚫 Ботты бұғаттағандар: {b_count}\n\n"
                    f"✅ Жалпы белсенді база: {u_count - b_count} адам."
                )
            return

        if user_id in broadcast_mode:
            broadcast_mode.remove(user_id)
            async with aiosqlite.connect("bot_main_v3.db") as db:
                users = await (await db.execute("SELECT user_id FROM users")).fetchall()
                count, blocked = 0, 0
                for (u_id,) in users:
                    try:
                        await message.copy_to(u_id)
                        count += 1
                        await asyncio.sleep(0.05)
                    except TelegramForbiddenError:
                        blocked += 1
                        await db.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (u_id,))
                    except: pass
                await db.commit()
            await message.answer(f"✅ Рассылка аяқталды.\n📤 Жіберілді: {count}\n🚫 Блоктағандар: {blocked}")
            return
        
        # (Басқа админ функциялары өзгеріссіз қалады...)
        if message.text == "💰 Доллар беру":
            give_balance_mode.add(user_id)
            await message.answer("💵 ID және соманы жазыңыз:", reply_markup=types.ReplyKeyboardRemove()); return
        elif message.text == "📢 Рассылка":
            broadcast_mode.add(user_id)
            await message.answer("📝 Хабарламаны жазыңыз:", reply_markup=types.ReplyKeyboardRemove()); return
        elif message.text == "🔒 Жасырын":
            await show_approval(message); return
        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Режим ауыстырылды.", reply_markup=get_main_kb()); return

    # Пайдаланушы бөлімі
    if message.text == "👤 Профиль":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
            ref_count = await (await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))).fetchone()
            link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
            await message.answer(
                f"👤 **Сіздің жеке профиліңіз**\n\n"
                f"🆔 ID: `{user_id}`\n"
                f"💰 Балансыңыз: **{res[0] if res else 0.0}$**\n"
                f"👥 Шақырылған достар: **{ref_count[0] if ref_count else 0}**\n\n"
                f"🔗 Сіздің реферал сілтемеңіз:\n`{link}`\n\n"
                f"🎁 Әр дос үшін **10$** бонус аласыз!", parse_mode="Markdown")

    elif message.text == "🎁 Задания":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            task_status = (await (await db.execute("SELECT task_completed FROM users WHERE user_id = ?", (user_id,))).fetchone())[0]
        
        if task_status == 2:
            await message.answer("❌ Сіз бұл тапсырманы орындап қойғансыз. Бонус тек бір рет беріледі!")
        elif task_status == 1:
            await message.answer("⏳ Тапсырмаңыз тексерілуде. 10 минут күтіңіз, каналдан шықпаңыз!")
        else:
            ikb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1. Каналға тіркелу", url=CHANNEL_URL)],
                [InlineKeyboardButton(text="2. Тексеру", callback_data="check_task")]
            ])
            await message.answer(
                "💰 **ТЕГІН 25$ БОНУС АЛЫҢЫЗ!**\n\n"
                "Шарттар өте қарапайым:\n"
                "1️⃣ Төмендегі батырма арқылы каналға тіркеліңіз.\n"
                "2️⃣ Каналдан **10 минут** бойы шықпаңыз.\n\n"
                "✅ Егер шарт орындалса, 10 минуттан соң бот автоматты түрде балансыңызға 25$ қосады. "
                "Егер шығып кетсеңіз, бонус берілмейді!\n\n"
                "⚠️ Бұл тапсырманы тек **БІР РЕТ** орындауға болады.", reply_markup=ikb)

    elif message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Жабық каналға кіру үшін менеджерге жазыңыз:", reply_markup=ikb)

    # Контент жіберу логикасы
    if (message.video or message.photo) and message.chat.type == "private":
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, is_a))
            await db.commit()
        await message.answer("✅ Контент сақталды!" if is_a else "📩 Контент тексеруге жіберілді.")

# --- CALLBACKS ---
@dp.callback_query(F.data == "check_task")
async def check_task_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    if await check_sub(user_id):
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET task_completed = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
        await call.message.answer("⏳ Керемет! Тіркелгеніңіз анықталды. Енді 10 минут күтіңіз, бот автоматты түрде тексереді. Каналдан шықпаңыз!", reply_markup=get_main_kb())
        asyncio.create_task(wait_and_verify_task(user_id))
        await call.message.delete()
    else:
        await call.answer("❌ Сіз әлі тіркелмедіңіз! Алдымен каналға жазылыңыз.", show_alert=True)

# Модерация callback
@dp.callback_query(F.data.startswith(("ap_", "rj_")))
async def mod_callback(call: types.CallbackQuery):
    act, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_main_v3.db") as db:
        if act == "ap": await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
        else: await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    await call.message.delete()
    await show_approval(call.message)

# --- ҚОСЫМША ФУНКЦИЯЛАР ---
async def send_media(message, m_type):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance, last_video_id, last_photo_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        if not res: return
        balance, last_v, last_p = res
        last_id = last_v if m_type == "video" else last_p
        if balance < 5.0:
            return await message.answer(f"💰 Баланс: {balance}$\n❌ Көру үшін 5$ керек.\n🔗 Шақыру сілтемесі: https://t.me/{BOT_USERNAME}?start={user_id}")
        media = await (await db.execute(f"SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 AND id > ? ORDER BY id ASC LIMIT 1", (m_type, last_id))).fetchone()
        if not media:
            media = await (await db.execute(f"SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 ORDER BY id ASC LIMIT 1", (m_type,))).fetchone()
        if not media: return await message.answer("😔 Әзірге контент жоқ.")
        
        col = "last_video_id" if m_type == "video" else "last_photo_id"
        await db.execute(f"UPDATE users SET balance = balance - 5.0, {col} = ? WHERE user_id = ?", (media[0], user_id))
        await db.commit()
        
        caption = f"✅ Көру сәтті!\n💰 Қалған баланс: {balance-5.0}$\n⚠️ Хабарлама 2 сағаттан соң жойылады."
        if m_type == "video": sent = await bot.send_video(user_id, media[1], caption=caption, protect_content=True)
        else: sent = await bot.send_photo(user_id, media[1], caption=caption, protect_content=True)
        asyncio.create_task(delete_message_after_delay(user_id, sent.message_id))

async def show_approval(message):
    async with aiosqlite.connect("bot_main_v3.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Тексерілетін контент жоқ.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Рұқсат", callback_data=f"ap_{item[0]}"), InlineKeyboardButton(text="❌ Жою", callback_data=f"rj_{item[0]}")]])
        if item[2] == "video": await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else: await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

# --- ІСКЕ ҚОСУ ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
