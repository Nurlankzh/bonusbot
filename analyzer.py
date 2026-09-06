import ast
import re
import traceback


def analyze_code(code):
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "ok": False,
            "error": (
                f"SyntaxError: {e.msg}\n"
                f"Файл: main.py\n"
                f"Жол: {e.lineno}\n"
                f"Баған: {e.offset}"
            )
        }

    warnings = []

    token_pattern = re.compile(
        r"\d{8,12}:[A-Za-z0-9_-]{30,}"
    )

    if token_pattern.search(code):
        warnings.append(
            "Telegram token кодтың ішінде ашық жазылған. "
            "BOT_TOKEN environment variable қолдан."
        )

    return {
        "ok": True,
        "warnings": warnings
    }


def format_exception(exc):
    return "".join(
        traceback.format_exception(
            type(exc),
            exc,
            exc.__traceback__
        )
    )
