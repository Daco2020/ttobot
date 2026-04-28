# 012 - 슬랙 writing_participation 이벤트 테스트 작성하기

투두 10번 — 글쓰기 참여 신청을 다루는 `writing_participation.py` 에 **총 8개 테스트** 가 추가됐어요.
이 모듈은 짧지만 CSV 분기가 다양해서 꼼꼼히 다뤘어요.

## 1. 다룬 핸들러

| 핸들러                                  | 케이스 수 | 핵심                                |
| --------------------------------------- | --------- | ----------------------------------- |
| open_writing_participation_view         | 2         | 신청/완료 분기                      |
| submit_writing_participation_view       | 6         | CSV 미존재/append/갱신/유지/누락컬럼/DM |

## 2. open 모달 — 두 갈래 분기

`is_writing_participation` 은 User 모델의 property 로, `store/writing_participation.csv` 를 매번
읽어서 결정돼요. 테스트에서는 이 property 를 직접 mock 으로 갈아끼웠어요.

```python
mocker.patch.object(
    type(user), "is_writing_participation", new_callable=mocker.PropertyMock
).return_value = True
```

- True → 완료 안내 모달 (callback_id 없음, 단순 안내)
- False → 신청 모달 (callback_id=writing_participation_view)

`callback_id` 차이로 두 모달의 의도를 구분했어요. submit 가능한 모달인지 단순 알림 모달인지를 한 줄로
검증할 수 있어요.

## 3. CSV 분기 5종 — submit 의 코어

이 핸들러는 글쓰기 참여 CSV 의 **상태 5가지** 를 정확하게 다뤄야 해요.

```python
try:
    df = pd.read_csv("store/writing_participation.csv", dtype=str, na_filter=False)
except FileNotFoundError:
    df = pd.DataFrame(columns=columns)

# 필요한 컬럼 보장 — 기존 CSV 에 컬럼이 누락됐다면 추가
for c in columns:
    if c not in df.columns:
        df[c] = ""

mask = df["user_id"] == user.user_id
if mask.any():
    df.loc[mask, "name"] = user.name
    if (df.loc[mask, "created_at"] == "").any():
        df.loc[mask, "created_at"] = tz_now_to_str()
    df.loc[mask, "is_writing_participation"] = "True"
else:
    df = pd.concat([df, pd.DataFrame([{...}])], ignore_index=True)
```

각 분기별로 별도 테스트:

| 케이스                                       | 입력 상태                       | 검증                                  |
| -------------------------------------------- | ------------------------------- | ------------------------------------- |
| CSV 미존재                                   | unlink() 로 파일 삭제           | 헤더 + 새 행 1개                      |
| 같은 user 없음                               | U_OLD 만 있음                   | U_OLD + U_NEW 두 행                   |
| 같은 user + created_at 빈 문자열             | U_X (created_at="")             | name 갱신 + created_at 채워짐         |
| 같은 user + created_at 있음                  | U_X (created_at="2024-12-01...")| created_at 유지 (덮어쓰지 않음)       |
| 컬럼 누락된 CSV                              | is_writing_participation 컬럼 X | 누락 컬럼 자동 추가                   |
| DM 메시지                                    | 모든 정상 케이스                | chat_postMessage(channel=user_id, ...)|

## 4. 까다로웠던 부분 — `created_at` 의 두 분기

코드를 자세히 보면 `created_at` 은 **빈 문자열일 때만** 갱신돼요.

```python
if (df.loc[mask, "created_at"] == "").any():
    df.loc[mask, "created_at"] = tz_now_to_str()
```

이 동작은 **중요한 의미** 가 있어요. 사용자가 한 번 신청하고 취소했다가 다시 신청한 경우, **최초 신청
시점** 을 보존해야 한다는 의도예요. 이 사소해 보이는 분기를 두 개 테스트로 박아두면 누군가 무심코
"기존 created_at 도 갱신하자!" 라고 바꾸면 즉시 잡혀요.

```python
# 빈 문자열 → 채워짐
csv_writer_helper(csv_path, WP_HEADER, [{..., "created_at": ""}])
...
assert rows[0]["created_at"]  # 채워짐

# 채워짐 → 유지
csv_writer_helper(csv_path, WP_HEADER, [{..., "created_at": "2024-12-01 09:00:00"}])
...
assert rows[0]["created_at"] == "2024-12-01 09:00:00"  # 그대로
```

> 💡 **배운 것**: "갱신 vs 보존" 분기는 한 줄짜리 if 라도 두 개 테스트로 양쪽을 다 박아두자. 미래의
> 무의식적 수정에 대한 가장 강력한 안전망이에요.

## 5. 컬럼 누락 자동 보강 — 또 다른 안전망

```python
for c in columns:
    if c not in df.columns:
        df[c] = ""
```

이 작은 루프는 CSV 마이그레이션 시점의 안전망이에요. 누군가 컬럼을 추가했는데 기존 CSV 가 이전
스키마라도 핸들러는 죽지 않고 동작해요. 테스트에서는 `is_writing_participation` 컬럼이 빠진 CSV 를
일부러 만들어 검증했어요.

```python
df = pd.DataFrame([{"user_id": "U_OLD", "name": "기존", "created_at": "2025-01-01 09:00:00"}])
df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)

# ... submit 호출 ...

rows = _read_wp_csv(csv_path)
for row in rows:
    for col in WP_HEADER:  # 4개 컬럼 모두 있어야 함
        assert col in row
```

## 6. 결과

```
$ uv run pytest test/
========================= 213 passed in 2.52s =========================
```

| 항목                                                  | 상태   |
| ----------------------------------------------------- | ------ |
| `test/slack/test_writing_participation_events.py`     | ✅ 8개  |
| 발견한 버그                                           | 0건    |
| 전체 테스트                                           | ✅ 213 passed |

## 7. 다음 단계

투두 11번 — **미들웨어 / 에러 핸들러** (`app/slack/event_handler.py`).

- `log_event_middleware` (이벤트 종류 분류)
- `dependency_injection_middleware` (service/point_service/user 주입)
- `handle_error` (한국어 에러는 사용자에게 모달로, 그 외는 일반 메시지)

여기서부터는 미들웨어/에러 핸들러라 이전과 다른 패턴이 나와요. `BoltRequest`/`BoltResponse` mock 이
필요해요.
