from functools import wraps
from app import slack
from app.logging import logger
import traceback


def exception_handler_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(e)
            admin_id = "U02HPESDZT3"  # TODO: 어드민 유저 아이디로 환경변수 주입
            trace = traceback.format_exc()
            print(trace)
            await slack.app.client.chat_postMessage(channel=admin_id, text=trace)

    return wrapper
