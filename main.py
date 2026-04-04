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
REF_BOT_USERNAME = "adeptiemesbot"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
db_lock = threading.Lock()

# ==========================================
# DATABASE
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
            last_daily TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploader_id INTEGER,
            content_type TEXT,
            file_id TEXT,
            created_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, added_by INTEGER, created_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, added_by INTEGER, created_at TEXT
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
    if user_id == ADMIN_ID:
        kb.row(KeyboardButton("💰 Бонус беру"), KeyboardButton("✅ Pending файлдар"))
        kb.row(KeyboardButton("📊 Статистика"))
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
            # Referral bonus
            if invited_by and invited_by != user_id:
                cursor.execute("UPDATE users SET balance = balance + 6, referral_count = referral_count + 1 WHERE user_id=?", (invited_by,))
                conn.commit()
                ref_count = cursor.execute("SELECT referral_count FROM users WHERE user_id=?", (invited_by,)).fetchone()[0]
                try:
                    bot.send_message(invited_by, f"🎊 Сіз 1 жаңа адам шақырдыңыз!\n🎁 +6💸 бонус\n📊 Барлығы шақырғандар: {ref_count}")
                except: pass
    conn.close()

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_ref_msg(user_id):
    return (f"❌ Баланс жетпейді!\n"
            f"Дос шақырыңыз, әр дос үшін +6💸 беріледі.\n"
            f"🔗 Сіздің сілтемеңіз:\n`https://t.me/{REF_BOT_USERNAME}?start={user_id}`")

# ==========================================
# START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    text_parts = message.text.split()
    ref_id = int(text_parts[1]) if len(text_parts) > 1 and text_parts[1].isdigit() else None
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
    
    elif call.data.startswith("appr_"):
        pid = call.data.split("_")[1]
        p = conn.execute("SELECT uploader_id, content_type, file_id FROM pending WHERE id=?", (pid,)).fetchone()
        if p:
            uid, ctype, fid = p
            table = "videos" if ctype == "video" else "photos"
            with db_lock:
                conn.execute(f"INSERT INTO {table} (file_id, added_by, created_at) VALUES (?,?,?)", (fid, uid, datetime.now().isoformat()))
                conn.execute("UPDATE users SET balance = balance + 12 WHERE user_id=?", (uid,))
                conn.execute("DELETE FROM pending WHERE id=?", (pid,))
                conn.commit()
            bot.send_message(uid, "✅ Файлыңыз қабылданды! +12💸 бонус берілді.")
        bot.edit_message_caption("✅ Мақұлданды", ADMIN_ID, call.message.message_id)
    conn.close()

# ==========================================
# DAILY BONUS
# ==========================================
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
        new_balance = (user_data[1] if user_data else 0) + 10
        conn.execute("UPDATE users SET balance = ?, last_daily = ? WHERE user_id=?", (new_balance, now.isoformat(), user_id))
        conn.commit()
    bot.send_message(user_id, f"🎉 +10💸 бонус берілді!\n💰 Жаңа баланс: {new_balance}💸")
    conn.close()

# ==========================================
# ADMIN BONUS PROCESS
# ==========================================
def process_bonus(message):
    try:
        data = message.text.split()
        target_id, amount = int(data[0]), int(data[1])
        conn = get_db_connection()
        with db_lock:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_id))
            conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ {amount}💸 бонус {target_id} ID пайдаланушыға сәтті берілді!")
        try:
            bot.send_message(target_id, f"🎁 Сізге админ {amount}💸 бонус берді!")
        except: pass
    except Exception:
        bot.send_message(ADMIN_ID, "❌ Қате. Формат: ID сома (мысалы: 123456789 100)")

# ==========================================
# MAIN MENU HANDLER
# ==========================================
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    user_id = message.from_user.id
    text = message.text
    conn = get_db_connection()
    user_data = conn.execute("SELECT is_adult, balance, progress_video, progress_photo FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user_data or user_data[0] == 0:
        conn.close()
        return

    balance, vid_prog, pic_prog = user_data[1], user_data[2], user_data[3]

    # --- Видео көру ---
    if text == "🎥 Видео көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif balance < 2:
            bot.send_message(user_id, get_ref_msg(user_id), parse_mode="Markdown")
        else:
            vid = conn.execute("SELECT file_id FROM videos ORDER BY id ASC LIMIT 1 OFFSET ?", (vid_prog,)).fetchone()
            if vid:
                new_balance = balance - 2
                bot.send_video(user_id, vid[0], caption=f"🎬 Видео қарадыңыз!\n💰 Баланс: {new_balance}💸\n📊 Прогресс: {vid_prog+1}/∞")
                with db_lock:
                    conn.execute("UPDATE users SET balance=?, progress_video=progress_video+1 WHERE user_id=?", (new_balance, user_id))
                    conn.commit()
            else:
                bot.send_message(user_id, "😔 Видеолар таусылды.")

    # --- Фото көру ---
    elif text == "🖼 Фото көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif balance < 3:
            bot.send_message(user_id, get_ref_msg(user_id), parse_mode="Markdown")
        else:
            pic = conn.execute("SELECT file_id FROM photos ORDER BY id ASC LIMIT 1 OFFSET ?", (pic_prog,)).fetchone()
            if pic:
                new_balance = balance - 3
                bot.send_photo(user_id, pic[0], caption=f"🖼 Фото қарадыңыз!\n💰 Баланс: {new_balance}💸\n📊 Прогресс: {pic_prog+1}/∞")
                with db_lock:
                    conn.execute("UPDATE users SET balance=?, progress_photo=progress_photo+1 WHERE user_id=?", (new_balance, user_id))
                    conn.commit()
            else:
                bot.send_message(user_id, "😔 Фотолар таусылды.")

    # --- Видео/Фото жіберу ---
    elif text == "➕ Видео/Фото жіберу":
        bot.send_message(user_id, "📩 Файл жіберіңіз (Фото немесе Видео), модерациядан кейін бонус беріледі.")

    # --- Админ: бонус беру ---
    elif text == "💰 Бонус беру" and user_id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "⚡️ Бонус беру форматы: `ID сома` (Мысалы: `123456789 100)`", parse_mode="Markdown")
        bot.register_next_step_handler(message, process_bonus)

    # --- Админ: pending файлдар ---
    elif text == "✅ Pending файлдар" and user_id == ADMIN_ID:
        p = conn.execute("SELECT id, uploader_id, content_type, file_id FROM pending LIMIT 1").fetchone()
        if p:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Мақұлдау", callback_data=f"appr_{p[0]}"))
            if p[2] == 'video':
                bot.send_video(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
            else:
                bot.send_photo(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
        else:
            bot.send_message(ADMIN_ID, "Тізім бос.")

    # --- Админ: статистика ---
    elif text == "📊 Статистика" and user_id == ADMIN_ID:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(ADMIN_ID, f"👥 Пайдаланушылар: {count}")

    conn.close()

# ==========================================
# UPLOAD HANDLER
# ==========================================
@bot.message_handler(content_types=['photo', 'video'])
def handle_uploads(message):
    user_id = message.from_user.id
    is_video = message.content_type == 'video'
    file_id = message.video.file_id if is_video else message.photo[-1].file_id
    conn = get_db_connection()
    with db_lock:
        conn.execute("INSERT INTO pending (uploader_id, content_type, file_id, created_at) VALUES (?,?,?,?)",
                     (user_id, 'video' if is_video else 'photo', file_id, datetime.now().isoformat()))
        conn.commit()
    conn.close()
    bot.send_message(user_id, "📩 Файл модерацияға жіберілді. Қабылданса бонус беріледі.")

# ==========================================
# RUN BOT
# ==========================================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
