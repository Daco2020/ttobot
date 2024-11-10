import csv
from datetime import timedelta
import os
import traceback
from typing import TypedDict

import pandas as pd
import tenacity
from app.constants import remind_message
from app.logging import log_event
from app.models import User
from app.slack.repositories import SlackRepository
from slack_sdk.models.blocks import (
    SectionBlock,
    TextObject,
    ActionsBlock,
    ContextBlock,
    ButtonElement,
    DividerBlock,
)

from slack_bolt.async_app import AsyncApp
from app.config import settings


import asyncio

from app.utils import dict_to_json_str, tz_now


class SubscriptionMessage(TypedDict):
    user_id: str
    target_user_id: str
    target_user_channel: str
    ts: str
    title: str
    dt: str


class BackgroundService:
    def __init__(self, repo: SlackRepository) -> None:
        self._repo = repo

    async def send_reminder_message_to_user(self, slack_app: AsyncApp) -> None:
        """사용자에게 리마인드 메시지를 전송합니다."""
        users = self._repo.fetch_users()

        target_users: list[User] = []
        for user in users:
            if user.cohort != "10기":  # 10기 외의 사용자 제외
                continue
            if user.channel_name == "-":  # 채널 이름이 없는 경우 제외
                continue
            if user.is_submit:  # 이미 제출한 경우 제외
                continue

            target_users.append(user)

        for user in target_users:
            log_event(
                actor="slack_reminder_service",
                event="send_reminder_message_to_user",
                type="reminder",
                description=f"{user.name} 님에게 리마인드 메시지를 전송합니다.",
            )

            await slack_app.client.chat_postMessage(
                channel=user.user_id,
                text=remind_message.format(user_name=user.name),
            )

            # 슬랙은 메시지 전송을 초당 1개를 권장하기 때문에 1초 대기합니다.
            # 참고문서: https://api.slack.com/methods/chat.postMessage#rate_limiting
            await asyncio.sleep(1)

        await slack_app.client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL,
            text=f"총 {len(target_users)} 명에게 리마인드 메시지를 전송했습니다.",
        )

    async def prepare_subscribe_message_data(self) -> None:
        """사용자에게 구독 알림 메시지 목록을 임시 CSV 파일로 저장합니다."""

        # 기존 임시 파일 삭제
        if os.path.exists("store/_subscription_messages.csv"):
            os.remove("store/_subscription_messages.csv")

        # 모든 구독 정보를 가져옵니다
        subscriptions = self._repo.fetch_subscriptions()

        # 구독 대상자들의 user_id를 중복 없이 set으로 추출합니다
        target_user_ids = {
            subscription.target_user_id for subscription in subscriptions
        }

        yesterday = (tz_now() - timedelta(days=1)).date()
        contents_df = pd.read_csv("store/contents.csv")

        # dt 컬럼을 datetime 타입으로 변환하고 date 부분만 추출합니다
        contents_df["dt"] = pd.to_datetime(contents_df["dt"]).dt.date

        # 구독 대상자의 콘텐츠 중 어제 작성된 제출 글만 필터링합니다
        filtered_contents = contents_df[
            (contents_df["user_id"].isin(target_user_ids))
            & (contents_df["dt"] == yesterday)
            & (contents_df["type"] == "submit")
        ]

        # 구독 알림 메시지 데이터를 저장할 리스트
        subscription_messages: list[SubscriptionMessage] = []

        # 각 구독 대상자별로 처리를 시작합니다
        for target_user_id in target_user_ids:
            target_contents = filtered_contents[
                filtered_contents["user_id"] == target_user_id
            ]

            # 해당 구독 대상자의 콘텐츠가 없으면 다음 대상자로 넘어갑니다
            if len(target_contents) == 0:
                continue

            # 현재 구독 대상자를 구독하는 모든 구독자 정보를 가져옵니다
            target_subscriptions = self._repo.fetch_subscriptions_by_target_user_id(
                target_user_id
            )

            # 구독자에게 보낼 알림을 배열에 담습니다.
            for subscription in target_subscriptions:
                for _, content in target_contents.iterrows():
                    subscription_messages.append(
                        {
                            "user_id": subscription.user_id,
                            "target_user_id": target_user_id,
                            "target_user_channel": subscription.target_user_channel,
                            "ts": content["ts"],
                            "title": content["title"],
                            "dt": content["dt"],
                        }
                    )

        # 임시 CSV 파일에 저장합니다.
        if subscription_messages:
            pd.DataFrame(subscription_messages).to_csv(
                "store/_subscription_messages.csv",
                index=False,
                quoting=csv.QUOTE_ALL,
            )

    async def send_subscription_messages(self, slack_app: AsyncApp) -> None:
        """사용자에게 구독 알림 메시지를 전송합니다."""
        if not os.path.exists("store/_subscription_messages.csv"):
            return

        df = pd.read_csv("store/_subscription_messages.csv")
        for _, row in df.iterrows():
            try:
                message: SubscriptionMessage = row.to_dict()
                await self._send_subscription_message(slack_app, message)

            except Exception as e:
                trace = traceback.format_exc()
                error_message = f"⚠️ <@{row['user_id']}>님의 구독 알림 메시지 전송에 실패했습니다. 오류: {e} {trace}"
                log_event(
                    actor="slack_subscribe_service",
                    event="send_subscription_message_to_user",
                    type="error",
                    description=error_message,
                )
                await slack_app.client.chat_postMessage(
                    channel=settings.ADMIN_CHANNEL,
                    text=error_message,
                )
                continue

        await slack_app.client.chat_postMessage(
            channel=settings.ADMIN_CHANNEL,
            text=f"총 {len(df['user_id'].unique())} 명에게 {len(df)} 개의 구독 알림 메시지를 전송했습니다.",
        )

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(1),
        reraise=True,
    )
    async def _send_subscription_message(
        self, slack_app: AsyncApp, message: SubscriptionMessage
    ) -> None:
        permalink_res = await slack_app.client.chat_getPermalink(
            message_ts=message["ts"],
            channel=message["target_user_channel"],
        )

        text = f"구독하신 <@{message['target_user_id']}>님의 새로운 글이 올라왔어요! 🤩"
        blocks = [
            SectionBlock(
                text=text,
            ),
            ContextBlock(
                elements=[
                    TextObject(
                        type="mrkdwn",
                        text=f"글 제목 : {message['title']}\n제출 날짜 : {message['dt'][:4]}년 {int(message['dt'][5:7])}월 {int(message['dt'][8:10])}일",
                    ),
                ],
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="글 보러가기",
                        action_id="open_subscription_permalink",
                        url=permalink_res["permalink"],
                        style="primary",
                        value=dict_to_json_str(
                            {
                                "user_id": message["user_id"],  # 구독자
                                "ts": message["ts"],  # 클릭한 콘텐츠 id
                            }
                        ),
                    ),
                    ButtonElement(
                        text="감사의 종이비행기 보내기",
                        action_id="send_paper_plane_message",
                        value=message["target_user_id"],
                    ),
                ]
            ),
            DividerBlock(),
        ]
        await slack_app.client.chat_postMessage(
            channel=message["user_id"],
            text=text,
            blocks=blocks,
        )

        # 슬랙은 메시지 전송을 초당 1개를 권장하기 때문에 1초 대기합니다.
        # 참고문서: https://api.slack.com/methods/chat.postMessage#rate_limiting
        await asyncio.sleep(1)
