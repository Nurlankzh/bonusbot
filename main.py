import os
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = "СЕНІҢ_ТОКЕНІҢІЗ"
ADMIN_ID = 6303091468
CHANNEL_USERNAME = "@senin_kanalyngyz"
REF_BOT_USERNAME = "@Deetskay_bot"
VIP_CONTACT = "Kazhabs"
DB_FILE = "data.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
db_lock = threading.Lock()

# ================= DATABASE =================
def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    with db_lock:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 3,
            progress_video INTEGER DEFAULT 0,
            progress_photo INTEGER DEFAULT 0,
            invited_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            is_adult INTEGER DEFAULT 0,
            joined_at TEXT,
            last_daily TEXT,
            is_vip INTEGER DEFAULT 0
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            added_at TEXT
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            added_at TEXT
        )""")
        conn.commit()
    conn.close()

init_db()

# ================= KEYBOARDS =================
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎥 Видео көру"), KeyboardButton("🖼 Фото көру"))
    kb.row(KeyboardButton("🎁 Күндік бонус алу"))
    kb.row(KeyboardButton("💎 VIP алу"))
    if user_id == ADMIN_ID:
        kb.row(KeyboardButton("➕ Видео қосу"), KeyboardButton("➕ Фото қосу"))
        kb.row(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
    return kb

# ================= HELPERS =================
def ensure_user(user_id, invited_by=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    with db_lock:
        user = cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            now = datetime.now().isoformat()
            cursor.execute("INSERT INTO users (user_id, balance, invited_by, joined_at) VALUES (?, ?, ?, ?)",
                           (user_id, 3, invited_by, now))
            conn.commit()
            if invited_by and invited_by != user_id:
                cursor.execute("UPDATE users SET balance = balance + 6, referral_count = referral_count + 1 WHERE user_id=?", (invited_by,))
                conn.commit()
                ref_count = cursor.execute("SELECT referral_count FROM users WHERE user_id=?", (invited_by,)).fetchone()[0]
                try:
                    bot.send_message(invited_by, f"🎊 Сіз 1 жаңа адам шақырдыңыз!\n🎁 Бонус: +6💸\n📊 Барлық шақырылғандар: {ref_count} адам.")
                except: pass
    conn.close()

def check_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_ref_msg(user_id):
    return (f"❌ Сіздің бонустарыңыз бітті!\n\n"
            f"Жалғастыру үшін дос шақырыңыз. Әр дос үшін **+6💸** беріледі.\n"
            f"🔗 Сіздің сілтемеңіз:\n`https://t.me/{REF_BOT_USERNAME}?start={user_id}`")

def file_exists(file_id, content_type):
    conn = get_db_connection()
    table = "videos" if content_type == "video" else "photos"
    exists = conn.execute(f"SELECT 1 FROM {table} WHERE file_id=?", (file_id,)).fetchone() is not None
    conn.close()
    return exists

# ================= START COMMAND =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    text_parts = message.text.split()
    ref_id = int(text_parts[1]) if len(text_parts) > 1 and text_parts[1].isdigit() else None
    ensure_user(user_id, ref_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ 18-ден астым", callback_data="confirm_adult"))
    bot.send_message(user_id, "🔞 Бұл ботта ересектерге арналған контент бар. Жасыңызды растаңыз:", reply_markup=markup)

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback_manager(call):
    user_id = call.from_user.id
    if call.data == "confirm_adult":
        conn = get_db_connection()
        with db_lock:
            conn.execute("UPDATE users SET is_adult=1 WHERE user_id=?", (user_id,))
            conn.commit()
        conn.close()
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "✅ Рақмет! Қалаған батырманы басыңыз.", reply_markup=get_main_keyboard(user_id))

# ================= VIP =================
@bot.message_handler(func=lambda m: m.text == "💎 VIP алу")
def vip_handler(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    user_data = conn.execute("SELECT is_vip FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user_data and user_data[0] == 1:
        bot.send_message(user_id, "💎 Сізде VIP режим бар!")
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📨 VIP сұрау жіберу", url=f"https://t.me/{VIP_CONTACT}?start=VIP_{user_id}"))
        bot.send_message(user_id,
                         f"💎 VIP режимді алу үшін @{VIP_CONTACT}-қа хабарласыңыз.\n"
                         f"Барлық видеолар мен фотолар тегін қол жетімді болады.", reply_markup=markup)
    conn.close()

# ================= DAILY BONUS =================
@bot.message_handler(func=lambda m: m.text == "🎁 Күндік бонус алу")
def daily_bonus_handler(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    user_data = conn.execute("SELECT last_daily, balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    now = datetime.now()
    if user_data and user_data[0]:
        next_time = datetime.fromisoformat(user_data[0]) + timedelta(hours=24)
        if now < next_time:
            diff = next_time - now
            bot.send_message(user_id, f"⚠️ Бонусты тек 24 сағатта бір рет алуға болады.\nКүте тұрыңыз: {int(diff.total_seconds() // 3600)} сағат.")
            conn.close()
            return
    with db_lock:
        new_balance = user_data[1] + 10 if user_data else 10
        conn.execute("UPDATE users SET balance=?, last_daily=? WHERE user_id=?", (new_balance, now.isoformat(), user_id))
        conn.commit()
    bot.send_message(user_id, "🎉 +10💸 бонус берілді!")
    conn.close()

# ================= VIEW VIDEO / PHOTO (ЦИКЛ) =================
@bot.message_handler(func=lambda m: m.text in ["🎥 Видео көру", "🖼 Фото көру"])
def view_content_handler(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    user_data = conn.execute(
        "SELECT is_adult, balance, progress_video, progress_photo, is_vip FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    if not user_data or user_data[0] == 0:
        conn.close()
        return

    is_vip = user_data[4]
    balance = user_data[1]

    # Баланс тексеру
    if balance <= 0 and not is_vip:
        bot.send_message(user_id, get_ref_msg(user_id))
        conn.close()
        return

    if message.text == "🎥 Видео көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
            conn.close()
            return
        total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        if total_videos == 0:
            bot.send_message(user_id, "😔 Видеолар әлі жоқ.")
            conn.close()
            return
        offset = user_data[2] % total_videos  # цикл басынан
        vid = conn.execute("SELECT file_id FROM videos ORDER BY id ASC LIMIT 1 OFFSET ?", (offset,)).fetchone()
        new_balance = balance if is_vip else balance - 2
        bot.send_video(user_id, vid[0], caption=f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}💸")
        with db_lock:
            conn.execute("UPDATE users SET balance=?, progress_video=progress_video+1 WHERE user_id=?", (new_balance, user_id))
            conn.commit()

    elif message.text == "🖼 Фото көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
            conn.close()
            return
        total_photos = conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        if total_photos == 0:
            bot.send_message(user_id, "😔 Фотолар әлі жоқ.")
            conn.close()
            return
        offset = user_data[3] % total_photos  # цикл басынан
        pic = conn.execute("SELECT file_id FROM photos ORDER BY id ASC LIMIT 1 OFFSET ?", (offset,)).fetchone()
        new_balance = balance if is_vip else balance - 3
        bot.send_photo(user_id, pic[0], caption=f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}💸")
        with db_lock:
            conn.execute("UPDATE users SET balance=?, progress_photo=progress_photo+1 WHERE user_id=?", (new_balance, user_id))
            conn.commit()

    conn.close()

# ================= ADMIN ADD CONTENT =================
@bot.message_handler(func=lambda m: m.text in ["➕ Видео қосу", "➕ Фото қосу"] and m.from_user.id == ADMIN_ID)
def admin_add_content(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "📤 Бірден бірнеше файл жіберуге болады (видео/фото):")
    bot.register_next_step_handler(message, handle_admin_upload)

def handle_admin_upload(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    conn = get_db_connection()
    # Видео
    if message.content_type == "video":
        file_ids = [message.video.file_id]
        for file_id in file_ids:
            if not file_exists(file_id, "video"):
                with db_lock:
                    conn.execute("INSERT INTO videos (file_id, added_at) VALUES (?, ?)", (file_id, datetime.now().isoformat()))
                    conn.commit()
                bot.send_message(user_id, "✅ Видео қосылды!")
            else:
                bot.send_message(user_id, "⚠️ Видео бұрын қосылған!")

    # Фото (қатарынан)
    elif message.content_type == "photo":
        file_ids = [p.file_id for p in message.photo]
        for file_id in file_ids:
            if not file_exists(file_id, "photo"):
                with db_lock:
                    conn.execute("INSERT INTO photos (file_id, added_at) VALUES (?, ?)", (file_id, datetime.now().isoformat()))
                    conn.commit()
                bot.send_message(user_id, "✅ Фото қосылды!")
            else:
                bot.send_message(user_id, "⚠️ Фото бұрын қосылған!")
    else:
        bot.send_message(user_id, "⚠️ Тек видео немесе фото жіберуге болады.")
    conn.close()

# ================= ADMIN STATS / BROADCAST =================
@bot.message_handler(func=lambda m: m.text in ["📊 Статистика", "📢 Рассылка"] and m.from_user.id == ADMIN_ID)
def admin_tools(message):
    if message.text == "📊 Статистика":
        conn = get_db_connection()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        total_photos = conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        conn.close()
        bot.send_message(ADMIN_ID, f"👥 Пайдаланушылар: {total_users}\n🎥 Видеолар: {total_videos}\n🖼 Фотолар: {total_photos}")
    elif message.text == "📢 Рассылка":
        bot.send_message(ADMIN_ID, "✉️ Хабарламаны жазыңыз:")
        bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    text = message.text
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    for u in users:
        try:
            bot.send_message(u[0], f"📢 Админ хабарламасы:\n{text}")
        except: pass
    bot.send_message(ADMIN_ID, f"✅ Хабарлама {len(users)} адамға жіберілді.")

# ================= RUN BOT =================
logger.info("Bot is polling...")
bot.infinity_polling()
