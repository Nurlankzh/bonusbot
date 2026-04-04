import asyncio
import logging
import aiosqlite
import base64
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link, decode_payload

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8775883190:AAFEbBqsZDJvKo8H2yWES1U6rgnbVBEXvhs"
ADMIN_ID = 6303091468
CHANNEL_ID = "@uyatsizoqiga" 
CHANNEL_LINK = "https://t.me/uyatsizoqiga"
MANAGER_USER = "@Kazhabs"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Уақытша күйлер
broadcast_mode = set()
give_balance_mode = set()

# --- ДЕРЕКТЕР ҚОРЫ ---
async def init_db():
    async with aiosqlite.connect("bot_main_v3.db") as db:
        # Пайдаланушылар кестесі
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 5.0, 
            referrer_id INTEGER)''')
        # Контент кестесі
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

# --- СТАРТ ЖӘНЕ РЕФЕРАЛ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    payload = message.text.split()
    ref_id = None

    # Реферал ID-ді анықтау (қарапайым немесе кодталған)
    if len(payload) > 1:
        try:
            arg = payload[1]
            if arg.isdigit():
                ref_id = int(arg)
            else:
                ref_id = int(decode_payload(arg))
        except:
            ref_id = None

    async with aiosqlite.connect("bot_main_v3.db") as db:
        user = await (await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))).fetchone()
        
        if not user:
            # Жаңа юзерге 5.0$ бонус
            await db.execute("INSERT INTO users (user_id, balance, referrer_id) VALUES (?, ?, ?)", 
                             (user_id, 5.0, ref_id))
            await db.commit()
            
            # Шақырған адамға +10$ беру
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
        await message.answer("🌟 Қош келдіңіз! Видео көру үшін балансыңызда қаражат болуы керек.", reply_markup=get_main_kb())

# --- КОНТЕНТ ШЫҒАРУ ---
async def send_media(message: types.Message, m_type: str):
    user_id = message.from_user.id
    async with aiosqlite.connect("bot_main_v3.db") as db:
        res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
        balance = res[0] if res else 0.0

        if balance < 5.0:
            link = await create_start_link(bot, str(user_id), encode=True)
            return await message.answer(
                f"💰 Баланс: {balance}$\n❌ Видео көру үшін кемінде 5$ керек.\n\n"
                f"🔗 Досыңызды шақырып, +10$ бонус алыңыз (шектеусіз):\n{link}"
            )

        # Контентті таңдау
        media = await (await db.execute("SELECT file_id FROM content WHERE file_type = ? AND is_approved = 1 ORDER BY RANDOM() LIMIT 1", (m_type,))).fetchone()
        
        if not media:
            return await message.answer("😔 Әзірге жаңа контент жоқ. Сәлден соң қайталаңыз.")

        # Балансты шегеру (тек жіберер алдында)
        new_balance = balance - 5.0
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()

        cap = f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}$"
        try:
            if m_type == "video":
                await bot.send_video(user_id, media[0], caption=cap, protect_content=True)
            else:
                await bot.send_photo(user_id, media[0], caption=cap, protect_content=True)
        except:
            await message.answer("❌ Файлды жіберу кезінде қате кетті.")

# --- НЕГІЗГІ ХЭНДЛЕР ---
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # --- АДМИН ФУНКЦИЯЛАРЫ ---
    if user_id == ADMIN_ID:
        if user_id in give_balance_mode:
            try:
                target_id, amount = message.text.split()
                async with aiosqlite.connect("bot_main_v3.db") as db:
                    check = await (await db.execute("SELECT user_id FROM users WHERE user_id = ?", (int(target_id),))).fetchone()
                    if check:
                        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(amount), int(target_id)))
                        await db.commit()
                        await message.answer(f"✅ ID {target_id} балансына {amount}$ қосылды!", reply_markup=get_admin_kb())
                        try: await bot.send_message(int(target_id), f"🎁 Админ сізге {amount}$ бонус салды!")
                        except: pass
                    else:
                        await message.answer("❌ Мұндай пайдаланушы табылмады.")
                give_balance_mode.remove(user_id)
                return
            except:
                await message.answer("⚠️ Қате! Формат: `ID сома` (Мысалы: 1234567 50)")
                give_balance_mode.remove(user_id)
                return

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
            await message.answer(f"✅ Рассылка аяқталды! {count} адамға жетті.", reply_markup=get_admin_kb())
            return

        if message.text == "📊 Статистика":
            async with aiosqlite.connect("bot_main_v3.db") as db:
                u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                m_count = (await (await db.execute("SELECT COUNT(*) FROM content WHERE is_approved = 1")).fetchone())[0]
                await message.answer(f"👥 Пайдаланушылар: {u_count}\n🎥 Дайын контент: {m_count}")
            return
        elif message.text == "💰 Доллар беру":
            give_balance_mode.add(user_id)
            await message.answer("💵 ID және соманы жазыңыз:", reply_markup=types.ReplyKeyboardRemove())
            return
        elif message.text == "📢 Рассылка":
            broadcast_mode.add(user_id)
            await message.answer("📝 Жіберілетін хабарламаны жазыңыз:", reply_markup=types.ReplyKeyboardRemove())
            return
        elif message.text == "🔒 Жасырын":
            await show_approval(message); return
        elif message.text == "🏠 Пайдаланушы мәзірі":
            await message.answer("Режим ауыстырылды.", reply_markup=get_main_kb()); return

    # --- ПАЙДАЛАНУШЫ ФУНКЦИЯЛАРЫ ---
    if message.text == "🎥 Видео көру":
        await send_media(message, "video")
    elif message.text == "🖼 Фото көру":
        await send_media(message, "photo")
    elif message.text == "👤 Профиль":
        async with aiosqlite.connect("bot_main_v3.db") as db:
            res = await (await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))).fetchone()
            balance = res[0] if res else 0.0
            link = await create_start_link(bot, str(user_id), encode=True)
            await message.answer(f"👤 Сіздің профиліңіз:\n🆔 ID: `{user_id}`\n💰 Баланс: {balance}$\n\n🔗 Сіздің реферал сілтемеңіз:\n{link}", parse_mode="Markdown")
    elif message.text == "💎 Канал сатып алу":
        ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Менеджерге жазу", url=f"https://t.me/{MANAGER_USER[1:]}")]])
        await message.answer("💎 Жабық каналға кіру үшін төмендегі батырманы басыңыз:", reply_markup=ikb)

    # Контент қабылдау (Админ жіберсе бірден базаға, юзер жіберсе тексеруге)
    if message.video or message.photo:
        f_id = message.video.file_id if message.video else message.photo[-1].file_id
        f_type = "video" if message.video else "photo"
        is_a = 1 if user_id == ADMIN_ID else 0
        async with aiosqlite.connect("bot_main_v3.db") as db:
            await db.execute("INSERT INTO content (file_id, file_type, is_approved) VALUES (?, ?, ?)", (f_id, f_type, is_a))
            await db.commit()
        await message.answer("✅ Контент сақталды!" if is_a else "📩 Контент тексеруге жіберілді. Мақұлданса, бонус аласыз!")

# --- APPROVAL (ЖАСЫРЫН) ---
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

# --- ІСКЕ ҚОСУ ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
