import asyncio
import logging
import os
import psutil
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
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

# FSM States
class AddBotStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_token = State()

class CodeStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_restore = State()

class VarStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_value = State()

class TerminalStates(StatesGroup):
    waiting_for_command = State()

# --- Middleware (Қауіпсіздік) ---
@dp.message()
async def admin_check_msg(message: types.Message, handler):
    if message.from_user.id != ADMIN_ID: return
    return await handler(message, message)

@dp.callback_query()
async def admin_check_cb(callback: types.CallbackQuery, handler):
    if callback.from_user.id != ADMIN_ID: return
    return await handler(callback, callback)

# --- Мәзірлер ---
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Жаңа Жоба Қосу", callback_data="add_bot")],
        [InlineKeyboardButton(text="📋 Жобалар тізімі", callback_data="list_bots")]
    ])

def railway_menu(bot_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Жүктеулер (Deploy)", callback_data=f"menu_deploy_{bot_id}"),
         InlineKeyboardButton(text="🔐 Айнымалылар (Vars)", callback_data=f"menu_vars_{bot_id}")],
        [InlineKeyboardButton(text="📊 Метрика (Metrics)", callback_data=f"menu_metrics_{bot_id}"),
         InlineKeyboardButton(text="💻 Консоль (Console)", callback_data=f"menu_console_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Басты мәзір", callback_data="main_menu")]
    ])

# --- Бастау ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("👋 **Railway Bot Builder** жүйесіне қош келдіңіз!\nСерверлеріңізді басқарыңыз.", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🏠 Басты мәзір:", reply_markup=main_menu())

# --- Бот Қосу ---
@dp.callback_query(F.data == "add_bot")
async def add_bot_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddBotStates.waiting_for_name)
    await callback.message.answer("✏️ Жобаның (Сервистің) атауын жазыңыз:")

@dp.message(AddBotStates.waiting_for_name)
async def add_bot_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddBotStates.waiting_for_token)
    await message.answer("🔑 Боттың Token-ін жіберіңіз (Ол қауіпсіз Variables базасында сақталады):")

@dp.message(AddBotStates.waiting_for_token)
async def add_bot_token(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_id = await db.add_bot(message.from_user.id, data['name'], message.text.strip())
    await state.clear()
    await message.answer(f"✅ **Жоба құрылды!** (ID: {bot_id})", reply_markup=main_menu(), parse_mode="Markdown")

# --- Жобалар Тізімі ---
@dp.callback_query(F.data == "list_bots")
async def list_bots(callback: types.CallbackQuery):
    bots = await db.get_user_bots(callback.from_user.id)
    if not bots:
        return await callback.message.edit_text("📭 Жобалар жоқ.", reply_markup=main_menu())
    
    kb = [[InlineKeyboardButton(text=f"{'🟢' if b['status'] == 'running' else ('💥' if b['status'] == 'crashed' else '🔴')} {b['bot_id_name']}", callback_data=f"manage_{b['id']}")] for b in bots]
    kb.append([InlineKeyboardButton(text="⬅️ Артқа", callback_data="main_menu")])
    await callback.message.edit_text("📋 **Сіздің сервистеріңіз:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_id)
    status_text = {"running": "🟢 Қосулы", "stopped": "🔴 Тоқтатылды", "crashed": "💥 Құлады (Crash)"}.get(b['status'], "Белгісіз")
    await callback.message.edit_text(f"🖥 **Сервис:** `{b['bot_id_name']}`\n📊 **Күйі:** {status_text}", reply_markup=railway_menu(bot_id), parse_mode="Markdown")

# --- 1. Deployments (Жүктеулер және Rollback) ---
@dp.callback_query(F.data.startswith("menu_deploy_"))
async def menu_deploy(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    code_info = await db.get_latest_code(bot_id)
    ver = f"v{code_info['version']}" if code_info else "Код жоқ"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Іске қосу", callback_data=f"run_{bot_id}"), InlineKeyboardButton(text="🛑 Тоқтату", callback_data=f"stop_{bot_id}")],
        [InlineKeyboardButton(text="📝 Жаңа код (Deploy)", callback_data=f"write_code_{bot_id}")],
        [InlineKeyboardButton(text="↩️ Ескі нұсқаға қайту (Rollback)", callback_data=f"rollback_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]
    ])
    await callback.message.edit_text(f"🚀 **Deployments (Жүктеулер)**\n📦 Ағымдағы нұсқа: `{ver}`\nЖаңа код жіберу үшін немесе қосу/тоқтату үшін батырмаларды қолданыңыз.", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("write_code_"))
async def ask_for_code(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(CodeStates.waiting_for_code)
    await callback.message.answer("💻 Python кодын жіберіңіз.\n*Ескерту: Токенді кодқа жазбаңыз, ол `os.getenv('BOT_TOKEN')` арқылы автоматты түрде оқылады.*", parse_mode="Markdown")

@dp.message(CodeStates.waiting_for_code)
async def save_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ver, diff = await db.save_code_version(data['bot_id'], message.text)
    await state.clear()
    await message.answer(f"✅ **Код сақталды!** (v{ver})\n\n📝 **Өзгерістер (Diff):**\n```diff\n{diff[:1000]}\n```", reply_markup=railway_menu(data['bot_id']), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("rollback_"))
async def rollback_version(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(CodeStates.waiting_for_restore)
    await callback.message.answer("↩️ Қайтқыңыз келетін нұсқа нөмірін жазыңыз (мысалы: `1` немесе `2`):")

@dp.message(CodeStates.waiting_for_restore)
async def process_rollback(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_id = data['bot_id']
    try:
        ver = int(message.text.strip())
        old_code = await db.get_code_by_version(bot_id, ver)
        if old_code:
            new_ver, _ = await db.save_code_version(bot_id, old_code['code'])
            await message.answer(f"✅ Сәтті түрде `v{ver}` нұсқасына қайтарылды! Жаңа нұсқа: `v{new_ver}`", reply_markup=railway_menu(bot_id), parse_mode="Markdown")
        else:
            await message.answer("❌ Бұл нұсқа табылмады.")
    except ValueError:
        await message.answer("❌ Тек сандарды енгізіңіз.")
    await state.clear()

# --- Run / Stop ---
@dp.callback_query(F.data.startswith("run_"))
async def run_bot(callback: types.CallbackQuery):
    await runner_manager.start_sub_bot(int(callback.data.split("_")[1]), callback.message.chat.id, bot)
    await callback.answer()

@dp.callback_query(F.data.startswith("stop_"))
async def stop_bot(callback: types.CallbackQuery):
    await runner_manager.stop_sub_bot(int(callback.data.split("_")[1]), callback.message.chat.id, bot)
    await callback.answer()

# --- 2. Variables ---
@dp.callback_query(F.data.startswith("menu_vars_"))
async def menu_vars(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[2])
    vars_data = await db.get_env_vars(bot_id)
    
    text = "🔐 **Environment Variables**\n\n"
    for k in vars_data.keys():
        text += f"🔑 `{k}` : `********` (Құпия)\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Жаңа айнымалы қосу", callback_data=f"addvar_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("addvar_"))
async def add_var_key(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(bot_id=int(callback.data.split("_")[1]))
    await state.set_state(VarStates.waiting_for_key)
    await callback.message.answer("Айнымалының АТАУЫН (Key) жазыңыз (мысалы: `API_KEY`):")

@dp.message(VarStates.waiting_for_key)
async def add_var_val(message: types.Message, state: FSMContext):
    await state.update_data(key=message.text.upper())
    await state.set_state(VarStates.waiting_for_value)
    await message.answer("Айнымалының МӘНІН (Value) жазыңыз:")

@dp.message(VarStates.waiting_for_value)
async def save_var(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.set_env_var(data['bot_id'], data['key'], message.text)
    await state.clear()
    await message.answer(f"✅ Айнымалы сақталды: `{data['key']}`", reply_markup=railway_menu(data['bot_id']), parse_mode="Markdown")

# --- 3. Metrics ---
@dp.callback_query(F.data.startswith("menu_metrics_"))
async def menu_metrics(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    text = f"📊 **Метрика (Server Status)**\n\n🖥 **CPU:** `{cpu}%`\n💾 **RAM:** `{ram.percent}%` ({ram.used // 1048576} MB)\n\n*Бұл негізгі сервердің (Node) көрсеткіштері.*"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]]), parse_mode="Markdown")

# --- 4. Console (Қауіпсіз терминал) ---
@dp.callback_query(F.data.startswith("menu_console_"))
async def menu_console(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[2])
    await state.set_state(TerminalStates.waiting_for_command)
    await callback.message.edit_text("💻 **Консоль**\n\nКоманда жазыңыз (мысалы: `pip install requests`).\nҚауіпсіздік үшін қауіпті командаларға (`rm`, `reboot`) тыйым салынған.\nШығу үшін: `/exit`", parse_mode="Markdown")

@dp.message(TerminalStates.waiting_for_command)
async def execute_console(message: types.Message, state: FSMContext):
    if message.text.lower() == "/exit":
        await state.clear()
        return await message.answer("✅ Консоль жабылды.", reply_markup=main_menu())
    
    cmd = message.text
    if any(danger in cmd for danger in ["rm ", "sudo", "reboot", "shutdown", "mkfs"]):
        return await message.answer("❌ Бұл командаға қауіпсіздік үшін тыйым салынған.")

    process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    res = f"🖥 `$ {cmd}`\n\n"
    if stdout: res += f"**Нәтиже:**\n```\n{stdout.decode()[:3000]}\n```\n"
    if stderr: res += f"**Қате:**\n```\n{stderr.decode()[:1000]}\n```"
    await message.answer(res, parse_mode="Markdown")

async def main():
    await db.init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 Master Конструктор іске қосылды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
