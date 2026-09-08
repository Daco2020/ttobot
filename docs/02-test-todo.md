# 또봇 테스트 커버리지 기록 (완료)

> 📌 이 문서는 **완료된 테스트 커버리지 기록(참고용)**입니다. 아래 항목은 모두 구현됨
> (하단 대시보드 참고). 활성 TODO는 루트 [`/TODO.md`](../TODO.md) 한 곳에서만 관리합니다.
> (전역 규칙 #13 — 체크박스 TODO는 TODO.md 에만 둔다.)

작성된 테스트 케이스 분류:

- ✅ **성공** : 정상 흐름
- ⚠️ **실패** : 권한/유효성/외부 오류 처리
- 🌀 **엣지** : 경계값/특수 입력/누락된 필드/타이밍

하나의 라우터/핸들러 안에 case가 부족한 경우는 본문에 “해당 시나리오 없음”으로 명시했다.

---

## 0. 사전 작업

- uv 가상환경 전환 (`pyproject.toml`, `uv.lock`)
- `Makefile` `test` 타겟 추가 (`uv run pytest`)
- `test/conftest.py` 정비 — 환경 변수, settings override, fake slack client
- `test/factories.py` — `make_user()`, `make_content()`, `make_paper_plane()` 등
- `test/api/conftest.py` — FastAPI `TestClient`, 토큰 발급 헬퍼
- `test/slack/conftest.py` — slack_app/client mock, body 빌더
- 기존 `test_point.py`, `test_reminder.py` → `test/services/` 이동

---

## 1. API — 인증 & 로그인 (`app/api/auth.py`, `app/api/views/login.py`)

### 1-1. `encode_token` / `decode_token`

- ✅ 정상 페이로드 인코드 → 디코드 시 `user_id`, `iss`, `iat`, `exp` 보존
- ⚠️ 만료된 토큰 → `decode_token`이 예외 발생
- ⚠️ 잘못된 secret/algorithm → 예외 발생
- 🌀 페이로드에 한국어/특수문자 포함되어도 round-trip 보존

### 1-2. `current_user` 의존성

- ✅ 정상 access_token + 유효한 user → `SimpleUser` 반환
- ⚠️ Authorization 헤더 없음 → 403 "토큰이 존재하지 않습니다."
- ⚠️ 토큰 디코딩 실패 → 403 "토큰이 유효하지 않습니다."
- ⚠️ refresh 타입 토큰을 access로 사용 → 403
- ⚠️ 디코딩은 성공하지만 user 미존재 → 404
- 🌀 user_id가 빈 문자열 → 404

### 1-3. `GET /v1/slack/login`

- ✅ state 발급 후 redirect_url 반환
- 🌀 state_store 호출 횟수/인자 검증 (authorize_url_generator.generate 호출 검증으로 대체)

### 1-4. `GET /v1/slack/auth`

- ✅ code 정상 → access/refresh 토큰 JSON 반환 (oauth_flow.run_installation mock)
- ⚠️ `error` 쿼리 파라미터 존재 → 404
- ⚠️ `code`가 None → 403
- ⚠️ `oauth_flow.run_installation`이 None 반환 → 403

### 1-5. `GET /v1/slack/auth/refresh`

- ✅ refresh 토큰으로 access 재발급
- ⚠️ access 타입 토큰을 refresh로 사용 → 403 (버그 수정 완료: `return HTTPException` → `raise HTTPException`)
- ⚠️ user 미존재 → 404
- ⚠️ 토큰 디코드 실패 → 403
- 🌀 만료된 refresh 토큰 → 403

### 1-6. `GET /v1/slack/me`

- ✅ 인증된 유저 → `SimpleUser` JSON 반환
- ⚠️ 인증 누락 → 403

---

## 2. API — 콘텐츠 (`app/api/views/contents.py`)

### 2-1. `GET /v1/contents`

- ✅ "전체보기" 키워드 → 최신순으로 limit/offset 잘 적용
- ✅ 일반 키워드 → 매칭된 콘텐츠 반환 + relevance 정렬
- ✅ `category` 필터 — 키워드 검색 / 전체보기 양쪽 모두에서 동작. (버그 발견 후 수정 완료: `joined_df` 를 필터하도록 변경 + 분기를 전체보기 앞으로 이동. 별도 회귀: polars 1.x 에서 `.apply`/`.groupby` 제거 → `polars<1.0` 으로 핀)
- ✅ `job_category` 필터 적용
- ⚠️ `limit > 50` → 422 (Query 검증)
- 🌀 매칭되는 콘텐츠 없음 → `count=0, data=[]`
- 🌀 키워드에 콤마/슬래시 포함 → 다중 키워드로 분리되는지
- 🌀 `keyword` 빈 문자열(누락) → 422
- 🌀 `descending=False` 정렬

### 2-2. `GET /v1/messages`

- ✅ admin이 조회 → slack 메시지 dict 반환 (slack mock)
- ✅ `multiple_messages=True` → 리스트 반환
- ✅ `type=reply` → conversations_replies 호출
- ⚠️ 비-admin 유저 → 403
- ⚠️ 메시지가 검색되지 않음 → 404
- ⚠️ Slack `SlackApiError` → 409
- 🌀 인증 누락 → 403

### 2-3. `POST /v1/messages`

- ✅ admin이 메시지 수정 + permalink 반환
- ⚠️ 비-admin → 403
- ⚠️ Slack `SlackApiError` → 409

---

## 3. API — 종이비행기 (`app/api/views/paper_planes.py`)

### 3-1. `POST /v1/paper-planes`

- ✅ 정상 발송 → 201 + service.send_paper_plane 호출
- ⚠️ 자기 자신에게 발송 → 400
- ⚠️ 텍스트 300자 초과 → 400
- ⚠️ receiver_id가 BOT_IDS에 포함 → 400
- ⚠️ receiver 없는 유저 → 404 (service 내부)
- ⚠️ 인증 누락 → 403
- 🌀 정확히 300자 → 성공
- 🌀 SUPER_ADMIN 발신자도 분기 통과해 service까지 도달 (현재 코드는 비활성화 상태)

### 3-2. `GET /v1/paper-planes/sent`

- ✅ 보낸 종이비행기 페이지네이션 응답
- ⚠️ 인증 누락 → 403
- 🌀 limit > 1000 → 422
- 🌀 offset 매우 큼 → 빈 data

### 3-3. `GET /v1/paper-planes/received`

- ✅ 받은 종이비행기 응답
- ⚠️ 인증 누락 → 403

### 3-4. `ApiService.send_paper_plane`

- ✅ receiver 존재 → PaperPlane 생성 + repo create + 큐 적재 + chat_postMessage 2번
- ⚠️ receiver 없음 → HTTPException(404)

### 3-5. `ApiService.fetch_current_week_paper_planes`

- ✅ 토~금 범위 내 비행기 필터
- 🌀 토요일 00:00 정시 → 포함 (시작 boundary)
- 🌀 시작 1초 전 → 제외
- 🌀 금요일 23:59:59 → 포함 (end boundary)
- 🌀 다음주 토요일 00:00 → 제외
- 🌀 비행기 0건 → 빈 리스트

---

## 4. API — 포인트 / 메시지 / 인프런 / 글쓰기 참여

### 4-1. `POST /v1/points`

- ✅ `point_type=curation` 다수 유저 처리 (`grant_if_curation_selected` 호출 + 알림)
- ✅ `point_type=village_conference` 처리
- ✅ `point_type=special` + point/reason 정상
- ⚠️ 비-admin → 403
- ⚠️ 인증 누락 → 403
- ⚠️ `point_type=special` 인데 point=0 → 400
- ⚠️ `point_type=special` 인데 reason="" → 400
- 🌀 `user_ids` 빈 리스트 → 200 + 호출 0회

### 4-2. `POST /v1/send-messages`

- ✅ admin이 다수 메시지 전송
- ⚠️ 비-admin → 403
- ⚠️ 인증 누락 → 403
- 🌀 `dto_list`가 빈 리스트 → 200 + 호출 0회

### 4-3. `GET /v1/inflearn/coupons` (2026-09-08 기능 제거, worklog 021. 아래 케이스는 삭제됨)

- ✅ admin → CSV 데이터 반환
- ⚠️ 비-admin → 403
- ⚠️ 인증 누락 → 403
- 🌀 CSV가 비어 있을 때 빈 리스트

### 4-4. `GET /v1/writing-participation`

- ✅ CSV 행을 dict 리스트로 반환
- 🌀 CSV가 헤더만 있는 경우 빈 리스트

---

## 5. 슬랙 — core 이벤트 (`app/slack/events/core.py`)

### 5-1. `handle_app_mention`

- ✅ ack 호출 (그 외 부수효과 없음)

### 5-2. `open_deposit_view`

- ✅ 예치금 있는 유저 → 80,000 / 커피챗 2개 등 텍스트 포함
- 🌀 deposit 빈 문자열 → "확인 중" 메시지

### 5-3. `open_submission_history_view`

- ✅ 제출 내역 있을 때 회차/링크가 모달에 포함
- 🌀 제출 내역 없을 때 "글 제출 내역이 없어요." 표시

### 5-4. `download_submission_history`

- ⚠️ contents 비어있을 때 안내 메시지 후 종료

### 5-5. `open_help_view`

- ✅ views_open 호출 + 명령어 안내(/제출 /패스 /북마크) 포함

### 5-6. `admin_command`

- ✅ admin → ephemeral 메시지 표시
- ⚠️ 비-admin → `PermissionError` raise

### 5-7. `handle_sync_store`

- ✅ "유저" → store.pull_users 호출 + 시작/완료 메시지 2회
- ⚠️ 알 수 없는 옵션 → "동기화 테이블이 존재하지 않습니다."
- ⚠️ store 메서드 예외 → 관리자 채널에 에러 메시지(swallow)

### 5-8. `handle_invite_channel` / `handle_invite_channel_view` / `_invite_channel`

- ✅ handle_invite_channel → views_open
- ✅ 선택 채널 있음 → 그 채널만 초대 (시작/완료 메시지)
- ✅ 채널 미선택 → 모든 공개 채널 fetch 후 초대
- ⚠️ already_in_channel → "이미 채널에 참여 중"
- ⚠️ cant_invite_self → "자기 자신 초대"
- ⚠️ not_in_channel → conversations_join 후 재초대
- ⚠️ 알 수 없는 SlackApiError → 코드 + 문서 링크 포함

### 5-9. `handle_home_tab`

- ✅ 등록 안 된 user(None) → 안내 home 뷰만 publish
- ✅ 등록된 user → "내 글또 포인트" 등 풀세팅 publish

### 5-10. `open_*_view` (point/coffee_chat/etc) 액션 핸들러

- ✅ open_point_history_view → views_open
- ✅ open_point_guide_view → views_open
- ✅ open_paper_plane_guide_view → views_open
- 🌀 open_coffee_chat_history_view + 커피챗 0건 → "아직 커피챗 인증 내역이 없어요"
- ✅ open_coffee_chat_history_view + 인증 있음 → 다운로드 버튼 노출
- ✅ open_paper_plane_url → ack 만 (로그용)
- ✅ handle_channel_created → ack

### 5-11. `send_paper_plane_message` / `send_paper_plane_message_view`

- ✅ 액션 → 모달 open
- ⚠️ 자기 자신에게 보내기 → ack(errors=...)
- ⚠️ 텍스트 300자 초과 → ack(errors=...)
- ⚠️ 봇에게 보내기 → ack(errors=...)

### 5-12. `download_point_history`, `download_coffee_chat_history`, `download_submission_history`

- ✅ point_history: CSV 업로드 + permalink 메시지
- ⚠️ point_history 빈 내역 → 안내 메시지 후 종료
- ⚠️ coffee_chat_history 빈 내역 → 안내 메시지 후 종료
- ⚠️ submission_history 빈 내역 → 안내 메시지 후 종료

---

## 6. 슬랙 — contents 이벤트 (`app/slack/events/contents.py`)

### 6-1. `submit_command`

- ✅ 글쓰기 채널에서 호출 → 제출 모달 open
- ⚠️ 글쓰기 채널이 아닌 곳 → 글쓰기 참여 신청 안내 모달

### 6-2. `submit_view`

- ✅ 정상 url + 메타 → create_submit_content + chat_postMessage + 콤보/랭킹 분기
- ⚠️ url 형식 오류 → ack errors + raise
- ⚠️ get_title ClientException → ack errors + raise

### 6-3. `pass_command`, `pass_view`

- ✅ pass 가능 상태 → 패스 모달 (callback_id="pass_view")
- ⚠️ pass_count 한도 도달 → BotException
- ✅ pass_view → create_pass_content + chat_postMessage

### 6-4. `search_command`, `submit_search`, `web_search`, `back_to_search_view`

- ✅ /검색 → 검색 모달 open
- ✅ 키워드 검색 결과 ack(update) + 제목 갱신
- 🌀 결과 0건 → "총 0 개의 글" 표시
- ✅ web_search → ack 만 (외부 url)
- ✅ back_to_search_view → 검색 모달로 update

### 6-5. `bookmark_command`, `bookmark_modal`, `create_bookmark_view`, `handle_bookmark_page`, `open_overflow_action`

- 🌀 북마크 0건 → 모달 open
- ✅ 북마크 21개 (페이지 2개) → '다음 페이지' 버튼 노출
- ⚠️ 이미 북마크된 글 → "이미 북마크한 글이에요"
- ✅ 신규 북마크 → 저장 폼 모달 (callback_id=bookmark_view)
- ✅ create_bookmark_view → service.create_bookmark + ack(update)
- ✅ next_bookmark_page_action → views_update
- ✅ overflow remove_bookmark → service.update_bookmark + "북마크를 취소했어요"
- ✅ overflow view_note + 메모 → 메모 노출
- 🌀 overflow view_note + 메모 없음 → "메모가 없어요"

### 6-6. `intro_modal`, `edit_intro_view`, `submit_intro_view`, `contents_modal`

- ✅ 본인의 자기소개 → 수정 버튼이 있는 모달 (callback_id=edit_intro_view)
- 🌀 다른 유저의 자기소개 → 수정 버튼 없음
- ✅ edit_intro_view → ack(update) + callback_id=submit_intro_view
- ✅ submit_intro_view → service.update_user_intro 호출
- ✅ contents_modal → views_open

---

## 7. 슬랙 — community 이벤트 (`app/slack/events/community.py`)

### 7-1. `handle_coffee_chat_message`

- ✅ 일반(스레드 아님) → ephemeral 인증 안내 (cancel/submit 버튼 둘 다 포함)
- ✅ 답글 메시지 + 인증 가능 → reactions_add + 포인트 지급
- ⚠️ check_coffee_chat_proof BotException → 조용히 종료
- ⚠️ subtype="message_changed" + 답글 → 무동작

### 7-2. `cancel_coffee_chat_proof_button`

- ✅ requests.post 로 ephemeral 삭제 (delete_original=True)

### 7-3. `submit_coffee_chat_proof_button`

- ✅ views_open + private_metadata(ephemeral_url, message_ts) JSON 직렬화 검증

### 7-4. `submit_coffee_chat_proof_view`

- ⚠️ 본인만 선택(1명) → ack(errors=...)
- ✅ 본인 + 2명 이상 → reaction + 포인트 + 호출 메시지(본인 제외) + create_coffee_chat_proof + ephemeral 삭제
- 🌀 호출 메시지의 thread_ts 가 create_coffee_chat_proof.participant_call_thread_ts 로 전달
- 🌀 본인 + 1명 → 1명만 호출

### 7-5. `paper_plane_command`

- 🌀 SUPER_ADMIN → 무한(∞) 표시
- 🌀 일반 유저도 현재 코드 상 무한(∞) + send/open 버튼 노출

---

## 8. 슬랙 — log 이벤트 (`app/slack/events/log.py`)

### 8-1. `handle_comment_data` / `handle_post_data`

- ✅ comments_upload_queue 에 정확한 dict push (ts=thread_ts, comment_ts=event ts)
- ✅ posts_upload_queue 에 정확한 dict push

### 8-2. `handle_reaction_added`

- ✅ 일반 리액션 → emoji 큐 적재만
- ✅ 공지 채널 + noti-check + 첫 확인 + 3일 이내 → 포인트 + 기록 저장
- ⚠️ 스레드 메시지 → 포인트 X
- ⚠️ 이미 확인 → 포인트 X
- ⚠️ 3일 초과 → 포인트 X
- ✅ PRIMARY 채널 + catch-kyle + 1일 이내 + super_admin 글 → 포인트
- ⚠️ 1일 초과 → 포인트 X
- ⚠️ 글 작성자가 super_admin 아님 → 포인트 X
- ⚠️ 이미 확인한 글 → 포인트 X

### 8-3. `_is_thread_message`

- ✅ thread_ts 없음 → False
- ✅ thread_ts == ts → False (댓글 있는 일반 메시지)
- ✅ thread_ts != ts → True
- 🌀 messages 비어있음 → False

### 8-4. `_is_checked_notice` / `_write_checked_notice` & super_admin 버전

- 🌀 파일 미존재 → False (notice / super_admin 각각)
- ✅ 신규 기록 작성 → 다음 호출에서 True (notice / super_admin 각각)
- 🌀 다른 user_id → False (notice)

### 8-5. `handle_reaction_removed`

- ✅ ack 만 호출

---

## 9. 슬랙 — subscriptions 이벤트 (`app/slack/events/subscriptions.py`)

### 9-0. `_process_user_subscription` (5단계 검증)

- ⚠️ 자기 자신 → '자기 자신은 구독할 수 없어요'
- ⚠️ 봇 → '봇은 구독할 수 없어요'
- ⚠️ 이미 5명 → '구독은 최대 5명까지'
- ⚠️ 대상 미존재 → '구독할 멤버를 찾을 수 없습니다'
- ⚠️ 이미 구독 중 → '이미 구독한 멤버입니다'
- ✅ 모두 통과 → service.create_subscription 호출 + 빈 문자열 반환

### 9-1. `open_subscribe_member_view`

- ✅ value 없음 → 빈 메시지 + 모달 open
- ✅ value 있음 → _process_user_subscription 처리 후 모달 open

### 9-2. `subscribe_member`

- ✅ 정상 구독 → views_update + create_subscription 호출
- ⚠️ 자기 자신 선택 → 경고 메시지가 모달에 노출
- 🌀 selected_user 없음 → ack 만 + 무동작

### 9-3. `unsubscribe_member`

- ✅ subscription_id로 cancel_subscription + views_update

### 9-4. `open_subscription_permalink`

- ✅ ack 만 호출 (로깅용)

### 9-5. `_get_subscribe_member_view`

- 🌀 구독 0건 → 구독 목록 블록 없음
- ✅ 구독 2건 → '구독 목록' + 각 멤버 + 날짜(01월 01일 형식)
- 🌀 message 인자 있음 → 경고 컨텍스트 블록

---

## 10. 슬랙 — writing_participation 이벤트 (`app/slack/events/writing_participation.py`)

### 10-1. `open_writing_participation_view`

- ✅ is_writing_participation=True → 완료 안내 모달 (callback_id 없음)
- ✅ False → 신청 모달 (callback_id=writing_participation_view)

### 10-2. `submit_writing_participation_view`

- ✅ CSV 미존재 (FileNotFoundError) → 헤더 + 새 행 작성
- ✅ 기존 CSV에 같은 user_id 없음 → 행 append
- ✅ 기존 행(created_at 빈 문자열) → name/created_at/플래그 갱신
- 🌀 기존 created_at 채워져 있으면 유지 (덮어쓰지 않음)
- 🌀 컬럼 누락된 CSV → 누락 컬럼 자동 채움
- ✅ DM 메시지 전송 ("글쓰기 참여 신청을 완료")

---

## 11. 미들웨어 / 에러 핸들러 (`app/slack/event_handler.py`)

### 11-1. `log_event_middleware`

- ✅ command → event=명령어, type=command, description 매핑
- ✅ view_submission → callback_id, type=view_submission
- ✅ block_actions → action_id, type=block_actions
- ✅ event_callback → event.type, type=event
- ⚠️ event=message → 로깅 우회 (handle_message 가 별도 처리)
- ⚠️ event=reaction_added → 로깅 우회
- 🌀 알 수 없는 body 모양 → event="unknown", type="unknown"

### 11-2. `dependency_injection_middleware`

- ✅ event=message → 의존성 주입 X, next() 즉시
- ✅ event=app_mention → 우회
- ✅ 일반 이벤트 + 등록 유저 → service/point_service/user 주입
- ✅ app_home_opened + 미등록 유저 → service/point_service/user 모두 None
- ⚠️ 미등록 유저 + 일반 이벤트 → 관리자 채널 알림 + BotException
- 🌀 user_id=None (일부 슬랙 봇) → silent return

### 11-3. `handle_error`

- ✅ 한국어 에러 → 사용자 모달 + 관리자 알림
- ✅ 영문 에러 → "예기치 못한 오류" 모달
- ⚠️ ValueError → reraise (모달/알림 없음)
- 🌀 trigger_id 없음 → views_open 안 부르고 관리자 알림만

---

## 12. 백그라운드 서비스 (`app/slack/services/background.py`)

> 기존 `test_reminder.py` 보완. mock 기반 단위 테스트.

### 12-1. `send_reminder_message_to_user`

- ✅ 대상 필터링 (10기 / 채널명 - / 미제출) — 기존 test_background_service.py
- ✅ 관리자 채널 총원 메시지 — 기존
- 🌀 대상 0명 → 관리자 채널에 "총 0 명" — 신규

### 12-2. `prepare_subscribe_message_data`

- ✅ 어제 날짜의 submit 만 필터링 (그저께/pass 제외)
- 🌀 매칭 콘텐츠 0건 → 임시 CSV 미생성
- ✅ writing_participation 등록 유저 → target_user_channel 을 WRITING_CHANNEL 로 치환
- 🌀 기존 임시 CSV 있음 → 삭제 후 진행

### 12-3. `send_subscription_messages`

- 🌀 임시 CSV 미존재 → silent return
- ✅ 행마다 _send_subscription_message + 마지막에 요약 메시지
- ⚠️ 개별 발송 실패 → 관리자 알림 + 다음 행 계속

### 12-4. `_send_subscription_message`

- ✅ permalink 가져오기 + chat_postMessage 호출
- ⚠️ chat_getPermalink 계속 실패 → tenacity 3회 재시도 후 예외 전파

---

## 13. 회귀(이미 있는 테스트) 정리

- `test_point.py` → `test/services/test_point_service.py`로 이동 (0번 사전 작업에서 처리)
- `test_reminder.py` → `test/services/test_background_service.py`로 이동 (0번 사전 작업에서 처리)
- 기존 conftest의 `FakeSlackApp`을 새 위치에서 재사용 (백그라운드 서비스 테스트에서 활용)

---

## 진행 현황 (대시보드)

전체 항목 수와 완료 여부를 한눈에 보기 위한 칸. 대략적인 % 또는 N/M 형태로 갱신.

- 0. 사전 작업: 7/7 ✅
- 1. API 인증/로그인: 16/16 ✅ (refresh 라우터 버그 발견 + 수정 완료)
- 2. API 콘텐츠/메시지: 21/21 ✅ (category 필터 버그 발견 + 수정 완료, polars<1.0 핀)
- 3. API 종이비행기: 22/22 ✅ (라우터 14 + ApiService 단위 8, 토~금 경계 포함)
- 4. API 포인트/메시지/인프런/글쓰기: 18/18 ✅
- 5. 슬랙 core: 35/35 ✅
- 6. 슬랙 contents: 27/27 ✅
- 7. 슬랙 community: 11/11 ✅
- 8. 슬랙 log: 21/21 ✅
- 9. 슬랙 subscriptions: 16/16 ✅
- 10. 슬랙 writing_participation: 8/8 ✅
- 11. 미들웨어/에러: 17/17 ✅
- 12. 백그라운드 서비스: 11/11 ✅ (기존 1개 + 신규 10개)
- 13. 회귀 정리: 3/3 ✅ (0번 사전 작업과 12번에서 자연스럽게 처리됨)

**총합 약 180개 케이스** (정확한 수는 작성 중 변동). 단계 진행하며 본 문서 갱신.
