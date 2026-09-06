import asyncio
import os
import shutil
import sys
from pathlib import Path

import aiohttp

import config
import database


class RunnerManager:

    def __init__(self):
        self.processes = {}
        self.locks = {}
        self.watchers = {}

    # ========================================================
    # LOCK
    # ========================================================

    def get_lock(self, bot_id):
        if bot_id not in self.locks:
            self.locks[bot_id] = asyncio.Lock()

        return self.locks[bot_id]

    # ========================================================
    # WORKSPACE
    # ========================================================

    def get_workspace(self, bot_id):
        return Path(config.WORKSPACE_DIR) / str(bot_id)

    # ========================================================
    # LOG
    # ========================================================

    async def safe_log(self, bot_id, level, message):
        try:
            await database.add_log(
                bot_id,
                level,
                message
            )
        except Exception as error:
            print(
                f"[DATABASE LOG ERROR] "
                f"bot={bot_id}: {error}"
            )

    # ========================================================
    # DELETE WEBHOOK
    # ========================================================

    async def delete_webhook(self, token):
        """
        Child bot webhook-ын автомат түрде өшіреді.
        Бұл getUpdates / polling конфликтін жояды.
        """

        url = (
            f"https://api.telegram.org/"
            f"bot{token}/deleteWebhook"
        )

        try:

            timeout = aiohttp.ClientTimeout(
                total=15
            )

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.post(
                    url,
                    json={
                        "drop_pending_updates": True
                    }
                ) as response:

                    data = await response.json()

                    if data.get("ok"):

                        print(
                            "🟢 Child bot webhook "
                            "өшірілді"
                        )

                        return True

                    print(
                        f"🔴 Webhook өшіру қатесі: "
                        f"{data}"
                    )

                    return False

        except Exception as error:

            print(
                f"🔴 Webhook request error: "
                f"{error}"
            )

            return False

    # ========================================================
    # START BOT
    # ========================================================

    async def start_sub_bot(self, bot_id):

        async with self.get_lock(bot_id):

            # ------------------------------------------------
            # EXISTING PROCESS
            # ------------------------------------------------

            existing = self.processes.get(
                bot_id
            )

            if existing:

                if existing.returncode is None:

                    return (
                        False,
                        "⚠️ Бот әлдеқашан "
                        "іске қосылып тұр."
                    )

                self.processes.pop(
                    bot_id,
                    None
                )

            # ------------------------------------------------
            # GET BOT
            # ------------------------------------------------

            bot_data = await database.get_bot(
                bot_id
            )

            if not bot_data:

                return (
                    False,
                    "❌ Бот табылмады."
                )

            # ------------------------------------------------
            # TOKEN
            # ------------------------------------------------

            token = (
                bot_data.get("bot_token")
                or ""
            ).strip()

            master_token = (
                config.BOT_TOKEN
                or ""
            ).strip()

            if not token:

                return (
                    False,
                    "❌ Child bot токені жоқ."
                )

            # ------------------------------------------------
            # MASTER TOKEN PROTECTION
            # ------------------------------------------------

            if getattr(
                config,
                "REJECT_MASTER_TOKEN_AS_CHILD",
                True
            ):

                if token == master_token:

                    return (
                        False,
                        "❌ Master bot токенін "
                        "Child bot ретінде "
                        "қолдануға болмайды."
                    )

            # ------------------------------------------------
            # GET LATEST CODE
            # ------------------------------------------------

            code_data = (
                await database.get_latest_code(
                    bot_id
                )
            )

            if not code_data:

                return (
                    False,
                    "❌ Ботқа Python коды "
                    "жазылмаған."
                )

            code = code_data.get(
                "code"
            )

            if not code:

                return (
                    False,
                    "❌ Код бос."
                )

            # ------------------------------------------------
            # CODE SIZE
            # ------------------------------------------------

            max_code_size = getattr(
                config,
                "MAX_CODE_SIZE",
                10 * 1024 * 1024
            )

            code_size = len(
                code.encode("utf-8")
            )

            if code_size > max_code_size:

                return (
                    False,
                    "❌ Python код тым үлкен."
                )

            # ------------------------------------------------
            # DELETE WEBHOOK
            # ------------------------------------------------

            webhook_deleted = (
                await self.delete_webhook(
                    token
                )
            )

            if webhook_deleted:

                await self.safe_log(
                    bot_id,
                    "INFO",
                    "Child bot webhook "
                    "өшірілді"
                )

            else:

                await self.safe_log(
                    bot_id,
                    "WARNING",
                    "Webhook өшірілмеді. "
                    "Bot polling кезінде "
                    "Conflict болуы мүмкін."
                )

            # ------------------------------------------------
            # WORKSPACE
            # ------------------------------------------------

            workspace = self.get_workspace(
                bot_id
            )

            workspace.mkdir(
                parents=True,
                exist_ok=True
            )

            # ------------------------------------------------
            # MAIN.PY
            # ------------------------------------------------

            main_file = (
                workspace / "main.py"
            )

            main_file.write_text(
                code,
                encoding="utf-8"
            )

            # ------------------------------------------------
            # ENV VARIABLES
            # ------------------------------------------------

            variables = (
                await database.get_env_vars(
                    bot_id
                )
            )

            env = os.environ.copy()

            for key, value in variables.items():

                env[str(key)] = str(value)

            # ------------------------------------------------
            # CHILD BOT TOKEN
            # ------------------------------------------------

            env["BOT_TOKEN"] = token

            # ------------------------------------------------
            # PYTHON SETTINGS
            # ------------------------------------------------

            env["PYTHONUNBUFFERED"] = "1"

            env[
                "PYTHONDONTWRITEBYTECODE"
            ] = "1"

            # ------------------------------------------------
            # PYTHON EXECUTABLE
            # ------------------------------------------------

            python_executable = getattr(
                config,
                "PYTHON_EXECUTABLE",
                "python"
            )

            # ------------------------------------------------
            # START PROCESS
            # ------------------------------------------------

            try:

                process = (
                    await asyncio.create_subprocess_exec(
                        python_executable,
                        "-u",
                        "main.py",

                        cwd=str(workspace),

                        env=env,

                        stdout=(
                            asyncio.subprocess.PIPE
                        ),

                        stderr=(
                            asyncio.subprocess.STDOUT
                        )
                    )
                )

            except Exception as error:

                await database.update_bot_status(
                    bot_id,
                    "crashed"
                )

                await self.safe_log(
                    bot_id,
                    "ERROR",
                    f"Process create error: "
                    f"{error}"
                )

                return (
                    False,
                    "❌ Процесті іске қосу қатесі:\n"
                    f"{error}"
                )

            # ------------------------------------------------
            # SAVE PROCESS
            # ------------------------------------------------

            self.processes[
                bot_id
            ] = process

            await database.update_bot_status(
                bot_id,
                "running"
            )

            # ------------------------------------------------
            # PID LOG
            # ------------------------------------------------

            await self.safe_log(
                bot_id,
                "INFO",
                f"Process started: "
                f"PID={process.pid}"
            )

            # ------------------------------------------------
            # WATCHER
            # ------------------------------------------------

            watcher = asyncio.create_task(
                self._watch_process(
                    bot_id,
                    process
                )
            )

            self.watchers[
                bot_id
            ] = watcher

            return (
                True,
                f"🟢 Бот іске қосылды.\n"
                f"PID: {process.pid}"
            )

    # ========================================================
    # WATCH PROCESS
    # ========================================================

    async def _watch_process(
        self,
        bot_id,
        process
    ):

        try:

            while True:

                line = (
                    await process.stdout.readline()
                )

                if not line:
                    break

                text = line.decode(
                    "utf-8",
                    errors="replace"
                ).rstrip()

                if not text:
                    continue

                print(
                    f"[BOT {bot_id}] "
                    f"{text}"
                )

                asyncio.create_task(
                    self.safe_log(
                        bot_id,
                        "OUTPUT",
                        text
                    )
                )

        except Exception as error:

            print(
                f"[WATCH ERROR] "
                f"bot={bot_id}: {error}"
            )

            asyncio.create_task(
                self.safe_log(
                    bot_id,
                    "ERROR",
                    str(error)
                )
            )

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        try:

            return_code = (
                await process.wait()
            )

        except Exception as error:

            return_code = -1

            await self.safe_log(
                bot_id,
                "ERROR",
                f"Process wait error: "
                f"{error}"
            )

        # ----------------------------------------------------
        # CURRENT PROCESS CHECK
        # ----------------------------------------------------

        current = self.processes.get(
            bot_id
        )

        if current is not process:
            return

        self.processes.pop(
            bot_id,
            None
        )

        self.watchers.pop(
            bot_id,
            None
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if return_code == 0:

            await database.update_bot_status(
                bot_id,
                "stopped"
            )

            await self.safe_log(
                bot_id,
                "INFO",
                f"Process exited: "
                f"{return_code}"
            )

        else:

            await database.update_bot_status(
                bot_id,
                "crashed"
            )

            await self.safe_log(
                bot_id,
                "ERROR",
                f"Process crashed: "
                f"exit code {return_code}"
            )

    # ========================================================
    # STOP BOT
    # ========================================================

    async def stop_sub_bot(
        self,
        bot_id
    ):

        async with self.get_lock(bot_id):

            process = self.processes.get(
                bot_id
            )

            if not process:

                await database.update_bot_status(
                    bot_id,
                    "stopped"
                )

                return (
                    False,
                    "⚠️ Бот іске қосылмаған."
                )

            if process.returncode is not None:

                self.processes.pop(
                    bot_id,
                    None
                )

                await database.update_bot_status(
                    bot_id,
                    "stopped"
                )

                return (
                    False,
                    "⚠️ Бот іске қосылмаған."
                )

            # ------------------------------------------------
            # TERMINATE
            # ------------------------------------------------

            try:

                process.terminate()

                try:

                    await asyncio.wait_for(
                        process.wait(),
                        timeout=getattr(
                            config,
                            "PROCESS_STOP_TIMEOUT",
                            10
                        )
                    )

                except asyncio.TimeoutError:

                    process.kill()

                    await process.wait()

            except ProcessLookupError:

                pass

            except Exception as error:

                await self.safe_log(
                    bot_id,
                    "ERROR",
                    f"Stop error: {error}"
                )

            # ------------------------------------------------
            # CLEAN PROCESS
            # ------------------------------------------------

            self.processes.pop(
                bot_id,
                None
            )

            watcher = self.watchers.pop(
                bot_id,
                None
            )

            if watcher:

                if not watcher.done():

                    watcher.cancel()

            await database.update_bot_status(
                bot_id,
                "stopped"
            )

            await self.safe_log(
                bot_id,
                "INFO",
                "Process stopped"
            )

            return (
                True,
                "🛑 Бот тоқтатылды."
            )

    # ========================================================
    # RESTART
    # ========================================================

    async def restart_sub_bot(
        self,
        bot_id
    ):

        await self.stop_sub_bot(
            bot_id
        )

        await asyncio.sleep(1)

        return await self.start_sub_bot(
            bot_id
        )

    # ========================================================
    # IS RUNNING
    # ========================================================

    def is_running(
        self,
        bot_id
    ):

        process = self.processes.get(
            bot_id
        )

        if not process:
            return False

        return process.returncode is None

    # ========================================================
    # PROCESS INFO
    # ========================================================

    async def get_process_info(
        self,
        bot_id
    ):

        process = self.processes.get(
            bot_id
        )

        if not process:
            return None

        return {
            "pid": process.pid,
            "running": (
                process.returncode is None
            ),
            "returncode": process.returncode
        }

    # ========================================================
    # STOP ALL
    # ========================================================

    async def stop_all(self):

        bot_ids = list(
            self.processes.keys()
        )

        for bot_id in bot_ids:

            try:

                await self.stop_sub_bot(
                    bot_id
                )

            except Exception as error:

                print(
                    f"STOP ALL ERROR "
                    f"{bot_id}: {error}"
                )

    # ========================================================
    # DELETE WORKSPACE
    # ========================================================

    async def delete_workspace(
        self,
        bot_id
    ):

        workspace = self.get_workspace(
            bot_id
        )

        if workspace.exists():

            shutil.rmtree(
                workspace,
                ignore_errors=True
            )


# ============================================================
# GLOBAL RUNNER
# ============================================================

runner_manager = RunnerManager()

runner = runner_manager
