# 또봇 TODO (단일 추적 문서)

> 마지막 업데이트 2026-09-08
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
- [ ] 포트 **3389**, 헬스체크 경로 `/`
- [ ] 환경변수: `.env`의 모든 키를 Koyeb 환경변수로 (dict·list 값은 JSON 문자열). **`KOYEB_URL`**(https:// 포함 공개 URL) 추가하면 self-ping 활성
- [ ] 첫 배포 로그 확인: "시트 탭 생성: writing_participation"(최초 1회) · "시트에서 복원한 테이블: [...]" · 슬랙 소켓 연결 · 5분 뒤 "self-ping 성공: 200"

### A-2. 컷오버 (봇 두 개 동시 실행 금지)
- [ ] 기존 서버: 마지막 활동 후 **20초 이상** 기다렸다가(큐 flush) `make kill-server`. 슬랙 소켓 모드는 두 곳이 같이 뜨면 이벤트가 분산됨
- [ ] Koyeb 서비스 재배포 → 부팅 복원으로 시트에서 CSV 재구성 → 슬랙 `/도움말`·`/제출`·글쓰기 참여 신청 확인
- [ ] 도메인 ✋
  - 커스텀 도메인 되면: `ttobot.kro.kr` CNAME → Koyeb 제공 대상, TLS 자동
  - 안 되면: 프론트(`geultto-paper-plane.vercel.app`)의 API 베이스 URL을 `*.koyeb.app`으로 교체
- [ ] 며칠 무탈 후 기존 서버 정지 → 한 달 뒤 삭제

### A-3. 운영 확인 (선택)
- [ ] 주간 재배치 뒤 자동 복원 1회 관찰 (로그 + 글쓰기 참여 신청 기록 유지 여부)
- [ ] UptimeRobot 등 외부 다운 알림 (self-ping과는 별개)

---

## B. 비기능적 정리 (`docs/04` 참고)

- [ ] `community.py`의 `requests.post` 2곳 → `httpx.AsyncClient`, 사용처 0이면 `requests` 의존성 제거
- [ ] `/v1/contents` CSV를 mtime 기반 캐시로 (매요청 5MB 파싱 제거). 0.1 vCPU에서 체감 큼
- [ ] `app/__init__.py` startup 헬퍼 분리 → `lifespan` 전환 → `jobs.py`·`lifespan.py` 분리 (3 PR)
- [ ] `SlackRepository` 매요청 CSV read → mtime 기반 인메모리 인덱스

---

## C. 문서

- [ ] `docs/05`·`docs/06`(GCP 가이드, gitignore 로컬 문서) 상단에 "Koyeb로 전환, GCP는 폴백" 한 줄
- [ ] 배포·리팩터링 worklog는 **020부터** (017~019 사용됨)
