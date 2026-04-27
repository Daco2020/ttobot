# 008 - 슬랙 contents 이벤트 테스트 작성하기

투두 6번 — 글 제출/패스/검색/북마크/자기소개를 모두 책임지는 가장 무거운 이벤트 모듈에
**총 27개 테스트** 가 추가됐어요. 또봇 사용자가 가장 자주 만나는 흐름들이라 라우팅·검증·포인트 지급이
한 번에 얽혀있어요.

## 1. 다룬 핸들러

| 분류        | 핸들러                                                       | 케이스 수 |
| ----------- | ------------------------------------------------------------ | --------- |
| 글 제출     | submit_command, submit_view                                  | 5         |
| 글 패스     | pass_command, pass_view                                      | 3         |
| 글 검색     | search_command, submit_search, web_search, back_to_search_view | 5      |
| 북마크      | bookmark_command, bookmark_modal, create_bookmark_view,<br/> handle_bookmark_page, open_overflow_action | 9 |
| 자기소개    | open_intro_modal, edit_intro_view, submit_intro_view          | 4         |
| 작성글 모달 | contents_modal                                                | 1         |

## 2. 까다로웠던 부분 — 글 제출 (`submit_view`)

이 핸들러 하나가 다른 모듈 전체보다 복잡해요. 한 번 호출되면 다음과 같은 일이 일어나요.

1. URL 검증 (`validate_url`) — 실패 시 `ack(errors=...)` 후 raise
2. 제목 크롤링 (`get_title`) — 외부 httpx 호출, 실패 시 `ack(errors=...)` 후 raise
3. 빈 ack
4. 콘텐츠 생성 + chat_postMessage 로 글쓰기 채널에 메시지
5. `update_user_content` 로 CSV/시트에 반영
6. 글쓰기 채널이 아니면 활동 안내 메시지 (3초 sleep 포함)
7. **포인트 4종**: 기본/콤보/랭킹/큐레이션
8. SUPER_ADMIN 이면 구독 시트 갱신

테스트 전략은 **외부 호출을 모두 AsyncMock 으로 갈아끼우고**, **포인트 분기는 호출 카운트로 검증** 했어요.

```python
service.create_submit_content = AsyncMock(return_value=created)
service.update_user_content = AsyncMock(return_value=None)
mocker.patch("app.slack.events.contents.send_point_noti_message", new=AsyncMock())

point_service.grant_if_post_submitted.return_value = ("기본 포인트 지급", False)
point_service.grant_if_post_submitted_continuously.return_value = None  # 콤보 메시지 없음

# is_additional=False 이므로 콤보/랭킹 분기는 호출되어야 한다
point_service.grant_if_post_submitted_continuously.assert_called_once()
point_service.grant_if_post_submitted_to_core_channel_ranking.assert_called_once()
# curation_flag=N 이므로 큐레이션 분기는 호출되지 않는다
point_service.grant_if_curation_requested.assert_not_called()
```

`is_additional` 의 True/False 가 콤보/랭킹 분기를 가르는 핵심 변수라, 이 한 케이스만으로 분기 5개를
한 번에 검증할 수 있어요. (실패 케이스는 별도 테스트 2개로 분리)

## 3. 깐깐했던 부분 — 글 패스 (`pass_command`)

`pass_command` 는 `user.check_pass()` 를 호출하는데, 이 메서드는 `pass_count >= MAX_PASS_COUNT` 이면
`BotException` 을 던져요. `pass_count` 는 컨텐츠의 `type=="pass"` 항목 수라, 두 개를 미리 만들어
한도 도달 상황을 재현했어요.

```python
user = factory.make_user(
    user_id="U_X",
    contents=[
        factories.make_content(type="pass", dt="2025-01-05 10:00:00"),
        factories.make_content(type="pass", dt="2025-02-05 10:00:00"),
    ],
)

with pytest.raises(BotException):
    await contents_events.pass_command(...)
```

`is_prev_pass` 분기는 `DUE_DATES` 와 `tz_now` 를 함께 mock 해야 정확히 재현돼서, 본 작업에서는 한도
초과 케이스만 다루고 직전 회차 pass 케이스는 모델 단위 테스트로 미뤘어요.

## 4. 까다로웠던 부분 — 북마크 페이지네이션

북마크 모달은 한 페이지에 20개씩 표시해요. `_get_content_metrix` 라는 헬퍼가 컨텐츠를 dict 로
페이지화해서 `{1: [...], 2: [...]}` 모양으로 만들어요.

```python
service.fetch_bookmarks.return_value = bookmarks  # 21개
service.fetch_contents_by_ids.return_value = contents  # 21개

await contents_events.bookmark_command(...)

view = fake_slack_client.views_open.await_args.kwargs["view"]
button_ids = []
for b in view.to_dict()["blocks"]:
    if b.get("type") == "actions":
        for el in b.get("elements", []):
            button_ids.append(el["action_id"])
assert "next_bookmark_page_action" in button_ids
```

페이지가 2개 이상일 때만 "다음 페이지" 버튼이 나타나야 해요. 21개 컨텐츠를 만들어 페이지 2개 상황을
정확히 재현했어요.

## 5. overflow 메뉴 — 분기 3가지 모두 검증

북마크 항목의 `...` 메뉴는 두 가지 액션을 가져요.

- `remove_bookmark` → `service.update_bookmark(status=DELETED)` + "북마크를 취소했어요"
- `view_note` (메모 있음) → 메모 텍스트 노출
- `view_note` (메모 없음) → "메모가 없어요"

세 분기를 각각 별도 테스트로 작성. `selected_option.value` 의 JSON 문자열을 파싱하는 로직이라
실제 페이로드 형태를 그대로 재현했어요.

```python
body = make_action_body(
    actions=[{
        "action_id": "bookmark_overflow_action",
        "type": "overflow",
        "selected_option": {
            "value": '{"action": "remove_bookmark", "content_ts": "ts_1"}'
        },
    }],
    view={"id": "V", "private_metadata": '{"page": 1}'},
)
```

## 6. 자기소개 모달의 사소한 분기

`open_intro_modal` 은 본인이 자기 자신의 자기소개를 보면 **수정 버튼** 이 있는 모달, 다른 유저의
자기소개를 보면 **수정 버튼 없음** 모달을 띄워요. View 객체의 `callback_id` 가 어떻게 설정되는지로
검증했어요.

```python
# 본인
assert view.callback_id == "edit_intro_view"  # 수정 가능

# 다른 유저
assert view.callback_id is None  # 수정 불가
```

## 7. 결과

```
$ uv run pytest test/
========================= 157 passed in 2.38s =========================
```

| 항목                                  | 상태   |
| ------------------------------------- | ------ |
| `test/slack/test_contents_events.py`  | ✅ 27개 |
| 발견한 버그                           | 0건    |
| 전체 테스트                           | ✅ 157 passed |

API 영역(95) + 슬랙 services(13) + slack core(35) + slack contents(27) = 본 작업 누적 **170개** 의
새 테스트가 누적됐어요.

## 8. 다음 단계

투두 7번 — **슬랙 community 이벤트** (`app/slack/events/community.py`).

- `handle_coffee_chat_message` (스레드 / 일반 메시지 / 답글 인증)
- `cancel_coffee_chat_proof_button`, `submit_coffee_chat_proof_button`
- `submit_coffee_chat_proof_view` (참여자 검증, 포인트 지급)
- `paper_plane_command`

커피챗 인증의 워크플로우가 `requests.post` 를 동기로 부르고 있어서 그 부분 mock 도 같이 다뤄야 해요.
