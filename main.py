import asyncio
import logging

from aiogram import (
    Bot,
    Dispatcher,
    F,
    types
)

from aiogram.filters import (
    CommandStart
)

from aiogram.fsm.context import (
    FSMContext
)

from aiogram.fsm.state import (
    State,
    StatesGroup
)

from aiogram.fsm.storage.memory import (
    MemoryStorage
)

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiogram.exceptions import (
    TelegramBadRequest
)

import config
import database
from runner import runner_manager


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)


bot = Bot(
    token=config.BOT_TOKEN
)


dp = Dispatcher(
    storage=MemoryStorage()
)


class AddBotStates(
    StatesGroup
):

    waiting_for_name = State()

    waiting_for_token = State()


class CodeStates(
    StatesGroup
):

    waiting_for_code = State()


class VarStates(
    StatesGroup
):

    waiting_for_key = State()

    waiting_for_value = State()


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
    bot_id
):

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🚀 Start",

                    callback_data=(
                        f"start_{bot_id}"
                    )

                ),

                InlineKeyboardButton(

                    text="🛑 Stop",

                    callback_data=(
                        f"stop_{bot_id}"
                    )

                )

            ],

            [

                InlineKeyboardButton(

                    text="📝 Код",

                    callback_data=(
                        f"code_{bot_id}"
                    )

                )

            ],

            [

                InlineKeyboardButton(

                    text="🔐 Variables",

                    callback_data=(
                        f"vars_{bot_id}"
                    )

                )

            ],

            [

                InlineKeyboardButton(

                    text="📜 Logs",

                    callback_data=(
                        f"logs_{bot_id}"
                    )

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


def back_manage_menu(
    bot_id
):

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="⬅️ Артқа",

                    callback_data=(
                        f"manage_{bot_id}"
                    )

                )

            ]

        ]

    )


@dp.message()
async def security_check(
    message: types.Message
):

    if (
        message.from_user.id
        != config.ADMIN_ID
    ):

        await message.answer(
            "⛔ Рұқсат жоқ."
        )

        return


@dp.callback_query()
async def callback_security(
    callback: types.CallbackQuery
):

    if (
        callback.from_user.id
        != config.ADMIN_ID
    ):

        await callback.answer(
            "⛔ Рұқсат жоқ.",
            show_alert=True
        )

        return


@dp.message(
    CommandStart()
)
async def start_command(
    message: types.Message
):

    if (
        message.from_user.id
        != config.ADMIN_ID
    ):

        return


    await message.answer(

        "🛠 Бот Конструктор\n\n"
        "Мұнда өз Telegram "
        "боттарыңызды қосып, "
        "кодын сақтап және "
        "іске қоса аласыз.",

        reply_markup=main_menu()

    )


@dp.callback_query(
    F.data == "main_menu"
)
async def back_main(
    callback: types.CallbackQuery
):

    await safe_edit(

        callback,

        "🏠 Басты мәзір",

        main_menu()

    )


@dp.callback_query(
    F.data == "add_bot"
)
async def add_bot(
    callback: types.CallbackQuery,
    state: FSMContext
):

    await state.set_state(

        AddBotStates.waiting_for_name

    )


    await callback.message.answer(

        "✏️ Боттың атауын жазыңыз:"

    )


    await callback.answer()


@dp.message(
    AddBotStates.waiting_for_name
)
async def get_bot_name(
    message: types.Message,
    state: FSMContext
):

    if not message.text:

        return


    await state.update_data(

        bot_name=message.text.strip()

    )


    await state.set_state(

        AddBotStates.waiting_for_token

    )


    await message.answer(

        "🔑 Бот токенін жіберіңіз:"

    )


@dp.message(
    AddBotStates.waiting_for_token
)
async def get_bot_token(
    message: types.Message,
    state: FSMContext
):

    if not message.text:

        return


    data = await state.get_data()


    bot_id = await database.add_bot(

        message.from_user.id,

        data["bot_name"],

        message.text.strip()

    )


    await state.clear()


    await message.answer(

        f"✅ Бот қосылды!\n\n"
        f"ID: {bot_id}",

        reply_markup=main_menu()

    )


@dp.callback_query(
    F.data == "list_bots"
)
async def list_bots(
    callback: types.CallbackQuery
):

    bots = (
        await database.get_user_bots(

            callback.from_user.id

        )
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

                    text=(
                        f"{icon} "
                        f"{item['bot_name']}"
                    ),

                    callback_data=(
                        f"manage_{item['id']}"
                    )

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


@dp.callback_query(
    F.data.startswith(
        "manage_"
    )
)
async def manage_bot(
    callback: types.CallbackQuery
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    bot_data = (
        await database.get_bot(bot_id)
    )


    if not bot_data:

        await callback.answer(

            "Бот табылмады.",

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

        f"📛 Атауы: "
        f"{bot_data['bot_name']}\n"

        f"📊 Күйі: "
        f"{status}\n"

        f"🆔 ID: "
        f"{bot_id}"

    )


    await safe_edit(

        callback,

        text,

        manage_menu(bot_id)

    )


@dp.callback_query(
    F.data.startswith(
        "start_"
    )
)
async def start_bot(
    callback: types.CallbackQuery
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    success, result = (

        await runner_manager.start_sub_bot(

            bot_id

        )

    )


    await callback.answer(

        result,

        show_alert=not success

    )


    if success:

        await callback.message.answer(

            result

        )


@dp.callback_query(
    F.data.startswith(
        "stop_"
    )
)
async def stop_bot(
    callback: types.CallbackQuery
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    success, result = (

        await runner_manager.stop_sub_bot(

            bot_id

        )

    )


    await callback.answer(

        result,

        show_alert=not success

    )


    await callback.message.answer(

        result

    )


@dp.callback_query(
    F.data.startswith(
        "code_"
    )
)
async def code_menu(
    callback: types.CallbackQuery,
    state: FSMContext
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    await state.update_data(

        bot_id=bot_id

    )


    await state.set_state(

        CodeStates.waiting_for_code

    )


    await callback.message.answer(

        "📝 Python кодын толық "
        "жіберіңіз.\n\n"

        "Бот токенін кодқа "
        "жазбаңыз.\n\n"

        "Код ішінде:\n"

        "os.getenv('BOT_TOKEN')\n\n"

        "деп қолданыңыз."

    )


    await callback.answer()


@dp.message(
    CodeStates.waiting_for_code
)
async def save_code(
    message: types.Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(

            "❌ Тек мәтін түріндегі "
            "Python кодын жіберіңіз."

        )

        return


    data = await state.get_data()


    version = (

        await database.save_code_version(

            data["bot_id"],

            message.text

        )

    )


    await state.clear()


    await message.answer(

        f"✅ Код сақталды!\n\n"
        f"📦 Version: v{version}",

        reply_markup=manage_menu(

            data["bot_id"]

        )

    )


@dp.callback_query(
    F.data.startswith(
        "vars_"
    )
)
async def variables_menu(
    callback: types.CallbackQuery
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    variables = (

        await database.get_env_vars(

            bot_id

        )

    )


    text = (

        "🔐 Environment Variables\n\n"

    )


    if not variables:

        text += "📭 Айнымалылар жоқ."

    else:

        for key in variables:

            text += (

                f"🔑 {key} = "
                f"********\n"

            )


    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="➕ Variable қосу",

                    callback_data=(
                        f"addvar_{bot_id}"
                    )

                )

            ],

            [

                InlineKeyboardButton(

                    text="⬅️ Артқа",

                    callback_data=(
                        f"manage_{bot_id}"
                    )

                )

            ]

        ]

    )


    await safe_edit(

        callback,

        text,

        keyboard

    )


@dp.callback_query(
    F.data.startswith(
        "addvar_"
    )
)
async def add_variable(
    callback: types.CallbackQuery,
    state: FSMContext
):

    bot_id = int(

        callback.data.split("_")[1]

    )


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


@dp.message(
    VarStates.waiting_for_key
)
async def get_variable_key(
    message: types.Message,
    state: FSMContext
):

    key = (

        message.text.strip().upper()

    )


    await state.update_data(

        var_key=key

    )


    await state.set_state(

        VarStates.waiting_for_value

    )


    await message.answer(

        "📝 Variable мәнін жазыңыз:"

    )


@dp.message(
    VarStates.waiting_for_value
)
async def get_variable_value(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()


    await database.set_env_var(

        data["bot_id"],

        data["var_key"],

        message.text

    )


    await state.clear()


    await message.answer(

        "✅ Variable сақталды.",

        reply_markup=manage_menu(

            data["bot_id"]

        )

    )


@dp.callback_query(
    F.data.startswith(
        "logs_"
    )
)
async def logs(
    callback: types.CallbackQuery
):

    bot_id = int(

        callback.data.split("_")[1]

    )


    logs_data = (

        await database.get_logs(

            bot_id

        )

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


            message = item.get(

                "message",

                ""

            )


            lines.append(

                f"[{level}] "
                f"{message}"

            )


        text = (

            "📜 Latest Logs\n\n"

            + "\n".join(lines)

        )


    if len(text) > 3800:

        text = text[-3800:]

        text = (

            "📜 Latest Logs\n\n"

            + text

        )


    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🔄 Жаңарту",

                    callback_data=(
                        f"logs_{bot_id}"
                    )

                )

            ],

            [

                InlineKeyboardButton(

                    text="⬅️ Артқа",

                    callback_data=(
                        f"manage_{bot_id}"
                    )

                )

            ]

        ]

    )


    await safe_edit(

        callback,

        text,

        keyboard

    )


async def safe_edit(
    callback,
    text,
    keyboard=None
):

    try:

        await callback.message.edit_text(

            text=text,

            reply_markup=keyboard

        )


    except TelegramBadRequest as error:

        if (
            "message is not modified"
            not in str(error).lower()
        ):

            raise


    try:

        await callback.answer()

    except Exception:

        pass


async def main():

    if not config.BOT_TOKEN:

        raise RuntimeError(

            "BOT_TOKEN Railway Variables "
            "ішінде көрсетілмеген."

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
