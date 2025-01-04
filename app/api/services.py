from datetime import datetime, timedelta
import random
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from app import models, store
from app.api.repositories import ApiRepository
from app.utils import tz_now
from app.config import settings
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.models.blocks import (
    SectionBlock,
    ContextBlock,
    MarkdownTextObject,
)
from app.constants import paper_plane_color_maps


class ApiService:
    def __init__(self, api_repo: ApiRepository) -> None:
        self._repo = api_repo

    def get_user_by(self, user_id: str) -> models.User | None:
        """특정 유저를 조회합니다."""
        return self._repo.get_user(user_id)

    async def send_paper_plane(
        self,
        sender_id: str,
        sender_name: str,
        receiver_id: str,
        text: str,
        client: AsyncWebClient,
    ) -> models.PaperPlane:
        """종이비행기를 보냅니다."""
        receiver = self.get_user_by(user_id=receiver_id)
        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="받는 사람을 찾을 수 없어요. 😢",
            )
        color_map = random.choice(paper_plane_color_maps)
        model = models.PaperPlane(
            sender_id=sender_id,
            sender_name=sender_name,
            receiver_id=receiver_id,
            receiver_name=receiver.name,
            text=text,
            text_color=color_map["text_color"],
            bg_color=color_map["bg_color"],
            color_label=color_map["color_label"],
        )
        self._repo.create_paper_plane(model)
        store.paper_plane_upload_queue.append(model.to_list_for_sheet())

        await client.chat_postMessage(
            channel=settings.THANKS_CHANNEL,
            text=f"💌 *<@{receiver_id}>* 님에게 종이비행기가 도착했어요!",
            blocks=[
                SectionBlock(
                    text=f"💌 *<@{receiver_id}>* 님에게 종이비행기가 도착했어요!\n\n",
                ),
                ContextBlock(
                    elements=[
                        MarkdownTextObject(
                            text=">받은 종이비행기는 `/종이비행기` 명령어 -> [주고받은 종이비행기 보기] 를 통해 확인할 수 있어요."
                        )
                    ],
                ),
            ],
        )

        await client.chat_postMessage(
            channel=sender_id,
            text=f"💌 *<@{sender_id}>* 님에게 종이비행기를 보냈어요!",
            blocks=[
                SectionBlock(
                    text=f"💌 *<@{receiver_id}>* 님에게 종이비행기를 보냈어요!\n\n",
                ),
                ContextBlock(
                    elements=[
                        MarkdownTextObject(
                            text=">보낸 종이비행기는 `/종이비행기` 명령어 -> [주고받은 종이비행기 보기] 를 통해 확인할 수 있어요."
                        )
                    ],
                ),
            ],
        )

        return model

    def fetch_sent_paper_planes(
        self,
        user_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperPlane]]:
        """유저가 보낸 종이비행기를 가져옵니다."""
        return self._repo.fetch_sent_paper_planes(
            sender_id=user_id,
            offset=offset,
            limit=limit,
        )

    def fetch_received_paper_planes(
        self,
        user_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, list[models.PaperPlane]]:
        """유저가 받은 종이비행기를 가져옵니다."""
        return self._repo.fetch_received_paper_planes(
            receiver_id=user_id, offset=offset, limit=limit
        )

    def fetch_current_week_paper_planes(
        self,
        user_id: str,
    ) -> list[models.PaperPlane]:
        """이번 주 종이비행기를 가져옵니다."""
        today = tz_now()

        # 지난주 토요일 00시 계산
        last_saturday = today - timedelta(days=(today.weekday() + 2) % 7)
        start_dt = last_saturday.replace(hour=0, minute=0, second=0, microsecond=0)

        # 이번주 금요일 23:59:59 계산
        this_friday = start_dt + timedelta(days=6)
        end_dt = this_friday.replace(hour=23, minute=59, second=59, microsecond=999999)

        paper_planes = []
        for plane in self._repo.fetch_paper_planes(sender_id=user_id):
            plane_created_ad = datetime.fromisoformat(plane.created_at).replace(
                tzinfo=ZoneInfo("Asia/Seoul")
            )
            if start_dt <= plane_created_ad <= end_dt:
                paper_planes.append(plane)

        return paper_planes
