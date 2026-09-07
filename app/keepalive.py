"""self-ping(keepalive).

Koyeb 무료 인스턴스는 1시간 동안 인바운드 트래픽이 없으면 scale-to-zero 된다. 슬랙 소켓 모드는
봇이 밖으로 여는 연결이라 트래픽으로 세지 않으므로, 자기 공개 URL 을 주기적으로 GET 해
인바운드 트래픽을 만든다. (sigongbot-mini 에서 검증된 패턴, 5분 주기)
"""

import httpx

from app.logging import logger


async def ping_self(url: str, *, timeout: float = 5.0) -> bool:
    """자기 공개 URL 을 한 번 GET 합니다.

    응답이 오면(상태 코드 무관) True, 실패하거나 URL 이 비어 있으면 False. 예외를 내지 않는다.
    스케줄러 잡으로 돌기 때문에 예외가 새면 잡 자체가 죽는다.
    """
    url = url.strip()
    if not url:
        logger.warning("KOYEB_URL 이 비어 있어 self-ping 을 건너뜁니다.")
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except Exception as e:
        logger.warning(f"self-ping 실패: {type(e).__name__}: {e} ({url})")
        return False
    logger.info(f"self-ping 성공: {response.status_code} ({url})")
    return True
