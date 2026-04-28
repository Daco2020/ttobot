# 또봇 테스트 TODO

테스트 코드 작성 체크리스트. 케이스 분류:

- ✅ **성공** : 정상 흐름
- ⚠️ **실패** : 권한/유효성/외부 오류 처리
- 🌀 **엣지** : 경계값/특수 입력/누락된 필드/타이밍

각 항목은 `[ ]` 체크박스. 작업이 끝나면 PR 또는 커밋 단위로 체크한다.
하나의 라우터/핸들러 안에 case가 부족한 경우는 본문에 “해당 시나리오 없음”으로 명시.

---

## 0. 사전 작업

- [x] uv 가상환경 전환 (`pyproject.toml`, `uv.lock`)
- [x] `Makefile` `test` 타겟 추가 (`uv run pytest`)
- [x] `test/conftest.py` 정비 — 환경 변수, settings override, fake slack client
- [x] `test/factories.py` — `make_user()`, `make_content()`, `make_paper_plane()` 등
- [x] `test/api/conftest.py` — FastAPI `TestClient`, 토큰 발급 헬퍼
- [x] `test/slack/conftest.py` — slack_app/client mock, body 빌더
- [x] 기존 `test_point.py`, `test_reminder.py` → `test/services/` 이동

---

## 1. API — 인증 & 로그인 (`app/api/auth.py`, `app/api/views/login.py`)

### 1-1. `encode_token` / `decode_token`

- [x] ✅ 정상 페이로드 인코드 → 디코드 시 `user_id`, `iss`, `iat`, `exp` 보존
- [x] ⚠️ 만료된 토큰 → `decode_token`이 예외 발생
- [x] ⚠️ 잘못된 secret/algorithm → 예외 발생
- [x] 🌀 페이로드에 한국어/특수문자 포함되어도 round-trip 보존

### 1-2. `current_user` 의존성

- [x] ✅ 정상 access_token + 유효한 user → `SimpleUser` 반환
- [x] ⚠️ Authorization 헤더 없음 → 403 "토큰이 존재하지 않습니다."
- [x] ⚠️ 토큰 디코딩 실패 → 403 "토큰이 유효하지 않습니다."
- [x] ⚠️ refresh 타입 토큰을 access로 사용 → 403
- [x] ⚠️ 디코딩은 성공하지만 user 미존재 → 404
- [x] 🌀 user_id가 빈 문자열 → 404

### 1-3. `GET /v1/slack/login`

- [x] ✅ state 발급 후 redirect_url 반환
- [x] 🌀 state_store 호출 횟수/인자 검증 (authorize_url_generator.generate 호출 검증으로 대체)

### 1-4. `GET /v1/slack/auth`

- [x] ✅ code 정상 → access/refresh 토큰 JSON 반환 (oauth_flow.run_installation mock)
- [x] ⚠️ `error` 쿼리 파라미터 존재 → 404
- [x] ⚠️ `code`가 None → 403
- [x] ⚠️ `oauth_flow.run_installation`이 None 반환 → 403

### 1-5. `GET /v1/slack/auth/refresh`

- [x] ✅ refresh 토큰으로 access 재발급
- [x] ⚠️ access 타입 토큰을 refresh로 사용 → 403 (버그 수정 완료: `return HTTPException` → `raise HTTPException`)
- [x] ⚠️ user 미존재 → 404
- [x] ⚠️ 토큰 디코드 실패 → 403
- [x] 🌀 만료된 refresh 토큰 → 403

### 1-6. `GET /v1/slack/me`

- [x] ✅ 인증된 유저 → `SimpleUser` JSON 반환
- [x] ⚠️ 인증 누락 → 403

---

## 2. API — 콘텐츠 (`app/api/views/contents.py`)

### 2-1. `GET /v1/contents`

- [x] ✅ "전체보기" 키워드 → 최신순으로 limit/offset 잘 적용
- [x] ✅ 일반 키워드 → 매칭된 콘텐츠 반환 + relevance 정렬
- [x] ✅ `category` 필터 — 키워드 검색 / 전체보기 양쪽 모두에서 동작. (버그 발견 후 수정 완료: `joined_df` 를 필터하도록 변경 + 분기를 전체보기 앞으로 이동. 별도 회귀: polars 1.x 에서 `.apply`/`.groupby` 제거 → `polars<1.0` 으로 핀)
- [x] ✅ `job_category` 필터 적용
- [x] ⚠️ `limit > 50` → 422 (Query 검증)
- [x] 🌀 매칭되는 콘텐츠 없음 → `count=0, data=[]`
- [x] 🌀 키워드에 콤마/슬래시 포함 → 다중 키워드로 분리되는지
- [x] 🌀 `keyword` 빈 문자열(누락) → 422
- [x] 🌀 `descending=False` 정렬

### 2-2. `GET /v1/messages`

- [x] ✅ admin이 조회 → slack 메시지 dict 반환 (slack mock)
- [x] ✅ `multiple_messages=True` → 리스트 반환
- [x] ✅ `type=reply` → conversations_replies 호출
- [x] ⚠️ 비-admin 유저 → 403
- [x] ⚠️ 메시지가 검색되지 않음 → 404
- [x] ⚠️ Slack `SlackApiError` → 409
- [x] 🌀 인증 누락 → 403

### 2-3. `POST /v1/messages`

- [x] ✅ admin이 메시지 수정 + permalink 반환
- [x] ⚠️ 비-admin → 403
- [x] ⚠️ Slack `SlackApiError` → 409

---

## 3. API — 종이비행기 (`app/api/views/paper_planes.py`)

### 3-1. `POST /v1/paper-planes`

- [x] ✅ 정상 발송 → 201 + service.send_paper_plane 호출
- [x] ⚠️ 자기 자신에게 발송 → 400
- [x] ⚠️ 텍스트 300자 초과 → 400
- [x] ⚠️ receiver_id가 BOT_IDS에 포함 → 400
- [x] ⚠️ receiver 없는 유저 → 404 (service 내부)
- [x] ⚠️ 인증 누락 → 403
- [x] 🌀 정확히 300자 → 성공
- [x] 🌀 SUPER_ADMIN 발신자도 분기 통과해 service까지 도달 (현재 코드는 비활성화 상태)

### 3-2. `GET /v1/paper-planes/sent`

- [x] ✅ 보낸 종이비행기 페이지네이션 응답
- [x] ⚠️ 인증 누락 → 403
- [x] 🌀 limit > 1000 → 422
- [x] 🌀 offset 매우 큼 → 빈 data

### 3-3. `GET /v1/paper-planes/received`

- [x] ✅ 받은 종이비행기 응답
- [x] ⚠️ 인증 누락 → 403

### 3-4. `ApiService.send_paper_plane`

- [x] ✅ receiver 존재 → PaperPlane 생성 + repo create + 큐 적재 + chat_postMessage 2번
- [x] ⚠️ receiver 없음 → HTTPException(404)

### 3-5. `ApiService.fetch_current_week_paper_planes`

- [x] ✅ 토~금 범위 내 비행기 필터
- [x] 🌀 토요일 00:00 정시 → 포함 (시작 boundary)
- [x] 🌀 시작 1초 전 → 제외
- [x] 🌀 금요일 23:59:59 → 포함 (end boundary)
- [x] 🌀 다음주 토요일 00:00 → 제외
- [x] 🌀 비행기 0건 → 빈 리스트

---

## 4. API — 포인트 / 메시지 / 인프런 / 글쓰기 참여

### 4-1. `POST /v1/points`

- [x] ✅ `point_type=curation` 다수 유저 처리 (`grant_if_curation_selected` 호출 + 알림)
- [x] ✅ `point_type=village_conference` 처리
- [x] ✅ `point_type=special` + point/reason 정상
- [x] ⚠️ 비-admin → 403
- [x] ⚠️ 인증 누락 → 403
- [x] ⚠️ `point_type=special` 인데 point=0 → 400
- [x] ⚠️ `point_type=special` 인데 reason="" → 400
- [x] 🌀 `user_ids` 빈 리스트 → 200 + 호출 0회

### 4-2. `POST /v1/send-messages`

- [x] ✅ admin이 다수 메시지 전송
- [x] ⚠️ 비-admin → 403
- [x] ⚠️ 인증 누락 → 403
- [x] 🌀 `dto_list`가 빈 리스트 → 200 + 호출 0회

### 4-3. `GET /v1/inflearn/coupons`

- [x] ✅ admin → CSV 데이터 반환
- [x] ⚠️ 비-admin → 403
- [x] ⚠️ 인증 누락 → 403
- [x] 🌀 CSV가 비어 있을 때 빈 리스트

### 4-4. `GET /v1/writing-participation`

- [x] ✅ CSV 행을 dict 리스트로 반환
- [x] 🌀 CSV가 헤더만 있는 경우 빈 리스트

---

## 5. 슬랙 — core 이벤트 (`app/slack/events/core.py`)

### 5-1. `handle_app_mention`

- [x] ✅ ack 호출 (그 외 부수효과 없음)

### 5-2. `open_deposit_view`

- [x] ✅ 예치금 있는 유저 → 80,000 / 커피챗 2개 등 텍스트 포함
- [x] 🌀 deposit 빈 문자열 → "확인 중" 메시지

### 5-3. `open_submission_history_view`

- [x] ✅ 제출 내역 있을 때 회차/링크가 모달에 포함
- [x] 🌀 제출 내역 없을 때 "글 제출 내역이 없어요." 표시

### 5-4. `download_submission_history`

- [x] ⚠️ contents 비어있을 때 안내 메시지 후 종료

### 5-5. `open_help_view`

- [x] ✅ views_open 호출 + 명령어 안내(/제출 /패스 /북마크) 포함

### 5-6. `admin_command`

- [x] ✅ admin → ephemeral 메시지 표시
- [x] ⚠️ 비-admin → `PermissionError` raise

### 5-7. `handle_sync_store`

- [x] ✅ "유저" → store.pull_users 호출 + 시작/완료 메시지 2회
- [x] ⚠️ 알 수 없는 옵션 → "동기화 테이블이 존재하지 않습니다."
- [x] ⚠️ store 메서드 예외 → 관리자 채널에 에러 메시지(swallow)

### 5-8. `handle_invite_channel` / `handle_invite_channel_view` / `_invite_channel`

- [x] ✅ handle_invite_channel → views_open
- [x] ✅ 선택 채널 있음 → 그 채널만 초대 (시작/완료 메시지)
- [x] ✅ 채널 미선택 → 모든 공개 채널 fetch 후 초대
- [x] ⚠️ already_in_channel → "이미 채널에 참여 중"
- [x] ⚠️ cant_invite_self → "자기 자신 초대"
- [x] ⚠️ not_in_channel → conversations_join 후 재초대
- [x] ⚠️ 알 수 없는 SlackApiError → 코드 + 문서 링크 포함

### 5-9. `handle_home_tab`

- [x] ✅ 등록 안 된 user(None) → 안내 home 뷰만 publish
- [x] ✅ 등록된 user → "내 글또 포인트" 등 풀세팅 publish

### 5-10. `open_*_view` (point/coffee_chat/etc) 액션 핸들러

- [x] ✅ open_point_history_view → views_open
- [x] ✅ open_point_guide_view → views_open
- [x] ✅ open_paper_plane_guide_view → views_open
- [x] 🌀 open_coffee_chat_history_view + 커피챗 0건 → "아직 커피챗 인증 내역이 없어요"
- [x] ✅ open_coffee_chat_history_view + 인증 있음 → 다운로드 버튼 노출
- [x] ✅ open_paper_plane_url → ack 만 (로그용)
- [x] ✅ handle_channel_created → ack

### 5-11. `send_paper_plane_message` / `send_paper_plane_message_view`

- [x] ✅ 액션 → 모달 open
- [x] ⚠️ 자기 자신에게 보내기 → ack(errors=...)
- [x] ⚠️ 텍스트 300자 초과 → ack(errors=...)
- [x] ⚠️ 봇에게 보내기 → ack(errors=...)

### 5-12. `download_point_history`, `download_coffee_chat_history`, `download_submission_history`

- [x] ✅ point_history: CSV 업로드 + permalink 메시지
- [x] ⚠️ point_history 빈 내역 → 안내 메시지 후 종료
- [x] ⚠️ coffee_chat_history 빈 내역 → 안내 메시지 후 종료
- [x] ⚠️ submission_history 빈 내역 → 안내 메시지 후 종료

---

## 6. 슬랙 — contents 이벤트 (`app/slack/events/contents.py`)

### 6-1. `submit_command`

- [x] ✅ 글쓰기 채널에서 호출 → 제출 모달 open
- [x] ⚠️ 글쓰기 채널이 아닌 곳 → 글쓰기 참여 신청 안내 모달

### 6-2. `submit_view`

- [x] ✅ 정상 url + 메타 → create_submit_content + chat_postMessage + 콤보/랭킹 분기
- [x] ⚠️ url 형식 오류 → ack errors + raise
- [x] ⚠️ get_title ClientException → ack errors + raise

### 6-3. `pass_command`, `pass_view`

- [x] ✅ pass 가능 상태 → 패스 모달 (callback_id="pass_view")
- [x] ⚠️ pass_count 한도 도달 → BotException
- [x] ✅ pass_view → create_pass_content + chat_postMessage

### 6-4. `search_command`, `submit_search`, `web_search`, `back_to_search_view`

- [x] ✅ /검색 → 검색 모달 open
- [x] ✅ 키워드 검색 결과 ack(update) + 제목 갱신
- [x] 🌀 결과 0건 → "총 0 개의 글" 표시
- [x] ✅ web_search → ack 만 (외부 url)
- [x] ✅ back_to_search_view → 검색 모달로 update

### 6-5. `bookmark_command`, `bookmark_modal`, `create_bookmark_view`, `handle_bookmark_page`, `open_overflow_action`

- [x] 🌀 북마크 0건 → 모달 open
- [x] ✅ 북마크 21개 (페이지 2개) → '다음 페이지' 버튼 노출
- [x] ⚠️ 이미 북마크된 글 → "이미 북마크한 글이에요"
- [x] ✅ 신규 북마크 → 저장 폼 모달 (callback_id=bookmark_view)
- [x] ✅ create_bookmark_view → service.create_bookmark + ack(update)
- [x] ✅ next_bookmark_page_action → views_update
- [x] ✅ overflow remove_bookmark → service.update_bookmark + "북마크를 취소했어요"
- [x] ✅ overflow view_note + 메모 → 메모 노출
- [x] 🌀 overflow view_note + 메모 없음 → "메모가 없어요"

### 6-6. `intro_modal`, `edit_intro_view`, `submit_intro_view`, `contents_modal`

- [x] ✅ 본인의 자기소개 → 수정 버튼이 있는 모달 (callback_id=edit_intro_view)
- [x] 🌀 다른 유저의 자기소개 → 수정 버튼 없음
- [x] ✅ edit_intro_view → ack(update) + callback_id=submit_intro_view
- [x] ✅ submit_intro_view → service.update_user_intro 호출
- [x] ✅ contents_modal → views_open

---

## 7. 슬랙 — community 이벤트 (`app/slack/events/community.py`)

### 7-1. `handle_coffee_chat_message`

- [x] ✅ 일반(스레드 아님) → ephemeral 인증 안내 (cancel/submit 버튼 둘 다 포함)
- [x] ✅ 답글 메시지 + 인증 가능 → reactions_add + 포인트 지급
- [x] ⚠️ check_coffee_chat_proof BotException → 조용히 종료
- [x] ⚠️ subtype="message_changed" + 답글 → 무동작

### 7-2. `cancel_coffee_chat_proof_button`

- [x] ✅ requests.post 로 ephemeral 삭제 (delete_original=True)

### 7-3. `submit_coffee_chat_proof_button`

- [x] ✅ views_open + private_metadata(ephemeral_url, message_ts) JSON 직렬화 검증

### 7-4. `submit_coffee_chat_proof_view`

- [x] ⚠️ 본인만 선택(1명) → ack(errors=...)
- [x] ✅ 본인 + 2명 이상 → reaction + 포인트 + 호출 메시지(본인 제외) + create_coffee_chat_proof + ephemeral 삭제
- [x] 🌀 호출 메시지의 thread_ts 가 create_coffee_chat_proof.participant_call_thread_ts 로 전달
- [x] 🌀 본인 + 1명 → 1명만 호출

### 7-5. `paper_plane_command`

- [x] 🌀 SUPER_ADMIN → 무한(∞) 표시
- [x] 🌀 일반 유저도 현재 코드 상 무한(∞) + send/open 버튼 노출

---

## 8. 슬랙 — log 이벤트 (`app/slack/events/log.py`)

### 8-1. `handle_comment_data` / `handle_post_data`

- [x] ✅ comments_upload_queue 에 정확한 dict push (ts=thread_ts, comment_ts=event ts)
- [x] ✅ posts_upload_queue 에 정확한 dict push

### 8-2. `handle_reaction_added`

- [x] ✅ 일반 리액션 → emoji 큐 적재만
- [x] ✅ 공지 채널 + noti-check + 첫 확인 + 3일 이내 → 포인트 + 기록 저장
- [x] ⚠️ 스레드 메시지 → 포인트 X
- [x] ⚠️ 이미 확인 → 포인트 X
- [x] ⚠️ 3일 초과 → 포인트 X
- [x] ✅ PRIMARY 채널 + catch-kyle + 1일 이내 + super_admin 글 → 포인트
- [x] ⚠️ 1일 초과 → 포인트 X
- [x] ⚠️ 글 작성자가 super_admin 아님 → 포인트 X
- [x] ⚠️ 이미 확인한 글 → 포인트 X

### 8-3. `_is_thread_message`

- [x] ✅ thread_ts 없음 → False
- [x] ✅ thread_ts == ts → False (댓글 있는 일반 메시지)
- [x] ✅ thread_ts != ts → True
- [x] 🌀 messages 비어있음 → False

### 8-4. `_is_checked_notice` / `_write_checked_notice` & super_admin 버전

- [x] 🌀 파일 미존재 → False (notice / super_admin 각각)
- [x] ✅ 신규 기록 작성 → 다음 호출에서 True (notice / super_admin 각각)
- [x] 🌀 다른 user_id → False (notice)

### 8-5. `handle_reaction_removed`

- [x] ✅ ack 만 호출

---

## 9. 슬랙 — subscriptions 이벤트 (`app/slack/events/subscriptions.py`)

### 9-1. `open_subscribe_member_view`

- [ ] ✅ 액션 value 없음 → 빈 메시지 + 모달 open
- [ ] ✅ 액션 value의 target_user 처리 후 모달 open
- [ ] ⚠️ 자기 자신 구독 → 경고 메시지

### 9-2. `subscribe_member`

- [ ] ✅ 정상 구독 → views_update + create_subscription 호출
- [ ] ⚠️ 자기 자신, 봇, 5명 초과, 미존재 유저, 이미 구독 → 메시지로 차단
- [ ] 🌀 `selected_user` 없음 → 무동작

### 9-3. `unsubscribe_member`

- [ ] ✅ subscription_id로 cancel + 모달 갱신

### 9-4. `open_subscription_permalink`

- [ ] ✅ ack 호출 (로깅만)

### 9-5. `_get_subscribe_member_view`

- [ ] ✅ 구독 0/1/N 명에 따른 블록 구성
- [ ] 🌀 message 인자 유무에 따른 안내 블록 포함 여부

---

## 10. 슬랙 — writing_participation 이벤트 (`app/slack/events/writing_participation.py`)

### 10-1. `open_writing_participation_view`

- [ ] ✅ `is_writing_participation=True` → 완료 안내 모달
- [ ] ✅ False → 신청 모달

### 10-2. `submit_writing_participation_view`

- [ ] ✅ CSV 미존재 → 헤더 포함 신규 작성
- [ ] ✅ 기존 CSV에 같은 user_id 없음 → 행 append
- [ ] ✅ 기존 행 존재 → name/created_at/플래그 갱신
- [ ] 🌀 컬럼 누락된 CSV → 누락 컬럼 자동 채움
- [ ] ✅ DM 메시지 전송 (slack client mock)

---

## 11. 미들웨어 / 에러 핸들러 (`app/slack/event_handler.py`)

### 11-1. `log_event_middleware`

- [ ] ✅ command body → event/type=command 로 로깅
- [ ] ✅ view_submission body → callback_id 로 로깅
- [ ] ✅ block_actions body → action_id 로 로깅
- [ ] ✅ event body → event.type 로 로깅
- [ ] ✅ message/reaction 이벤트 → 로깅 우회
- [ ] 🌀 description "종이비행기 메시지 전송 완료" 분기

### 11-2. `dependency_injection_middleware`

- [ ] ✅ 일반 이벤트 + 등록 유저 → service/point_service/user 주입
- [ ] ✅ 메시지/멘션/리액션 등 우회 이벤트 → next() 즉시 호출
- [ ] ✅ app_home_opened + 미등록 유저 → service None 주입 후 next
- [ ] ⚠️ 미등록 유저 + 일반 이벤트 → 관리자 채널 알림 + BotException

### 11-3. `handle_error`

- [ ] ✅ 한국어 에러 메시지 → 사용자에게 동일 메시지 노출
- [ ] ✅ 영문 에러 → "예기치 못한 오류" 노출
- [ ] ⚠️ ValueError → reraise (사용자 알림 X)
- [ ] ✅ trigger_id가 있을 때 views_open으로 안내 모달 표시
- [ ] ✅ 관리자 채널에 traceback 포함 메시지 전송

---

## 12. 백그라운드 서비스 (`app/slack/services/background.py`)

> 기존 `test_reminder.py` 보완. mock 기반 단위 테스트.

### 12-1. `send_reminder_message_to_user` (이미 일부 존재)

- [ ] ✅ 대상 필터링 (10기 / 채널명 - / 미제출)
- [ ] ✅ 메시지 본문 포맷
- [ ] ✅ 관리자 채널에 총원 메시지 전송
- [ ] 🌀 대상 0명일 때 admin 채널에 "0 명" 메시지

### 12-2. `prepare_subscribe_message_data`

- [ ] ✅ 어제 날짜의 submit 콘텐츠만 필터링
- [ ] ✅ writing_participation 등록 유저는 WRITING_CHANNEL로 채널 치환
- [ ] 🌀 구독 0건/대상 콘텐츠 0건 → CSV 미생성
- [ ] 🌀 기존 임시 CSV 존재 시 삭제 후 진행

### 12-3. `send_subscription_messages`

- [ ] ✅ CSV 행마다 chat_postMessage 호출
- [ ] ⚠️ `_send_subscription_message`에서 예외 → 관리자 채널에 에러 메시지 + 다음 행 진행
- [ ] ✅ 마지막에 총원 요약 메시지

### 12-4. `_send_subscription_message`

- [ ] ✅ permalink 가져오기 + 블록 구성 + chat_postMessage 호출
- [ ] ⚠️ 3회 재시도 후 실패 → 예외 전파

---

## 13. 회귀(이미 있는 테스트) 정리

- [ ] `test_point.py` → `test/services/test_point_service.py`로 이동, import 경로 갱신
- [ ] `test_reminder.py` → `test/services/test_background_service.py`로 이동
- [ ] 기존 conftest의 `FakeSlackApp`을 새 위치에서 재사용

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
- 9. 슬랙 subscriptions: 0/10
- 10. 슬랙 writing_participation: 0/7
- 11. 미들웨어/에러: 0/11
- 12. 백그라운드 서비스: 0/10
- 13. 회귀 정리: 0/3

**총합 약 180개 케이스** (정확한 수는 작성 중 변동). 단계 진행하며 본 문서 갱신.
