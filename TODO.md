# 또봇 TODO (단일 추적 문서)

> 마지막 업데이트 2026-07-08
>
> 이 문서가 **활성 TODO의 유일한 source of truth**입니다. `docs/` 의 계획 문서들은
> 배경·설계·클릭 가이드로 참고하고, "지금 뭘 해야 하나"는 여기서만 관리합니다.
> (전역 규칙 #13)

---

## 현재 상황 한눈에

| 영역 | 상태 | 근거 |
| --- | --- | --- |
| 테스트 보강 (API + 슬랙 전 계층) | ✅ 완료 | `docs/02` 180+ 케이스 전부 ✅, 현재 코드 **248개 테스트 함수** |
| CI (`test.yml`) | ✅ 완료 | worklog 015, `.github/workflows/test.yml` |
| Dockerization Stage 1 (로컬 컨테이너) | ✅ 완료 | worklog 016, `Dockerfile`·`docker-compose.yml`·`nginx/`·`scripts/` 존재 |
| 마감일(DUE_DATES) 자동 확장 | ✅ 완료 | worklog 017 (이번 작업) |
| **운영 배포 (GCP)** | ⬜ **Stage 2~7 미착수** | `docs/05` 대시보드 — Stage 1만 ✅ |
| **비기능적 정리 (성능·구조)** | ⬜ **4건 전부 미착수** | `docs/04` — 코드 확인 결과 아직 원본 패턴 그대로 |

**결론:** 개발·테스트·로컬 컨테이너화는 끝났고, **남은 큰 덩어리는 (1) 실제 GCP 배포**와
**(2) 배포 후 비기능적 리팩터링 4건**입니다. 나머지는 문서 정리 소소한 항목.

---

## A. 운영 배포 — GCP (가장 큰 남은 작업)

> 상세: `docs/05-배포-투두.md` (실행 체크리스트) + `docs/03-배포-가이드.md` (설계) +
> `docs/06-GCP-인스턴스-셋업-가이드.md` (클릭 가이드).
> 대부분 **인프라/콘솔 수작업**이라 사용자 주도가 필요. ✋ = 의사결정 포인트.

### A-2. Stage 2 — GCP 인스턴스 셋업 (1~2h)
- [ ] GCP 콘솔 진입 + 결제 계정 등록 + 예산 알림(₩1,000) 설정 ✋
- [ ] `ttobot-prod` 프로젝트 + `e2-micro`(us-central1-a, Ubuntu 22.04, 30GB) 인스턴스 생성
- [ ] 외부 고정 IP(`ttobot-static-ip`) 예약
- [ ] `ttobot.kro.kr` A 레코드를 새 IP로 변경 + `dig` 전파 확인 ⚠️ 다운타임 시작점
- [ ] gcloud CLI SSH 접속 + Docker 설치 + `hello-world` 검증
- [ ] 80/443 방화벽 룰 확인
- [ ] worklog 작성 (※ 번호는 018+ — 017은 마감일 작업이 이미 사용)

### A-3. Stage 3 — GHCR 이미지 빌드/푸시 (1h)
- [ ] GitHub repo Workflow 권한을 "Read and write"로
- [ ] `.github/workflows/image-build.yml` 작성 (`docs/03` 4-4 참고) — **현재 `test.yml`만 존재**
- [ ] main 푸시 → GHCR에 `ttobot:latest` + `ttobot:<sha>` 확인
- [ ] worklog 작성

### A-4. Stage 4 — 인스턴스에서 컨테이너 실행 (30m~1h)
- [ ] 운영 데이터(`store/*.csv`, `.env`, `logs.csv`) 새 인스턴스로 scp
- [ ] GHCR 로그인(private면 read:packages PAT)
- [ ] `docker compose pull && up -d` → 슬랙 소켓 연결 + `/도움말` 동작 확인
- [ ] ✋ **우회 해제 4-3-A**: watchtower를 공식 `containrrr/watchtower`로 재시도 → 되면 커밋, 안 되면 `nickfedor` 유지 (worklog 016 9장 참고)
- [ ] 기존 인스턴스 정지(1주 후) → 삭제(1달 후)
- [ ] worklog 작성

### A-5. Stage 5 — Watchtower 자동 갱신 (30m)
- [ ] ✋ 배포 알림 채널 결정 + Slack Incoming Webhook 발급
- [ ] ✋ **우회 해제 5-2**: `docker-compose.yml` watchtower Slack 알림 4줄 주석 해제 + `SLACK_WEBHOOK_FOR_DEPLOY` 주입
- [ ] 사소한 변경 push → 1~2분 내 자동 배포 + 알림 검증
- [ ] worklog 작성

### A-6. Stage 6 — HTTPS (nginx + Let's Encrypt) (30m)
- [ ] `docker-compose.yml` `CERTBOT_EMAIL` 본인 이메일로
- [ ] `docker compose up -d nginx` → 인증서 자동 발급 로그 확인
- [ ] HTTP→HTTPS 리다이렉트 + `curl https://ttobot.kro.kr/ → true` + 외부 프론트 mixed-content 없음
- [ ] 자동 갱신 시뮬레이션 + worklog 작성

### A-7. Stage 7 — 운영 안정화 (선택)
- [ ] UptimeRobot 헬스체크(5분) + 다운 알림
- [ ] `store/*.csv` 일일 백업(cron → GCS/Drive)
- [ ] 메모리/CPU 모니터링 + 컨테이너 로그 영속화

---

## B. 비기능적 정리 (배포 후 권장, 코드 확인 결과 4건 모두 미착수)

> 상세: `docs/04-비기능적-정리-가이드.md`. **기능 변경 0, 외부 응답 모양 보존, PR 단위 분리,
> 248개 테스트 회귀 확인**이 공통 전제. 권장 순서대로 나열.

### B-1. `requests` 동기 호출 → `httpx.AsyncClient` (가장 작음, 30m~1h)
- [ ] `app/slack/events/community.py`의 `requests.post` **2곳**(라인 121·259) → `httpx.AsyncClient`
- [ ] community 이벤트 테스트 mock 패턴 갱신
- [ ] `import requests` app/ 전역 grep 후 0이면 `pyproject.toml`에서 `requests` 제거
- [ ] worklog 작성

### B-2. `/v1/contents` CSV 캐싱 (반나절)
- [ ] `app/api/views/contents.py` — mtime 기반 LRU 캐시(`_load_*_df` 헬퍼)로 매요청 5MB 파싱 제거 (옵션 B 권장)
- [ ] 캐시 적중/무효화 테스트 2~3개 + worklog

### B-3. `app/__init__.py` startup 헬퍼 분리 (1~2일, 3 PR)
- [ ] PR1: startup 안 중첩 함수(`upload_queue`/`upload_bigquery`/`subscribe_job`)를 모듈 최상위로 + 단위 테스트
- [ ] PR2: `@app.on_event`(현재 deprecated 경고 발생) → `lifespan` 핸들러 전환
- [ ] PR3: `app/jobs.py`·`app/lifespan.py`로 파일 분리 (현재 둘 다 없음)
- [ ] 각 PR마다 회귀 확인 + worklog

### B-4. `SlackRepository` CSV 매요청 read → 인메모리 인덱스 (1~2일, 신중)
- [ ] `_Cache`(mtime 기반) 도입 → `get_user` 등 O(N)→O(1)
- [ ] write 후 캐시 무효화 정책 결정 + 캐시 테스트 + worklog
- [ ] (옵션 B: SQLite 이전은 데이터 폭증/동시성 이슈 보일 때만 검토)

---

## C. 문서·정합성 정리 (소소)

- [x] ~~전역 규칙 #13 준수: `docs/02·03·04·05`의 체크박스를 일반 불릿으로 전환 + 각 문서에 `/TODO.md` 포인터 추가~~ (2026-07-08 완료, 385개 체크박스 정리)
- [ ] worklog 번호 충돌 정리: `docs/05`가 "worklog/017-Stage2..."로 예약했으나 017은 마감일 작업이 사용 → 배포 worklog는 **018부터** 시작

---

## 변경 이력

| 날짜 | 내용 |
| --- | --- |
| 2026-07-08 | 최초 작성 — `docs/` 6개 문서 + 코드 실태 대조하여 남은 작업 정리 |
| 2026-07-08 | 체크박스 일원화 — `docs/02·03·04·05` 체크박스를 불릿으로 전환, 활성 TODO를 이 문서로 통일 |
