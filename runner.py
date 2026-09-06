import asyncio
import os
import shutil
import sys
from pathlib import Path

import config
import database


class RunnerManager:

    def __init__(self):
        self.processes = {}
        self.locks = {}

    def get_lock(self, bot_id):
        if bot_id not in self.locks:
            self.locks[bot_id] = asyncio.Lock()

        return self.locks[bot_id]

    def get_workspace(self, bot_id):
        return Path(config.WORKSPACE_DIR) / str(bot_id)

    async def start_sub_bot(self, bot_id):

        async with self.get_lock(bot_id):

            existing = self.processes.get(bot_id)

            if existing:
                if existing.returncode is None:
                    return False, "⚠️ Бот әлдеқашан іске қосылып тұр."

                self.processes.pop(bot_id, None)

            bot_data = await database.get_bot(bot_id)

            if not bot_data:
                return False, "❌ Бот табылмады."

            bot_token = (bot_data.get("bot_token") or "").strip()
            master_token = (config.BOT_TOKEN or "").strip()

            if not bot_token:
                return False, "❌ Child bot токені жоқ."

            if bot_token == master_token:
                return False, "❌ Child bot токені конструктор токенімен бірдей."

            code_data = await database.get_latest_code(bot_id)

            if not code_data:
                return False, "❌ Ботқа Python коды жазылмаған."

            code = code_data.get("code")

            if not code:
                return False, "❌ Код бос."

            workspace = self.get_workspace(bot_id)

            workspace.mkdir(
                parents=True,
                exist_ok=True
            )

            main_file = workspace / "main.py"

            main_file.write_text(
                code,
                encoding="utf-8"
            )

            variables = await database.get_env_vars(bot_id)

            env = os.environ.copy()

            for key, value in variables.items():
                env[str(key)] = str(value)

            env["BOT_TOKEN"] = bot_token

            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "main.py",
                cwd=str(workspace),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            self.processes[bot_id] = process

            await database.update_bot_status(
                bot_id,
                "running"
            )

            await database.add_log(
                bot_id,
                "INFO",
                f"Process started: PID={process.pid}"
            )

            asyncio.create_task(
                self._watch_process(
                    bot_id,
                    process
                )
            )

            return True, (
                "🟢 Бот іске қосылды.\n"
                f"PID: {process.pid}"
            )

    async def _watch_process(self, bot_id, process):

        try:

            while True:

                line = await process.stdout.readline()

                if not line:
                    break

                text = line.decode(
                    "utf-8",
                    errors="replace"
                ).rstrip()

                if text:
                    await database.add_log(
                        bot_id,
                        "OUTPUT",
                        text
                    )

        except Exception as error:

            await database.add_log(
                bot_id,
                "ERROR",
                str(error)
            )

        return_code = await process.wait()

        if self.processes.get(bot_id) is process:
            self.processes.pop(bot_id, None)

            if return_code == 0:
                await database.update_bot_status(
                    bot_id,
                    "stopped"
                )

                await database.add_log(
                    bot_id,
                    "INFO",
                    f"Process exited with code {return_code}"
                )

            else:
                await database.update_bot_status(
                    bot_id,
                    "crashed"
                )

                await database.add_log(
                    bot_id,
                    "ERROR",
                    f"Process exited with code {return_code}"
                )

    async def stop_sub_bot(self, bot_id):

        async with self.get_lock(bot_id):

            process = self.processes.get(bot_id)

            if not process:
                await database.update_bot_status(
                    bot_id,
                    "stopped"
                )

                return False, "⚠️ Бот іске қосылмаған."

            if process.returncode is not None:

                self.processes.pop(
                    bot_id,
                    None
                )

                await database.update_bot_status(
                    bot_id,
                    "stopped"
                )

                return False, "⚠️ Бот іске қосылмаған."

            try:

                process.terminate()

                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=10
                    )

                except asyncio.TimeoutError:

                    process.kill()

                    await process.wait()

            except ProcessLookupError:
                pass

            self.processes.pop(
                bot_id,
                None
            )

            await database.update_bot_status(
                bot_id,
                "stopped"
            )

            await database.add_log(
                bot_id,
                "INFO",
                "Process stopped"
            )

            return True, "🛑 Бот тоқтатылды."

    async def restart_sub_bot(self, bot_id):

        await self.stop_sub_bot(bot_id)

        await asyncio.sleep(1)

        return await self.start_sub_bot(bot_id)

    def is_running(self, bot_id):

        process = self.processes.get(bot_id)

        if not process:
            return False

        return process.returncode is None

    async def get_process_info(self, bot_id):

        process = self.processes.get(bot_id)

        if not process:
            return None

        return {
            "pid": process.pid,
            "running": process.returncode is None,
            "returncode": process.returncode
        }

    async def delete_workspace(self, bot_id):

        workspace = self.get_workspace(bot_id)

        if workspace.exists():
            shutil.rmtree(workspace)


runner_manager = RunnerManager()
runner = runner_manager
