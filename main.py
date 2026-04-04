import os
import logging
import sqlite3
import threading
import time
from datetime import datetime
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

# Логтарды консольден көру үшін
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ==========================================
# INITIALIZATION
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)
db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            added_by INTEGER,
            created_at TEXT
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            added_by INTEGER,
            created_at TEXT
        )""")
        conn.commit()
    conn.close()
    logger.info("Database initialized.")

init_db()

# ==========================================
# KEYBOARDS
# ==========================================
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎥 Видео көру"), KeyboardButton("🖼 Фото көру"))
    kb.row(KeyboardButton("➕ Видео/Фото жіберу"), KeyboardButton("💸 Мой бонус"))
    kb.row(KeyboardButton("🔗 Реферал сілтеме"), KeyboardButton("🎁 Күндік бонус алу"))  
    kb.row(KeyboardButton("ℹ️ Ақпарат"))

    if user_id == ADMIN_ID:  
        kb.row(KeyboardButton("✅ Pending файлдар"), KeyboardButton("📊 Статистика"))  
        kb.row(KeyboardButton("📢 Рассылка"))  
    return kb

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def ensure_user(user_id, invited_by=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    with db_lock:
        user = cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            now = datetime.utcnow().isoformat()
            cursor.execute("INSERT INTO users (user_id, balance, invited_by, joined_at) VALUES (?, ?, ?, ?)",
                           (user_id, 3, invited_by, now))
            conn.commit()
            if invited_by and invited_by != user_id:
                cursor.execute("UPDATE users SET balance = balance + 6 WHERE user_id=?", (invited_by,))
                conn.commit()
                try:
                    bot.send_message(invited_by, "🎊 Сіздің сілтемеңізбен жаңа қолданушы тіркелді! +6💸 бонус.")
                except: pass
    conn.close()

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# ==========================================
# HANDLERS
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
    
    bot.send_message(user_id, "👋 Сәлем! Ботқа қош келдіңіз.\nБұл бот тек 18 жастан асқандарға арналған.", reply_markup=markup)

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
        bot.send_message(user_id, "✅ Кіру рұқсат етілді!", reply_markup=get_main_keyboard(user_id))
    
    elif call.data.startswith("appr_"):
        pid = call.data.split("_")[1]
        conn = get_db_connection()
        p = conn.execute("SELECT uploader_id, content_type, file_id FROM pending WHERE id=?", (pid,)).fetchone()
        if p:
            uid, ctype, fid = p
            table = "videos" if ctype == "video" else "photos"
            with db_lock:
                conn.execute(f"INSERT INTO {table} (file_id, added_by, created_at) VALUES (?,?,?)", (fid, uid, datetime.utcnow().isoformat()))
                conn.execute("UPDATE users SET balance = balance + 12 WHERE user_id=?", (uid,))
                conn.execute("DELETE FROM pending WHERE id=?", (pid,))
                conn.commit()
            bot.send_message(uid, "✅ Файлыңыз қабылданды! +12💸")
        conn.close()
        bot.edit_message_caption("✅ Мақұлданды", ADMIN_ID, call.message.message_id)

@bot.message_handler(content_types=['photo', 'video'])
def media_handler(message):
    user_id = message.from_user.id
    is_video = message.content_type == 'video'
    file_id = message.video.file_id if is_video else message.photo[-1].file_id
    conn = get_db_connection()
    with db_lock:
        conn.execute("INSERT INTO pending (uploader_id, content_type, file_id, created_at) VALUES (?,?,?,?)",
                     (user_id, 'video' if is_video else 'photo', file_id, datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()
    bot.send_message(user_id, "📩 Файл жіберілді, админ тексерісін күтіңіз.")

@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text
    conn = get_db_connection()
    user_data = conn.execute("SELECT is_adult, balance, progress_video, progress_photo FROM users WHERE user_id=?", (user_id,)).fetchone()
    
    if not user_data:
        ensure_user(user_id)
        conn.close()
        return

    if text == "🎥 Видео көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif user_data[1] < 2:
            bot.send_message(user_id, "❌ Баланс жетпейді (2💸 қажет).")
        else:
            vid = conn.execute("SELECT file_id FROM videos ORDER BY id ASC LIMIT 1 OFFSET ?", (user_data[2],)).fetchone()
            if vid:
                bot.send_video(user_id, vid[0])
                with db_lock:
                    conn.execute("UPDATE users SET balance = balance - 2, progress_video = progress_video + 1 WHERE user_id=?", (user_id,))
                    conn.commit()
            else: bot.send_message(user_id, "😔 Видео таусылды.")

    elif text == "🖼 Фото көру":
        if not check_subscription(user_id):
            bot.send_message(user_id, f"⚠️ Каналға тіркеліңіз: {CHANNEL_USERNAME}")
        elif user_data[1] < 3:
            bot.send_message(user_id, "❌ Баланс жетпейді (3💸 қажет).")
        else:
            pic = conn.execute("SELECT file_id FROM photos ORDER BY id ASC LIMIT 1 OFFSET ?", (user_data[3],)).fetchone()
            if pic:
                bot.send_photo(user_id, pic[0])
                with db_lock:
                    conn.execute("UPDATE users SET balance = balance - 3, progress_photo = progress_photo + 1 WHERE user_id=?", (user_id,))
                    conn.commit()
            else: bot.send_message(user_id, "😔 Фото таусылды.")

    elif text == "💸 Мой бонус":
        bot.send_message(user_id, f"💰 Баланс: {user_data[1]}💸")

    elif text == "🔗 Реферал сілтеме":
        bot.send_message(user_id, f"🔗 Сілтеме: https://t.me/{REF_BOT_USERNAME}?start={user_id}")

    elif text == "🎁 Күндік бонус алу":
        now = datetime.utcnow().isoformat()
        with db_lock:
            conn.execute("UPDATE users SET balance = balance + 10 WHERE user_id=?", (user_id,))
            conn.commit()
        bot.send_message(user_id, "🎉 +10💸 бонус берілді!")

    # ADMIN
    if user_id == ADMIN_ID:
        if text == "✅ Pending файлдар":
            p = conn.execute("SELECT id, uploader_id, content_type, file_id FROM pending LIMIT 1").fetchone()
            if p:
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Ок", callback_data=f"appr_{p[0]}"))
                if p[2] == 'video': bot.send_video(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
                else: bot.send_photo(ADMIN_ID, p[3], caption=f"ID: {p[1]}", reply_markup=markup)
            else: bot.send_message(ADMIN_ID, "Тізім бос.")
    
    conn.close()

# ==========================================
# RUN BOT
# ==========================================
if __name__ == "__main__":
    logger.info("Bot is starting (Polling mode)...")
    bot.remove_webhook() # Ескі вебхукты өшіру
    time.sleep(1)
    bot.infinity_polling()
