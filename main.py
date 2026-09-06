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


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

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


async def check_admin_message(
    message: types.Message
) -> bool:

    if not message.from_user:
        return False

    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ Рұқсат жоқ."
        )
        return False

    return True


async def check_admin_callback(
    callback: types.CallbackQuery
) -> bool:

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
# BOT ACCESS
# =========================================================

async def get_owned_bot(
    bot_id: int,
    user_id: int
):

    try:

        bot_data = await database.get_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "get_bot error: %s",
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


def manage_menu(
    bot_id: int
):

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
                    text="⬅️ Боттар",
                    callback_data="list_bots"
                ]
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Басты мәзір",
                    callback_data="main_menu"
                )
            ]
        ]
    )


def variables_menu(
    bot_id: int
):

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
                    text="⬅️ Артқа",
                    callback_data=f"manage_{bot_id}"
                )
            ]
        ]
    )


# =========================================================
# CALLBACK ANSWER
# =========================================================

async def answer_callback(
    callback: types.CallbackQuery,
    text: str = None,
    show_alert: bool = False
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


# =========================================================
# SAFE EDIT
# =========================================================

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

        error_text = str(error).lower()

        if "message is not modified" not in error_text:

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

    await answer_callback(
        callback
    )


# =========================================================
# START COMMAND
# =========================================================

@dp.message(CommandStart())
async def start_command(
    message: types.Message,
    state: FSMContext
):

    if not await check_admin_message(
        message
    ):
        return

    await state.clear()

    await message.answer(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Бұл жерде Telegram боттарыңызды "
        "басқара аласыз.\n\n"
        "➕ Жаңа бот қосыңыз\n"
        "📋 Боттарыңызды басқарыңыз\n"
        "📝 Код сақтаңыз\n"
        "🔐 Variables орнатыңыз\n"
        "📜 Logs көріңіз",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# MAIN MENU
# =========================================================

@dp.callback_query(
    F.data == "main_menu"
)
async def back_main(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await check_admin_callback(
        callback
    ):
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

@dp.callback_query(
    F.data == "add_bot"
)
async def add_bot(
    callback: types.CallbackQuery,
    state: FSMContext
):

    if not await check_admin_callback(
        callback
    ):
        return

    await state.clear()

    await state.set_state(
        AddBotStates.waiting_for_name
    )

    await callback.message.answer(
        "➕ <b>Жаңа бот қосу</b>\n\n"
        "1️⃣ Боттың атауын жазыңыз:",
        parse_mode="HTML"
    )

    await answer_callback(
        callback
    )


# =========================================================
# BOT NAME
# =========================================================

@dp.message(
    AddBotStates.waiting_for_name
)
async def get_bot_name(
    message: types.Message,
    state: FSMContext
):

    if not await check_admin_message(
        message
    ):
        return

    if not message.text:

        await message.answer(
            "❌ Бот атауын мәтін түрінде жіберіңіз."
        )

        return

    bot_name = message.text.strip()

    if not bot_name:

        await message.answer(
            "❌ Бот атауы бос болмауы керек."
        )

        return

    if len(bot_name) > 100:

        await message.answer(
            "❌ Бот атауы 100 таңбадан аспауы керек."
        )

        return

    await state.update_data(
        bot_name=bot_name
    )

    await state.set_state(
        AddBotStates.waiting_for_token
    )

    await message.answer(
        "2️⃣ <b>BotFather токенін жіберіңіз:</b>\n\n"
        "Мысалы:\n"
        "<code>123456789:AA...</code>\n\n"
        "⚠️ Токенді ешкімге жарияламаңыз.",
        parse_mode="HTML"
    )


# =========================================================
# BOT TOKEN
# =========================================================

@dp.message(
    AddBotStates.waiting_for_token
)
async def get_bot_token(
    message: types.Message,
    state: FSMContext
):

    if not await check_admin_message(
        message
    ):
        return

    if not message.text:

        await message.answer(
            "❌ Токен мәтін түрінде болуы керек."
        )

        return

    token = message.text.strip()

    if not token:

        await message.answer(
            "❌ Токен бос болмауы керек."
        )

        return

    if ":" not in token:

        await message.answer(
            "❌ Telegram Bot Token форматы дұрыс емес."
        )

        return

    if token == config.BOT_TOKEN:

        await message.answer(
            "❌ Бұл конструктордың токені.\n\n"
            "Child bot үшін BotFather-дан жеке токен беріңіз."
        )

        return

    data = await state.get_data()

    bot_name = data.get(
        "bot_name"
    )

    if not bot_name:

        await state.clear()

        await message.answer(
            "❌ Бот атауы табылмады. Қайта бастаңыз: /start"
        )

        return

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
            "❌ Ботты базаға сақтау кезінде қате шықты.\n\n"
            "Railway Logs бөлімін тексеріңіз."
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Бот сәтті қосылды!</b>\n\n"
        f"📛 Атауы: <b>{bot_name}</b>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        "🔴 Күйі: Тоқтатылды",
        reply_markup=manage_menu(
            bot_id
        ),
        parse_mode="HTML"
    )


# =========================================================
# LIST BOTS
# =========================================================

@dp.callback_query(
    F.data == "list_bots"
)
async def list_bots(
    callback: types.CallbackQuery
):

    if not await check_admin_callback(
        callback
    ):
        return

    # Telegram loading белгісін бірден тоқтатамыз
    await answer_callback(
        callback
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

        try:

            await callback.message.answer(
                "❌ Боттар тізімін оқу кезінде қате шықты.\n\n"
                f"Қате: {error}"
            )

        except Exception:

            pass

        return

    if not bots:

        try:

            await callback.message.edit_text(
                "📭 <b>Боттар жоқ.</b>\n\n"
                "➕ Жаңа бот қосу үшін батырманы басыңыз.",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )

        except TelegramBadRequest as error:

            if "message is not modified" not in str(
                error
            ).lower():

                await callback.message.answer(
                    "📭 <b>Боттар жоқ.</b>\n\n"
                    "➕ Жаңа бот қосу үшін батырманы басыңыз.",
                    reply_markup=main_menu(),
                    parse_mode="HTML"
                )

        except Exception as error:

            logger.exception(
                "Empty list error: %s",
                error
            )

            await callback.message.answer(
                "📭 Боттар жоқ.",
                reply_markup=main_menu()
            )

        return

    keyboard = []

    for item in bots:

        bot_id = item.get(
            "id"
        )

        bot_name = item.get(
            "bot_name",
            "Атаусыз"
        )

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
                text="➕ Жаңа бот қосу",
                callback_data="add_bot"
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

    text = (
        "📋 <b>Боттар тізімі</b>\n\n"
        f"Барлығы: <b>{len(bots)}</b>\n\n"
        "Басқару үшін ботты таңдаңыз:"
    )

    try:

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=keyboard
            ),
            parse_mode="HTML"
        )

    except TelegramBadRequest as error:

        if "message is not modified" not in str(
            error
        ).lower():

            logger.exception(
                "list_bots Telegram error: %s",
                error
            )

            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=keyboard
                ),
                parse_mode="HTML"
            )

    except Exception as error:

        logger.exception(
            "list_bots error: %s",
            error
        )

        await callback.message.answer(
            "❌ Тізімді көрсету кезінде қате шықты.\n\n"
            f"{error}"
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

    if not await check_admin_callback(
        callback
    ):
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

    text = (
        "🖥 <b>Ботты басқару</b>\n\n"
        f"📛 Атауы: <b>{bot_data['bot_name']}</b>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        f"📊 Күйі: {status_text}\n\n"
        "Төменнен қажетті әрекетті таңдаңыз:"
    )

    await safe_edit(
        callback,
        text,
        manage_menu(
            bot_id
        )
    )


# =========================================================
# START CHILD BOT
# =========================================================

@dp.callback_query(
    F.data.startswith("start_")
)
async def start_bot(
    callback: types.CallbackQuery
):

    if not await check_admin_callback(
        callback
    ):
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
        "🚀 Бот іске қосылуда..."
    )

    try:

        success, result = await runner_manager.start_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "start_sub_bot error: %s",
            error
        )

        success = False

        result = (
            "❌ Ботты іске қосу кезінде қате шықты.\n\n"
            f"{error}"
        )

    await callback.message.answer(
        result
    )


# =========================================================
# STOP CHILD BOT
# =========================================================

@dp.callback_query(
    F.data.startswith("stop_")
)
async def stop_bot(
    callback: types.CallbackQuery
):

    if not await check_admin_callback(
        callback
    ):
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
        "🛑 Бот тоқтатылуда..."
    )

    try:

        success, result = await runner_manager.stop_sub_bot(
            bot_id
        )

    except Exception as error:

        logger.exception(
            "stop_sub_bot error: %s",
            error
        )

        result = (
            "❌ Ботты тоқтату кезінде қате шықты.\n\n"
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

    if not await check_admin_callback(
        callback
    ):
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
        "Кодта Bot Token-ді жазбаңыз.\n\n"
        "Оның орнына:\n"
        "<code>os.getenv(\"BOT_TOKEN\")</code>\n\n"
        "қолданыңыз.\n\n"
        "⚠️ Қазіргі нұсқада код Telegram хабарламасы "
        "ретінде қабылданады.",
        parse_mode="HTML"
    )

    await answer_callback(
        callback
    )


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

    if not await check_admin_message(
        message
    ):
        return

    if not message.text:

        await message.answer(
            "❌ Python кодын мәтін ретінде жіберіңіз."
        )

        return

    code = message.text

    if not code.strip():

        await message.answer(
            "❌ Код бос болмауы керек."
        )

        return

    data = await state.get_data()

    bot_id = data.get(
        "bot_id"
    )

    if not bot_id:

        await state.clear()

        await message.answer(
            "❌ Бот ID табылмады.\n"
            "Қайтадан бастаңыз."
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
            "save_code error: %s",
            error
        )

        await message.answer(
            "❌ Кодты сақтау кезінде қате шықты.\n\n"
            f"Қате: {error}"
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Код сақталды!</b>\n\n"
        f"🤖 Бот: <b>{bot_data['bot_name']}</b>\n"
        f"📦 Version: <b>v{version}</b>\n"
        f"📏 Код көлемі: <b>{len(code)}</b> таңба",
        reply_markup=manage_menu(
            bot_id
        ),
        parse_mode="HTML"
    )


# =========================================================
# VARIABLES MENU
# =========================================================

@dp.callback_query(
    F.data.startswith("vars_")
)
async def variables_menu_handler(
    callback: types.CallbackQuery
):

    if not await check_admin_callback(
        callback
    ):
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
            "get_env_vars error: %s",
            error
        )

        await callback.message.answer(
            "❌ Variables оқу кезінде қате шықты.\n\n"
            f"{error}"
        )

        await answer_callback(
            callback
        )

        return

    text = (
        "🔐 <b>Environment Variables</b>\n\n"
    )

    if not variables:

        text += (
            "📭 Variable жоқ.\n\n"
            "➕ Жаңа variable қосуға болады."
        )

    else:

        for key in variables:

            text += (
                f"🔑 <code>{key}</code> = "
                "••••••••\n"
            )

    await safe_edit(
        callback,
        text,
        variables_menu(
            bot_id
        )
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

    if not await check_admin_callback(
        callback
    ):
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
        "<code>DATABASE_URL</code>\n"
        "<code>ADMIN_ID</code>",
        parse_mode="HTML"
    )

    await answer_callback(
        callback
    )


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

    if not await check_admin_message(
        message
    ):
        return

    if not message.text:

        await message.answer(
            "❌ Variable атауын мәтін түрінде жіберіңіз."
        )

        return

    key = message.text.strip().upper()

    if not key:

        await message.answer(
            "❌ Variable атауы бос болмауы керек."
        )

        return

    if len(key) > 100:

        await message.answer(
            "❌ Variable атауы тым ұзын."
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
        f"🔑 Variable: <code>{key}</code>\n\n"
        "📝 Енді оның мәнін жазыңыз:",
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

    if not await check_admin_message(
        message
    ):
        return

    if not message.text:

        await message.answer(
            "❌ Variable мәнін мәтін түрінде жіберіңіз."
        )

        return

    value = message.text

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
            "❌ Variable деректері табылмады."
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
            value
        )

    except Exception as error:

        logger.exception(
            "set_env_var error: %s",
            error
        )

        await message.answer(
            "❌ Variable сақтау кезінде қате шықты.\n\n"
            f"{error}"
        )

        return

    await state.clear()

    await message.answer(
        "✅ <b>Variable сақталды!</b>\n\n"
        f"🔑 Атауы: <code>{var_key}</code>\n"
        "🔒 Мәні: сақталды",
        reply_markup=manage_menu(
            bot_id
        ),
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

    if not await check_admin_callback(
        callback
    ):
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
            "get_logs error: %s",
            error
        )

        await callback.message.answer(
            "❌ Logs оқу кезінде қате шықты.\n\n"
            f"{error}"
        )

        await answer_callback(
            callback
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

            level = item.get(
                "level",
                "INFO"
            )

            message_text = item.get(
                "message",
                ""
            )

            created_at = item.get(
                "created_at",
                ""
            )

            lines.append(
                f"<code>{created_at}</code> "
                f"[{level}] "
                f"{message_text}"
            )

        text = (
            "📜 <b>Latest Logs</b>\n\n"
            + "\n".join(lines)
        )

    # Telegram maximum message size
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
# CANCEL
# =========================================================

@dp.message(
    F.text == "/cancel"
)
async def cancel_command(
    message: types.Message,
    state: FSMContext
):

    if not await check_admin_message(
        message
    ):
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

    if not await check_admin_message(
        message
    ):
        return

    await message.answer(
        "ℹ️ Түсінбедім.\n\n"
        "/start басыңыз немесе мәзірдегі батырмаларды пайдаланыңыз.",
        reply_markup=main_menu()
    )


# =========================================================
# START APPLICATION
# =========================================================

async def main():

    logger.info(
        "🚀 Конструктор іске қосылуда..."
    )

    try:

        await database.init_db()

        logger.info(
            "✅ Database дайын"
        )

    except Exception as error:

        logger.exception(
            "❌ Database initialization error: %s",
            error
        )

        raise

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


# =========================================================
# ENTRY POINT
# =========================================================

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
