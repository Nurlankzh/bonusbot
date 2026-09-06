import os


BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()


admin_id_value = os.getenv(
    "ADMIN_ID",
    ""
).strip()


if not admin_id_value:
    raise RuntimeError(
        "ADMIN_ID Railway Variables ішінде көрсетілмеген."
    )


try:

    ADMIN_ID = int(
        admin_id_value
    )

except ValueError:

    raise RuntimeError(
        "ADMIN_ID тек сан болуы керек."
    )


WORKSPACE_DIR = os.getenv(
    "WORKSPACE_DIR",
    "/app/workspaces"
)


DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "/app/data/database.db"
)
