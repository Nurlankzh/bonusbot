import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0").strip())

DATABASE_PATH = os.environ.get("DATABASE_PATH", "builder.db")
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "workspaces")

CHILD_TIMEOUT = int(os.environ.get("CHILD_TIMEOUT", "30"))
MAX_CODE_SIZE = int(os.environ.get("MAX_CODE_SIZE", "500000"))
LOG_LIMIT = int(os.environ.get("LOG_LIMIT", "100"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Railway Variables ішінде жоқ немесе бос!")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID Railway Variables ішінде жоқ немесе бос!")

os.makedirs(WORKSPACE_DIR, exist_ok=True)
