# 024 - 테스트가 실제 store 를 건드리지 못하게

## 왜

023 리뷰에서 발견. 전체 테스트를 저장소 폴더에서 돌리면 `store/point_histories.csv` 에 가짜 행 3줄이 쌓였다. 2026-04-27 부터 180행.

## 문제

- `test_grant_if_post_submitted_continuously` 가 `tmp_store` 없이 실제 저장소를 썼다. 저장소 코드의 경로가 상대경로(`store/...`)라 실행한 폴더의 실제 파일에 기록된다.
- 로컬 store 는 운영 데이터 사본이라(컷오버·복원 점검에 쓴다) 가짜 행이 섞이면 비교가 틀어진다. git·Docker 이미지에는 빠져 있어 운영에는 가지 않았다.

## 해결

- 그 테스트에 `tmp_store` 픽스처를 붙였다.
- `conftest.py` 에 세션 범위 guard: `_STORE_FILES` 의 실제 파일 (크기·수정 시각)을 세션 시작·끝에 비교해 바뀌면 실패시킨다. logs.csv(로그 싱크)는 대상이 아니다.
- 순서: guard 먼저 → 스크래치 폴더 실행으로 RED(`['point_histories.csv']`) 확인 → 테스트 수정 → GREEN.

## 결과

- 저장소 폴더에서 전체 420 passed, `유저아이디` 행 수는 180 그대로(늘지 않음).
- 이미 쌓인 180행은 그대로 둔다 (사용자 결정 2026-09-12). 로컬 데이터를 시트와 비교할 때 이 행을 감안해야 한다.

## 사용자 검증 방법

1. `grep -c '"유저아이디"' store/point_histories.csv` → 180.
2. `make test` (저장소 폴더에서) → 420 passed, 위 숫자 그대로.
3. 엣지: 그 테스트에서 `tmp_store` 를 떼고 돌리면 세션 끝에 "테스트가 실제 store 파일을 바꿨습니다: ['point_histories.csv']" 로 실패.

| 날짜 | 내용 |
| --- | --- |
| 2026-09-12 | 테스트 격리 + 실제 store 변경 감지 guard |
