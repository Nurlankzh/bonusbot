import asyncio
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


if not config.BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN Railway Variables ішінде көрсетілмеген."
    )


bot = Bot(
    token=config.BOT_TOKEN
)

dp = Dispatcher(
    storage=MemoryStorage()
)


class AddBotStates(StatesGroup):

    waiting_for_name = State()
    waiting_for_token = State()


class CodeStates(StatesGroup):

    waiting_for_code = State()


class VarStates(StatesGroup):

    waiting_for_key = State()
    waiting_for_value = State()


def is_admin(user_id):

    return user_id == config.ADMIN_ID


async def admin_message(message):

    if not message.from_user:
        return False

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            "⛔ Рұқсат жоқ."
        )

        return False

    return True


async def admin_callback(callback):

    if not callback.from_user:
        return False

    if not is_admin(
        callback.from_user.id
    ):

        try:

            await callback.answer(
                "⛔ Рұқсат жоқ.",
                show_alert=True
            )

        except Exception:
            pass

        return False

    return True


async def owned_bot(bot_id, user_id):

    data = await database.get_bot(
        bot_id
    )

    if not data:
        return None

    if data["user_id"] != user_id:
        return None

    return data


def main_menu():

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
                    callback_data="list_bots"
                )
            ]

        ]
    )


def manage_menu(bot_id):

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
                )
            ],

            [
                InlineKeyboardButton(
                    text="📦 Version",
                    callback_data=f"versions_{bot_id}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔐 Variables",
                    callback_data=f"vars_{bot_id}"
                )
            ],

            [
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
                    callback_data="list_bots"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🏠 Басты мәзір",
                    callback_data="main_menu"
                )
            ]

        ]
    )


def variable_menu(bot_id):

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


async def edit(
    callback,
    text,
    keyboard=None
):

    try:

        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )

    except TelegramBadRequest as error:

        if "message is not modified" not in str(error).lower():

            await callback.message.answer(
                text,
                reply_markup=keyboard
            )

    except Exception:

        await callback.message.answer(
            text,
            reply_markup=keyboard
        )

    await callback_answer(
        callback
    )


@dp.message(CommandStart())
async def start_command(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    await state.clear()

    await message.answer(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Боттарыңызды осы жерден басқарыңыз.\n\n"
        "➕ Жаңа бот қосу\n"
        "📋 Боттар тізімі\n"
        "📝 Код\n"
        "📦 Version\n"
        "🔐 Variables\n"
        "📜 Logs\n"
        "🚀 Start / Stop / Restart",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    await state.clear()

    await edit(
        callback,
        "🏠 <b>Басты мәзір</b>\n\n"
        "Қажетті бөлімді таңдаңыз:",
        main_menu()
    )


@dp.callback_query(F.data == "add_bot")
async def add_bot_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    await state.clear()

    await state.set_state(
        AddBotStates.waiting_for_name
    )

    await callback.message.answer(
        "➕ <b>Жаңа бот қосу</b>\n\n"
        "Боттың атауын жазыңыз:",
        parse_mode="HTML"
    )

    await callback_answer(callback)


@dp.message(AddBotStates.waiting_for_name)
async def bot_name_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Атауды мәтін түрінде жіберіңіз."
        )
        return

    name = message.text.strip()

    if not name:
        await message.answer(
            "❌ Атау бос болмауы керек."
        )
        return

    if len(name) > 100:
        await message.answer(
            "❌ Атау 100 таңбадан аспауы керек."
        )
        return

    await state.update_data(
        bot_name=name
    )

    await state.set_state(
        AddBotStates.waiting_for_token
    )

    await message.answer(
        "🔑 Child bot токенін жіберіңіз.\n\n"
        "⚠️ Токенді ешкімге жарияламаңыз."
    )


@dp.message(AddBotStates.waiting_for_token)
async def bot_token_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Токен мәтін болуы керек."
        )
        return

    token = message.text.strip()

    if ":" not in token:
        await message.answer(
            "❌ Токен форматы дұрыс емес."
        )
        return

    if token == config.BOT_TOKEN:
        await message.answer(
            "❌ Конструктор токенін child bot ретінде қолдануға болмайды."
        )
        return

    data = await state.get_data()

    name = data.get(
        "bot_name"
    )

    test_bot = None

    try:

        test_bot = Bot(
            token=token
        )

        me = await test_bot.get_me()

        username = me.username or "unknown"

    except Exception:

        await message.answer(
            "❌ Child bot токені жарамсыз."
        )

        return

    finally:

        if test_bot:

            try:
                await test_bot.session.close()
            except Exception:
                pass

    try:

        bot_id = await database.add_bot(
            message.from_user.id,
            name,
            token
        )

    except Exception as error:

        logger.exception(
            error
        )

        await message.answer(
            "❌ Ботты сақтау кезінде қате шықты."
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Бот қосылды!</b>\n\n"
        f"📛 Атауы: <b>{name}</b>\n"
        f"🤖 Username: @{username}\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        "🔴 Күйі: Тоқтатылды",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "list_bots")
async def list_bots_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    bots = await database.get_user_bots(
        callback.from_user.id
    )

    if not bots:

        await edit(
            callback,
            "📭 <b>Боттар жоқ.</b>\n\n"
            "➕ Жаңа бот қосыңыз.",
            main_menu()
        )

        return

    keyboard = []

    for item in bots:

        status = item.get(
            "status",
            "stopped"
        )

        if status == "running":
            icon = "🟢"
        elif status == "crashed":
            icon = "💥"
        else:
            icon = "🔴"

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {item['bot_name']}",
                    callback_data=f"manage_{item['id']}"
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="➕ Жаңа бот",
                callback_data="add_bot"
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔄 Жаңарту",
                callback_data="list_bots"
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="🏠 Басты мәзір",
                callback_data="main_menu"
            )
        ]
    )

    await edit(
        callback,
        "📋 <b>Боттар тізімі</b>\n\n"
        f"🤖 Барлығы: <b>{len(bots)}</b>\n\n"
        "Ботты таңдаңыз:",
        InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


@dp.callback_query(F.data.startswith("manage_"))
async def manage_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    status = data.get(
        "status",
        "stopped"
    )

    if status == "running":
        status_text = "🟢 Қосулы"
    elif status == "crashed":
        status_text = "💥 Қате"
    else:
        status_text = "🔴 Тоқтатылды"

    await edit(
        callback,
        "🤖 <b>Ботты басқару</b>\n\n"
        f"📛 Атауы: <b>{data['bot_name']}</b>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        f"📊 Күйі: {status_text}\n\n"
        "Әрекетті таңдаңыз:",
        manage_menu(bot_id)
    )


@dp.callback_query(F.data.startswith("start_"))
async def start_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    try:

        success, result = await runner_manager.start_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            error
        )

        success = False

        result = (
            "❌ Іске қосу қатесі:\n"
            f"{error}"
        )

    await callback_answer(
        callback
    )

    await callback.message.answer(
        result
    )


@dp.callback_query(F.data.startswith("stop_"))
async def stop_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    try:

        success, result = await runner_manager.stop_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            error
        )

        result = (
            "❌ Тоқтату қатесі:\n"
            f"{error}"
        )

    await callback_answer(
        callback
    )

    await callback.message.answer(
        result
    )


@dp.callback_query(F.data.startswith("restart_"))
async def restart_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    try:

        success, result = await runner_manager.restart_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            error
        )

        result = (
            "❌ Restart қатесі:\n"
            f"{error}"
        )

    await callback_answer(
        callback
    )

    await callback.message.answer(
        result
    )


@dp.callback_query(F.data.startswith("code_"))
async def code_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    await state.clear()

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        CodeStates.waiting_for_code
    )

    await callback.message.answer(
        "📝 <b>Python кодын жіберіңіз.</b>\n\n"
        "Мысалы:\n\n"
        "<code>import asyncio\n"
        "import os\n\n"
        "from aiogram import Bot, Dispatcher\n"
        "from aiogram.filters import CommandStart\n\n"
        "dp = Dispatcher()</code>\n\n"
        "⚠️ BOT_TOKEN кодтың ішінде болмауы керек.\n"
        "Ол автоматты түрде беріледі.",
        parse_mode="HTML"
    )

    await callback_answer(callback)


@dp.message(CodeStates.waiting_for_code)
async def code_save_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Python кодын мәтін ретінде жіберіңіз."
        )
        return

    code = message.text

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

    bot_data = await owned_bot(
        bot_id,
        message.from_user.id
    )

    if not bot_data:
        await state.clear()

        await message.answer(
            "⛔ Бот табылмады."
        )

        return

    try:

        version = await database.save_code_version(
            bot_id,
            code
        )

    except Exception as error:

        await message.answer(
            f"❌ Кодты сақтау қатесі:\n{error}"
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Код сақталды!</b>\n\n"
        f"📦 Version: <b>v{version}</b>\n"
        f"📏 {len(code)} таңба",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("versions_"))
async def versions_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    if not versions:

        await edit(
            callback,
            "📦 <b>Versions</b>\n\n"
            "📭 Әзірге код сақталмаған.",
            manage_menu(bot_id)
        )

        return

    keyboard = []

    for version in versions[:20]:

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"📦 v{version['version']} — {len(version['code'])} таңба",
                    callback_data=(
                        f"viewversion_{bot_id}_{version['version']}"
                    )
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="⬅️ Артқа",
                callback_data=f"manage_{bot_id}"
            )
        ]
    )

    await edit(
        callback,
        "📦 <b>Code Versions</b>\n\n"
        f"Барлығы: <b>{len(versions)}</b>\n\n"
        "Version таңдаңыз:",
        InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


@dp.callback_query(F.data.startswith("viewversion_"))
async def view_version_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:

        _, bot_id, version = callback.data.split("_")

        bot_id = int(bot_id)
        version = int(version)

    except Exception:

        await callback_answer(
            callback,
            "❌ Дерек қате.",
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

    code_data = await database.get_code_version(
        bot_id,
        version
    )

    if not code_data:

        await callback_answer(
            callback,
            "❌ Version табылмады.",
            True
        )

        return

    code = code_data["code"]

    preview = code

    if len(preview) > 3000:
        preview = preview[:3000] + "\n..."

    await callback.message.answer(
        f"📦 <b>Version v{version}</b>\n\n"
        f"<pre>{preview}</pre>",
        parse_mode="HTML"
    )

    await callback_answer(callback)


@dp.callback_query(F.data.startswith("vars_"))
async def vars_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    text = "🔐 <b>Environment Variables</b>\n\n"

    if not variables:

        text += "📭 Variable жоқ."

    else:

        for key in variables:

            text += (
                f"🔑 <code>{key}</code> = "
                "••••••••\n"
            )

    await edit(
        callback,
        text,
        variable_menu(bot_id)
    )


@dp.callback_query(F.data.startswith("addvar_"))
async def addvar_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    await state.clear()

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        VarStates.waiting_for_key
    )

    await callback.message.answer(
        "🔑 Variable атауын жазыңыз.\n\n"
        "Мысалы:\n"
        "<code>API_KEY</code>\n"
        "<code>ADMIN_ID</code>\n"
        "<code>DATABASE_URL</code>",
        parse_mode="HTML"
    )

    await callback_answer(callback)


@dp.message(VarStates.waiting_for_key)
async def variable_key_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Variable атауын жазыңыз."
        )
        return

    key = message.text.strip().upper()

    if not key.replace("_", "").isalnum():
        await message.answer(
            "❌ Variable атауы дұрыс емес.\n"
            "Мысалы: API_KEY"
        )
        return

    data = await state.get_data()

    bot_id = data.get(
        "bot_id"
    )

    if not bot_id:
        await state.clear()

        await message.answer(
            "❌ Бот ID жоқ."
        )

        return

    await state.update_data(
        var_key=key
    )

    await state.set_state(
        VarStates.waiting_for_value
    )

    await message.answer(
        f"🔑 <b>{key}</b>\n\n"
        "Variable мәнін жіберіңіз:",
        parse_mode="HTML"
    )


@dp.message(VarStates.waiting_for_value)
async def variable_value_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Мәнді мәтін ретінде жіберіңіз."
        )
        return

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
            "❌ Variable деректері жоқ."
        )

        return

    bot_data = await owned_bot(
        bot_id,
        message.from_user.id
    )

    if not bot_data:
        await state.clear()

        await message.answer(
            "⛔ Бот табылмады."
        )

        return

    await database.set_env_var(
        bot_id,
        key,
        message.text
    )

    await state.clear()

    await message.answer(
        "✅ <b>Variable сақталды!</b>\n\n"
        f"🔑 {key}\n"
        "🔒 Мәні сақталды.",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("logs_"))
async def logs_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    if not logs:

        text = (
            "📜 <b>Logs</b>\n\n"
            "📭 Log жоқ."
        )

    else:

        lines = []

        for item in logs:

            line = (
                f"{item['created_at']} "
                f"[{item['level']}] "
                f"{item['message']}"
            )

            lines.append(line)

        text = (
            "📜 <b>Latest Logs</b>\n\n"
            + "\n".join(lines)
        )

    if len(text) > 3900:

        text = (
            "📜 <b>Latest Logs</b>\n\n"
            + text[-3800:]
        )

    keyboard = InlineKeyboardMarkup(
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

    await edit(
        callback,
        text,
        keyboard
    )


@dp.callback_query(F.data.startswith("delete_"))
async def delete_confirm_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🗑 Иә, өшіру",
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

    await edit(
        callback,
        "⚠️ <b>Ботты өшіру?</b>\n\n"
        f"📛 {data['bot_name']}\n\n"
        "Код, Version, Variables және Logs "
        "бірге өшіріледі.",
        keyboard
    )


@dp.callback_query(F.data.startswith("confirmdelete_"))
async def delete_handler(
    callback: types.CallbackQuery
):

    if not await admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
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
    except Exception:
        pass

    await database.delete_bot(
        bot_id
    )

    await callback_answer(
        callback,
        "🗑 Өшірілді."
    )

    await callback.message.answer(
        "✅ <b>Бот толық өшірілді.</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@dp.message(F.text == "/cancel")
async def cancel_handler(
    message: types.Message,
    state: FSMContext
):

    if not await admin_message(message):
        return

    await state.clear()

    await message.answer(
        "❌ Әрекет тоқтатылды.",
        reply_markup=main_menu()
    )


@dp.message()
async def unknown_handler(
    message: types.Message
):

    if not await admin_message(message):
        return

    await message.answer(
        "ℹ️ Түсінбедім.\n\n"
        "/start басыңыз.",
        reply_markup=main_menu()
    )


async def main():

    logger.info(
        "🚀 Telegram Bot Constructor іске қосылуда..."
    )

    await database.init_db()

    logger.info(
        "✅ Database дайын"
    )

    logger.info(
        "🚀 Constructor polling басталды"
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "🛑 Process stopped"
        )

    except Exception as error:

        logger.exception(
            "❌ Fatal error: %s",
            error
        )
