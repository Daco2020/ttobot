# 또봇 TODO (단일 추적 문서)

> 마지막 업데이트 2026-09-11
>
> 활성 TODO의 **유일한 source of truth**. 완료 항목과 결정 이력은 [`/TODO.DONE.md`](TODO.DONE.md).
> `docs/`는 배경·설계 참고용. (전역 규칙 #13)
>
> **호스팅 결정: Koyeb 무료 웹 서비스** (사용자 결정 2026-09-07). GCP e2-micro는 폴백.

---

## A. Koyeb 이전 마무리

> 2026-09-11 컷오버 완료. 프론트도 Koyeb 주소로 교체·로그인 확인 → **기능적 이전 완료.** 운영 주소는 **`https://deep-tilly-eunchan-317eb831.koyeb.app`** (커스텀 도메인은 Koyeb Pro 전용이라 쓰지 않음).
> 옛 서버 `ssh root@223.130.141.28`(키 인증) · 봇 **종료 확인**(프로세스·3389 없음) · `/root/ttobot` 파일 보존 중.

- [ ] 로컬 `~/ttobot-backup/koyeb-env.txt` 삭제 (운영 비밀값 사본, Koyeb 입력 완료)
- [ ] 주간 재배치 뒤 자동 복원 1회 관찰 (로그 + 글쓰기 참여 신청 기록 유지)
- [ ] 며칠 무탈 후 옛 서버 삭제. `cero.kro.kr` 은 이미 죽은 별개 서비스(백엔드 8000 다운, 502만 반환)라 불필요 확인됨(2026-09-11). 되살리려면 DNS 재지정 필요. 롤백은 옛 서버에서 `pull_all()` 후 `make prod`
- [ ] (선택) Koyeb `SERVER_DOMAIN` 을 koyeb 호스트로. 쿠키 도메인용인데 인증은 Bearer 헤더라 안 바꿔도 무방. 프론트·백엔드 도메인이 달라 이 쿠키는 어차피 미사용

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
