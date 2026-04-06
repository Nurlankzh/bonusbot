import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link, decode_payload

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8719065946:AAG8l3saBCpyzCWzmENkZZ4nhPSP73W_jX0" # ЖАҢА ТОКЕН
ADMIN_ID = 6303091468
MANAGER_USER = "@Kazhabs"
BOT_USERNAME = "qozubot" # ЖАҢА ЮЗЕРНЕЙМ

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
            last_photo_id INTEGER DEFAULT 0)''')
        
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
        [KeyboardButton(text="💎 Канал сатып алу"), KeyboardButton(text="👤 Профиль")]
    ], resize_keyboard=True)

def get_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔒 Жасырын"), KeyboardButton(text="💰 Доллар беру")],
        [KeyboardButton(text="🏠 Пайдаланушы мәзірі")]
    ], resize_keyboard=True)

# --- АВТО-ЖОЮ ФУНКЦИЯСЫ (2 САҒАТ / 7200 СЕКУНД) ---
async def delete_message_after_delay(chat_id: int, message_id: int, delay: int = 7200):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# --- СТАРТ ЖӘНЕ РЕФЕРАЛ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    payload = message.text.split()
    ref_id = None

    if len(payload) > 1:
        try:
            arg = payload[1]
            # Декодтау немесе тікелей ID алу
            if arg.isdigit():
                ref_id = int(arg)
            else:
                ref_id = int(decode_payload(arg))
        except:
            ref_id = None

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
        await message.answer("🌟 Қош келдіңіз! Контент көру үшін балансыңызда қаражат болуы керек.", reply_markup=get_main_kb())

# --- КОНТЕНТ ШЫҒАРУ (ОЧЕРЕДЬ + АВТО-ЦИКЛ) ---
async def send_media(message: types.Message, m_type: str):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance, last_video_id, last_photo_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        if not res: return
        
        balance, last_v, last_p = res
        last_id = last_v if m_type == "video" else last_p

        if balance < 5.0:
            link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
            return await message.answer(
                f"💰 Баланс: {balance}$\n❌ Көру үшін кемінде 5$ керек.\n\n"
                f"🔗 Досыңызды шақырып, +10$ бонус алыңыз:\n{link}"
            )

        # Келесі контентті ID бойынша табу
        media = await (await db.execute(
            "SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 AND id > ? ORDER BY id ASC LIMIT 1", 
            (m_type, last_id)
        )).fetchone()
        
        # Егер контент таусылса, басынан (ID 0-ден үлкен ең біріншісін) бастау
        if not media:
            media = await (await db.execute(
                "SELECT id, file_id FROM content WHERE file_type = ? AND is_approved = 1 ORDER BY id ASC LIMIT 1", 
                (m_type,)
            )).fetchone()

        if not media:
            return await message.answer("😔 Әзірге базада контент жоқ.")

        # Баланс шегеру және соңғы көрген ID сақтау
        new_balance = balance - 5.0
        col_name = "last_video_id" if m_type == "video" else "last_photo_id"
        await db.execute(f"UPDATE users SET balance = ?, {col_name} = ? WHERE user_id = ?", (new_balance, media[0], user_id))
        await db.commit()

        caption = f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}$\n\n⚠️ Бұл хабарлама 2 сағаттан кейін автоматты түрде жойылады!"
        
        try:
            if m_type == "video":
                sent = await bot.send_video(user_id, media[1], caption=caption, protect_content=True)
            else:
                sent = await bot.send_photo(user_id, media[1], caption=caption, protect_content=True)
            
            # Жою тапсырмасын жіберу
            asyncio.create_task(delete_message_after_delay(user_id, sent.message_id))
        except Exception:
            await message.answer("❌ Файлды жіберу кезінде қате кетті.")

# --- ХЭНДЛЕРЛЕР ---
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # --- АДМИН ПАНЕЛЬ ---
    if user_id == ADMIN_ID:
        if user_id in give_balance_mode:
            try:
                target_id, amount = message.text.split()
                async with aiosqlite.connect("bot_main_v3.db") as db:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(amount), int(target_id)))
                    await db.commit()
                    await message.answer(f"✅ ID {target_id} балансына {amount}$ қосылды!", reply_markup=get_admin_kb())
                give_balance_mode.remove(user_id)
                return
            except:
                await message.answer("⚠️ Қате! Формат: `ID сома` (Мысалы: 6303091468 50)")
                give_balance_mode.remove(user_id); return

        if user_id in broadcast_mode:
            broadcast_mode.remove(user_id)
            async with aiosqlite.connect("bot_main_v3.db") as db:
                users = await (await db.execute("SELECT user_id FROM users")).fetchall()
                count = 0
                for (u_id,) in users:
                    try:
                        await message.copy_to(u_id)
                        count += 1
                        await asyncio.sleep(0.05)
                    except: pass
            await message.answer(f"✅ Рассылка {count} адамға жіберілді.", reply_markup=get_admin_kb())
            return

        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                m_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE is_approved = 1")).fetchone())[0]
                await message.answer(f"👥 Юзерлер: {u_count}\n🎥 Контент: {m_count}")
            return
        elif message.text == "💰 Доллар беру":
            give_balance_mode.add(user_id)
            await message.answer("💵 ID және соманы жазыңыз:", reply_markup=types.ReplyKeyboardRemove()); return
        elif message.text == "📢 Рассылка":
            broadcast_mode.add(user_id)
            await message.answer("📝 Хабарламаны жазыңыз:", reply_markup=types.ReplyKeyboardRemove()); return
        elif message.text == "🔒 Жасырын":
            await show_approval(message); return
        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Режим ауыстырылды.", reply_markup=get_main_kb()); return

    # --- ПАЙДАЛАНУШЫ БӨЛІМІ ---
    if message.text == "👤 Профиль":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
            ref_count = await (await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))).fetchone()
            
            balance = res[0] if res else 0.0
            count = ref_count[0] if ref_count else 0
            link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
            
            text = (
                f"👤 **Сіздің жеке профиліңіз**\n\n"
                f"🆔 ID: `{user_id}`\n"
                f"💰 Балансыңыз: **{balance}$**\n"
                f"👥 Шақырылған достар: **{count}**\n\n"
                f"🔗 Сіздің реферал сілтемеңіз:\n`{link}`\n\n"
                f"🎁 Әр дос үшін **10$** бонус аласыз!"
            )
            await message.answer(text, parse_mode="Markdown")

    elif message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Жабық каналға кіру үшін менеджерге жазыңыз:", reply_markup=ikb)

    # Контентті базаға қосу (Фото/Видео жібергенде)
    if (message.video or message.photo) and message.chat.type == "private":
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, is_a))
            await db.commit()
        await message.answer("✅ Контент сақталды!" if is_a else "📩 Контент тексеруге жіберілді.")

# --- МОДЕРАЦИЯ (ЖАСЫРЫН) ---
async def show_approval(message):
    async with aiosqlite.connect("bot_main_v3.db") as db:
        item = await (await db.execute("SELECT id, file_id, file_type FROM content WHERE is_approved = 0 LIMIT 1")).fetchone()
        if not item: return await message.answer("📭 Тексерілетін контент жоқ.")
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Рұқсат", callback_data=f"ap_{item[0]}"), InlineKeyboardButton(text="❌ Жою", callback_data=f"rj_{item[0]}")]])
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

# --- БОТТЫ ҚОСУ ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
