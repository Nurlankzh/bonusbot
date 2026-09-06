import os
import aiosqlite
import config


async def init_db():
    directory = os.path.dirname(config.DATABASE_PATH)

    if directory:
        os.makedirs(directory, exist_ok=True)

    async with aiosqlite.connect(config.DATABASE_PATH) as db:
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


async def add_bot(user_id, name, token):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO bots
            (user_id, bot_name, bot_token, status)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, name, token, "stopped")
        )

        await db.commit()
        return cursor.lastrowid


async def get_user_bots(user_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM bots
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )

        rows = await cursor.fetchall()

        return [dict(row) for row in rows]


async def get_bot(bot_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM bots
            WHERE id = ?
            """,
            (bot_id,)
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)


async def update_bot_status(bot_id, status):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE bots
            SET status = ?
            WHERE id = ?
            """,
            (status, bot_id)
        )

        await db.commit()


async def save_code_version(bot_id, code):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

        cursor = await db.execute(
            """
            SELECT MAX(version)
            FROM code_versions
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        row = await cursor.fetchone()

        current_version = row[0] or 0
        new_version = current_version + 1

        await db.execute(
            """
            INSERT INTO code_versions
            (bot_id, version, code)
            VALUES (?, ?, ?)
            """,
            (bot_id, new_version, code)
        )

        await db.commit()

        return new_version


async def get_latest_code(bot_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (bot_id,)
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)


async def get_code_versions(bot_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            ORDER BY version DESC
            """,
            (bot_id,)
        )

        rows = await cursor.fetchall()

        return [dict(row) for row in rows]


async def get_code_version(bot_id, version):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            AND version = ?
            """,
            (bot_id, version)
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)


async def get_env_vars(bot_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

        cursor = await db.execute(
            """
            SELECT var_key, var_value
            FROM env_vars
            WHERE bot_id = ?
            ORDER BY var_key
            """,
            (bot_id,)
        )

        rows = await cursor.fetchall()

        return {
            row[0]: row[1]
            for row in rows
        }


async def set_env_var(bot_id, key, value):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

        await db.execute(
            """
            INSERT INTO env_vars
            (bot_id, var_key, var_value)
            VALUES (?, ?, ?)

            ON CONFLICT(bot_id, var_key)
            DO UPDATE SET
                var_value = excluded.var_value
            """,
            (bot_id, key, value)
        )

        await db.commit()


async def delete_env_var(bot_id, key):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

        await db.execute(
            """
            DELETE FROM env_vars
            WHERE bot_id = ?
            AND var_key = ?
            """,
            (bot_id, key)
        )

        await db.commit()


async def add_log(bot_id, level, message):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

        await db.execute(
            """
            INSERT INTO logs
            (bot_id, level, message)
            VALUES (?, ?, ?)
            """,
            (bot_id, level, message)
        )

        await db.commit()


async def get_logs(bot_id, limit=50):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM logs
            WHERE bot_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (bot_id, limit)
        )

        rows = await cursor.fetchall()

        result = [dict(row) for row in rows]

        result.reverse()

        return result


async def delete_bot(bot_id):
    async with aiosqlite.connect(config.DATABASE_PATH) as db:

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

        await db.commit()
