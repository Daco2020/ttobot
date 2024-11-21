from app.logging import logger


from slack_sdk.web.async_client import AsyncWebClient


from typing import Any


async def send_point_noti_message(
    client: AsyncWebClient,
    channel: str,
    text: str,
    **kwargs: Any,
) -> None:
    """포인트 알림 메시지를 전송합니다."""
    try:
        await client.chat_postMessage(channel=channel, text=text)
    except Exception as e:
        kwargs_str = ", ".join([f"{k}: {v}" for k, v in kwargs.items()])
        text = text.replace("\n", " ")
        logger.error(
            f"포인트 알림 전송 에러 👉 error: {str(e)} :: channel(user_id): {channel} text: {text} {kwargs_str}"
        )
        pass
