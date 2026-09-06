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
        await callback.answer(
            "⛔ Рұқсат жоқ.",
            show_alert=True
        )
        return False

    return True


async def get_owned_bot(bot_id: int, user_id: int):
    bot_data = await database.get_bot(bot_id)

    if not bot_data:
        return None

    if bot_data["user_id"] != user_id:
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
                    text="⬅️ Артқа",
                    callback_data="list_bots"
                )
            ]
        ]
    )


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
        if "message is not modified" not in str(error).lower():
            raise

    try:
        await callback.answer()
    except Exception:
        pass


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_command(message: types.Message):
    if not await check_admin_message(message):
        return

    await message.answer(
        "🛠 Бот Конструктор\n\n"
        "Мұнда өз Telegram боттарыңызды "
        "қосып, кодын сақтап және іске "
        "қоса аласыз.",
        reply_markup=main_menu()
    )


# =========================================================
# MAIN MENU
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def back_main(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    await safe_edit(
        callback,
        "🏠 Басты мәзір",
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

    await state.set_state(
        AddBotStates.waiting_for_name
    )

    await callback.message.answer(
        "✏️ Боттың атауын жазыңыз:"
    )

    await callback.answer()


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

    bot_name = message.text.strip()

    if not bot_name:
        await message.answer(
            "❌ Бот атауы бос болмауы керек."
        )
        return

    await state.update_data(
        bot_name=bot_name
    )

    await state.set_state(
        AddBotStates.waiting_for_token
    )

    await message.answer(
        "🔑 BotFather берген бот токенін жіберіңіз:"
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
            "❌ Токен мәтін түрінде болуы керек."
        )
        return

    token = message.text.strip()

    if not token:
        await message.answer(
            "❌ Токен бос болмауы керек."
        )
        return

    data = await state.get_data()

    # Конструктордың токенін child bot ретінде қолдануға тыйым салу
    if token == config.BOT_TOKEN:
        await message.answer(
            "❌ Бұл конструктор боттың токені.\n\n"
            "Child bot үшін BotFather-дан жеке токен қолданыңыз."
        )
        return

    # Telegram token форматына базалық тексеру
    if ":" not in token:
        await message.answer(
            "❌ Токен форматы дұрыс емес."
        )
        return

    bot_id = await database.add_bot(
        message.from_user.id,
        data["bot_name"],
        token
    )

    await state.clear()

    await message.answer(
        f"✅ Бот қосылды!\n\n"
        f"📛 Атауы: {data['bot_name']}\n"
        f"🆔 ID: {bot_id}",
        reply_markup=main_menu()
    )


# =========================================================
# LIST BOTS
# =========================================================

@dp.callback_query(F.data == "list_bots")
async def list_bots(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    bots = await database.get_user_bots(
        callback.from_user.id
    )

    if not bots:
        await safe_edit(
            callback,
            "📭 Боттар жоқ.",
            main_menu()
        )
        return

    keyboard = []

    for item in bots:
        status = item["status"]

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
                text="⬅️ Басты мәзір",
                callback_data="main_menu"
            )
        ]
    )

    await safe_edit(
        callback,
        "📋 Менің боттарым:",
        InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


# =========================================================
# MANAGE BOT
# =========================================================

@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады немесе сізге тиесілі емес.",
            show_alert=True
        )
        return

    status_map = {
        "running": "🟢 Қосулы",
        "stopped": "🔴 Тоқтатылды",
        "crashed": "💥 Қате"
    }

    status = status_map.get(
        bot_data["status"],
        "❓ Белгісіз"
    )

    text = (
        "🖥 Бот басқару\n\n"
        f"📛 Атауы: {bot_data['bot_name']}\n"
        f"📊 Күйі: {status}\n"
        f"🆔 ID: {bot_id}"
    )

    await safe_edit(
        callback,
        text,
        manage_menu(bot_id)
    )


# =========================================================
# START BOT
# =========================================================

@dp.callback_query(F.data.startswith("start_"))
async def start_bot(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    success, result = await runner_manager.start_sub_bot(
        bot_id
    )

    await callback.answer(
        result,
        show_alert=not success
    )

    if success:
        await callback.message.answer(
            result
        )


# =========================================================
# STOP BOT
# =========================================================

@dp.callback_query(F.data.startswith("stop_"))
async def stop_bot(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    success, result = await runner_manager.stop_sub_bot(
        bot_id
    )

    await callback.answer(
        result,
        show_alert=not success
    )

    await callback.message.answer(
        result
    )


# =========================================================
# CODE MENU
# =========================================================

@dp.callback_query(F.data.startswith("code_"))
async def code_menu(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        CodeStates.waiting_for_code
    )

    await callback.message.answer(
        "📝 Python кодын толық жіберіңіз.\n\n"
        "⚠️ Бот токенін кодқа жазбаңыз.\n\n"
        "Код ішінде:\n"
        "os.getenv('BOT_TOKEN')\n\n"
        "деп қолданыңыз."
    )

    await callback.answer()


@dp.message(CodeStates.waiting_for_code)
async def save_code(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Тек мәтін түріндегі Python кодын жіберіңіз."
        )
        return

    data = await state.get_data()

    bot_id = data.get("bot_id")

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

    version = await database.save_code_version(
        bot_id,
        message.text
    )

    await state.clear()

    await message.answer(
        f"✅ Код сақталды!\n\n"
        f"📦 Version: v{version}",
        reply_markup=manage_menu(bot_id)
    )


# =========================================================
# VARIABLES
# =========================================================

@dp.callback_query(F.data.startswith("vars_"))
async def variables_menu(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    variables = await database.get_env_vars(
        bot_id
    )

    text = "🔐 Environment Variables\n\n"

    if not variables:
        text += "📭 Айнымалылар жоқ."
    else:
        for key in variables:
            text += f"🔑 {key} = ********\n"

    keyboard = InlineKeyboardMarkup(
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

    await safe_edit(
        callback,
        text,
        keyboard
    )


@dp.callback_query(F.data.startswith("addvar_"))
async def add_variable(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате бот ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        VarStates.waiting_for_key
    )

    await callback.message.answer(
        "🔑 Variable атауын жазыңыз.\n\n"
        "Мысалы:\n"
        "API_KEY"
    )

    await callback.answer()


@dp.message(VarStates.waiting_for_key)
async def get_variable_key(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
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

    data = await state.get_data()

    bot_id = data.get("bot_id")

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
        "📝 Variable мәнін жазыңыз:"
    )


@dp.message(VarStates.waiting_for_value)
async def get_variable_value(
    message: types.Message,
    state: FSMContext
):
    if not await check_admin_message(message):
        return

    if not message.text:
        await message.answer(
            "❌ Variable мәнін мәтін түрінде жіберіңіз."
        )
        return

    data = await state.get_data()

    bot_id = data.get("bot_id")
    var_key = data.get("var_key")

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

    await database.set_env_var(
        bot_id,
        var_key,
        message.text
    )

    await state.clear()

    await message.answer(
        "✅ Variable сақталды.",
        reply_markup=manage_menu(bot_id)
    )


# =========================================================
# LOGS
# =========================================================

@dp.callback_query(F.data.startswith("logs_"))
async def logs(callback: types.CallbackQuery):
    if not await check_admin_callback(callback):
        return

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Қате bot ID.",
            show_alert=True
        )
        return

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "⛔ Бот табылмады.",
            show_alert=True
        )
        return

    logs_data = await database.get_logs(
        bot_id
    )

    if not logs_data:
        text = "📭 Log жоқ."
    else:
        lines = []

        for item in logs_data:
            level = item.get(
                "level",
                "INFO"
            )

            log_message = item.get(
                "message",
                ""
            )

            lines.append(
                f"[{level}] {log_message}"
            )

        text = (
            "📜 Latest Logs\n\n"
            + "\n".join(lines)
        )

    if len(text) > 3800:
        text = (
            "📜 Latest Logs\n\n"
            + text[-3700:]
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
# UNKNOWN TEXT
# =========================================================

@dp.message()
async def unknown_message(message: types.Message):
    if not await check_admin_message(message):
        return

    await message.answer(
        "ℹ️ Команданы немесе мәзірдегі батырманы пайдаланыңыз.",
        reply_markup=main_menu()
    )


# =========================================================
# MAIN
# =========================================================

async def main():
    if not config.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN Railway Variables ішінде көрсетілмеген."
        )

    await database.init_db()

    logging.info(
        "🚀 Конструктор іске қосылды"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())
