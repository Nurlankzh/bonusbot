import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_MASTER_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_NAME = "bot_builder_pro.db"
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080")) # GitHub webhooks үшін
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKERS_DIR = os.path.join(BASE_DIR, "workers") # Боттар осында оқшауланып сақталады
