import os
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo"
ADMIN_ID = 6303091468
CHANNEL_USERNAME = "@uyatsizoqiga"
DB_FILE = "data.db"
REF_BOT_USERNAME = "Darvinuyatszdaribot"
VIP_CONTACT = "Kazhabs"  # VIP алу үшін контакті

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
db_lock = threading.Lock()

# ==========================================
# DATABASE INIT
# ==========================================
def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    with db_lock:
        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
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
        cursor.execute("""CREATE TABLE IF NOT EXISTS pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploader_id INTEGER,
            content_type TEXT,
            file_id TEXT,
            created_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE, added_by INTEGER, created_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE, added_by INTEGER, created_at TEXT
        )""")
        conn.commit()
    conn.close()

init_db()

# ==========================================
# KEYBOARDS
# ==========================================
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎥 Видео көру"), KeyboardButton("🖼 Фото көру"))
    kb.row(KeyboardButton("🎁 Күндік бонус алу"), KeyboardButton("➕ Видео/Фото жіберу"))
    kb.row(KeyboardButton("💎 VIP алу"))
    if user_id == ADMIN_ID:
        kb.row(KeyboardButton("💰 Бонус беру"), KeyboardButton("✅ Pending файлдар"))
        kb.row(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
    return kb

# ==========================================
# HELPERS
# ==========================================
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
                ref_data = cursor.execute("SELECT referral_count FROM users WHERE user_id=?", (invited_by,)).fetchone()
                count = ref_data[0] if ref_data else 1
                try:
                    bot.send_message(invited_by, f"🎊 Сіз 1 жаңа адам шақырдыңыз!\n🎁 Бонус: +6💸\n📊 Барлық шақырылғандар: {count} адам.")
                except: pass
    conn.close()

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

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

# ==========================================
# START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    text_parts = message.text.split()
    ref_id = None
    if len(text_parts) > 1 and text_parts[1].isdigit():
        ref_id = int(text_parts[1])
    ensure_user(user_id, ref_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ 18-ден астым", callback_data="confirm_adult"))
    bot.send_message(user_id, "🔞 Бұл ботта ересектерге арналған контент бар. Жасыңызды растаңыз:", reply_markup=markup)

# ==========================================
# CALLBACK HANDLER
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_manager(call):
    user_id = call.from_user.id
    conn = get_db_connection()
    if call.data == "confirm_adult":
        with db_lock:
            conn.execute("UPDATE users SET is_adult=1 WHERE user_id=?", (user_id,))
            conn.commit()
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "✅ Рақмет! Қалаған батырманы басыңыз.", reply_markup=get_main_keyboard(user_id))
    conn.close()

# ==========================================
# VIP HANDLER
# ==========================================
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
                         f"💎 VIP режимді алу үшін келесі қадамдарды орындаңыз:\n\n"
                         f"1️⃣ @{VIP_CONTACT}-қа хабарласыңыз.\n"
                         f"2️⃣ «VIP режим алғым келеді» деп жазуға дайын текст шығады.\n"
                         f"3️⃣ VIP бекітілген соң барлық видеолар мен фотолар тегін қол жетімді болады.\n"
                         f"4️⃣ VIP қолданушыларға қосымша бонус беріледі.\n\n"
                         f"🚀 Тез әрекет жасаңыз, эксклюзив бонус үшін!",
                         reply_markup=markup)
    conn.close()

# ==========================================
# DAILY BONUS
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎁 Күндік бонус алу")
def daily_bonus_handler(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    user_data = conn.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)).fetchone()
    now = datetime.now()
    if user_data and user_data[0]:
        next_time = datetime.fromisoformat(user_data[0]) + timedelta(hours=24)
        if now < next_time:
            diff = next_time - now
            bot.send_message(user_id, f"⚠️ Бонусты тек 24 сағатта бір рет алуға болады.\nКүте тұрыңыз: {int(diff.total_seconds() // 3600)} сағат.")
            conn.close()
            return
    with db_lock:
        conn.execute("UPDATE users SET balance = balance + 10, last_daily = ? WHERE user_id=?", (now.isoformat(), user_id))
        conn.commit()
    bot.send_message(user_id, "🎉 +10💸 бонус берілді!")
    conn.close()

# ==========================================
# UPLOAD HANDLER
# ==========================================
@bot.message_handler(content_types=['photo', 'video'])
def handle_uploads(message):
    user_id = message.from_user.id
    is_video = message.content_type == 'video'
    file_id = message.video.file_id if is_video else message.photo[-1].file_id
    content_type = "video" if is_video else "photo"

    if file_exists(file_id, content_type):
        bot.send_message(user_id, f"⚠️ Бұл {content_type} файл ботта бұрын бар. Қосылмады.")
        return

    conn = get_db_connection()
    if user_id == ADMIN_ID:
        table = "videos" if is_video else "photos"
        with db_lock:
            conn.execute(f"INSERT INTO {table} (file_id, added_by, created_at) VALUES (?,?,?)", (file_id, user_id, datetime.now().isoformat()))
            conn.commit()
        bot.send_message(user_id, "✅ Файл тікелей қосылды!")
    else:
        with db_lock:
            conn.execute("INSERT INTO pending (uploader_id, content_type, file_id, created_at) VALUES (?,?,?,?)",
                         (user_id, content_type, file_id, datetime.now().isoformat()))
            conn.commit()
        bot.send_message(user_id, "📩 Файл модерацияға жіберілді. Қабылданса бонус беріледі.")
    conn.close()

# ==========================================
# BROADCAST HANDLER
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📢 Рассылка" and m.from_user.id == ADMIN_ID)
def broadcast_handler(message):
    bot.send_message(ADMIN_ID, "✉️ Жіберетін хабарламаны жазыңыз:")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    text = message.text
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 Админ хабарламасы:\n\n{text}")
            sent += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ Хабарлама {sent} адамға жіберілді.")

# ==========================================
# TEXT HANDLER (VIEW VIDEO/PHOTO, ADMIN)
# ==========================================
@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text
    conn = get_db_connection()
    user_data = conn.execute("SELECT is_adult, balance, progress_video, progress_photo, is_vip FROM users WHERE user_id=?", (user_id,)).fetchone()
    
    if not user_data or user_data[0] == 0:
        conn.close()
        return

    # --- VIDEO VIEW ---
    if text == "🎥 Видео көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif not user_data[4] and user_data[1] < 2:  # VIP болса тегін
            bot.send_message(user_id, get_ref_msg(user_id), parse_mode="Markdown")
        else:
            vid = conn.execute("SELECT file_id FROM videos ORDER BY id ASC LIMIT 1 OFFSET ?", (user_data[2],)).fetchone()
            if vid:
                new_balance = user_data[1] - 2 if not user_data[4] else user_data[1]
                bot.send_video(user_id, vid[0], caption=f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}💸")
                with db_lock:
                    conn.execute("UPDATE users SET balance = ?, progress_video = progress_video + 1 WHERE user_id=?", (new_balance, user_id))
                    conn.commit()
            else: bot.send_message(user_id, "😔 Видеолар таусылды.")

    # --- PHOTO VIEW ---
    elif text == "🖼 Фото көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif not user_data[4] and user_data[1] < 3:
            bot.send_message(user_id, get_ref_msg(user_id), parse_mode="Markdown")
        else:
            pic = conn.execute("SELECT file_id FROM photos ORDER BY id ASC LIMIT 1 OFFSET ?", (user_data[3],)).fetchone()
            if pic:
                new_balance = user_data[1] - 3 if not user_data[4] else user_data[1]
                bot.send_photo(user_id, pic[0], caption=f"✅ Көру сәтті! \n💰 Қалған баланс: {new_balance}💸")
                with db_lock:
                    conn.execute("UPDATE users SET balance = ?, progress_photo = progress_photo + 1 WHERE user_id=?", (new_balance, user_id))
                    conn.commit()
            else: bot.send_message(user_id, "😔 Фотолар таусылды.")

    # --- ADMIN BONUS ---
    elif text == "💰 Бонус беру" and user_id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "⚡️ Бонус беру форматы: ID сома (Мысалы: 123456789 100)", parse_mode="Markdown")
        bot.register_next_step_handler(message, process_bonus)

    # --- ADMIN PENDING ---
    elif text == "✅ Pending файлдар" and user_id == ADMIN_ID:
        p = conn.execute("SELECT id, uploader_id, content_type, file_id FROM pending LIMIT 1").fetchone()
        if p:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Мақұлдау", callback_data=f"appr_{p[0]}"))
            markup.add(InlineKeyboardButton("❌ Реджект", callback_data=f"reject_{p[0]}"))
            if p[2] == 'video':
                bot.send_video(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
            else:
                bot.send_photo(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
        else:
            bot.send_message(ADMIN_ID, "Тізім бос.")

    # --- ADMIN STATS ---
    elif text == "📊 Статистика" and user_id == ADMIN_ID:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(ADMIN_ID, f"👥 Пайдаланушылар: {count}")

    conn.close()

# ==========================================
# PROCESS BONUS
# ==========================================
def process_bonus(message):
    try:
        data = message.text.split()
        target_id, amount = int(data[0]), int(data[1])
        conn = get_db_connection()
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_id))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, "✅ Бонус берілді.")
        try: bot.send_message(target_id, f"🎁 Админ сізге {amount}💸 бонус берді!")
        except: pass
    except: bot.send_message(ADMIN_ID, "❌ Қате.")

# ==========================================
# RUN BOT
# ==========================================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
