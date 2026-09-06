import os
import aiosqlite

import config


# ============================================================
# DATABASE CONNECTION
# ============================================================

async def connect():
    """
    SQLite database connection.
    Railway Volume үшін config.DATABASE_PATH қолданылады.
    """

    folder = os.path.dirname(config.DATABASE_PATH)

    if folder:
        os.makedirs(folder, exist_ok=True)

    db = await aiosqlite.connect(
        config.DATABASE_PATH,
        timeout=30
    )

    # SQLite тұрақтылығы
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    await db.execute("PRAGMA foreign_keys=ON")

    return db


# ============================================================
# INIT DATABASE
# ============================================================

async def init_db():
    db = await connect()

    try:
        # ----------------------------------------------------
        # BOTS
        # ----------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_name TEXT NOT NULL,
                bot_token TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stopped'
            )
            """
        )

        # ----------------------------------------------------
        # CODE VERSIONS
        # ----------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS code_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                code TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # VARIABLES
        # ----------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS env_vars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                var_key TEXT NOT NULL,
                var_value TEXT NOT NULL,
                UNIQUE(bot_id, var_key)
            )
            """
        )

        # ----------------------------------------------------
        # LOGS
        # ----------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# BOT FUNCTIONS
# ============================================================

async def add_bot(user_id, name, token):
    """
    Жаңа child bot қосу.
    """

    db = await connect()

    try:
        cursor = await db.execute(
            """
            INSERT INTO bots
            (
                user_id,
                bot_name,
                bot_token,
                status
            )
            VALUES (?, ?, ?, 'stopped')
            """,
            (
                user_id,
                name,
                token
            )
        )

        await db.commit()

        return cursor.lastrowid

    finally:
        await db.close()


async def get_user_bots(user_id):
    """
    Белгілі бір қолданушының барлық боттары.
    """

    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                id,
                user_id,
                bot_name,
                bot_token,
                status
            FROM bots
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )

        rows = await cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        await db.close()


async def get_bot(bot_id):
    """
    ID арқылы child bot алу.
    """

    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM bots
            WHERE id = ?
            LIMIT 1
            """,
            (bot_id,)
        )

        row = await cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:
        await db.close()


async def update_bot_status(bot_id, status):
    """
    Бот статусын өзгерту.

    status:
        running
        stopped
        crashed
    """

    db = await connect()

    try:
        await db.execute(
            """
            UPDATE bots
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                bot_id
            )
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# CODE VERSION FUNCTIONS
# ============================================================

async def save_code_version(bot_id, code):
    """
    Child bot кодының жаңа Version-ын сақтау.
    """

    if code is None:
        code = ""

    code = str(code)

    db = await connect()

    try:
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
            (
                bot_id,
                version,
                code
            )
            VALUES (?, ?, ?)
            """,
            (
                bot_id,
                new_version,
                code
            )
        )

        await db.commit()

        return new_version

    finally:
        await db.close()


async def get_latest_code(bot_id):
    """
    Ең соңғы Version кодын алу.
    """

    db = await connect()

    try:
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

        if row:
            return dict(row)

        return None

    finally:
        await db.close()


async def get_code_versions(bot_id):
    """
    Барлық Version тізімі.
    """

    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                id,
                bot_id,
                version,
                created_at
            FROM code_versions
            WHERE bot_id = ?
            ORDER BY version DESC
            """,
            (bot_id,)
        )

        rows = await cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        await db.close()


async def get_code_version(bot_id, version):
    """
    Нақты Version кодын алу.
    """

    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM code_versions
            WHERE bot_id = ?
            AND version = ?
            LIMIT 1
            """,
            (
                bot_id,
                version
            )
        )

        row = await cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:
        await db.close()


async def delete_code_version(bot_id, version):
    """
    Белгілі бір Version-ды өшіру.
    """

    db = await connect()

    try:
        cursor = await db.execute(
            """
            DELETE FROM code_versions
            WHERE bot_id = ?
            AND version = ?
            """,
            (
                bot_id,
                version
            )
        )

        await db.commit()

        return cursor.rowcount > 0

    finally:
        await db.close()


async def delete_all_code_versions(bot_id):
    """
    Child bot-тың барлық Version-ын өшіру.
    """

    db = await connect()

    try:
        await db.execute(
            """
            DELETE FROM code_versions
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

async def get_env_vars(bot_id):
    """
    Child bot Variables алу.
    """

    db = await connect()

    try:
        cursor = await db.execute(
            """
            SELECT
                var_key,
                var_value
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

    finally:
        await db.close()


async def set_env_var(bot_id, key, value):
    """
    Variable қосу немесе жаңарту.
    """

    key = str(key).strip()
    value = str(value)

    if not key:
        raise ValueError(
            "Variable key бос болмауы керек."
        )

    db = await connect()

    try:
        await db.execute(
            """
            INSERT INTO env_vars
            (
                bot_id,
                var_key,
                var_value
            )
            VALUES (?, ?, ?)

            ON CONFLICT(bot_id, var_key)
            DO UPDATE SET
                var_value = excluded.var_value
            """,
            (
                bot_id,
                key,
                value
            )
        )

        await db.commit()

    finally:
        await db.close()


async def delete_env_var(bot_id, key):
    """
    Variable өшіру.
    """

    db = await connect()

    try:
        await db.execute(
            """
            DELETE FROM env_vars
            WHERE bot_id = ?
            AND var_key = ?
            """,
            (
                bot_id,
                key
            )
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# LOG FUNCTIONS
# ============================================================

async def add_log(bot_id, level, message):
    """
    Child bot логын сақтау.
    """

    if message is None:
        message = ""

    message = str(message)

    db = await connect()

    try:
        await db.execute(
            """
            INSERT INTO logs
            (
                bot_id,
                level,
                message
            )
            VALUES (?, ?, ?)
            """,
            (
                bot_id,
                str(level),
                message
            )
        )

        await db.commit()

        # ----------------------------------------------------
        # MAX LOGS
        # ----------------------------------------------------

        max_logs = getattr(
            config,
            "MAX_LOGS",
            1000
        )

        await db.execute(
            """
            DELETE FROM logs
            WHERE bot_id = ?
            AND id NOT IN (
                SELECT id
                FROM logs
                WHERE bot_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (
                bot_id,
                bot_id,
                max_logs
            )
        )

        await db.commit()

    finally:
        await db.close()


async def get_logs(bot_id, limit=50):
    """
    Соңғы логтарды алу.
    """

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50

    if limit < 1:
        limit = 1

    if limit > 1000:
        limit = 1000

    db = await connect()

    try:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                id,
                bot_id,
                level,
                message,
                created_at
            FROM logs
            WHERE bot_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                bot_id,
                limit
            )
        )

        rows = await cursor.fetchall()

        result = [
            dict(row)
            for row in rows
        ]

        # Ескі → жаңа
        result.reverse()

        return result

    finally:
        await db.close()


async def clear_logs(bot_id):
    """
    Барлық логтарды тазалау.
    """

    db = await connect()

    try:
        await db.execute(
            """
            DELETE FROM logs
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# DELETE BOT
# ============================================================

async def delete_bot(bot_id):
    """
    Child bot-ты толық өшіру.

    Өшіріледі:
        - bot
        - code versions
        - variables
        - logs
    """

    db = await connect()

    try:
        await db.execute(
            """
            DELETE FROM code_versions
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        await db.execute(
            """
            DELETE FROM env_vars
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        await db.execute(
            """
            DELETE FROM logs
            WHERE bot_id = ?
            """,
            (bot_id,)
        )

        await db.execute(
            """
            DELETE FROM bots
            WHERE id = ?
            """,
            (bot_id,)
        )

        await db.commit()

    finally:
        await db.close()


# ============================================================
# OWNERSHIP CHECK
# ============================================================

async def user_owns_bot(user_id, bot_id):
    """
    Бот осы қолданушыға тиесілі ме?
    """

    db = await connect()

    try:
        cursor = await db.execute(
            """
            SELECT id
            FROM bots
            WHERE id = ?
            AND user_id = ?
            LIMIT 1
            """,
            (
                bot_id,
                user_id
            )
        )

        row = await cursor.fetchone()

        return row is not None

    finally:
        await db.close()


# ============================================================
# BOT COUNT
# ============================================================

async def count_user_bots(user_id):
    """
    Қолданушының боттарының саны.
    """

    db = await connect()

    try:
        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM bots
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = await cursor.fetchone()

        return row[0] if row else 0

    finally:
        await db.close()


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

async def database_health_check():
    """
    Database жұмыс істеп тұрғанын тексеру.
    """

    db = await connect()

    try:
        cursor = await db.execute(
            "SELECT 1"
        )

        row = await cursor.fetchone()

        return row is not None

    finally:
        await db.close()
