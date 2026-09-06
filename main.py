import asyncio
import html
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import config
import database
from runner import runner_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

bot = Bot(
    token=config.BOT_TOKEN
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# FSM
# =========================================================

class AddBotStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_token = State()


class CodeStates(StatesGroup):
    waiting_for_code = State()


class VarStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_value = State()


# =========================================================
# HELPERS
# =========================================================

async def admin_message(message: types.Message):

    if message.from_user.id != config.ADMIN_ID:

        await message.answer(
            "⛔ Рұқсат жоқ."
        )

        return False

    return True


async def admin_callback(
    callback: types.CallbackQuery
):

    if callback.from_user.id != config.ADMIN_ID:

        try:
            await callback.answer(
                "⛔ Рұқсат жоқ.",
                show_alert=True
            )
        except Exception:
            pass

        return False

    return True


async def callback_answer(
    callback,
    text=None,
    alert=False
):

    try:

        if text:
            await callback.answer(
                text,
                show_alert=alert
            )
        else:
            await callback.answer()

    except Exception:
        pass


async def owned_bot(
    bot_id,
    user_id
):

    data = await database.get_bot(
        bot_id
    )

    if not data:
        return None

    if data["user_id"] != user_id:
        return None

    return data


def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Жаңа бот қосу",
                    callback_data="add_bot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Боттар тізімі",
                    callback_data="bots"
                )
            ]
        ]
    )


def manage_keyboard(bot_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Start",
                    callback_data=f"start_{bot_id}"
                ),
                InlineKeyboardButton(
                    text="🛑 Stop",
                    callback_data=f"stop_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Restart",
                    callback_data=f"restart_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Код",
                    callback_data=f"code_{bot_id}"
                ),
                InlineKeyboardButton(
                    text="📦 Version",
                    callback_data=f"versions_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔐 Variables",
                    callback_data=f"vars_{bot_id}"
                ),
                InlineKeyboardButton(
                    text="📜 Logs",
                    callback_data=f"logs_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Өшіру",
                    callback_data=f"delete_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Боттар",
                    callback_data="bots"
                ),
                InlineKeyboardButton(
                    text="🏠 Басты мәзір",
                    callback_data="home"
                )
            ]
        ]
    )


def variable_keyboard(bot_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Variable қосу",
                    callback_data=f"addvar_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Жаңарту",
                    callback_data=f"vars_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Артқа",
                    callback_data=f"manage_{bot_id}"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: types.Message
):

    if not await admin_message(message):
        return

    await message.answer(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Боттарды осы жерден басқара аласыз.",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# =========================================================
# HOME
# =========================================================

@dp.callback_query(
    F.data == "home"
)
async def home_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    await callback_answer(callback)

    await callback.message.edit_text(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Боттарды осы жерден басқара аласыз.",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# =========================================================
# ADD BOT
# =========================================================

@dp.callback_query(
    F.data == "add_bot"
)
async def add_bot_start(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    await callback_answer(callback)

    await state.set_state(
        AddBotStates.waiting_for_name
    )

    await callback.message.answer(
        "🤖 Child боттың атын жіберіңіз.\n\n"
        "Мысалы:\n"
        "<code>@mybot</code>",
        parse_mode="HTML"
    )


@dp.message(
    AddBotStates.waiting_for_name
)
async def add_bot_name(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    name = (
        message.text or ""
    ).strip()

    if not name:

        await message.answer(
            "❌ Атау бос болмауы керек."
        )

        return

    await state.update_data(
        bot_name=name
    )

    await state.set_state(
        AddBotStates.waiting_for_token
    )

    await message.answer(
        "🔐 Енді child боттың <b>BotFather токенін</b> жіберіңіз.",
        parse_mode="HTML"
    )


@dp.message(
    AddBotStates.waiting_for_token
)
async def add_bot_token(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    token = (
        message.text or ""
    ).strip()

    if ":" not in token:

        await message.answer(
            "❌ Токен форматы дұрыс емес."
        )

        return

    if config.REJECT_MASTER_TOKEN_AS_CHILD:

        if token == config.BOT_TOKEN:

            await message.answer(
                "❌ Бұл конструктордың токені.\n"
                "Child бот үшін басқа токен енгізіңіз."
            )

            return

    test_bot = None

    try:

        test_bot = Bot(
            token=token
        )

        me = await test_bot.get_me()

        username = (
            f"@{me.username}"
            if me.username
            else "Username жоқ"
        )

        data = await state.get_data()

        name = data.get(
            "bot_name",
            username
        )

        bot_id = await database.add_bot(
            message.from_user.id,
            name,
            token
        )

        await state.clear()

        await message.answer(
            "✅ <b>Бот қосылды!</b>\n\n"
            f"📛 Атауы: {html.escape(str(name))}\n"
            f"🤖 Username: {html.escape(username)}\n"
            f"🆔 ID: <code>{bot_id}</code>\n"
            "🔴 Күйі: Тоқтатылды",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🤖 Ботты басқару",
                            callback_data=f"manage_{bot_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📋 Боттар",
                            callback_data="bots"
                        )
                    ]
                ]
            )
        )

    except Exception as error:

        logger.exception(
            "TOKEN VALIDATION ERROR"
        )

        await message.answer(
            "❌ Токенді тексеру кезінде қате:\n\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )

    finally:

        if test_bot:

            try:
                await test_bot.session.close()
            except Exception:
                pass


# =========================================================
# BOT LIST
# =========================================================

@dp.callback_query(
    F.data == "bots"
)
async def list_bots(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    bots = await database.get_user_bots(
        callback.from_user.id
    )

    await callback_answer(callback)

    if not bots:

        await callback.message.edit_text(
            "📋 <b>Боттар тізімі</b>\n\n"
            "Әзірге бот жоқ.",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )

        return

    buttons = []

    for item in bots:

        status = item["status"]

        if status == "running":
            icon = "🟢"
        elif status == "crashed":
            icon = "🔴"
        else:
            icon = "⚪"

        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"{icon} "
                    f"{item['bot_name']} "
                    f"#{item['id']}"
                ),
                callback_data=f"manage_{item['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="➕ Жаңа бот қосу",
            callback_data="add_bot"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔄 Жаңарту",
            callback_data="bots"
        ),
        InlineKeyboardButton(
            text="🏠 Басты мәзір",
            callback_data="home"
        )
    ])

    await callback.message.edit_text(
        "📋 <b>Боттар тізімі</b>\n\n"
        f"Барлығы: <b>{len(bots)}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# MANAGE
# =========================================================

@dp.callback_query(
    F.data.startswith("manage_")
)
async def manage_bot(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    status = data["status"]

    if status == "running":
        status_text = "🟢 Іске қосылған"
    elif status == "crashed":
        status_text = "🔴 Қате / тоқтаған"
    else:
        status_text = "⚪ Тоқтатылған"

    await callback_answer(callback)

    await callback.message.edit_text(
        "🤖 <b>Ботты басқару</b>\n\n"
        f"📛 Атауы: <code>{html.escape(str(data['bot_name']))}</code>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        f"📊 Күйі: {status_text}",
        parse_mode="HTML",
        reply_markup=manage_keyboard(bot_id)
    )


# =========================================================
# START CHILD BOT
# =========================================================

@dp.callback_query(
    F.data.startswith("start_")
)
async def start_child_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    # Telegram callback-ты бірден жабамыз.
    try:
        await callback.answer(
            "🚀 Іске қосылуда..."
        )
    except Exception:
        pass

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        try:
            await callback.message.answer(
                "❌ Бот ID дұрыс емес."
            )
        except Exception:
            pass

        return

    try:

        data = await owned_bot(
            bot_id,
            callback.from_user.id
        )

        if not data:

            await callback.message.answer(
                "⛔ Бұл бот табылмады "
                "немесе сізге тиесілі емес."
            )

            return

        success, result = (
            await runner_manager.start_sub_bot(
                bot_id
            )
        )

        # Нәтиже тек бір рет жіберіледі.
        await callback.message.answer(
            result
        )

    except Exception as error:

        logger.exception(
            "START CHILD BOT ERROR"
        )

        try:

            await callback.message.answer(
                "❌ Ботты іске қосу кезінде "
                "қате шықты.\n\n"
                f"<code>{html.escape(str(error)[:3000])}</code>",
                parse_mode="HTML"
            )

        except Exception:
            pass


# =========================================================
# STOP
# =========================================================

@dp.callback_query(
    F.data.startswith("stop_")
)
async def stop_child_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await callback_answer(
        callback,
        "🛑 Тоқтатылуда..."
    )

    try:

        success, result = (
            await runner_manager.stop_sub_bot(
                bot_id
            )
        )

        await callback.message.answer(
            result
        )

    except Exception as error:

        await callback.message.answer(
            "❌ Stop қатесі:\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )


# =========================================================
# RESTART
# =========================================================

@dp.callback_query(
    F.data.startswith("restart_")
)
async def restart_child_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await callback_answer(
        callback,
        "🔄 Restart..."
    )

    try:

        success, result = (
            await runner_manager.restart_sub_bot(
                bot_id
            )
        )

        await callback.message.answer(
            result
        )

    except Exception as error:

        await callback.message.answer(
            "❌ Restart қатесі:\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )


# =========================================================
# CODE
# =========================================================

@dp.callback_query(
    F.data.startswith("code_")
)
async def code_start(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await state.set_state(
        CodeStates.waiting_for_code
    )

    await state.update_data(
        bot_id=bot_id
    )

    await callback_answer(callback)

    await callback.message.answer(
        "📝 Child боттың Python кодын жіберіңіз.\n\n"
        "Мысалы:\n"
        "<code>import asyncio\n"
        "from aiogram import Bot</code>\n\n"
        "⚠️ Қазір мәтін түріндегі код қабылданады.\n"
        "Кодты жібергеннен кейін автоматты түрде жаңа version жасалады.",
        parse_mode="HTML"
    )


@dp.message(
    CodeStates.waiting_for_code
)
async def code_save_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    code = message.text or ""

    if not code.strip():

        await message.answer(
            "❌ Код бос."
        )

        return

    if len(code.encode("utf-8")) > config.MAX_CODE_SIZE:

        await message.answer(
            "❌ Код тым үлкен."
        )

        return

    data = await state.get_data()

    bot_id = data.get(
        "bot_id"
    )

    if not bot_id:

        await state.clear()

        await message.answer(
            "❌ Бот ID табылмады."
        )

        return

    owned = await owned_bot(
        bot_id,
        message.from_user.id
    )

    if not owned:

        await state.clear()

        await message.answer(
            "⛔ Бот табылмады."
        )

        return

    version = await database.save_code_version(
        bot_id,
        code
    )

    await state.clear()

    await message.answer(
        "✅ <b>Код сақталды!</b>\n\n"
        f"🤖 Бот ID: <code>{bot_id}</code>\n"
        f"📦 Version: <b>v{version}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚀 Start",
                        callback_data=f"start_{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Ботты басқару",
                        callback_data=f"manage_{bot_id}"
                    )
                ]
            ]
        )
    )


# =========================================================
# VERSIONS
# =========================================================

@dp.callback_query(
    F.data.startswith("versions_")
)
async def versions_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    versions = await database.get_code_versions(
        bot_id
    )

    await callback_answer(callback)

    if not versions:

        await callback.message.edit_text(
            "📦 <b>Versions</b>\n\n"
            "Version жоқ.",
            parse_mode="HTML",
            reply_markup=manage_keyboard(bot_id)
        )

        return

    buttons = []

    for version in versions[:20]:

        buttons.append([
            InlineKeyboardButton(
                text=f"📦 v{version['version']}",
                callback_data=(
                    f"viewversion_"
                    f"{bot_id}_"
                    f"{version['version']}"
                )
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Артқа",
            callback_data=f"manage_{bot_id}"
        )
    ])

    await callback.message.edit_text(
        "📦 <b>Code Versions</b>\n\n"
        f"Барлығы: {len(versions)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(
    F.data.startswith("viewversion_")
)
async def view_version_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        parts = callback.data.split("_")

        bot_id = int(parts[1])
        version = int(parts[2])

    except Exception:

        await callback_answer(
            callback,
            "❌ Version ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    version_data = await database.get_code_version(
        bot_id,
        version
    )

    if not version_data:

        await callback_answer(
            callback,
            "❌ Version табылмады.",
            True
        )

        return

    code = version_data["code"]

    preview = code[:3000]

    await callback_answer(callback)

    await callback.message.answer(
        f"📦 <b>Version v{version}</b>\n\n"
        f"<pre>{html.escape(preview)}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Versions",
                        callback_data=f"versions_{bot_id}"
                    )
                ]
            ]
        )
    )


# =========================================================
# VARIABLES
# =========================================================

@dp.callback_query(
    F.data.startswith("vars_")
)
async def vars_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    variables = await database.get_env_vars(
        bot_id
    )

    text = "🔐 <b>Variables</b>\n\n"

    if variables:

        for key, value in variables.items():

            masked = (
                "•" * min(
                    8,
                    max(
                        4,
                        len(str(value))
                    )
                )
            )

            text += (
                f"🔑 <code>{html.escape(str(key))}</code>"
                f" = <code>{masked}</code>\n"
            )

    else:

        text += "Variable жоқ.\n"

    await callback_answer(callback)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=variable_keyboard(bot_id)
    )


@dp.callback_query(
    F.data.startswith("addvar_")
)
async def addvar_start(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await state.set_state(
        VarStates.waiting_for_key
    )

    await state.update_data(
        bot_id=bot_id
    )

    await callback_answer(callback)

    await callback.message.answer(
        "🔑 Variable key енгізіңіз.\n\n"
        "Мысалы:\n"
        "<code>API_KEY</code>",
        parse_mode="HTML"
    )


@dp.message(
    VarStates.waiting_for_key
)
async def variable_key_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    key = (
        message.text or ""
    ).strip()

    if not key:

        await message.answer(
            "❌ Key бос."
        )

        return

    if " " in key:

        await message.answer(
            "❌ Key ішінде бос орын болмауы керек."
        )

        return

    await state.update_data(
        var_key=key
    )

    await state.set_state(
        VarStates.waiting_for_value
    )

    await message.answer(
        "📝 Енді variable value енгізіңіз."
    )


@dp.message(
    VarStates.waiting_for_value
)
async def variable_value_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    value = (
        message.text or ""
    ).strip()

    data = await state.get_data()

    bot_id = data.get(
        "bot_id"
    )

    key = data.get(
        "var_key"
    )

    if not bot_id or not key:

        await state.clear()

        await message.answer(
            "❌ Variable мәліметі табылмады."
        )

        return

    owned = await owned_bot(
        bot_id,
        message.from_user.id
    )

    if not owned:

        await state.clear()

        await message.answer(
            "⛔ Бот табылмады."
        )

        return

    await database.set_env_var(
        bot_id,
        key,
        value
    )

    await state.clear()

    await message.answer(
        "✅ Variable сақталды.\n\n"
        f"🔑 Key: <code>{html.escape(key)}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔐 Variables",
                        callback_data=f"vars_{bot_id}"
                    )
                ]
            ]
        )
    )


# =========================================================
# LOGS
# =========================================================

@dp.callback_query(
    F.data.startswith("logs_")
)
async def logs_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    logs = await database.get_logs(
        bot_id,
        30
    )

    await callback_answer(callback)

    if not logs:

        text = (
            "📜 <b>Logs</b>\n\n"
            "Логтар жоқ."
        )

    else:

        lines = [
            "📜 <b>Logs</b>\n"
        ]

        for item in logs:

            level = html.escape(
                str(item["level"])
            )

            message_text = html.escape(
                str(item["message"])
            )

            if len(message_text) > 700:
                message_text = (
                    message_text[:700]
                    + "..."
                )

            lines.append(
                f"<b>{level}</b> "
                f"{message_text}"
            )

        text = "\n".join(lines)

        if len(text) > 3900:

            text = text[-3900:]

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Жаңарту",
                        callback_data=f"logs_{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Артқа",
                        callback_data=f"manage_{bot_id}"
                    )
                ]
            ]
        )
    )


# =========================================================
# DELETE
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_")
)
async def delete_start(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await callback_answer(callback)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Иә, өшіру",
                    callback_data=f"confirmdelete_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Жоқ",
                    callback_data=f"manage_{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "⚠️ <b>Ботты өшіру?</b>\n\n"
        "Бұл боттың:\n"
        "• кодтары\n"
        "• versions\n"
        "• variables\n"
        "• logs\n"
        "• workspace\n\n"
        "толығымен өшіріледі.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(
    F.data.startswith("confirmdelete_")
)
async def confirm_delete(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except Exception:

        await callback_answer(
            callback,
            "❌ ID қате.",
            True
        )

        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:

        await callback_answer(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await callback_answer(
        callback,
        "🗑 Өшірілуде..."
    )

    try:

        await runner_manager.stop_sub_bot(
            bot_id
        )

    except Exception:
        pass

    try:

        await runner_manager.delete_workspace(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "WORKSPACE DELETE ERROR"
        )

        await callback.message.answer(
            "⚠️ Workspace өшірілмеді:\n"
            f"<code>{html.escape(str(error)[:2000])}</code>",
            parse_mode="HTML"
        )

    await database.delete_bot(
        bot_id
    )

    await callback.message.edit_text(
        "✅ <b>Бот толығымен өшірілді.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Боттар",
                        callback_data="bots"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Басты мәзір",
                        callback_data="home"
                    )
                ]
            ]
        )
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(
    F.text == "/cancel"
)
async def cancel_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    await state.clear()

    await message.answer(
        "❌ Әрекет тоқтатылды.",
        reply_markup=main_keyboard()
    )


# =========================================================
# UNKNOWN CALLBACK
# =========================================================

@dp.callback_query()
async def unknown_callback(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    await callback_answer(
        callback,
        "⚠️ Бұл батырма ескірген."
    )


# =========================================================
# STARTUP
# =========================================================

async def main():

    await database.init_db()

    logger.info(
        "===================================="
    )

    logger.info(
        "🟢 Telegram Bot Constructor started"
    )

    logger.info(
        "👤 Admin ID: %s",
        config.ADMIN_ID
    )

    logger.info(
        "===================================="
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await runner_manager.stop_all()

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
