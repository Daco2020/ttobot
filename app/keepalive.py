"""self-ping(keepalive).

Koyeb 무료 인스턴스는 1시간 동안 인바운드 트래픽이 없으면 scale-to-zero 된다. 슬랙 소켓 모드는
봇이 밖으로 여는 연결이라 트래픽으로 세지 않으므로, 자기 공개 URL 을 주기적으로 GET 해
인바운드 트래픽을 만든다. (sigongbot-mini 에서 검증된 패턴, 5분 주기)
"""

from collections.abc import Awaitable, Callable

import httpx

from app.logging import logger

# 이만큼 연속 실패하면 관리자에게 1회 알린다. 5분 주기라 3회 = 15분.
ALERT_AFTER_FAILURES = 3
_failure_streak = 0


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


async def keepalive_job(url: str, notify: Callable[[str], Awaitable[None]]) -> bool:
    """스케줄러 잡. ping 결과를 돌려주고, 연속 실패가 ALERT_AFTER_FAILURES 에 닿는 순간 1회 알린다.

    성공하면 카운트를 0으로 되돌린다. 알림 전송이 실패해도 잡은 죽지 않는다.
    """
    global _failure_streak
    ok = await ping_self(url)
    if ok:
        _failure_streak = 0
        return True
    _failure_streak += 1
    if _failure_streak == ALERT_AFTER_FAILURES:
        try:
            await notify(
                f"🫢 self-ping 이 {ALERT_AFTER_FAILURES}회 연속 실패했어요. "
                f"KOYEB_URL 을 확인해주세요. ({url}) 이대로면 1시간 뒤 인스턴스가 잠듭니다."
            )
        except Exception as e:
            logger.warning(f"self-ping 알림 전송 실패: {type(e).__name__}: {e}")
    return False
