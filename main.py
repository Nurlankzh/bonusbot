import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ===== CONFIG =====
TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo"
ADMIN_ID = 6303091468
REF_LINK = "https://t.me/Darvinuyatszdaribot?start=6303091468"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# ===== DATABASE =====
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            bonus INTEGER DEFAULT 10,
            last_vid_id INTEGER DEFAULT 0,
            last_pic_id INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            last_bonus_date TEXT,
            streak INTEGER DEFAULT 0
        )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE)")
        await db.execute("CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE)")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            file_type TEXT
        )
        """)
        await db.commit()

async def db_query(sql, params=(), fetch=None):
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute(sql, params)
        if fetch == "one":
            return await cur.fetchone()
        if fetch == "all":
            return await cur.fetchall()
        await db.commit()

# ===== KEYBOARDS =====
def main_kb(user_id):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото"))
    kb.row(KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="🎁 Күндік бонус"))
    kb.row(KeyboardButton(text="💎 VIP"))
    if user_id == ADMIN_ID:
        kb.row(KeyboardButton(text="📤 Бонус беру"))
        # ===== ADMIN GIVE BONUS INTERACTIVE =====
bonus_state = {}  # админның уақытша күйі

@dp.message(F.text == "📤 Бонус беру", F.from_user.id == ADMIN_ID)
async def bonus_hint(msg: Message):
    bonus_state[msg.from_user.id] = {"step": 1}  # қадам 1: ID күту
    await msg.answer(
        "📝 Бонус беру үшін чатқа былай жазыңыз:\n\n"
        "1️⃣ Пайдаланушы ID енгізіңіз\n"
        "2️⃣ Бонус сомасын енгізіңіз\n\n"
        "Мысалы:\n6303091468\n100"
    )

@dp.message(F.from_user.id == ADMIN_ID)
async def bonus_process(msg: Message):
    state = bonus_state.get(msg.from_user.id)
    if not state:
        return  # басқа хабарламаларға қарамаймыз

    if state["step"] == 1:
        try:
            user_id = int(msg.text.strip())
            state["user_id"] = user_id
            state["step"] = 2
            await msg.answer(f"✅ ID қабылданды: {user_id}\nЕнді бонус сомасын енгізіңіз:")
        except ValueError:
            await msg.answer("❌ ID дұрыс емес, тек сандармен жазу керек. Қайта енгізіңіз:")
    elif state["step"] == 2:
        try:
            amount = int(msg.text.strip())
            user_id = state["user_id"]
            # Базада бонус қосу
            await db_query("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, user_id))
            await msg.answer(f"🎉 {amount} бонус {user_id}-ға сәтті қосылды!")
            # Күйді тазалау
            bonus_state.pop(msg.from_user.id, None)
        except ValueError:
            await msg.answer("❌ Сома дұрыс емес, тек сандармен жазу керек. Қайта енгізіңіз:")
        kb.row(KeyboardButton(text="⏳ Pending"), KeyboardButton(text="📊 Статистика"))
        kb.row(KeyboardButton(text="📢 Рассылка"))
    return kb.as_markup(resize_keyboard=True)

# ===== START =====
@dp.message(Command("start"))
async def start(msg: Message):
    user = await db_query("SELECT 1 FROM users WHERE user_id=?", (msg.from_user.id,), "one")
    if not user:
        await db_query("INSERT INTO users (user_id) VALUES (?)", (msg.from_user.id,))
    await msg.answer(
        "🔥 Қош келдің!\n\n🎥 Видео көр\n🖼 Фото аш\n💰 Бонус жина\n\n👇 Таңда:",
        reply_markup=main_kb(msg.from_user.id)
    )

# ===== BONUS INFO =====
@dp.message(F.text == "⭐ Бонус")
async def bonus(msg: Message):
    u = await db_query("SELECT bonus, is_vip FROM users WHERE user_id=?", (msg.from_user.id,), "one")
    status = "💎 VIP" if u[1] else "👤 Қарапайым"
    await msg.answer(
        f"{status}\n\n💰 Баланс: {u[0]}\n\n👥 Дос шақыр:\n{REF_LINK}\n\n🔥 Әр адам = +10 бонус"
    )

# ===== DAILY BONUS =====
@dp.message(F.text == "🎁 Күндік бонус")
async def daily(msg: Message):
    u = await db_query("SELECT last_bonus_date, streak FROM users WHERE user_id=?", (msg.from_user.id,), "one")
    today = datetime.now().date().isoformat()
    if u[0] == today:
        return await msg.answer("⏳ Бүгін алдың!")
    streak = (u[1] or 0) + 1
    bonus_val = 5 + (streak // 3) * 2
    await db_query("UPDATE users SET bonus=bonus+?, last_bonus_date=?, streak=? WHERE user_id=?",
                   (bonus_val, today, streak, msg.from_user.id))
    await msg.answer(f"🎁 +{bonus_val} бонус\n🔥 Серия: {streak}")

# ===== VIP =====
@dp.message(F.text == "💎 VIP")
async def vip(msg: Message):
    await msg.answer(
        "💎 VIP РЕЖИМ\n\n♾ Шексіз контент\n🚫 Бонус кетпейді\n\n💰 Бағасы: 100 бонус\n\n👇 Таңда:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Бонуспен алу", callback_data="buy_vip")],
            [InlineKeyboardButton(text="💬 Менеджер", url="https://t.me/Kazhabs")]
        ])
    )

@dp.callback_query(F.data == "buy_vip")
async def buy_vip(call: CallbackQuery):
    u = await db_query("SELECT bonus, is_vip FROM users WHERE user_id=?", (call.from_user.id,), "one")
    if u[1]:
        return await call.answer("Сенде VIP бар")
    if u[0] < 100:
        return await call.answer("❌ Бонус жетпейді", show_alert=True)
    await db_query("UPDATE users SET bonus=bonus-100, is_vip=1 WHERE user_id=?", (call.from_user.id,))
    await call.message.edit_text("💎 VIP қосылды! 🔥")

# ===== MEDIA LOOP =====
@dp.message(F.text.in_(["🎥 Видео", "🖼 Фото"]))
async def media(msg: Message):
    u = await db_query("SELECT * FROM users WHERE user_id=?", (msg.from_user.id,), "one")
    is_video = msg.text == "🎥 Видео"
    table = "videos" if is_video else "photos"
    cost = 4 if is_video else 2
    is_vip = u[4]
    if not is_vip and u[1] < cost:
        return await msg.answer(
            f"❌ Бонусың бітіп қалды!\n\n👥 Дос шақыр:\n{REF_LINK}\n\n🔥 Әр адам = +10 бонус"
        )
    last_id = u[2] if is_video else u[3]
    media_item = await db_query(f"SELECT id, file_id FROM {table} WHERE id>? ORDER BY id LIMIT 1", (last_id,), "one")
    if not media_item:
        await db_query(f"UPDATE users SET {'last_vid_id' if is_video else 'last_pic_id'}=0 WHERE user_id=?", (msg.from_user.id,))
        media_item = await db_query(f"SELECT id, file_id FROM {table} ORDER BY id LIMIT 1", fetch="one")
    if not media_item:
        return await msg.answer("❌ База бос")
    if is_video:
        await msg.answer_video(media_item[1], caption="🎬 Құпия видео")
        await db_query("UPDATE users SET last_vid_id=? WHERE user_id=?", (media_item[0], msg.from_user.id))
    else:
        await msg.answer_photo(media_item[1], caption="📸 Жаңа фото")
        await db_query("UPDATE users SET last_pic_id=? WHERE user_id=?", (media_item[0], msg.from_user.id))
    if not is_vip:
        await db_query("UPDATE users SET bonus=bonus-? WHERE user_id=?", (cost, msg.from_user.id))

# ===== UPLOAD & PENDING =====
@dp.message(F.video | F.photo)
async def upload(msg: Message):
    f_type = "video" if msg.video else "photo"
    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id
    if msg.from_user.id == ADMIN_ID:
        table = "videos" if f_type == "video" else "photos"
        await db_query(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
        await msg.answer(f"✅ {f_type.capitalize()} базаға қосылды! Шексіз қолжетімді.")
        return
    await db_query("INSERT INTO pending (user_id, file_id, file_type) VALUES (?, ?, ?)",
                   (msg.from_user.id, f_id, f_type))
    await msg.answer("⏳ Админ тексеруде...")

# ===== PENDING APPROVE/REJECT =====
async def show_next_pending(message_or_call):
    item = await db_query("SELECT * FROM pending ORDER BY id LIMIT 1", fetch="one")
    if not item:
        await message_or_call.answer("📂 Pending бос") if isinstance(message_or_call, CallbackQuery) else await message_or_call.answer("📂 Бос")
        return
    _, u_id, f_id, f_type = item
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Мақұлдау", callback_data=f"ok_{item[0]}"),
         InlineKeyboardButton(text="❌ Болдырмау", callback_data=f"no_{item[0]}")]
    ])
    if f_type == "video":
        await message_or_call.message.answer_video(f_id, caption=f"👤 {u_id}", reply_markup=kb) if isinstance(message_or_call, CallbackQuery) else await message_or_call.answer_video(f_id, caption=f"👤 {u_id}", reply_markup=kb)
    else:
        await message_or_call.message.answer_photo(f_id, caption=f"👤 {u_id}", reply_markup=kb) if isinstance(message_or_call, CallbackQuery) else await message_or_call.answer_photo(f_id, caption=f"👤 {u_id}", reply_markup=kb)

@dp.message(F.text == "⏳ Pending", F.from_user.id == ADMIN_ID)
async def pending(msg: Message):
    await show_next_pending(msg)

@dp.callback_query(F.data.startswith("ok_"))
async def ok(call: CallbackQuery):
    db_id = call.data.split("_")[1]
    data = await db_query("SELECT * FROM pending WHERE id=?", (db_id,), "one")
    if data:
        u_id, f_id, f_type = data[1], data[2], data[3]
        table = "videos" if f_type == "video" else "photos"
        await db_query(f"INSERT INTO {table} (file_id) VALUES (?)", (f_id,))
        bonus = 12 if f_type == "video" else 6
        await db_query("UPDATE users SET bonus=bonus+? WHERE user_id=?", (bonus, u_id))
        await db_query("DELETE FROM pending WHERE id=?", (db_id,))
        try: await bot.send_message(u_id, f"✅ Қабылданды! +{bonus} бонус")
        except: pass
    await call.message.delete()
    await show_next_pending(call)

@dp.callback_query(F.data.startswith("no_"))
async def no(call: CallbackQuery):
    db_id = call.data.split("_")[1]
    await db_query("DELETE FROM pending WHERE id=?", (db_id,))
    await call.message.delete()
    await show_next_pending(call)

# ===== ADMIN STATISTICS =====
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(msg: Message):
    total_users = await db_query("SELECT COUNT(*) FROM users", fetch="one")
    active_users = await db_query("SELECT COUNT(*) FROM users WHERE bonus>0 OR is_vip=1", fetch="one")
    pending_count = await db_query("SELECT COUNT(*) FROM pending", fetch="one")
    await msg.answer(
        f"📊 Статистика\n\n👥 Барлығы: {total_users[0]}\n🔥 Активті: {active_users[0]}\n⏳ Pending: {pending_count[0]}"
    )

# ===== BROADCAST =====
broadcast_state = {}
@dp.message(F.text == "📢 Рассылка", F.from_user.id == ADMIN_ID)
async def broadcast_start(msg: Message):
    broadcast_state[msg.from_user.id] = True
    await msg.answer("📢 Таратқыңыз келетін хабарламаны жіберіңіз:")

@dp.message(F.from_user.id == ADMIN_ID)
async def broadcast_send(msg: Message):
    if broadcast_state.get(msg.from_user.id):
        text = msg.text
        users = await db_query("SELECT user_id FROM users", fetch="all")
        sent = 0
        for u in users:
            try:
                await bot.send_message(u[0], text)
                sent += 1
                await asyncio.sleep(0.05)
            except: pass
        await msg.answer(f"📢 Жарияланды: {sent}/{len(users)}")
        broadcast_state[msg.from_user.id] = False

# ===== ADMIN GIVE BONUS QUICK =====
@dp.message(F.text.lower().startswith("бонус"), F.from_user.id == ADMIN_ID)
async def give_bonus(msg: Message):
    try:
        parts = msg.text.split()
        if len(parts) != 3:
            return await msg.answer("❌ Қате формат!\nМысалы: бонус 6303091468 50")
        target_id = int(parts[1])
        amount = int(parts[2])
        user = await db_query("SELECT 1 FROM users WHERE user_id=?", (target_id,), "one")
        if not user:
            return await msg.answer("❌ Бұл пайдаланушы базада жоқ!")
        await db_query("UPDATE users SET bonus=bonus+? WHERE user_id=?", (amount, target_id))
        try: await bot.send_message(target_id, f"🎁 Құттықтаймыз! Админ сізге {amount} бонус берді!")
        except: pass
        await msg.answer(f"✅ ID: {target_id} пайдаланушысына {amount} бонус сәтті қосылды!")
    except ValueError:
        await msg.answer("❌ Қате! ID және бонус саны тек сандар болуы керек.")

# ===== UNKNOWN MESSAGE =====
@dp.message()
async def unknown(msg: Message):
    known_commands = ["🎥 Видео", "🖼 Фото", "⭐ Бонус", "🎁 Күндік бонус",
                      "💎 VIP", "📤 Бонус беру", "⏳ Pending", "📊 Статистика",
                      "📢 Рассылка", "/start"]
    if not any(msg.text.startswith(k) for k in known_commands):
        await msg.answer("❌ Түсінбедім 🤔\nМенюдағы батырмаларды таңдаңыз немесе /start теріңіз.")

# ===== RUN =====
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
