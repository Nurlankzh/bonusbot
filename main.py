import os
import logging
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, request
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# CONFIGURATION
# ==========================================
# Токенді тексеріңіз, соңында бос орын қалмауы керек
BOT_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo"
ADMIN_ID = 6303091468
CHANNEL_USERNAME = "@uyatsizoqiga"
# СІЛТЕМЕ СОҢЫНДА / БОЛМАУЫ ТИІС
WEBHOOK_URL = "https://web-production-0cd8e.up.railway.app"
DB_FILE = "data.db"
PORT = int(os.environ.get("PORT", 10000)) 

REF_BOT_USERNAME = "adeptiemesbot"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ==========================================
# INITIALIZATION
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
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

init_db()

# ==========================================
# KEYBOARDS
# ==========================================
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎥 Видео көру"), KeyboardButton("🖼 Фото көру"))
    kb.row(KeyboardButton("➕ Видео/Фото жіберу"), KeyboardButton("💸 Мой бонус"))
    kb.row(KeyboardButton("🔗 Реферал сілтеме"), KeyboardButton("ℹ️ Ақпарат"))
    kb.row(KeyboardButton("🎁 Күндік бонус алу"))  

    if user_id == ADMIN_ID:  
        kb.row(KeyboardButton("✅ Pending файлдар"), KeyboardButton("📊 Статистика"))  
        kb.row(KeyboardButton("📢 Рассылка"))  
    return kb

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def ensure_user(user_id, invited_by=None):
    try:
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
    except Exception as e:
        logger.error(f"Database error in ensure_user: {e}")

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

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
    markup.add(
        InlineKeyboardButton("✅ Ия, 18-ден астым", callback_data="confirm_adult"),  
        InlineKeyboardButton("❌ Жоқ", callback_data="decline_adult")
    )  
  
    welcome_text = (
        "👋 Сәлем! Ботқа қош келдіңіз!\n\n"
        "Бұл ботта сіз 18+ контент көре аласыз.\n"
        "✋ Қолданбас бұрын жасыңызды растаңыз:"
    )
    bot.send_message(user_id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_manager(call):
    user_id = call.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()

    if call.data == "confirm_adult":  
        with db_lock:  
            cursor.execute("UPDATE users SET is_adult=1 WHERE user_id=?", (user_id,))  
            conn.commit()  
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "✅ Рақмет! Енді боттың барлық мүмкіндігі ашық.", reply_markup=get_main_keyboard(user_id))  

    elif call.data == "decline_adult":  
        bot.answer_callback_query(call.id, "Кешіріңіз, бұл бот тек ересектерге арналған.", show_alert=True)  

    elif call.data.startswith("appr_"):  
        pid = call.data.split("_")[1]  
        with db_lock:  
            p = cursor.execute("SELECT uploader_id, content_type, file_id FROM pending WHERE id=?", (pid,)).fetchone()  
            if p:  
                uid, ctype, fid = p  
                table = "videos" if ctype == "video" else "photos"  
                cursor.execute(f"INSERT INTO {table} (file_id, added_by, created_at) VALUES (?,?,?)",   
                               (fid, uid, datetime.utcnow().isoformat()))  
                cursor.execute("UPDATE users SET balance = balance + 12 WHERE user_id=?", (uid,))  
                cursor.execute("DELETE FROM pending WHERE id=?", (pid,))  
                conn.commit()  
                try: bot.send_message(uid, "✅ Сіздің файлыңыз мақұлданды! +12💸 бонус.")  
                except: pass  
        bot.edit_message_caption("✅ Мақұлданды", chat_id=ADMIN_ID, message_id=call.message.message_id)  

    elif call.data.startswith("rejc_"):  
        pid = call.data.split("_")[1]  
        with db_lock:  
            cursor.execute("DELETE FROM pending WHERE id=?", (pid,))  
            conn.commit()  
        bot.edit_message_caption("❌ Бас тартылды", chat_id=ADMIN_ID, message_id=call.message.message_id)  
  
    conn.close()

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
    bot.send_message(user_id, "📩 Файл модерацияға жіберілді.")

@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text
    conn = get_db_connection()
    cursor = conn.cursor()

    user_data = cursor.execute("SELECT is_adult, balance, progress_video, progress_photo FROM users WHERE user_id=?", (user_id,)).fetchone()  
    
    if not user_data:
        ensure_user(user_id)
        conn.close()
        return

    if user_data[0] == 0:  
        bot.send_message(user_id, "⚠️ Алдымен /start басып, жасыңызды растаңыз.")  
        conn.close()
        return  

    if text == "🎥 Видео көру":  
        if not check_subscription(user_id):  
            bot.send_message(user_id, f"⚠️ Видео көру үшін каналымызға тіркеліңіз: {CHANNEL_USERNAME}")  
        else:
            balance, progress = user_data[1], user_data[2]  
            if balance < 2 and user_id != ADMIN_ID:  
                bot.send_message(user_id, "❌ Бонус жеткіліксіз (2💸 қажет).")  
            else:
                videos = cursor.execute("SELECT file_id FROM videos ORDER BY id ASC").fetchall()  
                if not videos:  
                    bot.send_message(user_id, "😔 Видеолар әлі жоқ.")  
                else:
                    idx = progress if progress < len(videos) else 0  
                    vid_id = videos[idx][0]  
                    try:  
                        bot.send_video(user_id, vid_id)  
                        with db_lock:  
                            new_bal = balance if user_id == ADMIN_ID else balance - 2  
                            cursor.execute("UPDATE users SET balance=?, progress_video=? WHERE user_id=?", (new_bal, idx+1, user_id))  
                            conn.commit()  
                    except: bot.send_message(user_id, "❌ Қате шықты.")

    elif text == "🖼 Фото көру":  
        if not check_subscription(user_id):  
            bot.send_message(user_id, f"⚠️ Фото көру үшін каналымызға тіркеліңіз: {CHANNEL_USERNAME}")  
        else:
            balance, progress = user_data[1], user_data[3]  
            if balance < 3 and user_id != ADMIN_ID:  
                bot.send_message(user_id, "❌ Бонус жеткіліксіз (3💸 қажет).")  
            else:
                photos = cursor.execute("SELECT file_id FROM photos ORDER BY id ASC").fetchall()  
                if not photos:  
                    bot.send_message(user_id, "😔 Фотолар әлі жоқ.")  
                else:
                    idx = progress if progress < len(photos) else 0  
                    photo_id = photos[idx][0]  
                    try:  
                        bot.send_photo(user_id, photo_id)  
                        with db_lock:  
                            new_bal = balance if user_id == ADMIN_ID else balance - 3  
                            cursor.execute("UPDATE users SET balance=?, progress_photo=? WHERE user_id=?", (new_bal, idx+1, user_id))  
                            conn.commit()  
                    except: bot.send_message(user_id, "❌ Қате шықты.")

    elif text == "💸 Мой бонус":  
        bot.send_message(user_id, f"💰 Балансыңыз: {user_data[1]}💸")  

    elif text == "🔗 Реферал сілтеме":  
        bot.send_message(user_id, f"🎁 Дос шақырғаныңыз үшін: +6💸\nСілтемеңіз: https://t.me/{REF_BOT_USERNAME}?start={user_id}")  

    elif text == "🎁 Күндік бонус алу":
        now = datetime.utcnow()
        last_claim = cursor.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)).fetchone()
        if last_claim and last_claim[0]:
            last_time = datetime.fromisoformat(last_claim[0])
            if (now - last_time).total_seconds() < 86400:
                bot.send_message(user_id, "⚠️ Келесі бонусты 24 сағаттан кейін ала аласыз.")
                conn.close()
                return
        with db_lock:
            cursor.execute("UPDATE users SET balance = balance + 10, last_daily=? WHERE user_id=?", (now.isoformat(), user_id))
            conn.commit()
        bot.send_message(user_id, "🎉 Сізге 10💸 бонус берілді!")

    elif text == "➕ Видео/Фото жіберу":
        bot.send_message(user_id, "📸 Маған видео немесе фото жіберіңіз.")

    # --- ADMIN ---
    if user_id == ADMIN_ID:
        if text == "✅ Pending файлдар":
            pendings = cursor.execute("SELECT id, uploader_id, content_type, file_id FROM pending LIMIT 5").fetchall()
            if not pendings:
                bot.send_message(ADMIN_ID, "📭 Күтудегі файлдар жоқ.")
            for pid, uid, ctype, fid in pendings:
                markup = InlineKeyboardMarkup().add(
                    InlineKeyboardButton("✅ Мақұлдау", callback_data=f"appr_{pid}"),
                    InlineKeyboardButton("❌ Бас тарту", callback_data=f"rejc_{pid}")
                )
                try:
                    if ctype == 'video': bot.send_video(ADMIN_ID, fid, caption=f"ID: {uid}", reply_markup=markup)
                    else: bot.send_photo(ADMIN_ID, fid, caption=f"ID: {uid}", reply_markup=markup)
                except: pass
        elif text == "📊 Статистика":
            u_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            bot.send_message(ADMIN_ID, f"👥 Барлық пайдаланушылар: {u_count}")
        elif text == "📢 Рассылка":
            bot.send_message(ADMIN_ID, "Жарнама мәтінін жазыңыз:")
            bot.register_next_step_handler(message, run_broadcast)

    conn.close()

def run_broadcast(message):
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    for (uid,) in users:
        try:
            bot.send_message(uid, message.text)
            time.sleep(0.05)
        except: continue
    bot.send_message(ADMIN_ID, "✅ Рассылка аяқталды.")

# ==========================================
# WEBHOOK & RUN
# ==========================================
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

@app.route("/")
def index(): return "Bot is running!", 200

if __name__ == "__main__":
    # Webhook орнату
    bot.remove_webhook()
    time.sleep(1)
    # WEBHOOK_URL соңында / болмауы керек
    full_webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    bot.set_webhook(url=full_webhook_url)
    logger.info(f"Webhook set to: {full_webhook_url}")
    app.run(host="0.0.0.0", port=PORT)
