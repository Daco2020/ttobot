# 007 - 슬랙 `core` 이벤트 핸들러 테스트 작성하기

이번엔 슬랙 봇 영역으로 넘어왔어요. 첫 타자는 `app/slack/events/core.py` — **20+개 핸들러** 가 모여있는
가장 큰 이벤트 모듈입니다. **총 35개 테스트** 가 추가됐어요.

## 1. core 이벤트의 정체

`/예치금`, `/제출내역`, `/도움말`, `/관리자` 같은 **명령어 핸들러** 부터 홈 탭, 채널 초대, 데이터 동기화,
종이비행기 보내기, 다운로드까지 — 또봇 사용자가 일상적으로 만나는 거의 모든 모달/액션이 여기 모여있어요.

핸들러 종류를 분류하면 다섯 갈래로 나눌 수 있어요.

| 분류                   | 예시                                                | 테스트 포인트                          |
| ---------------------- | --------------------------------------------------- | -------------------------------------- |
| ack 만 호출 (로그용)   | `handle_app_mention`, `open_paper_plane_url`         | ack 호출 여부 + 부수효과 없음 검증     |
| 모달 open              | `open_help_view`, `open_point_guide_view`            | views_open 호출 + 블록 구조            |
| 권한 체크 후 모달      | `admin_command`                                      | admin / 비-admin 분기                  |
| 분기형                 | `handle_sync_store`                                  | 옵션별 호출 메서드 분기                |
| 외부 시스템 호출       | `download_point_history` (CSV 생성 + 슬랙 업로드)    | 파일 시스템 + 슬랙 API mock           |

## 2. 35개 케이스 분포

| 핸들러                                                       | 케이스 수 |
| ------------------------------------------------------------ | --------- |
| handle_app_mention / open_paper_plane_url / handle_channel_created | 3         |
| open_deposit_view (deposit 있음/빈 문자열)                   | 2         |
| open_submission_history_view (있음/없음)                     | 2         |
| open_help_view                                               | 1         |
| admin_command (admin / 비-admin)                             | 2         |
| handle_sync_store (정상 옵션 / 알 수 없음 / 예외 swallow)    | 3         |
| handle_invite_channel + view + _invite_channel (5가지 에러분기 포함) | 7  |
| handle_home_tab (미등록 / 등록됨)                            | 2         |
| open_*_view 액션 4종 + 커피챗 빈/있음                         | 5         |
| send_paper_plane_message + view (자기/300자/봇)              | 4         |
| download_*_history (3종, 빈/있음)                            | 4         |

## 3. 작성하면서 다진 패턴들

### 3-1. `View.to_dict()` 로 본문 검증

`views_open` 의 인자로 들어가는 `View` 객체는 `.title`, `.blocks` 같은 슬랙 SDK 타입이라 직접 인덱싱이
안 돼요. 대신 `.to_dict()` 으로 한 번 직렬화한 뒤 텍스트를 모아서 검증해요.

```python
rendered = fake_slack_client.views_open.await_args.kwargs["view"].to_dict()
body_text = "".join(
    b.get("text", {}).get("text", "") for b in rendered["blocks"] if b.get("text")
)
assert "내 글또 포인트" in body_text
```

이 패턴은 모달 텍스트 검증할 때 두고두고 재활용돼요.

### 3-2. SlackApiError 의 다섯 갈래 분기

`_invite_channel` 은 슬랙이 돌려주는 에러 코드에 따라 5가지 동작을 해요.

```python
try:
    await client.conversations_invite(channel=channel_id, users=user_id)
    result = " -> ✅ (채널 초대)"
except SlackApiError as e:
    if e.response["error"] == "not_in_channel":
        await client.conversations_join(channel=channel_id)
        await client.conversations_invite(channel=channel_id, users=user_id)
        result = " -> ✅ (또봇도 함께 채널 초대)"
    elif e.response["error"] == "already_in_channel": ...
    elif e.response["error"] == "cant_invite_self": ...
    else: ...  # 알 수 없는 에러 → 문서 링크
```

각 분기가 다른 메시지를 만들어내는데, `chat_postMessage` 의 호출 인자(`text`) 를 모아서 어떤 메시지가
나갔는지 검증했어요.

```python
posted = [c.kwargs["text"] for c in fake_slack_client.chat_postMessage.await_args_list]
assert any("이미 채널에 참여 중" in t for t in posted)
```

이 방법은 호출 횟수가 들쭉날쭉할 때 유용해요. 정확한 인덱스를 알 필요 없이 "어딘가 한 번은 있었다" 를
검증할 수 있어요.

### 3-3. `tmp_store` 픽스처가 빛을 발하는 다운로드 테스트

`download_point_history` 는 `temp/point_histories/` 디렉터리에 CSV 를 만들고 슬랙에 업로드한 뒤
파일을 지워요. 진짜 파일을 만드는 동작이라 `tmp_store` 픽스처가 cwd 를 임시 디렉터리로 옮겨주는 게
필수예요. 그렇지 않으면 프로젝트 루트에 파일 쓰레기가 생겨요.

```python
async def test_download_point_history_uploads_csv(
    ack, ..., tmp_store,  # ← 임시 디렉터리로 cwd 이동
):
    fake_slack_client.files_upload_v2.return_value = {
        "file": {"permalink": "https://slack.example/perma"}
    }
    ...
```

### 3-4. UserPoint 모델 직접 사용

홈 탭과 포인트 히스토리 모달은 `point_service.get_user_point()` 가 돌려주는 `UserPoint` 객체에
의존해요. mock 으로 뭉개기보다 **진짜 모델 인스턴스** 를 만들어서 주는 게 깔끔해요.

```python
from app.slack.services.point import UserPoint

point_service.get_user_point.return_value = UserPoint(
    user=user,
    point_histories=[factories.make_point_history(user_id="U_X", point=100)],
)
```

이러면 핸들러 안에서 `user_point.total_point` 같은 property 가 정상 동작해요. `MagicMock()` 으로 감싸면
property 호출이 또 다른 MagicMock 을 만들어서 검증이 꼬여요.

## 4. 결과

```
$ uv run pytest test/
========================= 130 passed in 2.31s =========================
```

| 항목                                | 상태   |
| ----------------------------------- | ------ |
| `test/slack/test_core_events.py`    | ✅ 35개 |
| 발견한 버그                         | 0건    |
| 전체 테스트                         | ✅ 130 passed |

API 영역(95개) + 슬랙 services(13개) + 슬랙 core(35개) = 143개 중 130개가 본 작업으로 추가/이동된 새 테스트.
원래 5개에서 25배 이상 늘었어요.

## 5. 다음 단계

투두 6번 — **슬랙 contents 이벤트** (`app/slack/events/contents.py`).

- `/제출`, `/패스`, `/검색`, `/북마크` 명령어
- 글 url 검증, 콤보 포인트 지급, 큐레이션 분기, 북마크 페이지네이션 등

이 모듈은 코어 모듈만큼 무거우면서도 비즈니스 로직이 가장 풍부한 곳이에요. 본격적인 시간이 시작돼요.
