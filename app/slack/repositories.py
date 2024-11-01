import csv
from typing import Any
import pandas as pd
import polars as pl

from app import store
from app import models
from app.exception import BotException
from app.utils import tz_now_to_str


class SlackRepository:
    def __init__(self) -> None: ...

    def get_user(self, user_id: str) -> models.User | None:
        """유저와 콘텐츠를 가져옵니다."""
        if user := self._get_user(user_id):
            user.contents = self._fetch_contents(user_id)
            return user
        return None

    def fetch_users(self) -> list[models.User]:
        """모든 유저를 가져옵니다."""
        users = [models.User(**user) for user in self._fetch_users()]
        for user in users:
            user.contents = self._fetch_contents(user.user_id)
        return users

    def _get_user(self, user_id: str) -> models.User | None:
        """유저를 가져옵니다."""
        users = self._fetch_users()
        for user in users:
            if user["user_id"] == user_id:
                return models.User(**user)
        return None

    def _fetch_users(self) -> list[dict[str, Any]]:
        """모든 유저를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            users = [dict(row) for row in reader]
            return users

    def _fetch_contents(self, user_id: str) -> list[models.Content]:
        """유저의 콘텐츠를 오름차순(날짜)으로 정렬하여 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["user_id"] == user_id
            ]
            return contents

    def update(self, user: models.User) -> None:
        """유저의 콘텐츠를 업데이트합니다."""
        # TODO: upload 로 이름 변경 필요
        if not user.contents:
            raise BotException("업데이트 대상 content 가 없어요.")
        store.content_upload_queue.append(user.recent_content.to_list_for_sheet())
        with open("store/contents.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(user.recent_content.to_list_for_csv())

    def fetch_contents(self) -> list[models.Content]:
        """모든 콘텐츠를 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def fetch_contents_by_keyword(self, keyword: str) -> list[models.Content]:
        """키워드가 포함된 콘텐츠를 가져옵니다."""
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)
                for content in reader
                if keyword.lower()
                in (content["title"] + content["description"] + content["tags"]).lower()
                and content["type"] == "submit"
            ]
            return sorted(contents, key=lambda content: content.dt_, reverse=True)

    def get_user_id_by_name(self, name: str) -> str | None:
        """이름으로 user_id를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            matching_users = [user for user in reader if name in user["name"]]

        if len(matching_users) == 1:  # 이름 부분 일치가 하나인 경우에만 반환
            return matching_users[0]["user_id"]
        elif len(matching_users) > 1:
            for user in matching_users:
                if user["name"] == name:
                    return user["user_id"]
        return None

    def fetch_user_ids_by_name(self, name: str) -> list[str]:
        """이름으로 user_ids를 가져옵니다."""
        with open("store/users.csv") as f:
            reader = csv.DictReader(f)
            return [user["user_id"] for user in reader if name in user["name"]]

    def create_bookmark(self, bookmark: models.Bookmark) -> None:
        """북마크를 생성합니다."""
        with open("store/bookmark.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(bookmark.to_list_for_csv())

    def get_bookmark(
        self,
        user_id: str,
        content_ts: str,
        status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> models.Bookmark | None:
        bookmarks = self.fetch_bookmarks(user_id, status)
        for bookmark in bookmarks:
            if bookmark.content_ts == content_ts:
                return bookmark
        return None

    def fetch_bookmarks(
        self,
        user_id: str,
        status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> list[models.Bookmark]:
        """유저의 삭제되지 않은 북마크를 내림차순으로 가져옵니다."""
        with open("store/bookmark.csv") as f:
            reader = csv.DictReader(f)
            bookmarks = [
                models.Bookmark(**bookmark)  # type: ignore
                for bookmark in reader
                if bookmark["user_id"] == user_id and bookmark["status"] == status
            ]

        return sorted(bookmarks, key=lambda bookmark: bookmark.created_at, reverse=True)

    def update_bookmark(
        self,
        content_ts: str,
        new_note: str = "",
        new_status: models.BookmarkStatusEnum = models.BookmarkStatusEnum.ACTIVE,
    ) -> None:
        """북마크를 업데이트합니다."""
        df = pd.read_csv("store/bookmark.csv", dtype=str, na_filter=False)

        if new_note:
            df.loc[df["content_ts"] == content_ts, "note"] = new_note
        if new_status:
            df.loc[df["content_ts"] == content_ts, "status"] = new_status
        if new_note or new_status:
            df.loc[df["content_ts"] == content_ts, "updated_at"] = tz_now_to_str()

        df.to_csv("store/bookmark.csv", index=False, quoting=csv.QUOTE_ALL)

    def update_user_intro(
        self,
        user_id: str,
        new_intro: str,
    ) -> None:
        """유저 정보를 업데이트합니다."""
        df = pd.read_csv("store/users.csv", dtype=str, na_filter=False)
        df.loc[df["user_id"] == user_id, "intro"] = new_intro
        df.to_csv("store/users.csv", index=False, quoting=csv.QUOTE_ALL)

        if user := self._get_user(user_id):
            store.user_update_queue.append(user.to_list_for_sheet())

    def get_content_by(
        self,
        ts: str | None = None,
        user_id: str | None = None,
        dt: str | None = None,
    ) -> models.Content | None:
        """
        콘텐츠를 조회합니다.
        - 우선적으로 ts(타임스탬프)를 기준으로 검색합니다. 이는 Unique한 값입니다.
        - ts가 없을 경우, user_id와 dt(생성일시)를 조합하여 검색합니다. 이는 Unique한 값입니다.
        - Unique한 값이 아닌 경우, 검색된 결과 중 가장 최신의 결과를 반환합니다.
        """
        with open("store/contents.csv") as f:
            reader = csv.DictReader(f)
            contents = [
                models.Content(**content)  # type: ignore
                for content in reader
                if content["ts"] == ts
                or (content["user_id"] == user_id and content["dt"] == dt)
            ]

        if not contents:
            return None

        return sorted(contents, key=lambda content: content.dt_, reverse=True)[0]

    def create_coffee_chat_proof(self, proof: models.CoffeeChatProof) -> None:
        """커피챗 인증을 생성합니다."""
        with open(
            "store/coffee_chat_proof.csv", "a", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(proof.to_list_for_csv())

    def get_coffee_chat_proof(self, ts: str) -> models.CoffeeChatProof | None:
        """ts로 커피챗 인증을 조회합니다."""
        with open("store/coffee_chat_proof.csv") as f:
            reader = csv.DictReader(f)
            proofs = [
                models.CoffeeChatProof(**proof)  # type: ignore
                for proof in reader
                if proof["ts"] == ts
            ]

        if not proofs:
            return None

        return proofs[0]

    def fetch_coffee_chat_proofs(
        self,
        *,
        thread_ts: str | None = None,
        user_id: str | None = None,
    ) -> list[models.CoffeeChatProof]:
        """thread_ts로 커피챗 인증을 조회합니다."""
        with open("store/coffee_chat_proof.csv") as f:
            reader = csv.DictReader(f)
            proofs = [
                models.CoffeeChatProof(**proof)  # type: ignore
                for proof in reader
                if (not thread_ts or proof["thread_ts"] == thread_ts)
                and (not user_id or proof["user_id"] == user_id)
            ]
            return sorted(proofs, key=lambda proof: proof.ts, reverse=True)

    def add_point(self, point_history: models.PointHistory) -> None:
        """포인트를 추가합니다."""
        with open("store/point_histories.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(point_history.to_list_for_csv())

    def fetch_point_histories(self, user_id: str) -> list[models.PointHistory]:
        """포인트 히스토리를 가져옵니다."""
        with open("store/point_histories.csv") as f:
            reader = csv.DictReader(f)
            point_histories = [
                models.PointHistory(**point_history)  # type: ignore
                for point_history in reader
                if point_history["user_id"] == user_id
            ]
            return sorted(
                point_histories, key=lambda point: point.created_at, reverse=True
            )

    def fetch_channel_users(self, channel_id: str) -> list[models.User]:
        """
        채널의 유저를 가져옵니다.
        성능향상을 위해 polars를 사용합니다.
        """
        users_df = pl.read_csv("store/users.csv", dtypes={"deposit": pl.Utf8})
        users = users_df.filter(pl.col("channel_id") == channel_id).to_dicts()
        users = [models.User(**user) for user in users]

        contents_df = pl.read_csv("store/contents.csv", dtypes={"ts": pl.Utf8})
        for user in users:
            contents = contents_df.filter(pl.col("user_id") == user.user_id).to_dicts()
            user.contents = [models.Content(**content) for content in contents]

        return users

    def create_paper_plane(self, paper_plane: models.PaperPlane) -> None:
        """종이비행기를 생성합니다."""
        with open("store/paper_plane.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(paper_plane.to_list_for_csv())

    def fetch_paper_planes(self, sender_id: str) -> list[models.PaperPlane]:
        """종이비행기를 가져옵니다."""
        with open("store/paper_plane.csv") as f:
            reader = csv.DictReader(f)
            paper_planes = [
                models.PaperPlane(**paper_plane)  # type: ignore
                for paper_plane in reader
                if paper_plane["sender_id"] == sender_id
            ]
            return paper_planes

    def create_subscription(self, subscription: models.Subscription) -> None:
        """구독을 생성합니다."""
        with open("store/subscriptions.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(subscription.to_list_for_csv())

    def fetch_subscriptions_by_user_id(
        self,
        user_id: str,
    ) -> list[models.Subscription]:
        """유저의 구독 내역을 가져옵니다."""
        with open("store/subscriptions.csv") as f:
            reader = csv.DictReader(f)
            subscriptions = [
                models.Subscription(**subscription)  # type: ignore
                for subscription in reader
                if subscription["status"] == models.SubscriptionStatusEnum.ACTIVE
                and subscription["user_id"] == user_id
            ]
            return subscriptions

    def fetch_subscriptions_by_target_user_id(
        self,
        target_user_id: str,
    ) -> list[models.Subscription]:
        """타겟 유저를 기준으로 구독 내역을 가져옵니다."""
        with open("store/subscriptions.csv") as f:
            reader = csv.DictReader(f)
            subscriptions = [
                models.Subscription(**subscription)  # type: ignore
                for subscription in reader
                if subscription["status"] == models.SubscriptionStatusEnum.ACTIVE
                and subscription["target_user_id"] == target_user_id
            ]
            return subscriptions
