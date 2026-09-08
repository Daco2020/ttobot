# 또봇 TODO 완료 기록

> 활성 TODO는 [`/TODO.md`](TODO.md). 여기엔 끝난 항목과 결정 이력만 둔다. (전역 규칙 #13)

## 완료 항목

| 완료일 | 항목 | 근거 |
| --- | --- | --- |
| 2026-09-08 | 인프런 쿠폰 기능 제거 (만료 2025-03, Koyeb 에선 종이비행기마다 관리자 알림) | worklog 021 · `595f612` |
| 2026-09-08 | 공지 확인·성윤을 잡아라 중복 판정을 point_histories 결정적 id 로 (재배포 무관) | worklog 021 · `74d2e21` |
| 2026-09-08 | 부팅 복원 실패 시 fail-closed (Koyeb 롤링 배포에서 정상 배포 보호) | worklog 021 · `2461469` |
| 2026-09-08 | `update_bookmark` 가 user_id 를 무시하던 기존 데이터 버그 수정 | worklog 021 · `e636017` |
| 2026-09-08 | `ts_to_dt` KST 명시 (UTC 컨테이너에서 BigQuery 날짜·커피챗 날짜 보존) | worklog 021 · `0ca8cab` |
| 2026-09-08 | 시트 동기화 리팩터링: 갱신 배치(읽기1·쓰기1) · 429 백오프 · 슬라이스 큐 · replace_table · 요청 예산 · self-ping 알림. 2행 손상 버그 수정 | worklog 020 · `6a25fbf` |
| 2026-09-07 | Koyeb 이행 견고화: `writing_participation` 시트 동기화 · 부팅 시 없는 테이블만 복원 · self-ping | worklog 019 · `58c467f` |
| 2026-08-13 | GHCR 이미지 빌드·푸시 워크플로우 (`image-build.yml`) | `dbd379e` |
| 2026-08-13 | 활성 TODO를 `/TODO.md`로 일원화, docs 체크박스 385개 불릿 전환 | `eed33cb` |
| 2026-08-13 | Medium 등 봇 차단 사이트 글 제출 허용 (`cf-mitigated`로 구분) | worklog 018 · `3df65b1` |
| 2026-07-08 | 마감일 2주 간격 자동 확장, pre-commit mypy에서 `test/` 제외 | worklog 017 · `0f5169c` |
| 2026-04-29 | Dockerization Stage 1 (Dockerfile · compose · nginx · scripts) | worklog 016 · `ccd1fa1` |
| 2026-04-29 | CI `test.yml` | worklog 015 · `a846968` |
| 2026-04 | API·슬랙 전 계층 테스트 180+ 케이스, uv 전환 | worklog 001~014 |

## 결정 이력

| 날짜 | 결정 | 근거 |
| --- | --- | --- |
| 2026-09-07 | 호스팅 **Koyeb 무료** 확정, GCP e2-micro는 폴백 | $0 · sigongbot-mini 운영 경험 · RAM 실측 259MB로 512MB 내 |
| 2026-09-07 | 완료 항목·이력을 `TODO.md`에서 이 문서로 이관 | 전역 규칙 #13 |
| 2026-07-08 | `TODO.md` 최초 작성, docs 체크박스 일원화 | 전역 규칙 #13 |
