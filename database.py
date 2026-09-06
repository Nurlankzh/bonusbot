import os
import aiosqlite
import config


async def connect():
    db = await aiosqlite.connect(config.DATABASE_PATH, timeout=30)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    return db


async def init_db():
    folder = os.path.dirname(config.DATABASE_PATH)

    if folder:
        os.makedirs(folder, exist_ok=True)

    db = await connect()

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_name TEXT NOT NULL,
                bot_token TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stopped'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS code_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                code TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS env_vars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                var_key TEXT NOT NULL,
                var_value TEXT NOT NULL,
                UNIQUE(bot_id, var_key)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

    finally:
        await db.close()


async def add_bot(user_id, name, token):
    db = await connect()

    try:
        cursor = await db.execute("""
            INSERT INTO bots
            (user_id, bot_name, bot_token, status)
            VALUES (?, ?, ?, 'stopped')
        """, (user_id, name, token))

        await db.commit()

        return cursor.lastrowid

    finally:
        await db.close()


async def get_user_bots(user_id):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM bots
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))

        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        await db.close()


async def get_bot(bot_id):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM bots
            WHERE id = ?
        """, (bot_id,))

        row = await cursor.fetchone()

        return dict(row) if row else None

    finally:
        await db.close()


async def update_bot_status(bot_id, status):
    db = await connect()

    try:
        await db.execute("""
            UPDATE bots
            SET status = ?
            WHERE id = ?
        """, (status, bot_id))

        await db.commit()

    finally:
        await db.close()


async def save_code_version(bot_id, code):
    db = await connect()

    try:
        cursor = await db.execute("""
            SELECT MAX(version)
            FROM code_versions
            WHERE bot_id = ?
        """, (bot_id,))

        row = await cursor.fetchone()

        current = row[0] or 0
        new_version = current + 1

        await db.execute("""
            INSERT INTO code_versions
            (bot_id, version, code)
            VALUES (?, ?, ?)
        """, (bot_id, new_version, code))

        await db.commit()

        return new_version

    finally:
        await db.close()


async def get_latest_code(bot_id):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            ORDER BY version DESC
            LIMIT 1
        """, (bot_id,))

        row = await cursor.fetchone()

        return dict(row) if row else None

    finally:
        await db.close()


async def get_code_versions(bot_id):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            ORDER BY version DESC
        """, (bot_id,))

        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        await db.close()


async def get_code_version(bot_id, version):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            AND version = ?
        """, (bot_id, version))

        row = await cursor.fetchone()

        return dict(row) if row else None

    finally:
        await db.close()


async def get_env_vars(bot_id):
    db = await connect()

    try:
        cursor = await db.execute("""
            SELECT var_key, var_value
            FROM env_vars
            WHERE bot_id = ?
            ORDER BY var_key
        """, (bot_id,))

        rows = await cursor.fetchall()

        return {
            row[0]: row[1]
            for row in rows
        }

    finally:
        await db.close()


async def set_env_var(bot_id, key, value):
    db = await connect()

    try:
        await db.execute("""
            INSERT INTO env_vars
            (bot_id, var_key, var_value)
            VALUES (?, ?, ?)

            ON CONFLICT(bot_id, var_key)
            DO UPDATE SET
                var_value = excluded.var_value
        """, (bot_id, key, value))

        await db.commit()

    finally:
        await db.close()


async def delete_env_var(bot_id, key):
    db = await connect()

    try:
        await db.execute("""
            DELETE FROM env_vars
            WHERE bot_id = ?
            AND var_key = ?
        """, (bot_id, key))

        await db.commit()

    finally:
        await db.close()


async def add_log(bot_id, level, message):
    db = await connect()

    try:
        await db.execute("""
            INSERT INTO logs
            (bot_id, level, message)
            VALUES (?, ?, ?)
        """, (bot_id, level, str(message)))

        await db.commit()

    finally:
        await db.close()


async def get_logs(bot_id, limit=50):
    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT *
            FROM logs
            WHERE bot_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (bot_id, limit))

        rows = await cursor.fetchall()

        result = [dict(row) for row in rows]
        result.reverse()

        return result

    finally:
        await db.close()


async def delete_bot(bot_id):
    db = await connect()

    try:
        await db.execute(
            "DELETE FROM code_versions WHERE bot_id = ?",
            (bot_id,)
        )

        await db.execute(
            "DELETE FROM env_vars WHERE bot_id = ?",
            (bot_id,)
        )

        await db.execute(
            "DELETE FROM logs WHERE bot_id = ?",
            (bot_id,)
        )

        await db.execute(
            "DELETE FROM bots WHERE id = ?",
            (bot_id,)
        )
        async def delete_code_version(bot_id, version):
    db = await connect()
    try:
        cursor = await db.execute(
            """
            DELETE FROM code_versions
            WHERE bot_id = ?
            AND version = ?
            """,
            (bot_id, version)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()

        await db.commit()

    finally:
        await db.close()
