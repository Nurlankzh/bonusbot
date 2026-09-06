import asyncio
import html
import logging
import os
import psutil

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
from analyzer import analyze_code
from runner import runner_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class AddBotStates(StatesGroup):
    waiting_name = State()
    waiting_token = State()


class CodeStates(StatesGroup):
    waiting_code = State()
    waiting_restore = State()


class VarStates(StatesGroup):
    waiting_key = State()
    waiting_value = State()


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Жаңа жоба",
                    callback_data="add_bot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Жобалар",
                    callback_data="list_bots"
                )
            ]
        ]
    )


def project_menu(bot_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Deployments",
                    callback_data=f"deploy:{bot_id}"
                ),
                InlineKeyboardButton(
                    text="🔐 Variables",
                    callback_data=f"vars:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Metrics",
                    callback_data=f"metrics:{bot_id}"
                ),
                InlineKeyboardButton(
                    text="💻 Logs",
                    callback_data=f"logs:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data=f"settings:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Басты мәзір",
                    callback_data="main_menu"
                )
            ]
        ]
    )


def deployment_menu(bot_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Run",
                    callback_data=f"run:{bot_id}"
                ),
                InlineKeyboardButton(
                    text="🛑 Stop",
                    callback_data=f"stop:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Restart",
                    callback_data=f"restart:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Код Deploy",
                    callback_data=f"code:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Rollback",
                    callback_data=f"rollback:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Versions",
                    callback_data=f"versions:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Артқа",
                    callback_data=f"manage:{bot_id}"
                )
            ]
        ]
    )


def settings_menu(bot_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Auto Restart",
                    callback_data=f"autorestart:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Артқа",
                    callback_data=f"manage:{bot_id}"
                )
            ]
        ]
    )


async def check_access(user_id):
    return user_id == config.ADMIN_ID


async def get_owned_bot(bot_id, user_id):
    if not await check_access(user_id):
        return None

    bot_data = await db.get_bot(bot_id)

    if not bot_data:
        return None

    if bot_data["owner_id"] != user_id:
        return None

    return bot_data


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if not await check_access(message.from_user.id):
        await message.answer("⛔ Access Denied.")
        return

    await message.answer(
        "🛠 <b>Railway Bot Builder</b>\n\n"
        "Telegram боттарыңызды осы жерден басқарыңыз.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        await callback.answer(
            "⛔ Access Denied.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "🏠 <b>Басты мәзір</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data == "add_bot")
async def add_bot_start(
    callback: types.CallbackQuery,
    state: FSMContext
):
    if not await check_access(callback.from_user.id):
        await callback.answer(
            "⛔ Access Denied.",
            show_alert=True
        )
        return

    await state.set_state(
        AddBotStates.waiting_name
    )

    await callback.message.answer(
        "✏️ Жобаның атауын жазыңыз:"
    )

    await callback.answer()


@dp.message(AddBotStates.waiting_name)
async def add_bot_name(
    message: types.Message,
    state: FSMContext
):
    if not await check_access(message.from_user.id):
        return

    name = (message.text or "").strip()

    if not name:
        await message.answer(
            "❌ Атау бос болмауы керек."
        )
        return

    if len(name) > 100:
        await message.answer(
            "❌ Атау тым ұзын."
        )
        return

    await state.update_data(name=name)

    await state.set_state(
        AddBotStates.waiting_token
    )

    await message.answer(
        "🔑 Child боттың token-ін жіберіңіз.\n\n"
        "Token database ішінде сақталады және интерфейсте көрсетілмейді."
    )


@dp.message(AddBotStates.waiting_token)
async def add_bot_token(
    message: types.Message,
    state: FSMContext
):
    if not await check_access(message.from_user.id):
        return

    token = (message.text or "").strip()

    if len(token) < 20:
        await message.answer(
            "❌ Token дұрыс емес сияқты."
        )
        return

    data = await state.get_data()

    bot_id = await db.add_bot(
        message.from_user.id,
        data["name"],
        token
    )

    await state.clear()

    await message.answer(
        f"✅ <b>Жоба құрылды!</b>\n\n"
        f"ID: <code>{bot_id}</code>\n"
        f"Атауы: <b>{html.escape(data['name'])}</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "list_bots")
async def list_bots(
    callback: types.CallbackQuery
):
    if not await check_access(callback.from_user.id):
        await callback.answer(
            "⛔ Access Denied.",
            show_alert=True
        )
        return

    bots = await db.get_user_bots(
        callback.from_user.id
    )

    if not bots:
        await callback.message.edit_text(
            "📭 <b>Жобалар жоқ.</b>",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )

        await callback.answer()
        return

    buttons = []

    for item in bots:
        status = item["status"]

        icon = {
            "running": "🟢",
            "starting": "🟡",
            "stopped": "🔴",
            "crashed": "💥"
        }.get(status, "⚪")

        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {item['bot_id_name']}",
                callback_data=f"manage:{item['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Артқа",
            callback_data="main_menu"
        )
    ])

    await callback.message.edit_text(
        "📋 <b>Жобалар</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("manage:"))
async def manage_bot(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "❌ Жоба табылмады.",
            show_alert=True
        )
        return

    status = {
        "running": "🟢 Қосулы",
        "starting": "🟡 Іске қосылуда",
        "stopped": "🔴 Тоқтатылған",
        "crashed": "💥 Crash"
    }.get(
        bot_data["status"],
        "⚪ Белгісіз"
    )

    await callback.message.edit_text(
        f"🖥 <b>{html.escape(bot_data['name'])}</b>\n\n"
        f"ID: <code>{bot_id}</code>\n"
        f"Күйі: <b>{status}</b>",
        reply_markup=project_menu(bot_id),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("deploy:"))
async def deployments(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    latest = await db.get_latest_code(
        bot_id
    )

    version = (
        f"v{latest['version']}"
        if latest
        else "Код жоқ"
    )

    await callback.message.edit_text(
        f"🚀 <b>Deployments</b>\n\n"
        f"📦 Version: <code>{version}</code>\n"
        f"📊 Status: <b>{bot_data['status']}</b>",
        reply_markup=deployment_menu(bot_id),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("code:"))
async def code_start(
    callback: types.CallbackQuery,
    state: FSMContext
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        CodeStates.waiting_code
    )

    await callback.message.answer(
        "📝 Python кодын толық жіберіңіз.\n\n"
        "Child бот ішінде token автоматты түрде "
        "<code>os.getenv('BOT_TOKEN')</code> арқылы қолжетімді.",
        parse_mode="HTML"
    )

    await callback.answer()


@dp.message(CodeStates.waiting_code)
async def save_code(
    message: types.Message,
    state: FSMContext
):
    if not await check_access(
        message.from_user.id
    ):
        return

    data = await state.get_data()

    bot_id = data["bot_id"]

    if not await get_owned_bot(
        bot_id,
        message.from_user.id
    ):
        await state.clear()
        await message.answer(
            "❌ Access denied."
        )
        return

    code = message.text or ""

    if not code.strip():
        await message.answer(
            "❌ Код бос."
        )
        return

    if len(code) > config.MAX_CODE_SIZE:
        await message.answer(
            "❌ Код тым үлкен."
        )
        return

    result = analyze_code(code)

    if not result["ok"]:
        await message.answer(
            "❌ <b>Кодта синтаксис қатесі бар.</b>\n\n"
            f"<pre>{html.escape(result['error'])}</pre>",
            parse_mode="HTML"
        )
        return

    version, diff = await db.save_code_version(
        bot_id,
        code
    )

    await state.clear()

    warnings = ""

    if result["warnings"]:
        warnings = (
            "\n\n⚠️ <b>Ескерту:</b>\n"
            + "\n".join(
                f"• {html.escape(x)}"
                for x in result["warnings"]
            )
        )

    await message.answer(
        f"✅ <b>Код сақталды!</b>\n\n"
        f"Version: <code>v{version}</code>"
        f"{warnings}",
        reply_markup=deployment_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("run:"))
async def run_bot(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await callback.answer(
        "🚀 Іске қосылуда..."
    )

    await runner_manager.start_sub_bot(
        bot_id,
        callback.message.chat.id,
        bot
    )


@dp.callback_query(F.data.startswith("stop:"))
async def stop_bot(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await callback.answer(
        "🛑 Тоқтатылуда..."
    )

    await runner_manager.stop_sub_bot(
        bot_id,
        callback.message.chat.id,
        bot
    )


@dp.callback_query(F.data.startswith("restart:"))
async def restart_bot(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await callback.answer(
        "🔄 Restart..."
    )

    await runner_manager.restart_sub_bot(
        bot_id,
        callback.message.chat.id,
        bot
    )


@dp.callback_query(F.data.startswith("vars:"))
async def variables(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    variables_data = await db.get_env_vars(
        bot_id
    )

    lines = [
        "🔐 <b>Environment Variables</b>",
        ""
    ]

    for key in variables_data:
        lines.append(
            f"🔑 <code>{html.escape(key)}</code> = <code>********</code>"
        )

    if len(lines) == 2:
        lines.append("Айнымалылар жоқ.")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Variable қосу",
                    callback_data=f"addvar:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Артқа",
                    callback_data=f"manage:{bot_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("addvar:"))
async def add_var(
    callback: types.CallbackQuery,
    state: FSMContext
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        VarStates.waiting_key
    )

    await callback.message.answer(
        "🔑 Variable KEY енгізіңіз.\n"
        "Мысалы: API_KEY"
    )

    await callback.answer()


@dp.message(VarStates.waiting_key)
async def variable_key(
    message: types.Message,
    state: FSMContext
):
    key = (message.text or "").strip().upper()

    if not key.replace("_", "").isalnum():
        await message.answer(
            "❌ Key тек A-Z, 0-9 және _ болуы керек."
        )
        return

    await state.update_data(
        key=key
    )

    await state.set_state(
        VarStates.waiting_value
    )

    await message.answer(
        "🔐 Variable VALUE енгізіңіз:"
    )


@dp.message(VarStates.waiting_value)
async def variable_value(
    message: types.Message,
    state: FSMContext
):
    data = await state.get_data()

    bot_id = data["bot_id"]

    if not await get_owned_bot(
        bot_id,
        message.from_user.id
    ):
        await state.clear()
        await message.answer(
            "❌ Access denied."
        )
        return

    value = message.text or ""

    await db.set_env_var(
        bot_id,
        data["key"],
        value
    )

    await state.clear()

    await message.answer(
        f"✅ Variable сақталды:\n"
        f"<code>{html.escape(data['key'])}</code>",
        reply_markup=project_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("metrics:"))
async def metrics(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    cpu = psutil.cpu_percent(
        interval=0.2
    )

    ram = psutil.virtual_memory()

    process = runner_manager.processes.get(
        bot_id
    )

    pid = process.pid if process else "—"

    text = (
        "📊 <b>Server Metrics</b>\n\n"
        f"🖥 CPU: <code>{cpu}%</code>\n"
        f"💾 RAM: <code>{ram.percent}%</code>\n"
        f"📦 RAM used: <code>{ram.used // 1048576} MB</code>\n"
        f"🔢 Child PID: <code>{pid}</code>\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Refresh",
                        callback_data=f"metrics:{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Артқа",
                        callback_data=f"manage:{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("logs:"))
async def logs(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    rows = await db.get_logs(
        bot_id,
        30
    )

    if not rows:
        text = "📭 <b>Log жоқ.</b>"
    else:
        parts = [
            "📜 <b>Latest Logs</b>",
            ""
        ]

        for row in reversed(rows):
            parts.append(
                f"[{html.escape(row['level'])}] "
                f"{html.escape(row['message'][:500])}"
            )

        text = "\n".join(parts)

    if len(text) > 3900:
        text = text[-3900:]

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Refresh",
                        callback_data=f"logs:{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Артқа",
                        callback_data=f"manage:{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("versions:"))
async def versions(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    rows = await db.get_code_versions(
        bot_id
    )

    if not rows:
        text = "📭 Version жоқ."
    else:
        text = "📜 <b>Code Versions</b>\n\n"

        for row in rows:
            text += (
                f"• <code>v{row['version']}</code> "
                f"{row['created_at']}\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Артқа",
                        callback_data=f"deploy:{bot_id}"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("rollback:"))
async def rollback_start(
    callback: types.CallbackQuery,
    state: FSMContext
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    if not await get_owned_bot(
        bot_id,
        callback.from_user.id
    ):
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    await state.update_data(
        bot_id=bot_id
    )

    await state.set_state(
        CodeStates.waiting_restore
    )

    await callback.message.answer(
        "↩️ Қай version-ға қайтқыңыз келеді?\n\n"
        "Мысалы: 1"
    )

    await callback.answer()


@dp.message(CodeStates.waiting_restore)
async def rollback_process(
    message: types.Message,
    state: FSMContext
):
    data = await state.get_data()

    bot_id = data["bot_id"]

    try:
        version = int(
            (message.text or "").strip()
        )
    except ValueError:
        await message.answer(
            "❌ Version тек сан болуы керек."
        )
        return

    old = await db.get_code_by_version(
        bot_id,
        version
    )

    if not old:
        await message.answer(
            "❌ Мұндай version жоқ."
        )
        return

    new_version, _ = await db.save_code_version(
        bot_id,
        old["code"]
    )

    await state.clear()

    await message.answer(
        f"✅ Rollback дайын.\n\n"
        f"Ескі version: <code>v{version}</code>\n"
        f"Жаңа version: <code>v{new_version}</code>\n\n"
        "Енді Run/Restart арқылы іске қосыңыз.",
        reply_markup=deployment_menu(bot_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("settings:"))
async def settings(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    auto = "🟢 ON" if bot_data["auto_restart"] else "🔴 OFF"

    await callback.message.edit_text(
        f"⚙️ <b>Settings</b>\n\n"
        f"Auto Restart: <b>{auto}</b>",
        reply_markup=settings_menu(bot_id),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("autorestart:"))
async def toggle_autorestart(
    callback: types.CallbackQuery
):
    bot_id = int(
        callback.data.split(":")[1]
    )

    bot_data = await get_owned_bot(
        bot_id,
        callback.from_user.id
    )

    if not bot_data:
        await callback.answer(
            "❌ Access denied.",
            show_alert=True
        )
        return

    enabled = not bool(
        bot_data["auto_restart"]
    )

    await db.set_auto_restart(
        bot_id,
        enabled
    )

    await callback.answer(
        "Auto Restart өзгертілді."
    )

    await settings(callback)


async def main():
    await db.init_db()

    logging.info(
        "🚀 Master Bot Builder started"
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())
