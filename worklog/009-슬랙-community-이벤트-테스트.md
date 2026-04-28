# 009 - 슬랙 community 이벤트 테스트 작성하기

투두 7번 — 커피챗 인증 워크플로우와 종이비행기 모달을 다루는 `community.py` 에 **총 11개 테스트** 가
추가됐어요. 이 모듈은 코드 양은 적지만 워크플로우가 가장 정교한 부분이에요.

## 1. 다룬 핸들러

| 핸들러                              | 케이스 수 | 핵심                                              |
| ----------------------------------- | --------- | ------------------------------------------------- |
| handle_coffee_chat_message          | 4         | 메시지 종류별 분기 (탑레벨/답글/이미인증/수정)    |
| cancel_coffee_chat_proof_button     | 1         | requests.post 로 ephemeral 삭제                   |
| submit_coffee_chat_proof_button     | 1         | 모달 open + private_metadata JSON 직렬화          |
| submit_coffee_chat_proof_view       | 3         | 인증 검증, 호출 메시지, 포인트 지급               |
| paper_plane_command                 | 2         | SUPER_ADMIN / 일반 유저 모두 ∞ 표시 (현재 코드)   |

## 2. 까다로웠던 부분 — 커피챗 인증 워크플로우

`handle_coffee_chat_message` 는 같은 채널의 메시지라도 **세 가지 모양**으로 처리해요.

```python
if not is_thread:
    # 1. 탑레벨 메시지 → 인증 안내 ephemeral 전송
    await asyncio.sleep(1)
    await client.chat_postEphemeral(...)
    return

if is_thread and subtype != "message_changed":
    # 2. 답글 메시지 → 인증 처리 + 포인트
    try:
        service.check_coffee_chat_proof(thread_ts, user_id)
    except BotException:
        return  # 이미 인증됐거나 대상 아님 → 조용히 종료
    service.create_coffee_chat_proof(...)
    await client.reactions_add(...)
    point_service.grant_if_coffee_chat_verified(...)
```

각 분기마다 다른 외부 호출 패턴이 일어나서, 4개 테스트로 커버했어요.

| 케이스                                     | 결과                                   |
| ------------------------------------------ | -------------------------------------- |
| 탑레벨 메시지                              | chat_postEphemeral 1번 (인증 안내)     |
| 답글 + 인증 가능                           | reactions_add + 포인트 지급            |
| 답글 + check 가 BotException 던짐          | 조용히 종료, reactions_add 호출 없음   |
| 답글 + subtype="message_changed"           | 아무 동작 없음                         |

> 💡 **배운 것**: `BotException` 을 try/except 로 잡고 silent return 하는 패턴은 의도적이에요. 이미 인증한
> 사용자가 추가 답글을 달아도 또 인증되지 않게 하려는 조용한 가드. 테스트로 이걸 못 박아두면 누군가
> "왜 여기서 BotException 을 삼키지?" 하고 무심코 raise 로 바꾸지 못해요.

## 3. requests.post mock — 동기 호출 한 줄

`cancel_coffee_chat_proof_button` 과 `submit_coffee_chat_proof_view` 는 **동기 라이브러리** `requests` 를
써요. 슬랙-볼트의 `client` 가 ephemeral 메시지 *삭제* 를 지원하지 않아서 어쩔 수 없이 `response_url` 로
직접 POST 하는 거예요.

```python
requests_mock = mocker.patch("app.slack.events.community.requests.post")

await community_events.cancel_coffee_chat_proof_button(...)

requests_mock.assert_called_once()
args, kwargs = requests_mock.call_args
assert args[0] == "https://hooks.slack.example/cancel"
assert kwargs["json"]["delete_original"] is True
```

`mocker.patch("app.slack.events.community.requests.post")` 처럼 **모듈 안에서 import 된 시점** 의
`requests` 를 갈아끼우는 게 핵심. 이렇게 하면 진짜 네트워크 호출이 일어나지 않아요.

## 4. 가장 복잡한 케이스 — `submit_coffee_chat_proof_view`

이 핸들러 하나가 다음을 한 번에 해요:

1. selected_users 검증 (2명 이상)
2. ack
3. 원본 메시지 가져오기 (`conversations_history`)
4. 원본 메시지에 reaction 추가
5. 포인트 지급
6. 본인 제외한 참여자 호출 메시지 전송 (스레드)
7. coffee_chat_proof 레코드 생성
8. ephemeral 메시지 삭제 (requests.post)

테스트는 **본인 + 2명 + 1명 + ephemeral 삭제** 까지 모두 검증.

```python
posted_text = fake_slack_client.chat_postMessage.await_args.kwargs["text"]
assert "<@U_OTHER1>" in posted_text
assert "<@U_OTHER2>" in posted_text
assert "<@U_X>" not in posted_text  # 본인 제외

cc_kwargs = service.create_coffee_chat_proof.call_args.kwargs
assert cc_kwargs["selected_user_ids"] == "U_OTHER1,U_OTHER2"
assert cc_kwargs["participant_call_thread_ts"] == "thread_ts_1"
```

특히 `selected_user_ids` 는 본인을 제외한 user_id 콤마 결합 형태로 저장돼요. CSV 형태로 그대로 들어가는
값이라 형식이 깨지면 데이터 오염이 생겨요. 테스트로 형식까지 박아두는 게 중요해요.

## 5. `paper_plane_command` — 비활성 코드 검증

이 핸들러는 원래 "주당 7개 한도" 로직이 있었는데 현재는 주석 처리되어 있어요. 코드 상으로는 모두
무한(∞) 으로 표시.

```python
if user.user_id == settings.SUPER_ADMIN:
    remain_paper_planes = "∞"
else:
    remain_paper_planes = "∞"
    # paper_planes = service.fetch_current_week_paper_planes(...)  # 주석 처리됨
```

테스트는 두 분기 모두 ∞ 가 표시되는 현재 동작을 그대로 기록. 추후 한도가 다시 활성화될 때 이 테스트가
빨갛게 변하면서 변경 시점을 잡아낼 수 있어요.

## 6. 결과

```
$ uv run pytest test/
========================= 168 passed in 2.41s =========================
```

| 항목                                  | 상태   |
| ------------------------------------- | ------ |
| `test/slack/test_community_events.py` | ✅ 11개 |
| 발견한 버그                           | 0건    |
| 전체 테스트                           | ✅ 168 passed |

## 7. 다음 단계

투두 8번 — **슬랙 log 이벤트** (`app/slack/events/log.py`).

- handle_comment_data, handle_post_data → BigQuery 큐 적재
- handle_reaction_added — 공지/성윤글 포인트 지급 (cache 가 얽혀 있어서 까다로움)
- handle_reaction_removed
- _is_thread_message, _is_checked_notice/super_admin_post (CSV 기반 헬퍼)

여기서 `aiocache.cached` 데코레이터와 CSV 파일 시스템이 본격 등장해요.
