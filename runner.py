import asyncio
import sys
import os
from aiogram import Bot
import database as db

class BotRunnerManager:
    def __init__(self):
        self.active_processes: dict[int, asyncio.subprocess.Process] = {}
        self.tasks: dict[int, list[asyncio.Task]] = {}

    async def start_sub_bot(self, bot_db_id: int, chat_id: int, master_bot: Bot):
        if bot_db_id in self.active_processes:
            await master_bot.send_message(chat_id, "⚠️ Бұл процесс қазірдің өзінде қосулы тұр!")
            return

        bot_data = await db.get_bot(bot_db_id)
        code_data = await db.get_latest_code(bot_db_id)
        env_vars = await db.get_env_vars(bot_db_id)

        if not code_data:
            await master_bot.send_message(chat_id, "❌ Ботта іске қосатын код жоқ. Алдымен код жүктеңіз.")
            return

        os.makedirs("user_bots", exist_ok=True)
        script_path = os.path.join("user_bots", f"bot_{bot_db_id}.py")

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code_data['code'])

        # Айнымалыларды оқшауланған ортаға (Environment) қосу
        env = os.environ.copy()
        env.update(env_vars)

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            self.active_processes[bot_db_id] = process
            await db.update_bot_status(bot_db_id, "running")
            await db.add_log(bot_db_id, "INFO", "Бот сәтті іске қосылды.")

            msg = await master_bot.send_message(chat_id, f"🚀 **Бот іске қосылды!**\n🆔 Сервис: `{bot_data['bot_id_name']}`\n📌 Нұсқа: `v{code_data['version']}`", parse_mode="Markdown")

            task_out = asyncio.create_task(self._read_stream(bot_db_id, process.stdout, "STDOUT", chat_id, master_bot))
            task_err = asyncio.create_task(self._read_stream(bot_db_id, process.stderr, "STDERR", chat_id, master_bot))
            task_monitor = asyncio.create_task(self._monitor_crash(bot_db_id, chat_id, master_bot))
            self.tasks[bot_db_id] = [task_out, task_err, task_monitor]

        except Exception as e:
            await master_bot.send_message(chat_id, f"🚨 **Жүйелік қате:**\n`{str(e)}`", parse_mode="Markdown")

    async def stop_sub_bot(self, bot_db_id: int, chat_id: int, master_bot: Bot):
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
            await db.add_log(bot_db_id, "INFO", "Бот тоқтатылды.")
            await master_bot.send_message(chat_id, f"🛑 **Бот тоқтатылды.** (ID: {bot_db_id})", parse_mode="Markdown")
        else:
            await master_bot.send_message(chat_id, "ℹ️ Бұл бот қосылмаған.")

    async def _monitor_crash(self, bot_db_id: int, chat_id: int, master_bot: Bot):
        """Боттың құлағанын бақылау және хабарлау (Crash Recovery)"""
        process = self.active_processes.get(bot_db_id)
        if not process: return
        await process.wait()
        
        if bot_db_id in self.active_processes:
            del self.active_processes[bot_db_id]
            await db.update_bot_status(bot_db_id, "crashed")
            await master_bot.send_message(chat_id, f"💥 **CRASH АНЫҚТАЛДЫ!**\nСервис (ID: {bot_db_id}) жұмысын тоқтатты. Логтарды тексеріңіз.", parse_mode="Markdown")

    async def _read_stream(self, bot_db_id: int, stream, stream_type: str, chat_id: int, master_bot: Bot):
        """Логтарды оқу. Егер қате болса, Телеграмға жіберу"""
        buffer = []
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode('utf-8', errors='replace').strip()
            if text:
                buffer.append(text)
                if stream_type == "STDERR" or "Traceback" in text or "Exception" in text:
                    full_error = "\n".join(buffer[-15:])
                    await db.add_log(bot_db_id, "ERROR", full_error)
                    try:
                        await master_bot.send_message(chat_id, f"⚠️ **ҚАТЕ (LOGS):**\n```python\n{full_error[:3500]}\n```", parse_mode="Markdown")
                    except: pass
                    buffer.clear()

runner_manager = BotRunnerManager()
