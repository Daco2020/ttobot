# 003 - `/slack/auth/refresh` 라우터 버그 수정하기

지난 002 작업에서 **`/v1/slack/auth/refresh` 라우터가 부정 케이스를 잘못 처리하고 있다** 는 사실을 발견했어요.
이번에는 그 버그를 직접 고치고, 기존 테스트도 정상 동작 기준으로 갱신했어요.

## 1. 문제 상황: `return HTTPException` 의 함정

원래 코드는 이런 모양이었어요.

```python
@router.get("/slack/auth/refresh")
async def slack_auth_refresh(refresh_token, service):
    try:
        decoded_payload = decode_token(refresh_token)
        if decoded_payload.get("type") != "refresh":
            return HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")  # ❌

        user = service.get_user_by(user_id=decoded_payload["user_id"])
        if not user:
            return HTTPException(status_code=404, detail="해당하는 유저가 없습니다.")  # ❌

    except PyJWTError:
        return HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")  # ❌
    ...
```

문제는 **`raise HTTPException(...)` 이 아니라 `return HTTPException(...)`** 이라는 점이에요.

FastAPI는 `raise HTTPException(...)` 을 만나면 그 자리에서 적절한 status_code 와 detail JSON 을
응답해줘요. 하지만 `return` 으로 돌려주면, FastAPI 는 그걸 그냥 **"라우터가 정상 응답한 객체"** 로 받아들여요.
결과적으로:

- HTTP 상태 코드는 무조건 **200 OK**
- 본문은 HTTPException 객체가 직렬화된 이상한 모양
- access_token 은 발급되지 않으니 클라이언트는 결국 새 토큰을 못 받음

토큰이 만료됐는데 200을 받으면 클라이언트는 "어 토큰이 살아있나?" 하고 헷갈려요. 보안상으로도, UX상으로도
모두 문제가 있는 동작이에요.

## 2. 어떻게 고쳤나요?

세 가지를 함께 정리했어요.

### 2-1. `return` → `raise`

`HTTPException` 은 발생시키는 게 정석이라, 단순히 `raise` 로 바꿔주면 끝.

### 2-2. 분기 순서 정리

원래 코드는 `try` 블록 안에서 `decode_token` 결과로 type 체크와 user 조회까지 하고 있었어요.
하지만 `service.get_user_by` 호출은 JWT 와 무관해서 `try/except` 로 감쌀 이유가 없어요.
괜히 PyJWTError 가 아닌 다른 예외(예: 서비스 내부 오류)가 발생할 때 토큰 에러로 둔갑할 수 있죠.

그래서 분기를 이렇게 정리했어요.

```python
try:
    decoded_payload = decode_token(refresh_token)
except PyJWTError:
    raise HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")

if decoded_payload.get("type") != "refresh":
    raise HTTPException(status_code=403, detail="토큰이 유효하지 않습니다.")

user = service.get_user_by(user_id=decoded_payload["user_id"])
if not user:
    raise HTTPException(status_code=404, detail="해당하는 유저가 없습니다.")
```

각 분기가 무엇을 검증하는지 한 줄에 하나씩 명확해졌어요.

### 2-3. 테스트도 정상 동작 기준으로

002 작업에서 작성한 4개 테스트는 "현재 버그 동작" 을 기록한 것이었어요. 함수명에 `_buggy_200` 이라고
붙어있던 게 그 흔적이에요. 이번에 코드를 고쳤으니 테스트도 다음과 같이 갱신했어요.

| 케이스                          | Before (버그)            | After (정상)              |
| ------------------------------- | ------------------------ | ------------------------- |
| access 타입 토큰을 refresh 로 사용 | 200 + 이상한 본문        | 403 "토큰이 유효하지 않습니다" |
| 유저 없음                        | 200 + 이상한 본문        | 404 "해당하는 유저가 없습니다" |
| JWT 디코드 실패                  | 200 + 이상한 본문        | 403 "토큰이 유효하지 않습니다" |

추가로 **만료된 refresh 토큰** 케이스 (🌀) 도 한 개 더 보탰어요. `decode_token` 이 만료 시
`ExpiredSignatureError` 를 던지는데, 이 역시 `PyJWTError` 의 서브클래스라 같은 분기로 처리돼요.

## 3. 사용자 규칙도 함께 기록

이번 일을 계기로 사용자가 새 규칙을 알려주셨어요.

> **"발견한 버그는 내가 수정해달라고 할 때에만 수정"**

작업 도중 버그를 발견하면 보고만 하고, 사용자가 "고쳐줘" 라고 명시 요청할 때만 손대는 원칙이에요.
한 번에 두 관심사(테스트 보강 + 버그 수정)가 섞이면 리뷰와 롤백이 어려워지고, 사용자가 의도적으로
그 동작을 유지하고 싶어할 가능성도 있으니까요.

이 규칙은 메모리에 저장해서 다음 세션에서도 잊지 않도록 했어요.

## 4. 결과

```
$ uv run pytest test/
========================= 34 passed in 2.05s =========================
```

| 항목                                    | 상태   |
| --------------------------------------- | ------ |
| `app/api/views/login.py` 수정           | ✅ `return` → `raise` 3곳 + 분기 정리 |
| `test/api/test_login.py` 갱신           | ✅ 4개 갱신, 1개 신규 (만료 케이스) |
| `docs/02-test-todo.md`                   | ✅ 1-5 섹션 갱신 |
| 사용자 규칙 메모리 저장                 | ✅ `feedback_bug_fix_policy.md` |
| 전체 테스트                             | ✅ 34 passed |

## 5. 다음 단계

원래 예정이었던 투두 2번 — **API 콘텐츠 / 메시지 라우터** 로 이어집니다.
이번에 만든 `override_api_service`, `auth_for` 같은 도구가 본격적으로 활약할 차례예요.
