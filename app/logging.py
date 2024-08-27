import datetime
import decimal
import uuid
import orjson

from typing import Any, Mapping

from pydantic import BaseModel
from app.utils import tz_now, tz_now_to_str
from loguru import logger


def filter(record):
    record["time"] = tz_now().strftime("%Y-%m-%d %H:%M:%S.%f%z")
    message = record["message"].replace('"', "'")
    record["message"] = f'"{message}"'
    return True


logger.add("store/logs.csv", format="{time},{level},{message}", filter=filter)


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
        return obj.model_dump()
    else:
        return "This object cannot be serialized."


def log_event(
    actor: str | None,
    event: str,
    type: str,
    description: str = "",
    body: Mapping[str, Any] = {},
) -> None:
    try:
        data = dict(
            actor=actor,
            event=event,
            type=type,
            description=description,
            timestamp=tz_now_to_str(),
            body=body,
        )
        logger.info(orjson.dumps(data, default=default).decode("utf-8"))
    except Exception as e:
        logger.debug(f"Failed to log event: {str(e)}")
