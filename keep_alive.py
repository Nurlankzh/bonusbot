from flask import Flask
from threading import Thread

# Flask қосымшасын құрамыз
app = Flask('')

# Тірі екенін тексеру үшін қарапайым бет
@app.route('/')
def home():
    return "Bot is alive!"

# Серверді іске қосатын функция
def run():
    app.run(host='0.0.0.0', port=8080)

# Осы функцияны ботқа қосамыз
def keep_alive():
    t = Thread(target=run)
    t.start()
