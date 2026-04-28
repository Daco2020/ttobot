# 011 - 슬랙 subscriptions 이벤트 테스트 작성하기

투두 9번 — 멤버 구독을 다루는 `subscriptions.py` 에 **총 16개 테스트** 가 추가됐어요.

## 1. 다룬 핸들러

| 핸들러                            | 케이스 수 | 핵심                                          |
| --------------------------------- | --------- | --------------------------------------------- |
| _process_user_subscription        | 6         | 5단계 검증 + 정상 통과                        |
| open_subscribe_member_view        | 2         | value 없음 / 있음                             |
| subscribe_member                  | 3         | 정상/자기자신/selected_user 없음              |
| unsubscribe_member                | 1         | cancel_subscription + views_update            |
| open_subscription_permalink       | 1         | ack 만                                        |
| _get_subscribe_member_view        | 3         | 구독 0/N건, message 인자                      |

## 2. 까다로웠던 부분 — 검증 분기의 "if 폭포"

`_process_user_subscription` 의 검증 로직은 elif 가 아닌 **if 5개의 폭포** 형태예요.

```python
def _process_user_subscription(user, service, target_user_id):
    message = ""
    if target_user_id == user.user_id:
        message = "⚠️ 자기 자신은 구독할 수 없어요."
    if target_user_id in BOT_IDS:
        message = "⚠️ 봇은 구독할 수 없어요."
    if len(service.fetch_subscriptions_by_user_id(...)) >= 5:
        message = "⚠️ 구독은 최대 5명까지 가능해요."
    target_user = service.get_only_user(target_user_id)
    if not target_user:
        message = "⚠️ 구독할 멤버를 찾을 수 없습니다."
    if any(...):  # 이미 구독 중
        message = "⚠️ 이미 구독한 멤버입니다."
    if not message:
        service.create_subscription(...)
```

각 분기가 **나중에 매칭된 메시지로 덮어쓰기** 되는 구조라, 분기 순서가 결과를 결정해요. 게다가
`service.get_only_user()` 는 분기 통과 여부와 무관하게 **항상 호출** 돼요.

> 💡 **운영 관점에서의 주의**: 만약 BOT_IDS 의 사용자가 우연히 user 데이터에 없다면(보통은 없음),
> `get_only_user()` 가 실제로는 `BotException` 을 던져요. SlackService 의 실제 구현은 None 반환이
> 아닌 raise 예요. 본 테스트에서는 mock 으로 None / User 를 반환하게 해서 분기 자체가 동작하는지를
> 검증했어요. 코드는 손대지 않고 **현재 동작** 만 박아두었습니다.

각 분기를 `_make_service_with_no_subscriptions()` 헬퍼로 깔끔하게 격리했어요.

```python
def _make_service_with_no_subscriptions():
    service = MagicMock()
    service.fetch_subscriptions_by_user_id.return_value = []
    service.get_only_user.return_value = factories.make_user(user_id="U_TARGET")
    return service
```

이러면 "5명 초과" 테스트만 별도로 5개 짜리 list 를 set 하고, "이미 구독" 테스트만 target_user_id 를
포함한 list 를 set 하면 돼요.

## 3. 발견한 작은 디테일 — 날짜 포맷

`_get_subscribe_member_view` 가 만드는 텍스트는 zero-padded 한국어 날짜를 써요.

```python
datetime.strptime(subscription.created_at[:10], '%Y-%m-%d').strftime('%Y년 %m월 %d일')
# => "2025년 01월 01일"
```

처음 테스트 단언은 `"2025년 1월 1일"` 로 썼다가 실패. 슬랙 모달에 노출되는 형식이 zero-padded 이라
`"2025년 01월 01일"` 로 맞췄어요. 사소하지만 실제 화면에서 보이는 모양이라 정확하게 박아두는 게
의미가 있어요.

## 4. View 텍스트 추출 — 컨텍스트 블록 포함

지금까지는 `b.get("text", {}).get("text", "")` 만 썼는데, 이번에는 **경고 메시지가 ContextBlock**
안에 들어가는 케이스가 있어 추출 로직을 확장했어요.

```python
body_text = ""
for b in rendered["blocks"]:
    if b.get("text"):
        body_text += b["text"].get("text", "")
    if b.get("type") == "context":
        for el in b.get("elements", []):
            body_text += el.get("text", "")
assert "자기 자신은 구독할 수 없어요" in body_text
```

이 패턴은 모달 안에 들어가는 모든 텍스트를 한 번에 모으는 표준 헬퍼로 만들 수도 있는데, 일단
필요한 곳에만 인라인으로 넣어두었어요.

## 5. 결과

```
$ uv run pytest test/
========================= 205 passed in 2.45s =========================
```

| 항목                                          | 상태   |
| --------------------------------------------- | ------ |
| `test/slack/test_subscriptions_events.py`     | ✅ 16개 |
| 발견한 버그                                   | 0건    |
| 발견한 잠재 이슈                              | `_process_user_subscription` 의 if 폭포 + get_only_user 동작 차이 (보고만) |
| 전체 테스트                                   | ✅ 205 passed |

## 6. 다음 단계

투두 10번 — **슬랙 writing_participation 이벤트** (`app/slack/events/writing_participation.py`).

- `open_writing_participation_view` (이미 신청 / 미신청 분기)
- `submit_writing_participation_view` (CSV 신규/기존 행 갱신)

CSV 분기 처리가 핵심이라 `tmp_store` + pandas 가 다시 등장해요.
