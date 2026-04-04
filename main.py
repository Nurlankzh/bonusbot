import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ================= CONFIG =================
TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo"
ADMIN_ID = 6303091468

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DB =================
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            bonus INTEGER DEFAULT 10,
            last_vid_id INTEGER DEFAULT 0,
            last_pic_id INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            ref_by INTEGER DEFAULT 0,
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

# ================= KEYBOARD =================
def main_kb(user_id):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="🎥 Видео"), KeyboardButton(text="🖼 Фото"))
    kb.row(KeyboardButton(text="⭐ Бонус"), KeyboardButton(text="📤 Жіберу"))
    kb.row(KeyboardButton(text="🎁 Күндік бонус"), KeyboardButton(text="👥 Дос шақыру"))
    kb.row(KeyboardButton(text="💎 VIP"))

    if user_id == ADMIN_ID:
        kb.row(KeyboardButton(text="⏳ Pending"), KeyboardButton(text="📊 Статистика"))

    return kb.as_markup(resize_keyboard=True)

# ================= START =================
@dp.message(Command("start"))
async def start(msg: Message):
    args = msg.text.split()
    ref = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0

    user = await db_query("SELECT 1 FROM users WHERE user_id=?", (msg.from_user.id,), "one")

    if not user:
        await db_query("INSERT INTO users (user_id, ref_by) VALUES (?, ?)", (msg.from_user.id, ref))

        if ref and ref != msg.from_user.id:
            await db_query("UPDATE users SET bonus=bonus+10 WHERE user_id=?", (ref,))
            try:
                await bot.send_message(ref, "👥 Жаңа адам шақырдың! +10 бонус")
            except:
                pass

    await msg.answer(
        "🔥 Қош келдің!\n\n"
        "🎥 Видео көр\n"
        "🖼 Фото аш\n"
        "💰 Бонус жина\n\n"
        "👇 Таңда:",
        reply_markup=main_kb(msg.from_user.id)
    )

# ================= DAILY BONUS =================
@dp.message(F.text == "🎁 Күндік бонус")
async def daily_bonus(msg: Message):
    u = await db_query("SELECT last_bonus_date, streak FROM users WHERE user_id=?", (msg.from_user.id,), "one")

    today = datetime.now().date().isoformat()

    if u[0] == today:
        return await msg.answer("⏳ Бүгін алдың!")

    streak = (u[1] or 0) + 1
    bonus = 5 + (streak // 3) * 2

    await db_query(
        "UPDATE users SET bonus=bonus+?, last_bonus_date=?, streak=? WHERE user_id=?",
        (bonus, today, streak, msg.from_user.id)
    )

    await msg.answer(f"🎁 +{bonus} бонус!\n🔥 Серия: {streak} күн")

# ================= REF =================
@dp.message(F.text == "👥 Дос шақыру")
async def ref(msg: Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={msg.from_user.id}"

    await msg.answer(f"👥 Дос шақыру:\n{link}\n\n🔥 Әр адам = +10 бонус")

# ================= BONUS =================
@dp.message(F.text == "⭐ Бонус")
async def bonus(msg: Message):
    u = await db_query("SELECT bonus FROM users WHERE user_id=?", (msg.from_user.id,), "one")

    await msg.answer(
        f"💰 Баланс: {u[0]}\n\n"
        f"📤 Контент жүкте\n"
        f"👥 Дос шақыр\n"
        f"🎁 Күн сайын кір"
    )

# ================= MEDIA =================
@dp.message(F.text.in_(["🎥 Видео", "🖼 Фото"]))
async def media(msg: Message):
    u = await db_query("SELECT * FROM users WHERE user_id=?", (msg.from_user.id,), "one")

    is_video = msg.text == "🎥 Видео"
    table = "videos" if is_video else "photos"
    cost = 4 if is_video else 2

    if not u[4] and u[1] < cost:
        return await msg.answer("❌ Бонус жетпейді")

    last_id = u[2] if is_video else u[3]

    media = await db_query(f"SELECT id, file_id FROM {table} WHERE id>? ORDER BY id LIMIT 1", (last_id,), "one")

    if not media:
        return await msg.answer("🏁 Контент бітті")

    if is_video:
        await msg.answer_video(media[1], caption="🎬 Құпия видео\n💰 -4 бонус")
        await db_query("UPDATE users SET last_vid_id=? WHERE user_id=?", (media[0], msg.from_user.id))
    else:
        await msg.answer_photo(media[1], caption="📸 Жаңа фото\n💰 -2 бонус")
        await db_query("UPDATE users SET last_pic_id=? WHERE user_id=?", (media[0], msg.from_user.id))

    if not u[4]:
        await db_query("UPDATE users SET bonus=bonus-? WHERE user_id=?", (cost, msg.from_user.id))

# ================= UPLOAD =================
@dp.message(F.video | F.photo)
async def upload(msg: Message):
    f_type = "video" if msg.video else "photo"
    f_id = msg.video.file_id if msg.video else msg.photo[-1].file_id

    if msg.from_user.id == ADMIN_ID:
        table = "videos" if f_type == "video" else "photos"
        await db_query(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))
        return await msg.answer("✅ Бірден базаға сақталды")

    await db_query("INSERT INTO pending (user_id, file_id, file_type) VALUES (?, ?, ?)",
                   (msg.from_user.id, f_id, f_type))

    await msg.answer("⏳ Админ тексеруде...")

# ================= ADMIN PENDING =================
@dp.message(F.text == "⏳ Pending", F.from_user.id == ADMIN_ID)
async def pending(msg: Message):
    item = await db_query("SELECT * FROM pending LIMIT 1", fetch="one")

    if not item:
        return await msg.answer("📂 Бос")

    _, u_id, f_id, f_type = item

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Мақұлдау", callback_data=f"ok_{item[0]}"),
            InlineKeyboardButton(text="❌ Бас тарту", callback_data=f"no_{item[0]}")
        ]
    ])

    if f_type == "video":
        await msg.answer_video(f_id, caption=f"👤 {u_id}", reply_markup=kb)
    else:
        await msg.answer_photo(f_id, caption=f"👤 {u_id}", reply_markup=kb)

@dp.callback_query(F.data.startswith("ok_"))
async def approve(call: CallbackQuery):
    db_id = call.data.split("_")[1]

    data = await db_query("SELECT * FROM pending WHERE id=?", (db_id,), "one")
    u_id, f_id, f_type = data[1], data[2], data[3]

    table = "videos" if f_type == "video" else "photos"

    await db_query(f"INSERT OR IGNORE INTO {table} (file_id) VALUES (?)", (f_id,))

    bonus = 12 if f_type == "video" else 6
    await db_query("UPDATE users SET bonus=bonus+? WHERE user_id=?", (bonus, u_id))

    await db_query("DELETE FROM pending WHERE id=?", (db_id,))
    await call.message.delete()

@dp.callback_query(F.data.startswith("no_"))
async def reject(call: CallbackQuery):
    db_id = call.data.split("_")[1]

    await db_query("DELETE FROM pending WHERE id=?", (db_id,))
    await call.message.delete()

# ================= STATS =================
@dp.message(F.text == "📊 Статистика", F.from_user.id == ADMIN_ID)
async def stats(msg: Message):
    users = await db_query("SELECT COUNT(*) FROM users", fetch="one")
    videos = await db_query("SELECT COUNT(*) FROM videos", fetch="one")
    photos = await db_query("SELECT COUNT(*) FROM photos", fetch="one")

    await msg.answer(
        f"👥 Users: {users[0]}\n"
        f"🎥 Videos: {videos[0]}\n"
        f"🖼 Photos: {photos[0]}"
    )

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
