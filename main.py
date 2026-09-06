import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from runner import runner_manager

# ================= КОНФИГУРАЦИЯ =================
# Бұл жерде Railway Environment variables қолданған дұрыс, бірақ 
# өзіңіз берген токенді әдепкі мән ретінде қалдырдым.
TOKEN = os.getenv("BOT_TOKEN", "8729117024:AAFhdneWszqgtsBwS8fOhOTkOeWxNDWW3zQ")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6303091468))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= FSM КҮЙЛЕРІ =================
class AddBotStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_token = State()

class CodeStates(StatesGroup):
    waiting_for_code = State()

class TerminalStates(StatesGroup):
    waiting_for_command = State()

# ================= КЛАВИАТУРАЛАР =================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Жаңа Бот Қосу", callback_data="add_bot")],
        [InlineKeyboardButton(text="📋 Менің Боттарым", callback_data="list_bots")],
        [InlineKeyboardButton(text="💻 Терминал (Console)", callback_data="open_terminal")]
    ])

# ================= БАСТАПҚЫ КОМАНДА =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Сізде бұл ботты басқаруға рұқсат жоқ.")
        return
    await message.answer(
        "👋 Қош келдіңіз! Бұл — кәсіби **Бот Конструкторы**.\n\n"
        "Боттарды қосыңыз, код жазыңыз және консоль арқылы серверді басқарыңыз.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ================= БОТ ҚОСУ =================
@dp.callback_query(F.data == "add_bot")
async def process_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddBotStates.waiting_for_id)
    await callback.message.edit_text("✏️ Боттың атауын немесе ID-сін енгізіңіз (мысалы: my_test_bot):")

@dp.message(AddBotStates.waiting_for_id)
async def process_bot_id(message: types.Message, state: FSMContext):
    await state.update_data(bot_id_name=message.text)
    await state.set_state(AddBotStates.waiting_for_token)
    await message.answer("🔑 Боттың Telegram Bot Token-ін жіберіңіз:")

@dp.message(AddBotStates.waiting_for_token)
async def process_bot_token(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_id_name = data['bot_id_name']
    token = message.text.strip()

    bot_db_id = await db.add_bot(message.from_user.id, bot_id_name, token)
    await state.clear()

    await message.answer(
        f"✅ Бот сәтті қосылды!\n🆔 DB ID: {bot_db_id}\n📌 Атауы: {bot_id_name}\n\n"
        "Енді осы ботқа Python кодын жаза аласыз.",
        reply_markup=main_keyboard()
    )

# ================= БОТТАР ТІЗІМІ =================
@dp.callback_query(F.data == "list_bots")
async def list_bots(callback: types.CallbackQuery):
    bots = await db.get_user_bots(callback.from_user.id)
    if not bots:
        await callback.message.edit_text("📭 Сізде әлі боттар жоқ.", reply_markup=main_keyboard())
        return

    kb = []
    for b in bots:
        status_icon = "🟢" if b['status'] == 'running' else "🔴"
        kb.append([InlineKeyboardButton(
            text=f"{status_icon} {b['bot_id_name']} (ID: {b['id']})",
            callback_data=f"manage_{b['id']}"
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Басты мәзір", callback_data="main_menu")])

    await callback.message.edit_text("📋 Сіздің Боттарыңыз:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ================= БОТТЫ БАСҚАРУ =================
@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_db_id)
    code_info = await db.get_latest_code(bot_db_id)

    ver = f"v{code_info['version']}" if code_info else "Код жоқ"
    status = "🟢 Жұмыс істеп тұр" if b['status'] == 'running' else "🔴 Тоқтатылған"

    text = (
        f"🤖 **Ботты Басқару:** {b['bot_id_name']}\n"
        f"🆔 `DB ID:` {b['id']}\n"
        f"📊 `Күйі:` {status}\n"
        f"📦 `Ағымдағы Нұсқасы:` {ver}\n"
    )

    kb = [
        [
            InlineKeyboardButton(text="🚀 Қосу", callback_data=f"run_{b['id']}"),
            InlineKeyboardButton(text="🛑 Тоқтату", callback_data=f"stop_{b['id']}")
        ],
        [InlineKeyboardButton(text="📝 Жаңа Код Жазу", callback_data=f"write_code_{b['id']}")],
        [InlineKeyboardButton(text="📜 Өзгерістер (Diff)", callback_data=f"diff_{b['id']}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data="list_bots")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

# ================= КОД ҚАБЫЛДАУ =================
@dp.callback_query(F.data.startswith("write_code_"))
async def start_code_write(callback: types.CallbackQuery, state: FSMContext):
    bot_db_id = int(callback.data.split("_")[2])
    await state.update_data(target_bot_id=bot_db_id)
    await state.set_state(CodeStates.waiting_for_code)

    await callback.message.edit_text(
        "💻 Python кодын жіберіңіз.\n\n"
        "💡 *Ескерту*: `BOT_TOKEN` айнымалысын автоматты түрде өзіміз қосамыз. Тек логикасын жазыңыз.",
        parse_mode="Markdown"
    )

@dp.message(CodeStates.waiting_for_code)
async def save_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_db_id = data['target_bot_id']
    code_text = message.text

    version, diff = await db.save_code_version(bot_db_id, code_text)
    await state.clear()

    diff_preview = diff[:1000] if len(diff) > 1000 else diff
    await message.answer(
        f"✅ Код сақталды!\n📌 Нұсқасы: v{version}\n\n"
        f"📝 Ең соңғы өзгерістер:\n```diff\n{diff_preview}\n```",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ================= ІСКЕ ҚОСУ / ТОҚТАТУ =================
@dp.callback_query(F.data.startswith("run_"))
async def run_bot_handler(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    await runner_manager.start_sub_bot(bot_db_id, callback.message.chat.id, bot)
    await callback.answer()

@dp.callback_query(F.data.startswith("stop_"))
async def stop_bot_handler(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    await runner_manager.stop_sub_bot(bot_db_id, callback.message.chat.id, bot)
    await callback.answer()

@dp.callback_query(F.data.startswith("diff_"))
async def view_diff(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    code_data = await db.get_latest_code(bot_db_id)
    if not code_data:
        await callback.answer("❌ Код тарихы табылған жоқ.", show_alert=True)
    else:
        await callback.message.answer(
            f"📦 Нұсқа: v{code_data['version']}\n\n"
            f"📝 Соңғы Diff:\n```diff\n{code_data['diff_changes']}\n```",
            parse_mode="Markdown"
        )
    await callback.answer()

# ================= ТЕРМИНАЛ / КОНСОЛЬ =================
@dp.callback_query(F.data == "open_terminal")
async def open_terminal(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TerminalStates.waiting_for_command)
    await callback.message.edit_text(
        "💻 **Терминалға қосылдыңыз.**\n\n"
        "Кез-келген Linux командасын енгізіңіз (мысалы: `ls`, `pip install requests`).\n"
        "Шығу үшін /cancel басыңыз.",
        parse_mode="Markdown"
    )

@dp.message(Command("cancel"))
async def cancel_terminal(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Терминалдан шықтыңыз.", reply_markup=main_keyboard())

@dp.message(TerminalStates.waiting_for_command)
async def execute_terminal_command(message: types.Message):
    if message.text.startswith("/"):
        return # Командаларға кедергі жасамау үшін
    
    cmd = message.text
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    res = f"🖥 **Команда:** `{cmd}`\n\n"
    if stdout:
        res += f"**Output:**\n```\n{stdout.decode('utf-8')[:3500]}\n```\n"
    if stderr:
        res += f"**Errors:**\n```\n{stderr.decode('utf-8')[:1000]}\n```"
    
    if not stdout and not stderr:
        res += "*(Нәтиже бос)*"

    await message.answer(res, parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Бас мәзір:", reply_markup=main_keyboard())

# ================= НЕГІЗГІ ИНЦИАЛИЗАЦИЯ =================
async def main():
    await db.init_db()
    logging.basicConfig(level=logging.INFO)
    print("🤖 Басқарушы бот қосылды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
