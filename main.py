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
BOT_TOKEN = "7748542247:AAGbtxMx-1F_08Xc2MKJW0nDIsv6vVvOlRo" # Сіз берген токен
ADMIN_ID = 6303091468
CHANNEL_USERNAME = "@uyatsizoqiga" # Канал сілтемесін тексеріңіз
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
        kb.row(KeyboardButton("🏆 Топ 10 шақырғандар"), KeyboardButton("📢 Рассылка"))  
        kb.row(KeyboardButton("💰 Бонус беру"))  
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
    markup.add(
        InlineKeyboardButton("✅ Ия, 18-ден астым", callback_data="confirm_adult"),  
        InlineKeyboardButton("❌ Жоқ", callback_data="decline_adult")
    )  
  
    welcome_text = (
        "👋 Сәлем! Ботқа қош келдіңіз!\n\n"
        "Бұл ботта сіз:\n"
        "- 🎥 Видео көре аласыз\n"
        "- 🖼 Фото көруге болады\n"
        "- Достарыңызды шақырып бонус жинай аласыз\n"
        "- 🎁 Күн сайын тегін бонус ала аласыз\n\n"
        "✋ Бірақ, қолданбас бұрын сіздің жасыңыз 18-ден асқан болуы қажет. Растайсыз ба?"
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
                try: bot.send_message(uid, "✅ Сіз жіберген файл мақұлданды. +12💸 бонус берілді.")  
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
    bot.send_message(user_id, "📩 Файл модерацияға жіберілді. Админ тексерген соң бонус аласыз.")

@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text
    conn = get_db_connection()
    cursor = conn.cursor()

    user_data = cursor.execute("SELECT is_adult, balance, progress_video, progress_photo FROM users WHERE user_id=?", (user_id,)).fetchone()  
    
    if not user_data:
        ensure_user(user_id)
        bot.send_message(user_id, "⚠️ Ботты бастау үшін /start басыңыз.")
        conn.close()
        return

    if user_data[0] == 0:  
        bot.send_message(user_id, "⚠️ Алдымен /start басып, жасыңызды растаңыз.")  
        conn.close()
        return  

    if text == "🎥 Видео көру":  
        if not check_subscription(user_id):  
            bot.send_message(user_id, f"⚠️ Видео көру үшін алдымен каналымызға тіркеліңіз: {CHANNEL_USERNAME}")  
        else:
            balance, progress = user_data[1], user_data[2]  
            if balance < 2 and user_id != ADMIN_ID:  
                bot.send_message(user_id, "❌ Кешіріңіз, видео көру үшін кемі 2💸 бонус керек.")  
            else:
                videos = cursor.execute("SELECT file_id FROM videos ORDER BY id ASC").fetchall()  
                if not videos:  
                    bot.send_message(user_id, "😔 Әзірге видеолар жоқ.")  
                else:
                    idx = progress if progress < len(videos) else 0  
                    vid_id = videos[idx][0]  
                    try:  
                        bot.send_video(user_id, vid_id)  
                        with db_lock:  
                            new_bal = balance if user_id == ADMIN_ID else balance - 2  
                            cursor.execute("UPDATE users SET balance=?, progress_video=? WHERE user_id=?", (new_bal, idx+1, user_id))  
                            conn.commit()  
                    except:  
                        bot.send_message(user_id, "❌ Файл жіберуде қате шықты.")  

    elif text == "🖼 Фото көру":  
        if not check_subscription(user_id):  
            bot.send_message(user_id, f"⚠️ Фото көру үшін алдымен каналымызға тіркеліңіз: {CHANNEL_USERNAME}")  
        else:
            balance, progress = user_data[1], user_data[3]  
            if balance < 3 and user_id != ADMIN_ID:  
                bot.send_message(user_id, "❌ Фото көру үшін кемі 3💸 бонус керек.")  
            else:
                photos = cursor.execute("SELECT file_id FROM photos ORDER BY id ASC").fetchall()  
                if not photos:  
                    bot.send_message(user_id, "😔 Әзірге фотолар жоқ.")  
                else:
                    idx = progress if progress < len(photos) else 0  
                    photo_id = photos[idx][0]  
                    try:  
                        bot.send_photo(user_id, photo_id)  
                        with db_lock:  
                            new_bal = balance if user_id == ADMIN_ID else balance - 3  
                            cursor.execute("UPDATE users SET balance=?, progress_photo=? WHERE user_id=?", (new_bal, idx+1, user_id))  
                            conn.commit()  
                    except:  
                        bot.send_message(user_id, "❌ Файл жіберуде қате шықты.")  

    elif text == "💸 Мой бонус":  
        bot.send_message(user_id, f"💰 Сіздің балансыңыз: {user_data[1]}💸")  

    elif text == "🔗 Реферал сілтеме":  
        ref_link = f"https://t.me/{REF_BOT_USERNAME}?start={user_id}"  
        bot.send_message(user_id, f"🎁 Достарыңызды шақырып, бонус алыңыз!\n\nӘр дос үшін: +6💸\nСілтемеңіз: {ref_link}")  

    elif text == "ℹ️ Ақпарат":  
        info_text = (  
            "📖 **Бот ережесі:**\n\n"  
            "- 1 видео көру = 2💸 бонус\n"  
            "- 1 фото көру = 3💸 бонус\n"  
            "- Дос шақыру = 6💸 бонус\n"  
            "- Видео/Фото жіберу = 12💸 бонус (мақұлданса)\n"  
            "- Барлық файлдар 18+ форматында."  
        )  
        bot.send_message(user_id, info_text, parse_mode="Markdown")  

    elif text == "🎁 Күндік бонус алу":
        now = datetime.utcnow()
        last_claim = cursor.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)).fetchone()
        if last_claim and last_claim[0]:
            last_time = datetime.fromisoformat(last_claim[0])
            if (now - last_time).total_seconds() < 86400:
                bot.send_message(user_id, "⚠️ Күндік бонус 24 сағатта 1 рет беріледі.")
                conn.close()
                return
        with db_lock:
            cursor.execute("UPDATE users SET balance = balance + 10, last_daily=? WHERE user_id=?", (now.isoformat(), user_id))
            conn.commit()
        bot.send_message(user_id, "🎉 Сіз күнделікті 10💸 бонус алдыңыз!")

    elif text == "➕ Видео/Фото жіберу":
        bot.send_message(user_id, "📸 Маған видео немесе фото жіберіңіз. Админ тексерген соң +12💸 бонус аласыз.")

    # --- ADMIN ---
    if user_id == ADMIN_ID:  
        if text == "✅ Pending файлдар":  
            pendings = cursor.execute("SELECT id, uploader_id, content_type, file_id FROM pending LIMIT 10").fetchall()  
            if not pendings:  
                bot.send_message(ADMIN_ID, "📭 Күтудегі файлдар жоқ.")  
            else:
                for pid, uid, ctype, fid in pendings:  
                    markup = InlineKeyboardMarkup()  
                    markup.add(InlineKeyboardButton("✅ Мақұлдау", callback_data=f"appr_{pid}"),  
                               InlineKeyboardButton("❌ Бас тарту", callback_data=f"rejc_{pid}"))  
                    try:
                        if ctype == 'video':  
                            bot.send_video(ADMIN_ID, fid, caption=f"Жіберуші: {uid}", reply_markup=markup)  
                        else:  
                            bot.send_photo(ADMIN_ID, fid, caption=f"Жіберуші: {uid}", reply_markup=markup)
                    except: pass

        elif text == "📊 Статистика":  
            total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]  
            total_vids = cursor.execute("SELECT COUNT(*) FROM videos").fetchone()[0]  
            total_photos = cursor.execute("SELECT COUNT(*) FROM photos").fetchone()[0]  
            bot.send_message(ADMIN_ID, f"📊 **Бот статистикасы:**\n\n👥 Юзерлер: {total_users}\n🎥 Видеолар: {total_vids}\n🖼 Фотолар: {total_photos}", parse_mode="Markdown")  

        elif text == "🏆 Топ 10 шақырғандар":  
            top_referrals = cursor.execute("SELECT invited_by, COUNT(*) as count FROM users WHERE invited_by IS NOT NULL GROUP BY invited_by ORDER BY count DESC LIMIT 10").fetchall()  
            report = "🏆 **Топ 10 шақырғандар:**\n\n"  
            for i, (uid, count) in enumerate(top_referrals, 1):  
                report += f"{i}. ID: `{uid}` — {count} адам\n"  
            bot.send_message(ADMIN_ID, report, parse_mode="Markdown")  

        elif text == "📢 Рассылка":  
            bot.send_message(ADMIN_ID, "Жарнама мәтінін жазыңыз:")  
            bot.register_next_step_handler(message, run_broadcast)  

        elif text == "💰 Бонус беру":  
            bot.send_message(ADMIN_ID, "Формат: `ID сома` (мысалы: 6303091468 50)")  
            bot.register_next_step_handler(message, give_bonus)

    conn.close()

# ==========================================
# ADMIN SUB-FUNCTIONS
# ==========================================
def give_bonus(message):
    try:
        uid, amount = map(int, message.text.split())
        conn = get_db_connection()
        with db_lock:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
            conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ {uid}-ге {amount} бонус берілді.")
        bot.send_message(uid, f"🎁 Админ сізге {amount}💸 бонус берді!")
    except:
        bot.send_message(ADMIN_ID, "❌ Қате! Формат дұрыс емес.")

def run_broadcast(message):
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    count = 0
    for (uid,) in users:
        try:
            bot.send_message(uid, message.text)
            count += 1
            time.sleep(0.05)
        except: continue
    bot.send_message(ADMIN_ID, f"📢 Жіберілді: {count} адамға.")

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
    else:
        return 'Forbidden', 403

@app.route("/")
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=PORT)
