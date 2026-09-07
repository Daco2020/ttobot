import csv
from slack_bolt.async_app import AsyncAck
from slack_sdk.models.views import View
from slack_sdk.web.async_client import AsyncWebClient
from app import models
from app import store
from app.slack.services.base import SlackService
from slack_sdk.models.blocks import (
    SectionBlock,
    InputBlock,
    Option,
    StaticSelectElement,
)
import pandas as pd
from app.slack.types import ActionBodyType, ViewBodyType
from app.utils import tz_now_to_str
from app.config import settings


async def open_writing_participation_view(
    ack: AsyncAck, body: ActionBodyType, client: AsyncWebClient, user: models.User
):
    await ack()

    if user.is_writing_participation:
        view = View(
            type="modal",
            title="글쓰기 참여 신청 완료",
            blocks=[
                SectionBlock(
                    text="이미 글쓰기 참여 신청을 완료했어요!",
                ),
            ],
        )
    else:
        view = View(
            type="modal",
            title="글쓰기 참여 신청",
            callback_id="writing_participation_view",
            submit="제출",
            blocks=[
                SectionBlock(text="글쓰기 참여 신청"),
                InputBlock(
                    label="글쓰기 참여 여부",
                    block_id="writing_participation",
                    element=StaticSelectElement(
                        action_id="writing_participation",
                        options=[
                            Option(
                                text="글쓰기 참여를 신청합니다.",
                                value="writing_participation",
                            )
                        ],
                    ),
                ),
            ],
        )

    await client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


async def submit_writing_participation_view(
    ack: AsyncAck,
    body: ViewBodyType,
    client: AsyncWebClient,
    user: models.User,
    service: SlackService,
):
    await ack()

    columns = ["user_id", "name", "created_at", "is_writing_participation"]

    try:
        df = pd.read_csv("store/writing_participation.csv", dtype=str, na_filter=False)
    except FileNotFoundError:
        df = pd.DataFrame(columns=columns)

    # 필요한 컬럼 보장
    for c in columns:
        if c not in df.columns:
            df[c] = ""

    # 존재 여부에 따라 업데이트/삽입
    mask = df["user_id"] == user.user_id
    if mask.any():
        # 이름 최신화
        df.loc[mask, "name"] = user.name
        # 최초 생성 시간 비어있으면 채움
        if (df.loc[mask, "created_at"] == "").any():
            df.loc[mask, "created_at"] = tz_now_to_str()

        # 신청 여부 True로 설정
        df.loc[mask, "is_writing_participation"] = "True"
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "user_id": user.user_id,
                            "name": user.name,
                            "created_at": tz_now_to_str(),
                            "is_writing_participation": "True",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    # 컬럼 순서 고정
    df = df[columns]

    df.to_csv("store/writing_participation.csv", index=False, quoting=csv.QUOTE_ALL)
    # 로컬에만 두면 디스크 초기화 시 유실되므로 upload_queue 가 시트에 반영하게 표시한다.
    store.writing_participation_dirty = True

    await client.chat_postMessage(
        channel=user.user_id,
        text=f"✏️ 글쓰기 참여 신청을 완료했어요!\n🤗 글쓰기는 <#{settings.WRITING_CHANNEL}> 채널에서 진행됩니다. 채널에 참여해주세요!",
    )
