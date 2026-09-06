import asyncio
import logging
import os
import psutil
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from runner import runner_manager

TOKEN = os.getenv("BOT_TOKEN", "8729117024:AAFhdneWszqgtsBwS8fOhOTkOeWxNDWW3zQ")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6303091468))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class TerminalStates(StatesGroup):
    waiting_for_command = State()

class VariableStates(StatesGroup):
    waiting_for_var = State()

# ================= БАСТЫ МӘЗІР (RAILWAY АНАЛОГЫ) =================
def railway_main_menu(bot_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Жүктеулер (Deployments)", callback_data=f"menu_deploy_{bot_id}"),
            InlineKeyboardButton(text="🔐 Айнымалылар (Variables)", callback_data=f"menu_vars_{bot_id}")
        ],
        [
            InlineKeyboardButton(text="📊 Метрика (Metrics)", callback_data=f"menu_metrics_{bot_id}"),
            InlineKeyboardButton(text="💻 Консоль (Console)", callback_data=f"menu_console_{bot_id}")
        ],
        [
            InlineKeyboardButton(text="⚙️ Баптаулар (Settings)", callback_data=f"menu_settings_{bot_id}")
        ],
        [InlineKeyboardButton(text="⬅️ Боттар тізіміне қайту", callback_data="list_bots")]
    ])

def settings_menu(bot_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Дереккөз (Source / GitHub)", callback_data=f"set_source_{bot_id}")],
        [InlineKeyboardButton(text="🌐 Желі және Домен (Networking)", callback_data=f"set_network_{bot_id}")],
        [InlineKeyboardButton(text="⚖️ Ресурстарды шектеу (Scale & Limits)", callback_data=f"set_scale_{bot_id}")],
        [InlineKeyboardButton(text="🛠 Құрастыру (Build & Deploy)", callback_data=f"set_build_{bot_id}")],
        [InlineKeyboardButton(text="🔄 Қайта қосу саясаты (Restart Policy)", callback_data=f"set_restart_{bot_id}")],
        [InlineKeyboardButton(text="🗑 Сервисті өшіру (Delete Service)", callback_data=f"set_delete_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Рұқсат жоқ.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Жаңа Жоба (Бот) Қосу", callback_data="add_bot")],
        [InlineKeyboardButton(text="📋 Менің Жобаларым", callback_data="list_bots")]
    ])
    
    await message.answer(
        "👋 **Бот Конструкторына Қош келдіңіз!**\n\n"
        "Бұл жүйе Railway.com платформасының негізінде жасалған. "
        "Өз боттарыңызды серверде басқарып, баптап, іске қоса аласыз.",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "list_bots")
async def list_bots(callback: types.CallbackQuery):
    bots = await db.get_user_bots(callback.from_user.id)
    if not bots:
        await callback.message.edit_text("📭 Жобалар жоқ.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Артқа", callback_data="main_menu")]]))
        return

    kb = []
    for b in bots:
        icon = "🟢" if b['status'] == 'running' else "🔴"
        kb.append([InlineKeyboardButton(text=f"{icon} {b['bot_id_name']}", callback_data=f"manage_{b['id']}")])
    
    await callback.message.edit_text("📋 **Сіздің Жобаларыңыз (Сервистер):**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

# ================= RAILWAY МӘЗІРІНЕ КІРУ =================
@dp.callback_query(F.data.startswith("manage_"))
async def manage_bot(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[1])
    b = await db.get_bot(bot_id)
    status = "ҚОСУЛЫ 🟢" if b['status'] == 'running' else "ТОҚТАТЫЛДЫ 🔴"
    
    text = (
        f"🖥 **Сервис:** `{b['bot_id_name']}`\n"
        f"📊 **Күйі:** {status}\n\n"
        f"Басқару тақтасынан қажетті бөлімді таңдаңыз:"
    )
    await callback.message.edit_text(text, reply_markup=railway_main_menu(bot_id), parse_mode="Markdown")

# --- 1. ЖҮКТЕУЛЕР (DEPLOYMENTS) ---
@dp.callback_query(F.data.startswith("menu_deploy_"))
async def menu_deploy(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    code_info = await db.get_latest_code(bot_id)
    ver = f"v{code_info['version']}" if code_info else "Код жүктелмеген"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Қосу (Start)", callback_data=f"run_{bot_id}"),
         InlineKeyboardButton(text="🛑 Тоқтату (Stop)", callback_data=f"stop_{bot_id}")],
        [InlineKeyboardButton(text="📝 Жаңа код жүктеу", callback_data=f"write_code_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]
    ])
    
    await callback.message.edit_text(
        f"🚀 **Жүктеулер (Deployments)**\n\n"
        f"Мұнда сіз ботты іске қосып, жаңа код жүктей аласыз.\n"
        f"📦 Ағымдағы нұсқа: `{ver}`\n",
        reply_markup=kb, parse_mode="Markdown"
    )

# --- 2. АЙНЫМАЛЫЛАР (VARIABLES) ---
@dp.callback_query(F.data.startswith("menu_vars_"))
async def menu_vars(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    b = await db.get_bot(bot_id)
    
    text = (
        "🔐 **Айнымалылар (Environment Variables)**\n\n"
        "Құпия деректерді осында сақтаңыз.\n"
        f"Кілт: `BOT_TOKEN`\nМән: ||{b['bot_token']}|| (басып көріңіз)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Айнымалы қосу (Жақында)", callback_data="dummy")],
        [InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="MarkdownV2")

# --- 3. МЕТРИКА (METRICS) ---
@dp.callback_query(F.data.startswith("menu_metrics_"))
async def menu_metrics(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    text = (
        "📊 **Жүйелік Метрика (Metrics)**\n\n"
        f"🖥 **CPU (Процессор):** `{cpu}%` (Шектеу: 7 vCPU)\n"
        f"💾 **RAM (Жад):** `{ram.percent}%` (Пайдаланылды: {ram.used // 1048576} MB / {ram.total // 1048576} MB)\n"
        f"💽 **Disk:** `{disk.percent}%`\n\n"
        "ℹ️ *Replica Limits: CPU: 7 vCPU | Memory: 8 GB*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Артқа", callback_data=f"manage_{bot_id}")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- 4. КОНСОЛЬ (CONSOLE) ---
@dp.callback_query(F.data.startswith("menu_console_"))
async def menu_console(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[2])
    await state.set_state(TerminalStates.waiting_for_command)
    
    text = (
        "💻 **Терминал (Console)**\n\n"
        "Бұл сервердің ішкі терминалы. Кез келген команданы жіберіңіз.\n"
        "Мысалы: `pip install aiogram`, `ls -la`, `python --version`\n\n"
        "🛑 Шығу үшін `/cancel` деп жазыңыз."
    )
    await callback.message.edit_text(text, parse_mode="Markdown")

@dp.message(TerminalStates.waiting_for_command)
async def execute_terminal(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("✅ Консольден шықтыңыз.")
        return
    
    cmd = message.text
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    res = f"🖥 **Команда:** `{cmd}`\n\n"
    if stdout:
        res += f"**Нәтиже:**\n```\n{stdout.decode('utf-8')[:3500]}\n```\n"
    if stderr:
        res += f"**Қате:**\n```\n{stderr.decode('utf-8')[:1000]}\n```"
        
    await message.answer(res, parse_mode="Markdown")

# --- 5. БАПТАУЛАР (SETTINGS) ---
@dp.callback_query(F.data.startswith("menu_settings_"))
async def menu_settings(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    await callback.message.edit_text(
        "⚙️ **Жалпы Баптаулар (Settings)**\n\nСервистің техникалық параметрлерін реттеу:",
        reply_markup=settings_menu(bot_id), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("set_"))
async def settings_details(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    bot_id = int(callback.data.split("_")[2])
    
    details = {
        "source": "📂 **Source Repo (Дереккөз)**\n\nБұл жерде сіздің кодыңыз қайдан алынатыны көрсетіледі.\nАвтоматты деплой (Auto deploys when pushed to GitHub) қосулы.",
        "network": "🌐 **Networking (Желі және Домен)**\n\nPublic Networking: Қосылған жоқ\nPrivate Networking: `service.railway.internal`\nIPv6: Қолжетімді.",
        "scale": "⚖️ **Scale (Масштабтау)**\n\nRegion: US West (California, USA)\nReplicas: 1\nLimits: 8GB RAM, 7 vCPU.",
        "build": "🛠 **Build Command (Құрастыру)**\n\nBuilder: Railpack (python@3.11)\nCustom Build Command: `pip install -r requirements.txt`",
        "restart": "🔄 **Restart Policy (Қайта қосу)**\n\nЕреже: `On Failure`\nЕгер бот қатемен тоқтап қалса (non-zero exit code), жүйе оны автоматты түрде қайта қосады.",
        "delete": "🗑 **Delete Service (Сервисті өшіру)**\n\nБұл әрекетті қайтару мүмкін емес! Боттың барлық коды мен базасы жойылады. (Қазіргі уақытта бұл функция бұғатталған)."
    }
    
    text = details.get(action, "Белгісіз баптау.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Баптауларға қайту", callback_data=f"menu_settings_{bot_id}")]])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ҚОСЫМША БАСҚАРУЛАР ---
@dp.callback_query(F.data.startswith("run_"))
async def run_bot_handler(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[1])
    await runner_manager.start_sub_bot(bot_id, callback.message.chat.id, bot)
    await callback.answer()

@dp.callback_query(F.data.startswith("stop_"))
async def stop_bot_handler(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[1])
    await runner_manager.stop_sub_bot(bot_id, callback.message.chat.id, bot)
    await callback.answer()

async def main():
    await db.init_db()
    print("🚀 Басқарушы (Railway) бот қосылды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
