from functools import wraps
from app.logging import logger
import traceback


def exception_handler_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Caught an exception: {e}")
            print(traceback.format_exc())

    return wrapper
