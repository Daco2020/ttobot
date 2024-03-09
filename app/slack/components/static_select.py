from typing import Any


def options(options: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "text": {"type": "plain_text", "text": value},
            "value": value,
        }
        for value in options
    ]
