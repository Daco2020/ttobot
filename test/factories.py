"""테스트용 도메인 모델 팩토리.

각 함수는 합리적인 기본값을 가진 모델 인스턴스를 반환한다.
필요한 필드만 키워드 인자로 덮어쓰면 된다.
"""

from __future__ import annotations

from typing import Any

from app import models


def make_user(**overrides: Any) -> models.User:
    defaults: dict[str, Any] = {
        "user_id": "U_TEST",
        "name": "테스트유저",
        "channel_name": "test_channel",
        "channel_id": "C_TEST",
        "intro": "안녕하세요. 테스트입니다.",
        "deposit": "100000",
        "cohort": "10기",
        "contents": [],
    }
    defaults.update(overrides)
    return models.User(**defaults)


def make_simple_user(**overrides: Any) -> models.SimpleUser:
    defaults: dict[str, Any] = {
        "user_id": "U_TEST",
        "name": "테스트유저",
        "channel_name": "test_channel",
        "channel_id": "C_TEST",
        "intro": "안녕하세요.",
        "cohort": "10기",
    }
    defaults.update(overrides)
    return models.SimpleUser(**defaults)


def make_content(**overrides: Any) -> models.Content:
    defaults: dict[str, Any] = {
        "dt": "2025-01-01 12:00:00",
        "user_id": "U_TEST",
        "username": "테스트유저",
        "type": "submit",
        "content_url": "https://example.com/post",
        "title": "테스트 글",
        "category": "기술 & 언어",
        "tags": "태그1,태그2",
        "curation_flag": "N",
        "ts": "1735700000.000000",
        "feedback_intensity": "HOT",
    }
    defaults.update(overrides)
    return models.Content(**defaults)


def make_bookmark(**overrides: Any) -> models.Bookmark:
    defaults: dict[str, Any] = {
        "user_id": "U_TEST",
        "content_user_id": "U_OTHER",
        "content_ts": "1735700000.000000",
        "note": "",
    }
    defaults.update(overrides)
    return models.Bookmark(**defaults)


def make_coffee_chat_proof(**overrides: Any) -> models.CoffeeChatProof:
    defaults: dict[str, Any] = {
        "ts": "1735700000.000000",
        "thread_ts": "",
        "user_id": "U_TEST",
        "text": "커피챗 후기입니다.",
        "image_urls": "",
        "selected_user_ids": "U_OTHER",
    }
    defaults.update(overrides)
    return models.CoffeeChatProof(**defaults)


def make_point_history(**overrides: Any) -> models.PointHistory:
    defaults: dict[str, Any] = {
        "user_id": "U_TEST",
        "reason": "글 제출",
        "point": 100,
        "category": models.PointCategory.WRITING,
    }
    defaults.update(overrides)
    return models.PointHistory(**defaults)


def make_paper_plane(**overrides: Any) -> models.PaperPlane:
    defaults: dict[str, Any] = {
        "sender_id": "U_SENDER",
        "sender_name": "발신자",
        "receiver_id": "U_RECEIVER",
        "receiver_name": "수신자",
        "text": "감사합니다.",
        "text_color": "#FFFFFF",
        "bg_color": "#BC2026",
        "color_label": "valentine_1",
    }
    defaults.update(overrides)
    return models.PaperPlane(**defaults)


def make_subscription(**overrides: Any) -> models.Subscription:
    defaults: dict[str, Any] = {
        "user_id": "U_TEST",
        "target_user_id": "U_OTHER",
        "target_user_channel": "C_OTHER",
    }
    defaults.update(overrides)
    return models.Subscription(**defaults)
