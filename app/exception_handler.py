from functools import wraps
from app import slack
from app.logging import logger
import traceback
from app.config import settings


def exception_handler_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(e)
            trace = traceback.format_exc()
            await slack.app.client.chat_postMessage(
                channel=settings.ADMIN_CHANNEL, text=trace
            )
            print(trace)

    return wrapper
