import aiosqlite
import os
from datetime import datetime
import config

DB_PATH = config.DATABASE_PATH


def now():
    return datetime.utcnow().isoformat()


async def init_db():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            bot_token TEXT NOT NULL,
            status TEXT DEFAULT 'stopped',
            auto_restart INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS code_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            code TEXT NOT NULL,
            diff TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS env_vars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(bot_id, key),
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_bot
        ON code_versions(bot_id, version)
        """)

        await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_bot
        ON logs(bot_id, id)
        """)

        await db.commit()


async def add_bot(owner_id, name, token):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        INSERT INTO bots
        (owner_id, name, bot_token, status, auto_restart, created_at, updated_at)
        VALUES (?, ?, ?, 'stopped', 1, ?, ?)
        """, (owner_id, name, token, now(), now()))

        bot_id = cur.lastrowid

        await db.execute("""
        INSERT OR REPLACE INTO env_vars(bot_id, key, value)
        VALUES (?, 'BOT_TOKEN', ?)
        """, (bot_id, token))

        await db.commit()
        return bot_id


async def get_user_bots(owner_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT id, name AS bot_id_name, status, auto_restart
        FROM bots
        WHERE owner_id=?
        ORDER BY id DESC
        """, (owner_id,))

        return await cur.fetchall()


async def get_bot(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT *
        FROM bots
        WHERE id=?
        """, (bot_id,))

        return await cur.fetchone()


async def update_bot_status(bot_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE bots
        SET status=?, updated_at=?
        WHERE id=?
        """, (status, now(), bot_id))

        await db.commit()


async def set_auto_restart(bot_id, enabled):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE bots
        SET auto_restart=?, updated_at=?
        WHERE id=?
        """, (1 if enabled else 0, now(), bot_id))

        await db.commit()


async def get_latest_code(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT *
        FROM code_versions
        WHERE bot_id=?
        ORDER BY version DESC
        LIMIT 1
        """, (bot_id,))

        return await cur.fetchone()


async def get_code_versions(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT id, version, created_at
        FROM code_versions
        WHERE bot_id=?
        ORDER BY version DESC
        """, (bot_id,))

        return await cur.fetchall()


async def get_code_by_version(bot_id, version):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT *
        FROM code_versions
        WHERE bot_id=? AND version=?
        LIMIT 1
        """, (bot_id, version))

        return await cur.fetchone()


async def save_code_version(bot_id, code):
    previous = await get_latest_code(bot_id)

    version = 1 if not previous else previous["version"] + 1

    old_code = previous["code"] if previous else ""

    diff = make_diff(old_code, code)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO code_versions
        (bot_id, version, code, diff, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (bot_id, version, code, diff, now()))

        await db.execute("""
        UPDATE bots
        SET updated_at=?
        WHERE id=?
        """, (now(), bot_id))

        await db.commit()

    return version, diff


def make_diff(old, new):
    import difflib

    return "".join(
        difflib.unified_diff(
            old.splitlines(True),
            new.splitlines(True),
            fromfile="old",
            tofile="new"
        )
    )


async def get_env_vars(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT key, value
        FROM env_vars
        WHERE bot_id=?
        ORDER BY key
        """, (bot_id,))

        rows = await cur.fetchall()

        return {row["key"]: row["value"] for row in rows}


async def set_env_var(bot_id, key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO env_vars(bot_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(bot_id, key)
        DO UPDATE SET value=excluded.value
        """, (bot_id, key, value))

        await db.commit()


async def delete_env_var(bot_id, key):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        DELETE FROM env_vars
        WHERE bot_id=? AND key=?
        """, (bot_id, key))

        await db.commit()


async def add_log(bot_id, level, message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO logs(bot_id, level, message, created_at)
        VALUES (?, ?, ?, ?)
        """, (bot_id, level, message, now()))

        await db.commit()


async def get_logs(bot_id, limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT level, message, created_at
        FROM logs
        WHERE bot_id=?
        ORDER BY id DESC
        LIMIT ?
        """, (bot_id, limit))

        return await cur.fetchall()
