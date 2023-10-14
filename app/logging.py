import datetime
import decimal
import uuid
import orjson

from typing import Any

from pydantic import BaseModel
from app.utils import now_dt_to_str
from loguru import logger

logger.add("store/logs.csv", format="{time},{level},{message}")


def default(obj: Any) -> str | list[Any] | dict[str, Any]:
    if isinstance(obj, (decimal.Decimal, uuid.UUID)):
        return str(obj)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode("utf-8")
    elif isinstance(obj, BaseModel):
        return obj.dict()
    else:
        return "This object cannot be serialized."


def log_event(
    actor: str | None,
    event: str,
    type: str,
    description: str = "",
    body: dict[str, Any] = {},
) -> None:
    try:
        data = dict(
            actor=actor,
            event=event,
            type=type,
            description=description,
            timestamp=now_dt_to_str(),
            body=body,
        )
        logger.info(orjson.dumps(data, default=default).decode("utf-8"))
    except Exception as e:
        logger.debug(f"Failed to log event: {str(e)}")
