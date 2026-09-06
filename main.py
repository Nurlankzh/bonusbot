import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from runner import runner_manager

TOKEN = os.getenv("BOT_TOKEN", "8729117024:AAFhdneWszqgtsBwS8fOhOTkOeWxNDWW3zQ")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6303091468"))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Күйлері
class AddBotStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_token = State()

class CodeStates(StatesGroup):
    waiting_for_code = State()

class ReqStates(StatesGroup):
    waiting_for_reqs = State()

class TokenStates(StatesGroup):
    waiting_for_new_token = State()

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Жаңа Бот Қосу", callback_data="add_bot")],
        [InlineKeyboardButton(text="📋 Менің Боттарым", callback_data="list_bots")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Сізде бұл ботты басқаруға рұқсат жоқ.")
        return
    await message.answer(
        "👋 **Қош келдіңіз! Бұл — Бот Конструкторы & Консоль Панелі.**\n\n"
        "Осы жерде боттарды қосып, олардың кодын, токенін, кітапханаларын басқара аласыз және **Нақты уақыттағы Консолін (Logs)** көре аласыз.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- БОТ ҚОСУ ---
@dp.callback_query(F.data == "add_bot")
async def process_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddBotStates.waiting_for_id)
    await callback.message.answer("✏️ Боттың атауын/ID-сін енгізіңіз (мысалы: `my_shop_bot`):")
    await callback.answer()

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
        f"✅ **Бот сәтті қосылды!**\n🆔 DB ID: `{bot_db_id}`\n📌 Атауы: `{bot_id_name}`\n\n"
        "Енді осы боттың менюінен кодын немесе кітапханаларын орнатыңыз.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- БОТТАР ТІЗІМІ ---
@dp.callback_query(F.data == "list_bots")
async def list_bots(callback: types.CallbackQuery):
    bots = await db.get_user_bots(callback.from_user.id)
    if not bots:
        await callback.message.answer("📭 Сізде әлі боттар жоқ.", reply_markup=main_keyboard())
        await callback.answer()
        return

    kb = []
    for b in bots:
        status_icon = "🟢" if b['status'] == 'running' else "🔴"
        kb.append([InlineKeyboardButton(
            text=f"{status_icon} {b['bot_id_name']} (ID: {b['id']})", 
            callback_data=f"manage_{b['id']}"
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Артқа", callback_data="main_menu")])

    await callback.message.answer("📋 **Сіздің Боттарыңыз:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

# --- БОТТЫ БАСҚАРУ МЕНЮІ ---
@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_db_id)
    code_info = await db.get_latest_code(bot_db_id)

    ver = f"v{code_info['version']}" if code_info else "Код жоқ"
    status = "🟢 Жұмыс істеп тұр" if b['status'] == 'running' else "🔴 Тоқтатылған"
    reqs = b['requirements'] if b['requirements'] else "Әлі кітапханалар жоқ"

    text = (
        f"🤖 **Ботты Басқару: {b['bot_id_name']}**\n"
        f"🆔 DB ID: `{b['id']}`\n"
        f"📊 Күйі: {status}\n"
        f"📦 Ағымдағы Нұсқасы: `{ver}`\n"
        f"📚 Кітапханалар: `{reqs}`\n"
    )

    kb = [
        [
            InlineKeyboardButton(text="🚀 Қосу", callback_data=f"run_{b['id']}"),
            InlineKeyboardButton(text="🛑 Тоқтату", callback_data=f"stop_{b['id']}"),
            InlineKeyboardButton(text="🔄 Қайта қосу", callback_data=f"restart_{b['id']}")
        ],
        [
            InlineKeyboardButton(text="📝 Код Жазу", callback_data=f"write_code_{b['id']}"),
            InlineKeyboardButton(text="📟 Консоль (Logs)", callback_data=f"console_{b['id']}")
        ],
        [
            InlineKeyboardButton(text="📦 Кітапханалар (req.txt)", callback_data=f"edit_reqs_{b['id']}"),
            InlineKeyboardButton(text="🔑 Токенді Өзгерту", callback_data=f"edit_token_{b['id']}")
        ],
        [
            InlineKeyboardButton(text="📜 Өзгерістер Тарихы (Diff)", callback_data=f"diff_{b['id']}"),
            InlineKeyboardButton(text="⬅️ Артқа", callback_data="list_bots")
        ]
    ]

    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

# --- 📟 КОНСОЛЬ / LOGS КӨРУ ---
@dp.callback_query(F.data.startswith("console_"))
async def view_console(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_db_id)
    logs = await db.get_recent_logs(bot_db_id, limit=20)

    if not logs:
        log_text = "📟 Консольде әлі ешқандай жазба жоқ."
    else:
        log_lines = []
        for l in logs:
            prefix = "🔴" if l['log_type'] == "STDERR" or "ERROR" in l['log_type'] else "🟢"
            log_lines.append(f"{prefix} [{l['created_at']}] {l['message']}")
        log_text = "\n".join(log_lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Жаңарту", callback_data=f"console_{bot_db_id}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_db_id}")]
    ])

    formatted_msg = (
        f"📟 **Бот Консолі (Терминал): {b['bot_id_name']}**\n\n"
        f"```text\n{log_text[:3500]}\n```"
    )

    try:
        await callback.message.edit_text(formatted_msg, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(formatted_msg, reply_markup=kb, parse_mode="Markdown")
    await callback.answer("Консоль жаңартылды!")

# --- 📝 КОД ЖАЗУ ---
@dp.callback_query(F.data.startswith("write_code_"))
async def start_code_write(callback: types.CallbackQuery, state: FSMContext):
    bot_db_id = int(callback.data.split("_")[2])
    await state.update_data(target_bot_id=bot_db_id)
    await state.set_state(CodeStates.waiting_for_code)
    
    await callback.message.answer("💻 **Python кодын жіберіңіз:**", parse_mode="Markdown")
    await callback.answer()

@dp.message(CodeStates.waiting_for_code)
async def save_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_db_id = data['target_bot_id']
    code_text = message.text

    version, diff = await db.save_code_version(bot_db_id, code_text)
    await state.clear()

    diff_preview = diff[:1000] if len(diff) > 1000 else diff
    
    await message.answer(
        f"✅ **Код сақталды!**\n📌 Нұсқасы: `v{version}`\n\n"
        f"📝 **Соңғы айырмашылықтар (Diff):**\n```diff\n{diff_preview}\n```",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- 📦 REQUIREMENTS.TXT / КІТАПХАНАЛАР ЕНГІЗУ ---
@dp.callback_query(F.data.startswith("edit_reqs_"))
async def start_reqs_edit(callback: types.CallbackQuery, state: FSMContext):
    bot_db_id = int(callback.data.split("_")[2])
    await state.update_data(target_bot_id=bot_db_id)
    await state.set_state(ReqStates.waiting_for_reqs)
    
    await callback.message.answer(
        "📦 **Қажетті Python кітапханаларын әр жолға бөлек жазып жіберіңіз:**\n\n"
        "Мысалы:\n```\nrequests\naiohttp\nbeautifulsoup4\n```",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(ReqStates.waiting_for_reqs)
async def save_reqs(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_db_id = data['target_bot_id']
    reqs_text = message.text.strip()

    await db.update_bot_requirements(bot_db_id, reqs_text)
    await state.clear()

    await message.answer(
        f"✅ **Кітапханалар сақталды!**\nБот келесі жолы қосылғанда бұл пакеттер автоматты түрде орнатылады.",
        reply_markup=main_keyboard()
    )

# --- 🔑 ТОКЕНДІ ӨЗГЕРТУ ---
@dp.callback_query(F.data.startswith("edit_token_"))
async def start_token_edit(callback: types.CallbackQuery, state: FSMContext):
    bot_db_id = int(callback.data.split("_")[2])
    await state.update_data(target_bot_id=bot_db_id)
    await state.set_state(TokenStates.waiting_for_new_token)
    
    await callback.message.answer("🔑 **Жаңа Бот Токенін енгізіңіз:**", parse_mode="Markdown")
    await callback.answer()

@dp.message(TokenStates.waiting_for_new_token)
async def save_token(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_db_id = data['target_bot_id']
    new_token = message.text.strip()

    await db.update_bot_token(bot_db_id, new_token)
    await state.clear()

    await message.answer("✅ **Бот токені сәтті жаңартылды!**", reply_markup=main_keyboard())

# --- ҚОСУ / ТОҚТАТУ / RESTART ---
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

@dp.callback_query(F.data.startswith("restart_"))
async def restart_bot_handler(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    await callback.message.answer("🔄 Бот кайта қосылуда...")
    await runner_manager.restart_sub_bot(bot_db_id, callback.message.chat.id, bot)
    await callback.answer()

# --- DIFF ТАРИХЫ ---
@dp.callback_query(F.data.startswith("diff_"))
async def view_diff(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    code_data = await db.get_latest_code(bot_db_id)
    if not code_data:
        await callback.message.answer("❌ Код тарихы табылған жоқ.")
    else:
        await callback.message.answer(
            f"📦 **Нұсқа:** `v{code_data['version']}`\n\n"
            f"📝 **Соңғы Diff:**\n```diff\n{code_data['diff_changes']}\n```",
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: types.CallbackQuery):
    await callback.message.answer("Бас меню:", reply_markup=main_keyboard())
    await callback.answer()

async def main():
    await db.init_db()
    logging.basicConfig(level=logging.INFO)
    
    # Сервер қайта қосылғанда бұрын қосулы болған боттарды қайта ояту
    await runner_manager.restore_running_bots(bot, ADMIN_ID)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
