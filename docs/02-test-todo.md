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

- [ ] ✅ 정상 발송 → 201 + service.send_paper_plane 호출
- [ ] ⚠️ 자기 자신에게 발송 → 400
- [ ] ⚠️ 텍스트 300자 초과 → 400
- [ ] ⚠️ receiver_id가 BOT_IDS에 포함 → 400
- [ ] ⚠️ receiver 없는 유저 → 404 (service 내부)
- [ ] ⚠️ 인증 누락 → 403
- [ ] 🌀 정확히 300자 → 성공
- [ ] 🌀 SUPER_ADMIN 발신자는 횟수 제한이 적용되지 않는지 (현재 코드는 비활성화 상태이지만 분기 자체는 검증)

### 3-2. `GET /v1/paper-planes/sent`

- [ ] ✅ 보낸 종이비행기 페이지네이션 응답
- [ ] ⚠️ 인증 누락 → 403
- [ ] 🌀 limit > 1000 → 422
- [ ] 🌀 offset 매우 큼 → 빈 data

### 3-3. `GET /v1/paper-planes/received`

- [ ] ✅ 받은 종이비행기 응답
- [ ] ⚠️ 인증 누락 → 403

### 3-4. `ApiService.send_paper_plane`

- [ ] ✅ receiver 존재 → PaperPlane 생성 + chat_postMessage 두 번 호출
- [ ] ⚠️ receiver 없음 → HTTPException(404)

### 3-5. `ApiService.fetch_current_week_paper_planes`

- [ ] ✅ 토~금 범위 내 비행기 필터
- [ ] 🌀 토요일 00:00 경계 / 금요일 23:59:59 경계 / 범위 밖

---

## 4. API — 포인트 / 메시지 / 인프런 / 글쓰기 참여

### 4-1. `POST /v1/points`

- [ ] ✅ `point_type=curation` 다수 유저 처리 (`grant_if_curation_selected` 호출)
- [ ] ✅ `point_type=village_conference` 처리
- [ ] ✅ `point_type=special` + point/reason 정상
- [ ] ⚠️ 비-admin → 403
- [ ] ⚠️ `point_type=special` 인데 point=0 또는 reason="" → 400
- [ ] 🌀 `user_ids` 빈 리스트 → 200 + 호출 0회

### 4-2. `POST /v1/send-messages`

- [ ] ✅ admin이 다수 메시지 전송
- [ ] ⚠️ 비-admin → 403
- [ ] 🌀 `dto_list`가 빈 리스트 → 200 + 호출 0회

### 4-3. `GET /v1/inflearn/coupons`

- [ ] ✅ admin → CSV 데이터 반환
- [ ] ⚠️ 비-admin → 403
- [ ] 🌀 CSV가 비어 있을 때 빈 리스트

### 4-4. `GET /v1/writing-participation`

- [ ] ✅ CSV 행을 dict 리스트로 반환
- [ ] 🌀 CSV가 비어있거나 헤더만 있는 경우 빈 리스트

---

## 5. 슬랙 — core 이벤트 (`app/slack/events/core.py`)

### 5-1. `handle_app_mention`

- [ ] ✅ ack 호출 (그 외 부수효과 없음)

### 5-2. `open_deposit_view`

- [ ] ✅ 예치금 있는 유저 → 안내 텍스트 + views_open 호출
- [ ] 🌀 deposit 빈 문자열 → "확인 중" 메시지
- [ ] 🌀 패스 횟수, 미제출 수, 커피챗 인증 수가 모두 반영되는지

### 5-3. `open_submission_history_view`

- [ ] ✅ 제출 내역 있을 때 SectionBlock 구성
- [ ] 🌀 제출 내역 없을 때 "글 제출 내역이 없어요." 표시
- [ ] 🌀 12개 초과 시 12개로 잘리는지
- [ ] 🌀 submit / pass 가 섞인 경우 라벨 분기

### 5-4. `download_submission_history`

- [ ] ✅ DM 채널 오픈 → CSV 업로드 → permalink 메시지 → 파일 삭제
- [ ] ⚠️ contents가 비어있을 때 "내역이 없습니다" 메시지 후 종료
- [ ] 🌀 임시 디렉터리 미존재 → 생성 후 진행

### 5-5. `open_help_view`

- [ ] ✅ views_open 호출 + 모든 명령어 안내가 블록에 포함

### 5-6. `admin_command`

- [ ] ✅ admin → ephemeral 메시지 표시
- [ ] ⚠️ 비-admin → `PermissionError` raise

### 5-7. `handle_sync_store`

- [ ] ✅ 각 옵션(전체/유저/...)별 store 메서드 호출 분기
- [ ] ⚠️ 알 수 없는 옵션 → "동기화 테이블이 존재하지 않습니다."
- [ ] ⚠️ 내부 store 메서드 예외 → 관리자 채널에 에러 메시지

### 5-8. `handle_invite_channel` / `handle_invite_channel_view`

- [ ] ✅ 채널 미선택 → 모든 공개 채널 fetch
- [ ] ✅ 선택 채널 → 해당 채널만 초대
- [ ] ⚠️ `_invite_channel`에서 `not_in_channel` → join 후 invite
- [ ] ⚠️ `already_in_channel` → "이미 참여 중" 메시지
- [ ] ⚠️ `cant_invite_self` → "자기 자신 초대" 메시지
- [ ] ⚠️ 알 수 없는 SlackApiError → 에러 메시지에 문서 링크 포함

### 5-9. `handle_home_tab`

- [ ] ✅ 등록 안 된 user → 안내 home 뷰
- [ ] ✅ 등록된 user → home 블록 정상 구성 (콤보 보너스 텍스트 포함)
- [ ] 🌀 콤보 1 미만, 일반 콤보, 특별 콤보(3·6·9...) 분기

### 5-10. `open_*_view` (point/coffee_chat/help/etc) 액션 핸들러

- [ ] ✅ 각각 ack + views_open 호출 검증

### 5-11. `send_paper_plane_message` / `send_paper_plane_message_view`

- [ ] ✅ 정상 메시지 전송
- [ ] ⚠️ 자기 자신에게 보내기 → 에러 응답
- [ ] ⚠️ 텍스트 300자 초과
- [ ] ⚠️ 봇에게 보내기

### 5-12. `download_point_history`, `download_coffee_chat_history`

- [ ] ✅ CSV 생성 → 슬랙 업로드 → 임시 파일 정리
- [ ] ⚠️ 내역 없음 → 안내 메시지 후 종료

---

## 6. 슬랙 — contents 이벤트 (`app/slack/events/contents.py`)

### 6-1. `submit_command`

- [ ] ✅ 글쓰기 채널에서 호출 → 제출 모달 open
- [ ] ⚠️ 글쓰기 채널이 아닌 곳 → 글쓰기 참여 신청 안내 모달
- [ ] 🌀 admin이 글쓰기 채널 외 채널에서 호출 → `private_metadata`가 호출 채널로 설정되는지

### 6-2. `submit_view`

- [ ] ✅ 정상 url + 메타데이터 → 콘텐츠 생성, 채널 메시지, 포인트 알림
- [ ] ⚠️ url 형식 오류 → ack errors
- [ ] ⚠️ 이미 제출한 url → ack errors
- [ ] ⚠️ 비공개/404 url → ack errors (httpx mock)
- [ ] ⚠️ 노션/네이버 링크인데 직접 입력 제목 없음 → ack errors
- [ ] 🌀 콤보 보너스/코어채널 등수 보너스가 함께 지급되는지

### 6-3. `pass_command`, `pass_view`

- [ ] ✅ 패스 가능 상태 → 모달 open / 패스 콘텐츠 생성
- [ ] ⚠️ pass_count 한도 도달 → BotException
- [ ] ⚠️ 직전 회차에 이미 pass → BotException

### 6-4. `search_command`, `submit_search`, `web_search`, `back_to_search_view`

- [ ] ✅ 키워드 검색 → 결과 블록 구성
- [ ] 🌀 결과 없음 → "결과 없음" 안내
- [ ] 🌀 카테고리 필터 적용

### 6-5. `bookmark_command`, `bookmark_modal`, `bookmark_view`,
       `bookmark_page_view`, `handle_bookmark_page`, `open_overflow_action`

- [ ] ✅ 북마크 추가 → repository 호출 + 큐 적재
- [ ] ⚠️ 이미 존재하는 북마크 → 적절한 안내
- [ ] 🌀 페이지네이션 (next/prev) 동작
- [ ] 🌀 overflow 메뉴: 삭제 / 메모 수정

### 6-6. `intro_modal`, `edit_intro_view`, `submit_intro_view`

- [ ] ✅ 자기소개 조회 / 수정
- [ ] ⚠️ 본인 외의 자기소개 수정 시도 → BotException

---

## 7. 슬랙 — community 이벤트 (`app/slack/events/community.py`)

### 7-1. `handle_coffee_chat_message`

- [ ] ✅ 일반 메시지 (스레드 아님) → ephemeral 인증 안내 전송
- [ ] ✅ 답글 메시지 + 인증 가능 → reaction_add + 포인트 지급
- [ ] ⚠️ 답글이지만 `check_coffee_chat_proof`에서 BotException → 무동작
- [ ] ⚠️ subtype="message_changed" + thread → 무시
- [ ] 🌀 file_share 첨부

### 7-2. `cancel_coffee_chat_proof_button`

- [ ] ✅ ephemeral 메시지 삭제 호출 (requests.post mock)

### 7-3. `submit_coffee_chat_proof_button`

- [ ] ✅ views_open 호출 + private_metadata 설정

### 7-4. `submit_coffee_chat_proof_view`

- [ ] ✅ 본인 포함 2명 이상 → reaction + 포인트 + create_coffee_chat_proof
- [ ] ⚠️ 1명만 선택 → ack errors
- [ ] 🌀 참여자 호출 메시지 thread_ts가 결과에 반영되는지

### 7-5. `paper_plane_command`

- [ ] ✅ 모달 open
- [ ] 🌀 SUPER_ADMIN은 무한, 일반 유저도 현재 무한(코드 값)

---

## 8. 슬랙 — log 이벤트 (`app/slack/events/log.py`)

### 8-1. `handle_comment_data` / `handle_post_data`

- [ ] ✅ 큐(`comments_upload_queue`/`posts_upload_queue`)에 정확한 데이터 push

### 8-2. `handle_reaction_added`

- [ ] ✅ 일반 리액션 → emoji 큐 적재만 수행
- [ ] ✅ 공지 채널 + `noti-check` + 첫 확인 + 3일 이내 → 포인트 지급 + 기록 저장
- [ ] ⚠️ 스레드 메시지인 경우 → 무시
- [ ] ⚠️ 이미 확인한 경우 → 무시
- [ ] ⚠️ 3일 초과 → 무시
- [ ] ✅ PRIMARY 채널 + `catch-kyle` + 1일 이내 + super_admin 글 → 포인트
- [ ] ⚠️ 이미 확인 / 1일 초과 / super_admin 글 아님 → 무시

### 8-3. `_is_thread_message`

- [ ] ✅ thread_ts 없음 → False
- [ ] ✅ thread_ts == ts → False
- [ ] ✅ thread_ts != ts → True
- [ ] 🌀 메시지 미존재 → False

### 8-4. `_is_checked_notice` / `_write_checked_notice` & super_admin 버전

- [ ] ✅ 신규 기록 작성 → 다음 호출에서 True
- [ ] 🌀 파일 미존재 → False

### 8-5. `handle_reaction_removed`

- [ ] ✅ ack 호출 (그 외 부수효과 없음)

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
- 3. API 종이비행기: 0/13
- 4. API 포인트/메시지/인프런/글쓰기: 0/9
- 5. 슬랙 core: 0/30
- 6. 슬랙 contents: 0/24
- 7. 슬랙 community: 0/12
- 8. 슬랙 log: 0/15
- 9. 슬랙 subscriptions: 0/10
- 10. 슬랙 writing_participation: 0/7
- 11. 미들웨어/에러: 0/11
- 12. 백그라운드 서비스: 0/10
- 13. 회귀 정리: 0/3

**총합 약 180개 케이스** (정확한 수는 작성 중 변동). 단계 진행하며 본 문서 갱신.
