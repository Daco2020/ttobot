# 005 - 종이비행기 라우터 / ApiService 테스트 작성하기

투두 3번 섹션을 마무리했어요. 종이비행기 기능은 또봇에서 가장 분기가 많은 라우터 중 하나라
**총 22개의 테스트** 가 추가됐어요. 라우터 14개 + ApiService 단위 8개.

## 1. 무엇을 테스트했나요?

종이비행기 기능은 두 계층으로 나뉘어요.

- **라우터** (`app/api/views/paper_planes.py`): 검증 분기와 권한 체크 위주
- **서비스** (`app/api/services.py`): 실제 도메인 로직 + 외부 호출

각자 책임이 다르니 테스트도 두 파일로 나눴어요.

## 2. 라우터 테스트 (14개)

### 2-1. `POST /v1/paper-planes` 검증 분기 망라 (8개)

이 라우터는 메시지 한 통을 보내기 전에 **5단계 검증** 을 거쳐요.

```python
if user.user_id == dto.receiver_id:        # 1. 자기 자신 차단
    raise HTTPException(400, ...)
if len(dto.text) > 300:                    # 2. 길이 제한
    raise HTTPException(400, ...)
if dto.receiver_id in BOT_IDS:             # 3. 봇 차단
    raise HTTPException(400, ...)
if user.user_id == settings.SUPER_ADMIN:   # 4. 슈퍼 어드민 분기 (현재 비활성)
    pass
else:
    pass                                   #     일반 유저 분기 (현재 비활성)
await service.send_paper_plane(...)        # 5. 서비스 위임
```

각 분기마다 정상 통과 / 차단 케이스를 빠짐없이 다뤘어요.

| 케이스                                      | 분류 | 응답  |
| ------------------------------------------- | ---- | ----- |
| 정상 발송                                    | ✅   | 201   |
| 자기 자신에게 발송                           | ⚠️   | 400   |
| 텍스트 301자                                 | ⚠️   | 400   |
| 텍스트 정확히 300자 (경계)                   | 🌀   | 201   |
| receiver_id 가 봇                            | ⚠️   | 400   |
| service 가 404 raise → 클라이언트도 404      | ⚠️   | 404   |
| 인증 누락                                    | ⚠️   | 403   |
| SUPER_ADMIN 도 동일 흐름 통과                 | 🌀   | 201   |

특히 **정확히 300자 케이스** 는 `len(text) > 300` 의 **부등호 방향** 이 맞는지 검증하는 의미가 있어요.
경계값 테스트를 해두면 누군가 무심코 `>=` 로 바꿔도 즉시 잡혀요.

### 2-2. GET 엔드포인트 (6개)

`/sent`, `/received` 는 사실상 같은 모양이라 핵심만 다뤘어요.

- ✅ 페이지네이션 응답 (count + data)
- ⚠️ 인증 누락 → 403
- 🌀 limit > 1000 → 422 (FastAPI Query 검증)
- 🌀 offset 매우 큼 → 빈 data + count는 그대로 유지

`override_api_service` 로 service mock 을 갈아끼우면 CSV 파일을 건드리지 않고도 다양한 응답 모양을
시뮬레이션할 수 있어요.

## 3. ApiService 단위 테스트 (8개)

### 3-1. `send_paper_plane` (2개)

이 메서드는 한 번 호출에 **세 가지 부수효과** 를 일으켜요.

1. `repo.create_paper_plane(plane)` — CSV 에 행 추가
2. `store.paper_plane_upload_queue.append(...)` — 시트 업로드 큐에 적재
3. `client.chat_postMessage(...)` — 슬랙 채널 + 발신자 DM 두 번 호출

이걸 모두 검증하려면 다음과 같이 격리했어요.

```python
repo = MagicMock()
repo.get_user.return_value = receiver
upload_queue = mocker.patch("app.api.services.store.paper_plane_upload_queue", new=[])
slack_client = AsyncMock()
```

`store.paper_plane_upload_queue` 를 빈 리스트로 갈아끼운 게 핵심이에요. 모듈 전역의 진짜 큐를
오염시키지 않으면서, 실제로 항목이 한 개 들어가는지 확인할 수 있어요.

부정 케이스(`receiver=None` → 404)는 **그 다음 단계가 일어나지 않아야 한다** 는 점도 함께 검증했어요.
`repo.create_paper_plane.assert_not_called()` 와 `slack_client.chat_postMessage.assert_not_awaited()`.

### 3-2. `fetch_current_week_paper_planes` 시간 경계 (6개)

이 메서드는 "이번 주 (토~금)" 의 비행기만 골라내요. 경계 계산이 흥미로워요.

```python
today = tz_now()
last_saturday = today - timedelta(days=(today.weekday() + 2) % 7)
start_dt = last_saturday.replace(hour=0, minute=0, second=0, microsecond=0)
this_friday = start_dt + timedelta(days=6)
end_dt = this_friday.replace(hour=23, minute=59, second=59, microsecond=999999)
```

테스트 기준일을 **수요일 2025-01-15 12:00** 로 고정하면, 한 주의 범위는 다음과 같아요.

- start: 2025-01-11 (토) 00:00:00
- end:   2025-01-17 (금) 23:59:59.999999

이를 기준으로 6가지 boundary 케이스를 만들었어요.

| created_at                | 위치             | 결과       |
| ------------------------- | ---------------- | ---------- |
| 2025-01-13 09:00:00       | 한 주 가운데     | ✅ 포함     |
| 2025-01-08 09:00:00       | 지난주           | ❌ 제외     |
| 2025-01-20 09:00:00       | 다음주           | ❌ 제외     |
| 2025-01-11 00:00:00       | 시작 boundary    | ✅ 포함     |
| 2025-01-10 23:59:59       | 시작 1초 전      | ❌ 제외     |
| 2025-01-17 23:59:59       | end boundary     | ✅ 포함     |
| 2025-01-18 00:00:00       | 다음 주의 시작   | ❌ 제외     |

`tz_now` 를 mock 으로 고정해서 매번 같은 결과가 나오게 했어요.

```python
@pytest.fixture
def fix_today(mocker):
    return mocker.patch("app.api.services.tz_now", return_value=_fixed_today())
```

> 💡 **배운 것**: 시간 의존 함수는 항상 mock 으로 고정. 그렇지 않으면 빌드가 어느 요일에 도느냐에 따라
> 통과/실패가 갈리는 flaky 테스트가 돼요.

## 4. 결과

```
$ uv run pytest test/
========================= 77 passed in 2.15s =========================
```

| 항목                                           | 상태   |
| ---------------------------------------------- | ------ |
| `test/api/test_paper_planes_router.py`         | ✅ 14개 |
| `test/services/test_api_service.py`            | ✅ 8개  |
| 발견한 버그                                    | 0건    |
| 전체 테스트                                    | ✅ 77 passed |

이번 섹션은 라우터와 서비스를 깔끔하게 분리해서 테스트하는 좋은 사례가 됐어요. 라우터는 **분기 위주**,
서비스는 **부수효과 + 경계값 위주** — 이 패턴이 뒤이어 나올 다른 라우터들에도 그대로 적용될 거예요.

## 5. 다음 단계

투두 4번 — **포인트 / 메시지 / 인프런 / 글쓰기 참여 라우터**.

라우터 4개를 묶어서 처리하는 섹션이에요. 각각 분기가 단순하지만 권한 체크와 외부 호출이 다양해서
"라우터 테스트의 표준 패턴" 을 다시 한 번 다지는 데 좋아요.
