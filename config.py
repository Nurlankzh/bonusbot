import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_NEW_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6303091468"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "builder.db")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "workspaces")

CHILD_TIMEOUT = int(os.getenv("CHILD_TIMEOUT", "30"))
MAX_CODE_SIZE = int(os.getenv("MAX_CODE_SIZE", "500000"))
LOG_LIMIT = int(os.getenv("LOG_LIMIT", "100"))

os.makedirs(WORKSPACE_DIR, exist_ok=True)
