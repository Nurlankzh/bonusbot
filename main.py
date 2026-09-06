import asyncio
import html
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

import config
import database
from runner import runner_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# FSM STATES
# ============================================================

class AddBotStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_token = State()


class CodeStates(StatesGroup):
    waiting_for_code = State()


class VariableStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_value = State()


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


async def admin_callback(callback: types.CallbackQuery) -> bool:
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


async def owned_bot(bot_id: int, user_id: int):
    bot_data = await database.get_bot(bot_id)

    if not bot_data:
        return None

    if bot_data["user_id"] != user_id:
        return None

    return bot_data


async def safe_edit(
    message: types.Message,
    text: str,
    reply_markup=None,
    parse_mode=None
):
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            try:
                await message.answer(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception:
                pass
    except Exception:
        try:
            await message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception:
            pass


async def send_long_message(
    message: types.Message,
    text: str,
    parse_mode=None
):
    limit = 3900

    if len(text) <= limit:
        await message.answer(
            text,
            parse_mode=parse_mode
        )
        return

    for i in range(0, len(text), limit):
        chunk = text[i:i + limit]

        try:
            await message.answer(
                chunk,
                parse_mode=parse_mode
            )
        except Exception:
            await message.answer(chunk)


# ============================================================
# KEYBOARDS
# ============================================================

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


def manage_keyboard(bot_id: int, running: bool):
    if running:
        start_button = InlineKeyboardButton(
            text="🟢 Іске қосылған",
            callback_data=f"noop_{bot_id}"
        )
    else:
        start_button = InlineKeyboardButton(
            text="🚀 Start",
            callback_data=f"start_{bot_id}"
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                start_button,
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
                    text="🗑 Ботты өшіру",
                    callback_data=f"delete_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Артқа",
                    callback_data="bots"
                ),
                InlineKeyboardButton(
                    text="🏠 Басты мәзір",
                    callback_data="home"
                )
            ]
        ]
    )


def variables_keyboard(bot_id: int):
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


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ Бұл конструкторға кіруге рұқсатыңыз жоқ."
        )
        return

    await message.answer(
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Бірнеше Telegram ботты осы жерден басқаруға болады.\n\n"
        "➕ Бот қосыңыз немесе 📋 боттарыңызды басқарыңыз.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# HOME
# ============================================================

@dp.callback_query(F.data == "home")
async def home_handler(callback: types.CallbackQuery, state: FSMContext):
    if not await admin_callback(callback):
        return

    await state.clear()
    await callback.answer()

    await safe_edit(
        callback.message,
        "🛠 <b>Telegram Bot Constructor</b>\n\n"
        "Қажетті әрекетті таңдаңыз:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# ADD BOT
# ============================================================

@dp.callback_query(F.data == "add_bot")
async def add_bot_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    await state.set_state(AddBotStates.waiting_for_name)

    await safe_edit(
        callback.message,
        "➕ <b>Жаңа бот қосу</b>\n\n"
        "1️⃣ Боттың атауын немесе username енгізіңіз.\n\n"
        "Мысалы:\n"
        "<code>My Test Bot</code>\n\n"
        "немесе\n"
        "<code>@my_test_bot</code>\n\n"
        "❌ Болдырмау үшін /cancel",
        parse_mode="HTML"
    )


@dp.message(AddBotStates.waiting_for_name)
async def receive_bot_name(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    name = (message.text or "").strip()

    if not name:
        await message.answer("❌ Атауы бос болмауы керек.")
        return

    if len(name) > 100:
        await message.answer(
            "❌ Атау 100 символдан аспауы керек."
        )
        return

    await state.update_data(bot_name=name)
    await state.set_state(AddBotStates.waiting_for_token)

    await message.answer(
        "🔐 Енді <b>child bot токенін</b> жіберіңіз.\n\n"
        "Токенді @BotFather арқылы алған болуыңыз керек.\n\n"
        "Мысалы:\n"
        "<code>123456789:AA...</code>\n\n"
        "⚠️ Master Constructor токенін енгізбеңіз.",
        parse_mode="HTML"
    )


@dp.message(AddBotStates.waiting_for_token)
async def receive_bot_token(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    token = (message.text or "").strip()

    if not token or ":" not in token:
        await message.answer(
            "❌ Токен форматы дұрыс емес."
        )
        return

    if token == config.BOT_TOKEN:
        await message.answer(
            "❌ Constructor токенін child bot ретінде қолдануға болмайды."
        )
        return

    try:
        test_bot = Bot(token=token)
        bot_info = await test_bot.get_me()
        await test_bot.session.close()

    except Exception as error:
        await message.answer(
            "❌ Бұл токен жарамсыз.\n\n"
            f"<code>{html.escape(str(error)[:1500])}</code>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    bot_name = data.get("bot_name", bot_info.username or "Bot")

    bot_id = await database.add_bot(
        message.from_user.id,
        bot_name,
        token
    )

    await state.clear()

    await message.answer(
        "✅ <b>Бот қосылды!</b>\n\n"
        f"📛 Атауы: <b>{html.escape(bot_name)}</b>\n"
        f"🤖 Username: @{html.escape(bot_info.username or 'unknown')}\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        "🔴 Күйі: Тоқтатылды",
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
        ),
        parse_mode="HTML"
    )


# ============================================================
# BOT LIST
# ============================================================

@dp.callback_query(F.data == "bots")
async def bots_handler(callback: types.CallbackQuery):
    if not await admin_callback(callback):
        return

    await callback.answer()

    bots = await database.get_user_bots(
        callback.from_user.id
    )

    if not bots:
        await safe_edit(
            callback.message,
            "📋 <b>Боттар тізімі</b>\n\n"
            "Әзірге бот жоқ.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➕ Бот қосу",
                            callback_data="add_bot"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🏠 Басты мәзір",
                            callback_data="home"
                        )
                    ]
                ]
            ),
            parse_mode="HTML"
        )
        return

    keyboard = []

    for bot_data in bots:
        status = bot_data["status"]

        if runner_manager.is_running(bot_data["id"]):
            status_icon = "🟢"
        elif status == "crashed":
            status_icon = "🔴"
        else:
            status_icon = "🔴"

        keyboard.append([
            InlineKeyboardButton(
                text=(
                    f"{status_icon} "
                    f"{bot_data['bot_name']} "
                    f"#{bot_data['id']}"
                ),
                callback_data=f"manage_{bot_data['id']}"
            )
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(
                text="➕ Жаңа бот",
                callback_data="add_bot"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Жаңарту",
                callback_data="bots"
            ),
            InlineKeyboardButton(
                text="🏠 Басты мәзір",
                callback_data="home"
            )
        ]
    ])

    await safe_edit(
        callback.message,
        "📋 <b>Боттар тізімі</b>\n\n"
        "Басқару үшін ботты таңдаңыз:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        ),
        parse_mode="HTML"
    )


# ============================================================
# MANAGE BOT
# ============================================================

@dp.callback_query(F.data.startswith("manage_"))
async def manage_handler(callback: types.CallbackQuery):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(callback.data.split("_", 1)[1])
    except Exception:
        return

    bot_data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    running = runner_manager.is_running(bot_id)

    if running:
        status = "🟢 Жұмыс істеп тұр"
    elif bot_data["status"] == "crashed":
        status = "🔴 Қате арқылы тоқтаған"
    else:
        status = "🔴 Тоқтатылды"

    process_info = await runner_manager.get_process_info(bot_id)

    pid_text = ""

    if process_info and process_info["running"]:
        pid_text = (
            f"\n🆔 PID: <code>{process_info['pid']}</code>"
        )

    await safe_edit(
        callback.message,
        "🤖 <b>Ботты басқару</b>\n\n"
        f"📛 Атауы: <b>{html.escape(bot_data['bot_name'])}</b>\n"
        f"🆔 ID: <code>{bot_id}</code>\n"
        f"📊 Күйі: {status}"
        f"{pid_text}\n\n"
        "Қажетті әрекетті таңдаңыз:",
        reply_markup=manage_keyboard(
            bot_id,
            running
        ),
        parse_mode="HTML"
    )


# ============================================================
# START CHILD
# ============================================================

@dp.callback_query(F.data.startswith("start_"))
async def start_child_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    try:
        await callback.answer(
            "🚀 Іске қосылуда..."
        )
    except Exception:
        pass

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        await callback.message.answer(
            "❌ Бот ID дұрыс емес."
        )
        return

    try:
        data = await owned_bot(
            bot_id,
            callback.from_user.id
        )

        if not data:
            await callback.message.answer(
                "⛔ Бұл бот табылмады немесе сізге тиесілі емес."
            )
            return

        success, result = await runner_manager.start_sub_bot(
            bot_id
        )

        await callback.message.answer(result)

    except Exception as error:
        logger.exception(
            "START CHILD BOT ERROR"
        )

        await callback.message.answer(
            "❌ Ботты іске қосу кезінде қате шықты.\n\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# STOP CHILD
# ============================================================

@dp.callback_query(F.data.startswith("stop_"))
async def stop_child_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer(
        "🛑 Тоқтатылуда..."
    )

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    try:
        success, result = await runner_manager.stop_sub_bot(
            bot_id
        )

        await callback.message.answer(result)

    except Exception as error:
        await callback.message.answer(
            "❌ Stop қатесі:\n\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# RESTART CHILD
# ============================================================

@dp.callback_query(F.data.startswith("restart_"))
async def restart_child_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer(
        "🔄 Restart..."
    )

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    try:
        success, result = await runner_manager.restart_sub_bot(
            bot_id
        )

        await callback.message.answer(result)

    except Exception as error:
        await callback.message.answer(
            "❌ Restart қатесі:\n\n"
            f"<code>{html.escape(str(error)[:3000])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# CODE MENU
# ============================================================

@dp.callback_query(F.data.startswith("code_"))
async def code_menu_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    await state.clear()
    await state.update_data(
        code_bot_id=bot_id
    )
    await state.set_state(
        CodeStates.waiting_for_code
    )

    await callback.message.answer(
        "📝 <b>Python код енгізу</b>\n\n"
        "Екі тәсіл бар:\n\n"
        "1️⃣ Python кодын хабарлама ретінде жіберу\n"
        "2️⃣ <code>.py</code> файл жіберу\n\n"
        "📦 2000+ жолдық кодты файл ретінде жіберген дұрыс.\n\n"
        "Код сақталған кезде автоматты түрде жаңа Version жасалады.\n\n"
        "❌ Болдырмау: /cancel",
        parse_mode="HTML"
    )


# ============================================================
# SAVE CODE FROM TEXT
# ============================================================

@dp.message(
    CodeStates.waiting_for_code,
    F.text
)
async def receive_code_text(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    code = message.text or ""

    data = await state.get_data()
    bot_id = data.get("code_bot_id")

    if not bot_id:
        await state.clear()
        await message.answer(
            "❌ Бот анықталмады."
        )
        return

    if len(code.encode("utf-8")) > config.MAX_CODE_SIZE:
        await message.answer(
            "❌ Код тым үлкен."
        )
        return

    version = await database.save_code_version(
        bot_id,
        code
    )

    await state.clear()

    await message.answer(
        "✅ <b>Код сақталды!</b>\n\n"
        f"🤖 Bot ID: <code>{bot_id}</code>\n"
        f"📦 Version: <b>v{version}</b>\n\n"
        "🚀 Start басқанда осы ең соңғы Version іске қосылады.",
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
                        text="📦 Version",
                        callback_data=f"versions_{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🤖 Басқару",
                        callback_data=f"manage_{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# ============================================================
# SAVE CODE FROM .PY FILE
# ============================================================

@dp.message(
    CodeStates.waiting_for_code,
    F.document
)
async def receive_code_file(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    document = message.document

    if not document:
        return

    filename = document.file_name or ""

    if not filename.lower().endswith(".py"):
        await message.answer(
            "❌ Тек <code>.py</code> файл қабылданады.",
            parse_mode="HTML"
        )
        return

    if document.file_size:
        if document.file_size > config.MAX_CODE_SIZE:
            await message.answer(
                "❌ Файл тым үлкен."
            )
            return

    data = await state.get_data()
    bot_id = data.get("code_bot_id")

    if not bot_id:
        await state.clear()
        await message.answer(
            "❌ Бот анықталмады."
        )
        return

    try:
        buffer = BytesIO()

        bot = message.bot

        await bot.download(
            document,
            destination=buffer
        )

        raw = buffer.getvalue()

        if len(raw) > config.MAX_CODE_SIZE:
            await message.answer(
                "❌ Файлдың нақты көлемі лимиттен үлкен."
            )
            return

        try:
            code = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                code = raw.decode("utf-8-sig")
            except Exception:
                await message.answer(
                    "❌ Python файл UTF-8 форматында болуы керек."
                )
                return

        if not code.strip():
            await message.answer(
                "❌ Файл бос."
            )
            return

        version = await database.save_code_version(
            bot_id,
            code
        )

        await state.clear()

        await message.answer(
            "✅ <b>Python файл сақталды!</b>\n\n"
            f"📄 Файл: <code>{html.escape(filename)}</code>\n"
            f"📏 Көлемі: <code>{len(raw)}</code> bytes\n"
            f"🤖 Bot ID: <code>{bot_id}</code>\n"
            f"📦 Version: <b>v{version}</b>\n\n"
            "🚀 Start басқанда осы Version іске қосылады.",
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
                            text="📦 Version",
                            callback_data=f"versions_{bot_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🤖 Басқару",
                            callback_data=f"manage_{bot_id}"
                        )
                    ]
                ]
            ),
            parse_mode="HTML"
        )

    except Exception as error:
        logger.exception(
            "PYTHON FILE ERROR"
        )

        await message.answer(
            "❌ Файлды оқу кезінде қате шықты.\n\n"
            f"<code>{html.escape(str(error)[:2500])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# VERSIONS
# ============================================================

@dp.callback_query(F.data.startswith("versions_"))
async def versions_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    versions = await database.get_code_versions(
        bot_id
    )

    if not versions:
        await safe_edit(
            callback.message,
            "📦 <b>Versions</b>\n\n"
            "❌ Әзірге код Version жоқ.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📝 Код қосу",
                            callback_data=f"code_{bot_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Артқа",
                            callback_data=f"manage_{bot_id}"
                        )
                    ]
                ]
            ),
            parse_mode="HTML"
        )
        return

    keyboard = []

    for version in versions:
        number = version["version"]

        keyboard.append([
            InlineKeyboardButton(
                text=f"👁 v{number}",
                callback_data=f"viewver_{bot_id}_{number}"
            ),
            InlineKeyboardButton(
                text=f"🗑 v{number}",
                callback_data=f"delver_{bot_id}_{number}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="🔄 Жаңарту",
            callback_data=f"versions_{bot_id}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Артқа",
            callback_data=f"manage_{bot_id}"
        )
    ])

    await safe_edit(
        callback.message,
        "📦 <b>Код Versions</b>\n\n"
        f"🤖 Bot ID: <code>{bot_id}</code>\n"
        f"📊 Барлығы: <b>{len(versions)}</b>\n\n"
        "👁 — кодты көру\n"
        "🗑 — Version өшіру",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        ),
        parse_mode="HTML"
    )


# ============================================================
# VIEW VERSION
# ============================================================

@dp.callback_query(F.data.startswith("viewver_"))
async def view_version_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        parts = callback.data.split("_")

        bot_id = int(parts[1])
        version = int(parts[2])

    except Exception:
        await callback.message.answer(
            "❌ Version ID дұрыс емес."
        )
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    version_data = await database.get_code_version(
        bot_id,
        version
    )

    if not version_data:
        await callback.message.answer(
            "❌ Version табылмады."
        )
        return

    code = version_data["code"]

    header = (
        f"📦 <b>Version v{version}</b>\n"
        f"🤖 Bot ID: <code>{bot_id}</code>\n"
        f"📏 {len(code)} символ\n\n"
    )

    await send_long_message(
        callback.message,
        header + code
    )

    await callback.message.answer(
        "Version басқару:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 Өшіру",
                        callback_data=f"delver_{bot_id}_{version}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Versions",
                        callback_data=f"versions_{bot_id}"
                    )
                ]
            ]
        )
    )


# ============================================================
# DELETE VERSION CONFIRM
# ============================================================

@dp.callback_query(F.data.startswith("delver_"))
async def delete_version_confirm(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        parts = callback.data.split("_")

        bot_id = int(parts[1])
        version = int(parts[2])

    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        return

    await callback.message.answer(
        f"⚠️ <b>Version v{version} өшірілсін бе?</b>\n\n"
        "Бұл әрекетті қайтару мүмкін емес.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Иә, өшіру",
                        callback_data=f"confirmdelver_{bot_id}_{version}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Жоқ",
                        callback_data=f"versions_{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# ============================================================
# DELETE VERSION
# ============================================================

@dp.callback_query(F.data.startswith("confirmdelver_"))
async def delete_version_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer(
        "🗑 Өшірілуде..."
    )

    try:
        parts = callback.data.split("_")

        bot_id = int(parts[1])
        version = int(parts[2])

    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    try:
        deleted = await database.delete_code_version(
            bot_id,
            version
        )

        if deleted:
            await callback.message.answer(
                f"✅ Version v{version} өшірілді."
            )
        else:
            await callback.message.answer(
                "❌ Version табылмады."
            )

        await versions_handler(callback)

    except Exception as error:
        logger.exception(
            "DELETE VERSION ERROR"
        )

        await callback.message.answer(
            "❌ Version өшіру кезінде қате:\n\n"
            f"<code>{html.escape(str(error)[:2000])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# VARIABLES
# ============================================================

@dp.callback_query(F.data.startswith("vars_"))
async def variables_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        return

    variables = await database.get_env_vars(
        bot_id
    )

    text = (
        "🔐 <b>Variables</b>\n\n"
        f"🤖 Bot ID: <code>{bot_id}</code>\n\n"
    )

    if not variables:
        text += "❌ Variable жоқ.\n"
    else:
        text += "📋 Орнатылған Variables:\n\n"

        for key, value in variables.items():
            safe_value = html.escape(str(value))

            if len(safe_value) > 100:
                safe_value = safe_value[:100] + "..."

            text += (
                f"🔑 <code>{html.escape(str(key))}</code>\n"
                f"💾 <code>{safe_value}</code>\n\n"
            )

    keyboard = []

    for key in variables.keys():
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 {key}",
                callback_data=f"delvar_{bot_id}_{key}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➕ Variable қосу",
            callback_data=f"addvar_{bot_id}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="🔄 Жаңарту",
            callback_data=f"vars_{bot_id}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Артқа",
            callback_data=f"manage_{bot_id}"
        )
    ])

    await safe_edit(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        ),
        parse_mode="HTML"
    )


# ============================================================
# ADD VARIABLE
# ============================================================

@dp.callback_query(F.data.startswith("addvar_"))
async def add_variable_handler(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        return

    await state.clear()

    await state.update_data(
        variable_bot_id=bot_id
    )

    await state.set_state(
        VariableStates.waiting_for_key
    )

    await callback.message.answer(
        "🔐 <b>Variable қосу</b>\n\n"
        "Variable атауын енгізіңіз.\n\n"
        "Мысалы:\n"
        "<code>API_KEY</code>",
        parse_mode="HTML"
    )


@dp.message(VariableStates.waiting_for_key)
async def receive_variable_key(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    key = (message.text or "").strip()

    if not key:
        await message.answer(
            "❌ Key бос болмауы керек."
        )
        return

    if len(key) > 100:
        await message.answer(
            "❌ Key тым ұзын."
        )
        return

    if any(
        char not in
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
        for char in key
    ):
        await message.answer(
            "❌ Key тек A-Z, a-z, 0-9 және _ таңбаларынан тұруы керек."
        )
        return

    await state.update_data(
        variable_key=key
    )

    await state.set_state(
        VariableStates.waiting_for_value
    )

    await message.answer(
        f"🔑 Key: <code>{html.escape(key)}</code>\n\n"
        "Енді Value енгізіңіз:",
        parse_mode="HTML"
    )


@dp.message(VariableStates.waiting_for_value)
async def receive_variable_value(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    value = message.text or ""

    data = await state.get_data()

    bot_id = data.get("variable_bot_id")
    key = data.get("variable_key")

    if not bot_id or not key:
        await state.clear()
        return

    await database.set_env_var(
        bot_id,
        key,
        value
    )

    await state.clear()

    await message.answer(
        "✅ Variable сақталды!\n\n"
        f"🔑 Key: <code>{html.escape(key)}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔐 Variables",
                        callback_data=f"vars_{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# ============================================================
# DELETE VARIABLE
# ============================================================

@dp.callback_query(F.data.startswith("delvar_"))
async def delete_variable_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    try:
        parts = callback.data.split("_", 2)

        bot_id = int(parts[1])
        key = parts[2]

    except Exception:
        await callback.answer(
            "❌ Қате.",
            show_alert=True
        )
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.answer(
            "⛔ Рұқсат жоқ.",
            show_alert=True
        )
        return

    await database.delete_env_var(
        bot_id,
        key
    )

    await callback.answer(
        "🗑 Variable өшірілді."
    )

    await variables_handler(callback)


# ============================================================
# LOGS
# ============================================================

@dp.callback_query(F.data.startswith("logs_"))
async def logs_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        return

    logs = await database.get_logs(
        bot_id,
        limit=100
    )

    if not logs:
        text = (
            "📜 <b>Logs</b>\n\n"
            "Логтар әзірге жоқ."
        )
    else:
        lines = [
            "📜 <b>Logs</b>",
            "",
        ]

        for log in logs:
            level = html.escape(
                str(log["level"])
            )

            msg = html.escape(
                str(log["message"])
            )

            created = html.escape(
                str(log["created_at"])
            )

            lines.append(
                f"{level} [{created}]\n{msg}"
            )

        text = "\n".join(lines)

    if len(text) > 3800:
        text = text[-3800:]

    await safe_edit(
        callback.message,
        text,
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
        ),
        parse_mode="HTML"
    )


# ============================================================
# DELETE BOT
# ============================================================

@dp.callback_query(F.data.startswith("delete_"))
async def delete_bot_confirm_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer()

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    await callback.message.answer(
        "⚠️ <b>Ботты толық өшіру керек пе?</b>\n\n"
        "Бұл әрекет:\n"
        "• Ботты тоқтатады\n"
        "• Барлық Version-ды өшіреді\n"
        "• Variables-ты өшіреді\n"
        "• Logs-ты өшіреді\n"
        "• Боттың өзін өшіреді",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 Иә, толық өшіру",
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
        ),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("confirmdelete_"))
async def delete_bot_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer(
        "🗑 Өшірілуде..."
    )

    try:
        bot_id = int(
            callback.data.split("_", 1)[1]
        )
    except Exception:
        return

    data = await owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not data:
        await callback.message.answer(
            "⛔ Бот табылмады."
        )
        return

    try:
        if runner_manager.is_running(bot_id):
            await runner_manager.stop_sub_bot(
                bot_id
            )

        await runner_manager.delete_workspace(
            bot_id
        )

        await database.delete_bot(
            bot_id
        )

        await callback.message.answer(
            "✅ Бот толық өшірілді.",
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

    except Exception as error:
        logger.exception(
            "DELETE BOT ERROR"
        )

        await callback.message.answer(
            "❌ Ботты өшіру қатесі:\n\n"
            f"<code>{html.escape(str(error)[:2500])}</code>",
            parse_mode="HTML"
        )


# ============================================================
# NOOP
# ============================================================

@dp.callback_query(F.data.startswith("noop_"))
async def noop_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    await callback.answer(
        "🟢 Бот қазір жұмыс істеп тұр."
    )


# ============================================================
# CANCEL
# ============================================================

@dp.message(CommandStart())
async def duplicate_start_handler(
    message: types.Message
):
    pass


@dp.message(F.text == "/cancel")
async def cancel_handler(
    message: types.Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "❌ Әрекет тоқтатылды.",
        reply_markup=main_keyboard()
    )


# ============================================================
# UNKNOWN CALLBACK
# ============================================================

@dp.callback_query()
async def unknown_callback_handler(
    callback: types.CallbackQuery
):
    if not await admin_callback(callback):
        return

    try:
        await callback.answer(
            "⚠️ Бұл батырма енді жарамсыз.",
            show_alert=True
        )
    except Exception:
        pass


# ============================================================
# STARTUP
# ============================================================

async def main():
    print("========================================")
    print("🛠 TELEGRAM BOT CONSTRUCTOR")
    print("========================================")

    await database.init_db()

    print("✅ Database дайын")
    print("🚀 Master bot іске қосылуда...")

    bot = Bot(
        token=config.BOT_TOKEN
    )

    try:
        await dp.start_polling(
            bot
        )

    finally:
        print("🛑 Master bot тоқтатылуда...")

        try:
            await runner_manager.stop_all()
        except Exception as error:
            print(
                f"STOP ALL ERROR: {error}"
            )

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
