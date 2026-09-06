import aiosqlite
import config
from datetime import datetime

async def init_db():
    async with aiosqlite.connect(config.DB_NAME) as db:
        # Bots
        await db.execute('''CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, github_repo TEXT, status TEXT DEFAULT 'stopped', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        # Environment Variables
        await db.execute('''CREATE TABLE IF NOT EXISTS env_vars (
            id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER, var_key TEXT, var_value TEXT,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE)''')
        # Code Versions (includes requirements)
        await db.execute('''CREATE TABLE IF NOT EXISTS code_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER, version INTEGER, main_code TEXT, reqs_code TEXT, diff_text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE)''')
        # Deployments
        await db.execute('''CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER, version INTEGER, status TEXT, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ended_at TIMESTAMP,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE)''')
        # Logs
        await db.execute('''CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER, level TEXT, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await db.commit()

# --- Helpers ---
async def get_bot(bot_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)) as cursor:
            return dict(await cursor.fetchone())

async def get_bot_vars(bot_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        async with db.execute("SELECT var_key, var_value FROM env_vars WHERE bot_id = ?", (bot_id,)) as cursor:
            return {row[0]: row[1] for row in await cursor.fetchall()}

async def create_deployment(bot_id: int, version: int) -> int:
    async with aiosqlite.connect(config.DB_NAME) as db:
        cursor = await db.execute("INSERT INTO deployments (bot_id, version, status) VALUES (?, ?, 'PENDING')", (bot_id, version))
        await db.commit()
        return cursor.lastrowid

async def update_deployment_status(dep_id: int, status: str):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute("UPDATE deployments SET status = ?, ended_at = CURRENT_TIMESTAMP WHERE id = ?", (status, dep_id))
        await db.commit()

async def log_event(bot_id: int, level: str, message: str):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute("INSERT INTO logs (bot_id, level, message) VALUES (?, ?, ?)", (bot_id, level, message))
        await db.commit()
