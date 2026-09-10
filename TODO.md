# 또봇 TODO (단일 추적 문서)

> 마지막 업데이트 2026-09-11
>
> 활성 TODO의 **유일한 source of truth**. 완료 항목과 결정 이력은 [`/TODO.DONE.md`](TODO.DONE.md).
> `docs/`는 배경·설계 참고용. (전역 규칙 #13)
>
> **호스팅 결정: Koyeb 무료 웹 서비스** (사용자 결정 2026-09-07). GCP e2-micro는 폴백.

---

## A. Koyeb 배포 (지금 할 일)

> 무료 티어: 웹 서비스 1개, 512MB / 0.1 vCPU / 2GB SSD, 프랑크푸르트·워싱턴.
> 디스크는 재배치마다 초기화(주 1회 이상), 1시간 인바운드 트래픽 없으면 잠듦.
> 이 둘은 worklog 019에서 코드로 대응 완료(없는 테이블만 시트 복원, self-ping).
>
> ✋ 아래 둘은 자료가 엇갈려 **콘솔에서 확인 후 분기**:
> (1) 무료 서비스에 Docker 이미지(GHCR) 배포 허용 여부 (2) 무료 서비스 커스텀 도메인 허용 여부.

### A-1. 서비스 생성
- [ ] Koyeb 로그인 → Create Web Service → 소스 선택 ✋
  - 이미지 배포가 되면: `ghcr.io/daco2020/ttobot:latest` (GHCR 패키지 public 전환 필요. push마다 재배포되는지 확인)
  - git만 되면: GitHub 레포 연결 + Dockerfile 빌드, main push 자동 배포 (GHCR 파이프라인은 GCP 폴백용으로 유지)
- [ ] 인스턴스 `Free`, 리전 프랑크푸르트 또는 워싱턴 ✋ (한국 지연은 비슷. 하나 골라 유지)
- [ ] 포트 **3389**(콘솔에서 노출 포트로), 헬스체크 경로 `/`, **grace period 120~180초**(부팅 시 시트 읽기 18회 + 슬랙 연결, 0.1 vCPU)
- [ ] 환경변수: **서버 `.env`**로 만든 `~/ttobot-backup/koyeb-env.txt`(권한 600, 입력 후 삭제)의 전체 키. ⚠️ **로컬 `.env`는 개발용이라 쓰면 안 됨**: 슬랙 토큰 2개·채널 7개·ENV가 서버와 다름(2026-09-11 해시 대조). dict·list 값은 바깥 따옴표 없는 순수 JSON. `SERVER_DOMAIN`은 커스텀 도메인이 안 되면 Koyeb 호스트로. **`KOYEB_URL`은 `https://{{ KOYEB_PUBLIC_DOMAIN }}/`**
- [ ] ⚠️ **첫 배포는 A-2의 시드 단계 뒤에.** 먼저 띄우면 빈 `writing_participation` 탭이 생기고 그걸 복원함
- [ ] 첫 배포 로그 확인(복원 실패 시 부팅 중단 + 관리자 알림, 옛 배포 유지): "시트에서 복원한 테이블: [8개]" · "시트 탭 생성"은 **없어야** 함(시드로 이미 존재) · 슬랙 소켓 연결 · 5분 뒤 "self-ping 성공"

### A-2. 컷오버 (봇 두 개 동시 실행 금지 · 검증된 절차, worklog 020 교차검증)
> 옛 서버 `ssh root@223.130.141.28`(키 인증 등록 2026-09-11) · `/root/ttobot` · 코드 `0f5169c`(017) · TZ KST. `ENV=prod`, 시트 URL·서비스 계정이 로컬과 같음, 컷오버 도구 업로드 완료.
- [ ] 시간 선택: 08:00 KST(구독 알림 잡)를 피해 조용한 시간대
- [ ] 정지 직전: 관리자 채널 공지 → 마지막 활동 후 **20초 이상** 대기 → `cp store/logs.csv store/logs.pre-cutover.csv`(shutdown이 logs.csv를 비움)
- [ ] `ps -ef | grep ttobot`으로 uvicorn만 잡히는지 눈으로 확인(vim/tail 오탐 주의) → `make kill-server` → `nohup.out`에 "Application shutdown complete" 확인
- [ ] 백업: `tar czf ~/store-$(date +%Y%m%d%H%M).tgz store/ .env nohup.out` → 로컬로 scp
- [ ] **flush 검증**: 옛 서버에서 `scripts/cutover_sheet_diff.py`(옛 코드로도 실행 가능) → `missing_in_sheet` 전부 0. 아니면 `--upload`로 빠진 행만 1회 append 후 재확인(전체 upload_all 금지: 중복)
- [ ] **WP 시드**: 옛 `store/writing_participation.csv`를 로컬로 scp → `uv run python scripts/seed_writing_participation.py <파일>` (HEAD 코드. 로컬 `.env`로 실행해도 됨: 시트 URL·서비스 계정이 서버와 같음). 시트의 수동 탭 `글쓰기신청자`는 값이 불리언 `TRUE`라 **재사용·붙여넣기 금지**
- [ ] Koyeb 배포(이미 띄운 적 있으면 **redeploy**로 디스크 초기화) → 로그 확인(A-1 마지막) → 슬랙 `/도움말`·`/제출`(참여자 계정: 모달 하단이 글쓰기 채널인지)·참여 신청 테스트 → 20초 내 시트 반영
- [ ] 도메인 ✋
  - 커스텀 도메인 되면: `ttobot.kro.kr` CNAME → Koyeb 제공 대상, TLS 자동
  - 안 되면: 프론트(`geultto-paper-plane.vercel.app`)의 API 베이스 URL을 `*.koyeb.app`으로 교체
- [ ] 롤백 대비: 옛 서버는 정지 상태로 보존(`store/` 삭제 금지). 롤백 시 옛 코드 `pull_all()` + WP 탭을 CSV로 내려받아 `make prod`
- [ ] 며칠 무탈 후 기존 서버 정지 → 한 달 뒤 삭제

### A-3. 운영 확인 (선택)
- [ ] 주간 재배치 뒤 자동 복원 1회 관찰 (로그 + 글쓰기 참여 신청 기록 유지 여부)
- [ ] **외부 핑 필수**(UptimeRobot 5분): 잠들면 self-ping도 같이 멈춰 스스로 못 깨어남. 다운 알림 겸용

---

## B. 비기능적 정리 (`docs/04` 참고)

- [ ] `community.py`의 `requests.post` 2곳 → `httpx.AsyncClient`, 사용처 0이면 `requests` 의존성 제거
- [ ] `/v1/contents` CSV를 mtime 기반 캐시로 (매요청 5MB 파싱 제거). 0.1 vCPU에서 체감 큼
- [ ] `app/__init__.py` startup 헬퍼 분리 → `lifespan` 전환 → `jobs.py`·`lifespan.py` 분리 (3 PR)
- [ ] `SlackRepository` 매요청 CSV read → mtime 기반 인메모리 인덱스
- [ ] 부팅 시 `worksheet()` 10회 → `doc.worksheets()` 1회, import 시 `gc.open_by_url` → 지연 로딩 (크래시 루프 시 429 방지)
- [ ] BigQuery 메모리 큐(10분) vs Koyeb SIGTERM 30초: 종료 시 최대 10분치 로그 유실 가능. 간격 단축 검토
- [ ] WP 참여 취소 관리 경로: 로컬 우선이라 시트에서 지워도 되돌아감. 취소 기능 또는 시트 우선 규칙 필요

---

## C. 문서

- [ ] `docs/05`·`docs/06`(GCP 가이드, gitignore 로컬 문서) 상단에 "Koyeb로 전환, GCP는 폴백" 한 줄
- [ ] 배포·리팩터링 worklog는 **020부터** (017~019 사용됨)
