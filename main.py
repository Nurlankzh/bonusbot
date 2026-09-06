import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from runner import runner_manager

# Конфигурация
TOKEN = "8729117024:AAFhdneWszqgtsBwS8fOhOTkOeWxNDWW3zQ"
ADMIN_ID = 6303091468

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM Күйлері
class AddBotStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_token = State()

class CodeStates(StatesGroup):
    waiting_for_code = State()

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
        "👋 **Қош келдіңіз! Бұл — Бот Конструкторы.**\n\n"
        "Осы жерде боттар қосып, олардың кодын жазып, іске қоса аласыз және қателерін қадағалай аласыз.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- БОТ ҚОСУ ЛОГИКАСЫ ---
@dp.callback_query(F.data == "add_bot")
async def process_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddBotStates.waiting_for_id)
    await callback.message.answer("✏️ Боттың атауын/атаулы ID-сін енгізіңіз (мысалы: `my_test_bot`):")
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
        f"✅ **Бот сәтті қосылды!**\n🆔 DB ID: `{bot_db_id}`\n📌 Name: `{bot_id_name}`\n\n"
        "Енді осы ботқа Python кодын жіберіңіз.",
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

@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    bot_db_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_db_id)
    code_info = await db.get_latest_code(bot_db_id)

    ver = f"v{code_info['version']}" if code_info else "Код жоқ"
    status = "🟢 Жұмыс істеп тұр" if b['status'] == 'running' else "🔴 Тоқтатылған"

    text = (
        f"🤖 **Ботты Басқару: {b['bot_id_name']}**\n"
        f"🆔 DB ID: `{b['id']}`\n"
        f"📊 Күйі: {status}\n"
        f"📦 Ағымдағы Нұсқасы: `{ver}`\n"
    )

    kb = [
        [
            InlineKeyboardButton(text="🚀 Қосу", callback_data=f"run_{b['id']}"),
            InlineKeyboardButton(text="🛑 Тоқтату", callback_data=f"stop_{b['id']}")
        ],
        [InlineKeyboardButton(text="📝 Жаңа Код Жазу", callback_data=f"write_code_{b['id']}")],
        [InlineKeyboardButton(text="📜 Өзгерістер Тарихы (Diff)", callback_data=f"diff_{b['id']}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data="list_bots")]
    ]

    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

# --- КОД ҚАБЫЛДАУ ЖӘНЕ ВЕРСИЯЛАУ ---
@dp.callback_query(F.data.startswith("write_code_"))
async def start_code_write(callback: types.CallbackQuery, state: FSMContext):
    bot_db_id = int(callback.data.split("_")[2])
    await state.update_data(target_bot_id=bot_db_id)
    await state.set_state(CodeStates.waiting_for_code)
    
    await callback.message.answer(
        "💻 **Python кодын жіберіңіз.**\n\n"
        "💡 *Ескерту:* Ботқа токен жазудың керегі жоқ, жүйе `BOT_TOKEN` айнымалысын автоматты түрде өзі қосады.",
        parse_mode="Markdown"
    )
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
        f"📝 **Ең соңғы енгізілген өзгерістер (Diff):**\n```diff\n{diff_preview}\n```",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- БОТТЫ ҚОСУ / ТОҚТАТУ КЛАВИШТЕРІ ---
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

# --- ӨЗГЕРІСТЕР ТАРИХЫН КӨРУ ---
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
