import asyncio
import sys
import os
from aiogram import Bot
import database as db

USER_BOTS_DIR = os.path.join(db.DATA_DIR, "user_bots")

class BotRunnerManager:
    def __init__(self):
        self.active_processes: dict[int, asyncio.subprocess.Process] = {}
        self.tasks: dict[int, list[asyncio.Task]] = {}

    async def start_sub_bot(self, bot_db_id: int, chat_id: int, master_bot: Bot):
        """Ішкі ботты жеке subprocess арқылы іске қосу"""
        if bot_db_id in self.active_processes:
            await master_bot.send_message(chat_id, "⚠️ Бұл бот қазірдің өзінде қосулы!")
            return
            
        bot_data = await db.get_bot(bot_db_id)
        code_data = await db.get_latest_code(bot_db_id)
        
        if not code_data:
            await master_bot.send_message(chat_id, "❌ Ботта іске қосатын код жоқ! Алдымен код жіберіңіз.")
            return

        # 'user_bots' папкасын құру және кодты файлға жазу
        os.makedirs(USER_BOTS_DIR, exist_ok=True)
        script_path = os.path.join(USER_BOTS_DIR, f"bot_{bot_db_id}.py")

        # Токенді кодтың басына автоматты түрде дайындау
        final_code = f"BOT_TOKEN = '{bot_data['bot_token']}'\n\n" + code_data['code']
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        # Процесті оқшауланған түрде ашу
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.active_processes[bot_db_id] = process
            await db.update_bot_status(bot_db_id, "running")

            # Бот қосылғанда хабарлау
            await master_bot.send_message(
                chat_id, 
                f"🚀 **Бот іске қосылды!**\n🆔 `Бот ID:` {bot_data['bot_id_name']}\n📌 `Нұсқасы:` v{code_data['version']}",
                parse_mode="Markdown"
            )
            await db.add_log(bot_db_id, "INFO", "Бот сәтті қосылды")

            # Логтар мен қателерді фондық режимде бақылау
            task_out = asyncio.create_task(self._read_stream(bot_db_id, process.stdout, "STDOUT", chat_id, master_bot))
            task_err = asyncio.create_task(self._read_stream(bot_db_id, process.stderr, "STDERR", chat_id, master_bot))
            self.tasks[bot_db_id] = [task_out, task_err]
            
        except Exception as e:
            await master_bot.send_message(chat_id, f"🚨 Ботты іске қосу кезінде жүйелік қате: `{str(e)}`")

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

    async def _read_stream(self, bot_db_id: int, stream, stream_type: str, chat_id: int, master_bot: Bot):
        """Процестің логтары мен Traceback қателерін оқу"""
        buffer = []
        while True:
            try:
                line = await stream.readline()
            except Exception:
                break
            if not line:
                break
                
            text = line.decode('utf-8', errors='replace').strip()
            if not text:
                continue
            buffer.append(text)

            # Қате немесе Traceback анықталса
            if stream_type == "STDERR" or "Traceback" in text or "Error" in text:
                full_error = "\n".join(buffer[-10:])  # Соңғы 10 жолды жинау
                await db.add_log(bot_db_id, "ERROR", full_error)

                # Қатені Telegram-ға жіберу
                msg = (
                    f"⚠️ **Бот кодонда ҚАТЕ АНЫҚТАЛДЫ!**\n"
                    f"🆔 `Бот DB ID:` {bot_db_id}\n"
                    f"🔍 `Қате / Лог сәті:`\n```python\n{full_error[:3500]}\n```"
                )
                try:
                    await master_bot.send_message(chat_id, msg, parse_mode="Markdown")
                except Exception:
                    pass

runner_manager = BotRunnerManager()
