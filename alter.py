import sqlite3

# bot.db файлын ашамыз (сол папкада тұрғанына көз жеткіз)
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

# last_video_id бағанын қосамыз
try:
    cur.execute("ALTER TABLE users ADD COLUMN last_video_id INTEGER DEFAULT 0")
    print("✅ last_video_id бағаны қосылды!")
except Exception as e:
    print("ℹ️ last_video_id бағаны бұрыннан бар сияқты немесе қате:", e)

# last_photo_id бағанын қосамыз
try:
    cur.execute("ALTER TABLE users ADD COLUMN last_photo_id INTEGER DEFAULT 0")
    print("✅ last_photo_id бағаны қосылды!")
except Exception as e:
    print("ℹ️ last_photo_id бағаны бұрыннан бар сияқты немесе қате:", e)

# Өзгерістерді сақтаймыз
conn.commit()
conn.close()

print("✅ Барлық бағандар тексерілді/қосылды!")
