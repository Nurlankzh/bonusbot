import os


# ============================================================
# TELEGRAM CONSTRUCTOR BOT
# ============================================================

# Конструктордың негізгі Telegram Bot токені
#
# МЫНА ЖЕРГЕ ТЕК ЖАҢА ТОКЕН ҚОЙ:
# BOT_TOKEN = "1234567890:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
#
# Бұрын жарияланған токенді қолданба.
BOT_TOKEN = "8729117024:AAH68IJU9QZ5yAMaAazYzQfWRvCyf_cH1KA"


# ============================================================
# ADMIN
# ============================================================

# Конструкторды басқаратын Telegram аккаунтының ID-і
ADMIN_ID = 6303091468


# ============================================================
# PATHS
# ============================================================

# Child bot-тардың жұмыс папкасы
WORKSPACE_DIR = "/app/workspaces"


# SQLite database
DATABASE_PATH = "/app/data/database.db"


# ============================================================
# BOT SETTINGS
# ============================================================

# Child bot іске қосылғанда Python
PYTHON_EXECUTABLE = os.getenv(
    "PYTHON_EXECUTABLE",
    "python"
)


# Child bot process timeout
PROCESS_STOP_TIMEOUT = 10


# ============================================================
# LOG SETTINGS
# ============================================================

# Бір бот үшін сақталатын соңғы лог саны
MAX_LOGS = 1000


# ============================================================
# CODE SETTINGS
# ============================================================

# Бір код нұсқасының максималды көлемі
# Файл арқылы келген үлкен Python кодтарына арналған.
MAX_CODE_SIZE = 10 * 1024 * 1024


# ============================================================
# SECURITY
# ============================================================

# Child bot токені конструктор токенімен бірдей болмауы керек
REJECT_MASTER_TOKEN_AS_CHILD = True


# ============================================================
# ENVIRONMENT
# ============================================================

# Railway Variables болса, оларды пайдалануға мүмкіндік береді.
# Бірақ негізгі BOT_TOKEN жоғарыдағы мәннен алынады.

USE_RAILWAY_ENV = False


# Егер кейін Railway Variables-ке қайтарғың келсе:
if USE_RAILWAY_ENV:

    railway_token = os.getenv(
        "BOT_TOKEN",
        ""
    ).strip()

    if railway_token:
        BOT_TOKEN = railway_token


# ============================================================
# VALIDATION
# ============================================================

BOT_TOKEN = BOT_TOKEN.strip()


if not BOT_TOKEN:

    raise RuntimeError(
        "BOT_TOKEN config.py ішінде көрсетілмеген."
    )


if ":" not in BOT_TOKEN:

    raise RuntimeError(
        "BOT_TOKEN форматы дұрыс емес."
    )


if not isinstance(ADMIN_ID, int):

    raise RuntimeError(
        "ADMIN_ID сан болуы керек."
    )


if not WORKSPACE_DIR:

    raise RuntimeError(
        "WORKSPACE_DIR бос болмауы керек."
    )


if not DATABASE_PATH:

    raise RuntimeError(
        "DATABASE_PATH бос болмауы керек."
    )


# ============================================================
# STARTUP INFO
# ============================================================

print(
    "✅ config.py жүктелді"
)

print(
    f"📁 WORKSPACE_DIR: {WORKSPACE_DIR}"
)

print(
    f"💾 DATABASE_PATH: {DATABASE_PATH}"
)

print(
    f"👤 ADMIN_ID: {ADMIN_ID}"
)

print(
    "🔐 BOT_TOKEN: орнатылған"
)
