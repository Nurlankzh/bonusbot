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
TOKEN = "8244608313:AAE40OlPa3x06gcplFzDPTF-h4RATJjkczM"
ADMIN_ID = 6303091468
MANAGER_USER = "@QAZAQSHACONTENT18"
BOT_USERNAME = "Qozunet_bot"
TARGET_CHANNEL = "@uyatsizoqiga" # Тіркелу қажет канал
CHANNEL_URL = "https://t.me/uyatsizoqiga"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Күйлер
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
            task_completed INTEGER DEFAULT 0)''') # task_completed: 0-істемеген, 1-күтуде, 2-аяқталды
        
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
    try: await bot.delete_message(chat_id, message_id)
    except: pass

async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=TARGET_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# Тапсырманы тексеру таймері (10 минут = 600 сек)
async def process_task_bonus(user_id: int):
    await asyncio.sleep(600)
    if await check_subscription(user_id):
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET balance = balance + 25.0, task_completed = 2 WHERE user_id = ?", (user_id,))
            await db.commit()
        try: await bot.send_message(user_id, "✅ Құттықтаймыз! Сіз каналдан шықпадыңыз, 25$ бонус есептелді!")
        except: pass
    else:
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET task_completed = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        try: await bot.send_message(user_id, "❌ Өкінішке орай, сіз каналдан шығып кеттіңіз немесе тіркелмедіңіз. Бонус берілмеді.")
        except: pass

# --- КОМАНДАЛАР ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])

    async with aiosqlite.connect("bot_main_v3.db") as db:
        user = await (await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, balance, referrer_id) VALUES (?, ?, ?)", (user_id, 5.0, ref_id))
            await db.commit()
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET balance = balance + 10.0 WHERE user_id = ?", (ref_id,))
                await db.commit()
                try: await bot.send_message(ref_id, "🤝 Жаңа реферал! +10$ бонус берілді!")
                except: pass

    if user_id == ADMIN_ID:
        await message.answer("👑 Админ панель", reply_markup=get_admin_kb())
    else:
        await message.answer("🌟 Қош келдіңіз! Контент көру үшін баланс қажет.", reply_markup=get_main_kb())

# --- ХЭНДЛЕРЛЕР ---
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # Админ логикасы
    if user_id == ADMIN_ID:
        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u_all = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                u_blocked = (await (await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")).fetchone())[0]
                v_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE file_type = 'video' AND is_approved = 1")).fetchone())[0]
                p_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE file_type = 'photo' AND is_approved = 1")).fetchone())[0]
                
                text = (f"📊 **Бот статистикасы:**\n\n"
                        f"👥 Барлық пайдаланушылар: {u_all}\n"
                        f"🚫 Ботты бұғаттағандар: {u_blocked}\n"
                        f"🎥 Видео саны: {v_count}\n"
                        f"🖼 Фото саны: {p_count}\n"
                        f"✅ Белсенді: {u_all - u_blocked}")
                await message.answer(text, parse_mode="Markdown")
            return

        if user_id in broadcast_mode:
            broadcast_mode.remove(user_id)
            async with aiosqlite.connect("bot_main_v3.db") as db:
                users = await (await db.execute("SELECT user_id FROM users")).fetchall()
                ok, block = 0, 0
                for (u_id,) in users:
                    try:
                        await message.copy_to(u_id)
                        ok += 1
                        await asyncio.sleep(0.05)
                    except TelegramForbiddenError:
                        await db.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (u_id,))
                        block += 1
                    except: pass
                await db.commit()
            await message.answer(f"📢 Сәтті: {ok}\n🚫 Блоктағандар: {block}")
            return
        
        # (Басқа админ кнопкалары бұрынғыша...)
        if message.text == "💰 Доллар беру":
            give_balance_mode.add(user_id)
            await message.answer("ID және соманы жазыңыз (мысалы: 12345 50):")
            return
        elif message.text == "📢 Рассылка":
            broadcast_mode.add(user_id)
            await message.answer("Хабарлама жіберіңіз:")
            return
        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Ауыстырылды", reply_markup=get_main_kb())
            return
        elif message.text == "🔒 Жасырын":
            await show_approval(message); return

    # Пайдаланушы логикасы
    if message.text == "👤 Профиль":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
            ref_count = await (await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))).fetchone()
            link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
            await message.answer(f"👤 **Профиль**\n\n🆔 ID: `{user_id}`\n💰 Баланс: {res[0]}$\n👥 Шақырылғандар: {ref_count[0]}\n\n🔗 Реферал сілтеме:\n`{link}`", parse_mode="Markdown")

    elif message.text == "🎁 Задания":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            status = (await (await db.execute("SELECT task_completed FROM users WHERE user_id = ?", (user_id,))).fetchone())[0]
        
        if status == 2:
            await message.answer("❌ Сіз бұл тапсырманы орындап қойғансыз! Бонус тек бір рет беріледі.")
        elif status == 1:
            await message.answer("⏳ Тапсырма тексерілуде... 10 минут күтіңіз. Каналдан шықпаңыз!")
        else:
            ikb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1. Каналға тіркелу", url=CHANNEL_URL)],
                [InlineKeyboardButton(text="2. Тіркелдім ✅", callback_data="check_task")]
            ])
            await message.answer("🎁 **Арнайы тапсырма!**\n\nТөмендегі каналға тіркелсеңіз, автоматты түрде **25$** бонус аласыз!\n\n"
                                 "⚠️ **Шарт:** Тіркелгеннен кейін 10 минут ішінде шығып кетпеуіңіз керек. "
                                 "Бот автоматты түрде тексереді. Бұл мүмкіндік тек 1 рет беріледі!", reply_markup=ikb, parse_mode="Markdown")

    elif message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджер", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Жабық каналға кіру үшін жазыңыз:", reply_markup=ikb)

    # Фото/Видео сақтау
    if (message.video or message.photo) and message.chat.type == "private":
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, 1 if user_id == ADMIN_ID else 0))
            await db.commit()
        await message.answer("✅ Сақталды!" if user_id == ADMIN_ID else "📩 Тексеруге жіберілді.")

# --- CALLBACKS ---
@dp.callback_query(F.data == "check_task")
async def check_task_handler(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("UPDATE users SET task_completed = 1 WHERE user_id = ?", (call.from_user.id,))
            await db.commit()
        await call.message.edit_text("⏳ Өте жақсы! Енді 10 минут каналда қалыңыз. Бот автоматты түрде балансыңызды толтырады.")
        asyncio.create_task(process_task_bonus(call.from_user.id))
    else:
        await call.answer("❌ Сіз әлі тіркелмедіңіз!", show_alert=True)

# (Қалған медиа жіберу және модерация функциялары бұрынғы кодпен бірдей...)
async def send_media(message: types.Message, m_type: str):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance, last_video_id, last_photo_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        if not res: return
        balance, last_v, last_p = res
        last_id = last_v if m_type == "video" else last_p
        if balance < 5.0:
            return await message.answer(f"💰 Баланс: {balance}$\n❌ Көру үшін 5$ керек.\n🔗 Шақыру: https://t.me/{BOT_USERNAME}?start={user_id}")
        media = await (await db.execute("SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 AND id > ? ORDER BY id ASC LIMIT 1", (m_type, last_id))).fetchone()
        if not media:
            media = await (await db.execute("SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 ORDER BY id ASC LIMIT 1", (m_type,))).fetchone()
        if not media: return await message.answer("😔 Контент жоқ.")
        await db.execute(f"UPDATE users SET balance = balance - 5.0, {'last_video_id' if m_type == 'video' else 'last_photo_id'} = ? WHERE user_id = ?", (media[0], user_id))
        await db.commit()
        try:
            caption = "⚠️ 2 сағаттан кейін жойылады!"
            sent = await bot.send_video(user_id, media[1], caption=caption, protect_content=True) if m_type == "video" else await bot.send_photo(user_id, media[1], caption=caption, protect_content=True)
            asyncio.create_task(delete_message_after_delay(user_id, sent.message_id))
        except: pass

async def show_approval(message):
    async with aiosqlite.connect("bot_main_v3.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Бос.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅", callback_data=f"ap_{item[0]}"), InlineKeyboardButton(text="❌", callback_data=f"rj_{item[0]}")]])
        if item[2] == "video": await bot.send_video(ADMIN_ID, item[1], reply_markup=ikb)
        else: await bot.send_photo(ADMIN_ID, item[1], reply_markup=ikb)

@dp.callback_query(F.data.startswith(("ap_", "rj_")))
async def callback_handler(call: types.CallbackQuery):
    act, c_id = call.data.split("_")
    async with aiosqlite.connect("bot_main_v3.db") as db:
        if act == "ap": await db.execute("UPDATE content SET is_approved = 1 WHERE id = ?", (c_id,))
        else: await db.execute("DELETE FROM content WHERE id = ?", (c_id,))
        await db.commit()
    await call.message.delete()
    await show_approval(call.message)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
