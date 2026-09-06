import asyncio
import os
import sys

import config
import database as db


class RunnerManager:
    def __init__(self):
        self.processes = {}
        self.locks = {}

    def get_lock(self, bot_id):
        if bot_id not in self.locks:
            self.locks[bot_id] = asyncio.Lock()
        return self.locks[bot_id]

    def workspace(self, bot_id):
        path = os.path.join(
            config.WORKSPACE_DIR,
            str(bot_id)
        )
        os.makedirs(path, exist_ok=True)
        return path

    async def start_sub_bot(self, bot_id, chat_id, master_bot):
        async with self.get_lock(bot_id):

            if bot_id in self.processes:
                process = self.processes[bot_id]

                if process.returncode is None:
                    await master_bot.send_message(
                        chat_id,
                        "🟢 Бот қазірдің өзінде қосулы."
                    )
                    return

            bot_data = await db.get_bot(bot_id)

            if not bot_data:
                await master_bot.send_message(
                    chat_id,
                    "❌ Жоба табылмады."
                )
                return

            code_data = await db.get_latest_code(bot_id)

            if not code_data:
                await master_bot.send_message(
                    chat_id,
                    "❌ Deploy жасау үшін алдымен код қосыңыз."
                )
                return

            workspace = self.workspace(bot_id)
            main_file = os.path.join(workspace, "main.py")

            with open(main_file, "w", encoding="utf-8") as f:
                f.write(code_data["code"])

            variables = await db.get_env_vars(bot_id)

            env = os.environ.copy()

            for key, value in variables.items():
                env[key] = value

            env["BOT_ID"] = str(bot_id)

            await db.update_bot_status(bot_id, "starting")

            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-u",
                    main_file,
                    cwd=workspace,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

                self.processes[bot_id] = process

                await db.update_bot_status(bot_id, "running")

                await db.add_log(
                    bot_id,
                    "INFO",
                    f"Process started: PID={process.pid}"
                )

                await master_bot.send_message(
                    chat_id,
                    f"🟢 Бот іске қосылды.\nPID: `{process.pid}`",
                    parse_mode="Markdown"
                )

                asyncio.create_task(
                    self.watch_process(
                        bot_id,
                        process,
                        chat_id,
                        master_bot
                    )
                )

            except Exception as e:
                await db.update_bot_status(bot_id, "crashed")

                await db.add_log(
                    bot_id,
                    "ERROR",
                    repr(e)
                )

                await master_bot.send_message(
                    chat_id,
                    f"❌ Іске қосу қатесі:\n`{str(e)[:1500]}`",
                    parse_mode="Markdown"
                )

    async def watch_process(
        self,
        bot_id,
        process,
        chat_id,
        master_bot
    ):
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
                    await db.add_log(
                        bot_id,
                        "OUTPUT",
                        text[:4000]
                    )

            return_code = await process.wait()

            self.processes.pop(bot_id, None)

            if return_code == 0:
                status = "stopped"
            else:
                status = "crashed"

            await db.update_bot_status(
                bot_id,
                status
            )

            await db.add_log(
                bot_id,
                "INFO" if return_code == 0 else "ERROR",
                f"Process exited with code {return_code}"
            )

            bot_data = await db.get_bot(bot_id)

            if (
                bot_data
                and bot_data["auto_restart"]
                and return_code != 0
            ):
                await db.add_log(
                    bot_id,
                    "WARNING",
                    "Auto restart scheduled"
                )

                await asyncio.sleep(5)

                await self.start_sub_bot(
                    bot_id,
                    chat_id,
                    master_bot
                )
            else:
                await master_bot.send_message(
                    chat_id,
                    f"ℹ️ Бот тоқтады.\nExit code: `{return_code}`",
                    parse_mode="Markdown"
                )

        except Exception as e:
            await db.update_bot_status(
                bot_id,
                "crashed"
            )

            await db.add_log(
                bot_id,
                "ERROR",
                repr(e)
            )

    async def stop_sub_bot(
        self,
        bot_id,
        chat_id,
        master_bot
    ):
        async with self.get_lock(bot_id):

            process = self.processes.get(bot_id)

            if not process:
                await db.update_bot_status(
                    bot_id,
                    "stopped"
                )

                await master_bot.send_message(
                    chat_id,
                    "🔴 Бот қазір қосулы емес."
                )
                return

            try:
                process.terminate()

                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=5
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                self.processes.pop(
                    bot_id,
                    None
                )

                await db.update_bot_status(
                    bot_id,
                    "stopped"
                )

                await db.add_log(
                    bot_id,
                    "INFO",
                    "Process manually stopped"
                )

                await master_bot.send_message(
                    chat_id,
                    "🔴 Бот тоқтатылды."
                )

            except Exception as e:
                await db.add_log(
                    bot_id,
                    "ERROR",
                    repr(e)
                )

                await master_bot.send_message(
                    chat_id,
                    f"❌ Stop қатесі: `{str(e)[:1000]}`",
                    parse_mode="Markdown"
                )

    async def restart_sub_bot(
        self,
        bot_id,
        chat_id,
        master_bot
    ):
        await self.stop_sub_bot(
            bot_id,
            chat_id,
            master_bot
        )

        await asyncio.sleep(1)

        await self.start_sub_bot(
            bot_id,
            chat_id,
            master_bot
        )


runner_manager = RunnerManager()
