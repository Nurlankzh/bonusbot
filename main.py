import asyncio
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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


bot = Bot(token=config.BOT_TOKEN)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# STATES
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
# SECURITY
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


async def check_admin_message(message: types.Message) -> bool:
    if not message.from_user:
        return False

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Рұқсат жоқ.")
        return False

    return True


async def check_admin_callback(callback: types.CallbackQuery) -> bool:
    if not callback.from_user:
        return False

    if not is_admin(callback.from_user.id):
        try:
            await callback.answer(
                "⛔ Рұқсат жоқ.",
                show_alert=True
            )
        except Exception:
            pass

        return False

    return True


# =========================================================
# DATABASE BOT ACCESS
# =========================================================

async def get_owned_bot(bot_id: int, user_id: int):
    try:
        bot_data = await database.get_bot(bot_id)
    except Exception as error:
        logger.exception(
            "Database error: %s",
            error
        )
        return None

    if not bot_data:
        return None

    if bot_data.get("user_id") != user_id:
        return None

    return bot_data


# =========================================================
# KEYBOARDS
# =========================================================

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


def manage_menu(bot_id: int):
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


def variables_menu(bot_id: int):
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
# CALLBACK
# =========================================================

async def answer_callback(
    callback: types.CallbackQuery,
    text=None,
    show_alert=False
):
    try:
        if text:
            await callback.answer(
                text,
                show_alert=show_alert
            )
        else:
            await callback.answer()
    except Exception:
        pass


async def safe_edit(
    callback: types.CallbackQuery,
    text: str,
    keyboard=None
):
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard
        )

    except TelegramBadRequest as error:

        if "message is not modified" not in str(
            error
        ).lower():

            logger.exception(
                "Telegram edit error: %s",
                error
            )

            try:
                await callback.message.answer(
                    text,
                    reply_markup=keyboard
                )
            except Exception:
                pass

    except Exception as error:

        logger.exception(
            "safe_edit error: %s",
            error
        )

        try:
            await callback.message.answer(
                text,
                reply_markup=keyboard
            )
        except Exception:
            pass

    await answer_callback(callback)


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_command(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    await state.clear()

    await message.answer(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Боттарыңызды осы жерден басқарыңыз.\n\n"
        "➕ Жаңа бот қосу\n"
        "📋 Боттар тізімі\n"
        "📝 Код сақтау\n"
        "🔐 Variables\n"
        "📜 Logs\n"
        "🚀 Start / Stop / Restart",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# MAIN MENU
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def back_main(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
        return

    await state.clear()

    await safe_edit(
        callback,
        "🏠 <b>Басты мәзір</b>\n\n"
        "Қажетті бөлімді таңдаңыз:",
        main_menu()
    )


# =========================================================
# ADD BOT
# =========================================================

@dp.callback_query(F.data == "add_bot")
async def add_bot(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
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

    await answer_callback(callback)


@dp.message(AddBotStates.waiting_for_name)
async def get_bot_name(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Бот атауын мәтін түрінде жіберіңіз."
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
        "🔑 Енді BotFather берген "
        "child bot токенін жіберіңіз.\n\n"
        "⚠️ Токенді ешкімге жарияламаңыз."
    )


@dp.message(AddBotStates.waiting_for_token)
async def get_bot_token(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
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
            "❌ Конструктордың токенін child bot ретінде қолдануға болмайды."
        )
        return

    data = await state.get_data()

    bot_name = data.get("bot_name")

    if not bot_name:
        await state.clear()

        await message.answer(
            "❌ Бот атауы табылмады.\n\n"
            "/start арқылы қайта бастаңыз."
        )
        return

    # Token-ді Telegram арқылы тексеру
    test_bot = None

    try:
        test_bot = Bot(token=token)

        me = await test_bot.get_me()

        username = me.username or "unknown"

    except Exception as error:

        logger.exception(
            "Child token validation error: %s",
            error
        )

        await message.answer(
            "❌ Бұл токен жарамсыз немесе Telegram қабылдамады."
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
            bot_name,
            token
        )

    except Exception as error:

        logger.exception(
            "add_bot error: %s",
            error
        )

        await message.answer(
            "❌ Ботты базаға сақтау кезінде қате шықты."
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Бот қосылды!</b>\n\n"
        f"📛 Атауы: <b>{bot_name}</b>\n"
        f"🤖 Username: @{username}\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        "🔴 Күйі: Тоқтатылды",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
    )


# =========================================================
# LIST BOTS
# =========================================================

@dp.callback_query(F.data == "list_bots")
async def list_bots(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    await answer_callback(
        callback,
        "📋 Жүктелуде..."
    )

    try:

        bots = await database.get_user_bots(
            callback.from_user.id
        )

    except Exception as error:

        logger.exception(
            "get_user_bots error: %s",
            error
        )

        await callback.message.answer(
            "❌ Боттар тізімін оқу кезінде қате шықты.\n\n"
            f"{error}"
        )

        return

    if not bots:

        await safe_edit(
            callback,
            "📭 <b>Боттар жоқ.</b>\n\n"
            "➕ Жаңа бот қосыңыз.",
            main_menu()
        )

        return

    keyboard = []

    for item in bots:

        bot_id = item["id"]

        bot_name = item["bot_name"]

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
                    text=f"{icon} {bot_name}",
                    callback_data=f"manage_{bot_id}"
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

    await safe_edit(
        callback,
        "📋 <b>Боттар тізімі</b>\n\n"
        f"🤖 Барлығы: <b>{len(bots)}</b>\n\n"
        "Басқару үшін ботты таңдаңыз:",
        InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


# =========================================================
# MANAGE BOT
# =========================================================

@dp.callback_query(
    F.data.startswith("manage_")
)
async def manage_bot(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    status = bot_data.get(
        "status",
        "stopped"
    )

    if status == "running":
        status_text = "🟢 Қосулы"
    elif status == "crashed":
        status_text = "💥 Қате"
    else:
        status_text = "🔴 Тоқтатылды"

    await safe_edit(
        callback,
        "🖥 <b>Ботты басқару</b>\n\n"
        f"📛 Атауы: <b>{bot_data['bot_name']}</b>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        f"📊 Күйі: {status_text}\n\n"
        "Төменнен әрекетті таңдаңыз:",
        manage_menu(bot_id)
    )


# =========================================================
# START
# =========================================================

@dp.callback_query(
    F.data.startswith("start_")
)
async def start_bot(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await answer_callback(
        callback,
        "🚀 Іске қосылуда..."
    )

    try:

        success, result = await runner_manager.start_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "Start error: %s",
            error
        )

        success = False

        result = (
            "❌ Іске қосу кезінде қате:\n"
            f"{error}"
        )

    await callback.message.answer(
        result
    )


# =========================================================
# STOP
# =========================================================

@dp.callback_query(
    F.data.startswith("stop_")
)
async def stop_bot(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await answer_callback(
        callback,
        "🛑 Тоқтатылуда..."
    )

    try:

        success, result = await runner_manager.stop_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "Stop error: %s",
            error
        )

        result = (
            "❌ Тоқтату кезінде қате:\n"
            f"{error}"
        )

    await callback.message.answer(
        result
    )


# =========================================================
# RESTART
# =========================================================

@dp.callback_query(
    F.data.startswith("restart_")
)
async def restart_bot(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    await answer_callback(
        callback,
        "🔄 Restart..."
    )

    try:

        success, result = await runner_manager.restart_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "Restart error: %s",
            error
        )

        result = (
            "❌ Restart кезінде қате:\n"
            f"{error}"
        )

    await callback.message.answer(
        result
    )


# =========================================================
# CODE MENU
# =========================================================

@dp.callback_query(
    F.data.startswith("code_")
)
async def code_menu(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
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
        "Кодта Bot Token жазбаңыз.\n\n"
        "Мысалы:\n"
        "<code>import os</code>\n"
        "<code>TOKEN = os.getenv(\"BOT_TOKEN\")</code>\n\n"
        "Код жіберілгеннен кейін Version сақталады.",
        parse_mode="HTML"
    )

    await answer_callback(callback)


# =========================================================
# SAVE CODE
# =========================================================

@dp.message(
    CodeStates.waiting_for_code
)
async def save_code(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:

        await message.answer(
            "❌ Кодты мәтін ретінде жіберіңіз."
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

    bot_data = await get_owned_bot(
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

        logger.exception(
            "Save code error: %s",
            error
        )

        await message.answer(
            "❌ Кодты сақтау кезінде қате шықты."
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Код сақталды!</b>\n\n"
        f"🤖 {bot_data['bot_name']}\n"
        f"📦 Version: <b>v{version}</b>\n"
        f"📏 Көлемі: <b>{len(code)}</b> таңба",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
    )


# =========================================================
# VARIABLES
# =========================================================

@dp.callback_query(
    F.data.startswith("vars_")
)
async def variables_menu_handler(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    try:

        variables = await database.get_env_vars(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "Variables error: %s",
            error
        )

        await callback.message.answer(
            "❌ Variables оқу кезінде қате шықты."
        )

        return

    text = (
        "🔐 <b>Environment Variables</b>\n\n"
    )

    if not variables:

        text += "📭 Variable жоқ."

    else:

        for key in variables:

            text += (
                f"🔑 <code>{key}</code> = "
                "••••••••\n"
            )

    await safe_edit(
        callback,
        text,
        variables_menu(bot_id)
    )


# =========================================================
# ADD VARIABLE
# =========================================================

@dp.callback_query(
    F.data.startswith("addvar_")
)
async def add_variable(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
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
        "🔑 <b>Variable атауын жазыңыз:</b>\n\n"
        "Мысалы:\n"
        "<code>API_KEY</code>\n"
        "<code>ADMIN_ID</code>\n"
        "<code>DATABASE_URL</code>",
        parse_mode="HTML"
    )

    await answer_callback(callback)


# =========================================================
# VARIABLE KEY
# =========================================================

@dp.message(
    VarStates.waiting_for_key
)
async def get_variable_key(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:

        await message.answer(
            "❌ Variable атауын мәтін ретінде жіберіңіз."
        )

        return

    key = message.text.strip().upper()

    if not key:

        await message.answer(
            "❌ Атауы бос."
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

    bot_data = await get_owned_bot(
        bot_id,
        message.from_user.id
    )

    if not bot_data:

        await state.clear()

        await message.answer(
            "⛔ Бот табылмады."
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
        "📝 Енді Variable мәнін жазыңыз:",
        parse_mode="HTML"
    )


# =========================================================
# VARIABLE VALUE
# =========================================================

@dp.message(
    VarStates.waiting_for_value
)
async def get_variable_value(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:

        await message.answer(
            "❌ Мән мәтін болуы керек."
        )

        return

    data = await state.get_data()

    bot_id = data.get(
        "bot_id"
    )

    var_key = data.get(
        "var_key"
    )

    if not bot_id or not var_key:

        await state.clear()

        await message.answer(
            "❌ Variable деректері жоқ."
        )

        return

    bot_data = await get_owned_bot(
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

        await database.set_env_var(
            bot_id,
            var_key,
            message.text
        )

    except Exception as error:

        logger.exception(
            "Variable save error: %s",
            error
        )

        await message.answer(
            "❌ Variable сақтау кезінде қате шықты."
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Variable сақталды!</b>\n\n"
        f"🔑 {var_key}\n"
        "🔒 Мәні сақталды.",
        reply_markup=manage_menu(bot_id),
        parse_mode="HTML"
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
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
            callback,
            "⛔ Бот табылмады.",
            True
        )

        return

    try:

        logs_data = await database.get_logs(
            bot_id,
            30
        )

    except Exception as error:

        logger.exception(
            "Logs error: %s",
            error
        )

        await callback.message.answer(
            "❌ Logs оқу кезінде қате шықты."
        )

        return

    if not logs_data:

        text = (
            "📜 <b>Logs</b>\n\n"
            "📭 Log жоқ."
        )

    else:

        lines = []

        for item in logs_data:

            created_at = item.get(
                "created_at",
                ""
            )

            level = item.get(
                "level",
                "INFO"
            )

            log_message = item.get(
                "message",
                ""
            )

            lines.append(
                f"<code>{created_at}</code> "
                f"[{level}] {log_message}"
            )

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

    await safe_edit(
        callback,
        text,
        keyboard
    )


# =========================================================
# DELETE CONFIRMATION
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_")
)
async def delete_confirm(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
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

    await safe_edit(
        callback,
        "⚠️ <b>Ботты өшіру?</b>\n\n"
        f"📛 {bot_data['bot_name']}\n\n"
        "Код, Variables және Logs бірге өшіріледі.",
        keyboard
    )


# =========================================================
# DELETE
# =========================================================

@dp.callback_query(
    F.data.startswith("confirmdelete_")
)
async def delete_bot(
    callback: types.CallbackQuery
):
    if not await check_admin_callback(callback):
        return

    try:

        bot_id = int(
            callback.data.split(
                "_",
                1
            )[1]
        )

    except (
        ValueError,
        IndexError
    ):

        await answer_callback(
            callback,
            "❌ Бот ID қате.",
            True
        )

        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:

        await answer_callback(
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

        await database.delete_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "Delete bot error: %s",
            error
        )

        await callback.message.answer(
            "❌ Ботты өшіру кезінде қате шықты."
        )

        return

    await answer_callback(
        callback,
        "🗑 Бот өшірілді."
    )

    await callback.message.answer(
        "✅ <b>Бот толық өшірілді.</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(
    F.text == "/cancel"
)
async def cancel_command(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    await state.clear()

    await message.answer(
        "❌ Әрекет тоқтатылды.",
        reply_markup=main_menu()
    )


# =========================================================
# UNKNOWN MESSAGE
# =========================================================

@dp.message()
async def unknown_message(
    message: types.Message
):
    if not await check_admin_message(message):
        return

    await message.answer(
        "ℹ️ Түсінбедім.\n\n"
        "/start басыңыз немесе мәзірдегі батырмаларды пайдаланыңыз.",
        reply_markup=main_menu()
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "🚀 Конструктор іске қосылуда..."
    )

    await database.init_db()

    logger.info(
        "✅ Database дайын"
    )

    logger.info(
        "🚀 Конструктор іске қосылды"
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()

        logger.info(
            "🛑 Конструктор тоқтатылды"
        )


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "🛑 Process interrupted"
        )

    except Exception as error:

        logger.exception(
            "❌ Fatal error: %s",
            error
                )
