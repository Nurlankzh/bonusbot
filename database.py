import aiosqlite
import difflib
import json
from datetime import datetime

DB_NAME = "bot_builder.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Боттар кестесі
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_id_name TEXT NOT NULL,
                status TEXT DEFAULT 'stopped',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Код нұсқалары (Version Control)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS code_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_db_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                code TEXT NOT NULL,
                diff_changes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_db_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        # Айнымалылар (Environment Variables)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS env_vars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_db_id INTEGER NOT NULL,
                var_key TEXT NOT NULL,
                var_value TEXT NOT NULL,
                FOREIGN KEY (bot_db_id) REFERENCES bots (id) ON DELETE CASCADE,
                UNIQUE(bot_db_id, var_key)
            )
        ''')
        # Логтар мен қателер
        await db.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_db_id INTEGER NOT NULL,
                log_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_db_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        ''')
        await db.commit()

async def add_bot(user_id: int, bot_id_name: str, token: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO bots (user_id, bot_id_name) VALUES (?, ?)", (user_id, bot_id_name))
        bot_id = cursor.lastrowid
        await db.execute("INSERT INTO env_vars (bot_db_id, var_key, var_value) VALUES (?, ?, ?)", (bot_id, "BOT_TOKEN", token))
        await db.commit()
        return bot_id

async def get_user_bots(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_bot(bot_db_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bots WHERE id = ?", (bot_db_id,)) as cursor:
            return await cursor.fetchone()

async def save_code_version(bot_db_id: int, new_code: str) -> tuple[int, str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT version, code FROM code_versions WHERE bot_db_id = ? ORDER BY version DESC LIMIT 1", (bot_db_id,)) as cursor:
            last_ver = await cursor.fetchone()

        if last_ver:
            next_version = last_ver["version"] + 1
            old_code = last_ver["code"].splitlines()
            new_code_lines = new_code.splitlines()
            diff = list(difflib.unified_diff(old_code, new_code_lines, fromfile=f'v{last_ver["version"]}', tofile=f'v{next_version}', lineterm=''))
            diff_text = "\n".join(diff) if diff else "Өзгерістер жоқ"
        else:
            next_version = 1
            diff_text = "Бастапқы нұсқа (v1)"

        await db.execute("INSERT INTO code_versions (bot_db_id, version, code, diff_changes) VALUES (?, ?, ?, ?)", (bot_db_id, next_version, new_code, diff_text))
        await db.commit()
        return next_version, diff_text

async def get_latest_code(bot_db_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM code_versions WHERE bot_db_id = ? ORDER BY version DESC LIMIT 1", (bot_db_id,)) as cursor:
            return await cursor.fetchone()

async def get_code_by_version(bot_db_id: int, version: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM code_versions WHERE bot_db_id = ? AND version = ?", (bot_db_id, version)) as cursor:
            return await cursor.fetchone()

async def get_env_vars(bot_db_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT var_key, var_value FROM env_vars WHERE bot_db_id = ?", (bot_db_id,)) as cursor:
            return dict(await cursor.fetchall())

async def set_env_var(bot_db_id: int, key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO env_vars (bot_db_id, var_key, var_value) VALUES (?, ?, ?) ON CONFLICT(bot_db_id, var_key) DO UPDATE SET var_value=excluded.var_value", (bot_db_id, key, value))
        await db.commit()

async def update_bot_status(bot_db_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE bots SET status = ? WHERE id = ?", (status, bot_db_id))
        await db.commit()

async def add_log(bot_db_id: int, log_type: str, message: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO logs (bot_db_id, log_type, message) VALUES (?, ?, ?)", (bot_db_id, log_type, message))
        await db.commit()
