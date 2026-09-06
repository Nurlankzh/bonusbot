import asyncio
import sys
import os
from aiogram import Bot
import database as db

USER_BOTS_DIR = os.path.join(db.DATA_DIR, "user_bots")
os.makedirs(USER_BOTS_DIR, exist_ok=True)

class BotRunnerManager:
    def __init__(self):
        self.active_processes: dict[int, asyncio.subprocess.Process] = {}
        self.tasks: dict[int, list[asyncio.Task]] = {}

    async def start_sub_bot(self, bot_db_id: int, chat_id: int, master_bot: Bot, silent: bool = False):
        """Ішкі ботты жеке оқшауланған ортада іске қосу"""
        if bot_db_id in self.active_processes:
            if not silent:
                await master_bot.send_message(chat_id, "⚠️ Бұл бот қазірдің өзінде қосулы!")
            return

        bot_data = await db.get_bot(bot_db_id)
        code_data = await db.get_latest_code(bot_db_id)

        if not code_data:
            if not silent:
                await master_bot.send_message(chat_id, "❌ Ботта іске қосатын код жоқ!")
            return

        script_path = os.path.join(USER_BOTS_DIR, f"bot_{bot_db_id}.py")

        # Боттың кодына Токенді автоматты түрде дайындау
        header = (
            "import os\n"
            f"os.environ['BOT_TOKEN'] = '{bot_data['bot_token']}'\n"
            f"BOT_TOKEN = '{bot_data['bot_token']}'\n\n"
        )
        final_code = header + code_data['code']
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        # Ішкі процесске де орта айнымалысын (env) беру
        env = os.environ.copy()
        env["BOT_TOKEN"] = bot_data['bot_token']

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            self.active_processes[bot_db_id] = process
            await db.update_bot_status(bot_db_id, "running")

            if not silent:
                await master_bot.send_message(
                    chat_id, 
                    f"🚀 **Бот іске қосылды!**\n🆔 `Бот ID:` {bot_data['bot_id_name']}\n📌 `Нұсқасы:` v{code_data['version']}"
                )
            await db.add_log(bot_db_id, "INFO", "Бот сәтті қосылды")

            # Логтар мен қателерді бақылау
            task_out = asyncio.create_task(self._read_stream(bot_db_id, process.stdout, "STDOUT", chat_id, master_bot))
            task_err = asyncio.create_task(self._read_stream(bot_db_id, process.stderr, "STDERR", chat_id, master_bot))
            self.tasks[bot_db_id] = [task_out, task_err]

        except Exception as e:
            if not silent:
                await master_bot.send_message(chat_id, f"🚨 Жүйелік қате: `{str(e)}`")

    async def stop_sub_bot(self, bot_db_id: int, chat_id: int, master_bot: Bot):
        """Ботты тоқтату"""
        if bot_db_id in self.active_processes:
            process = self.active_processes[bot_db_id]
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
            del self.active_processes[bot_db_id]
            
            if bot_db_id in self.tasks:
                for t in self.tasks[bot_db_id]:
                    t.cancel()
                del self.tasks[bot_db_id]

            await db.update_bot_status(bot_db_id, "stopped")
            await master_bot.send_message(chat_id, f"🛑 Бот (ID: {bot_db_id}) тоқтатылды!")
            await db.add_log(bot_db_id, "INFO", "Бот тоқтатылды")
        else:
            await master_bot.send_message(chat_id, "ℹ️ Бұл бот белсенді емес.")

    async def restore_running_bots(self, master_bot: Bot, admin_id: int):
        """Сервер қайта жүктелгенде бұған дейін қосылып тұрған боттарды қайта ояту"""
        running_bots = await db.get_running_bots()
        if not running_bots:
            return

        restarted_count = 0
        for b in running_bots:
            await self.start_sub_bot(b['id'], admin_id, master_bot, silent=True)
            restarted_count += 1

        try:
            await master_bot.send_message(
                admin_id, 
                f"🔄 **Сервер қайта қосылды.**\n"
                f"⚡️ Барлығы **{restarted_count}** ішкі бот автоматты түрде қайта оятылып, іске қосылды!"
            )
        except Exception:
            pass

    async def _read_stream(self, bot_db_id: int, stream, stream_type: str, chat_id: int, master_bot: Bot):
        """Қателерді оқып, Телеграмға жіберу"""
        buffer = []
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode('utf-8', errors='replace')
            buffer.append(text)
            
            if stream_type == "STDERR" or "Traceback" in text or "Error" in text:
                full_error = "".join(buffer[-12:])
                await db.add_log(bot_db_id, "ERROR", full_error)
                
                msg = (
                    f"⚠️ **Бот кодонда ҚАТЕ АНЫҚТАЛДЫ!**\n"
                    f"🆔 `Бот DB ID:` {bot_db_id}\n"
                    f"🔍 `Қате логы:`\n```python\n{full_error[:3500]}\n```"
                )
                try:
                    await master_bot.send_message(chat_id, msg, parse_mode="Markdown")
                except Exception:
                    pass

runner_manager = BotRunnerManager()
