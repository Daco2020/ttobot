# 019 - Koyeb 이행 견고화 (writing_participation 동기화 · 부팅 복원 · self-ping)

## 왜

무료 호스팅으로 Koyeb 를 검토했다. 무료 인스턴스는 **재배치마다 디스크가 초기화**되고,
**1시간 인바운드 트래픽이 없으면 scale-to-zero** 된다. 이 둘에 맞춰 세 가지를 손봤다.
(사용자 결정 2026-09-07: 탭 추가 승인, 환경변수명 `KOYEB_URL`)

## 문제

1. `writing_participation.csv` 가 **로컬 전용**이었다. 시트 업로드 경로 0건, `client.py` 탭 목록에도 없음.
   디스크가 지워지면 글쓰기 참여 신청 기록이 통째로 사라진다.
2. startup 에 시트 → 로컬 복원이 없었다. 로컬이 원본(시트보다 최대 20초 앞섬)인 구조라
   디스크 유지 서버에서는 필요가 없었던 것. 디스크가 없는 환경에선 빈 CSV 로 뜬다.
3. 슬랙 소켓 모드는 봇이 밖으로 여는 연결이라 Koyeb 가 트래픽으로 세지 않는다.

## 해결

- `client.py`: `writing_participation` 탭 추가. 없으면 **자동 생성 + 헤더** (`_get_or_create_worksheet`).
  덤으로 `__new__(cls)` 가 `doc=` 주입 인자를 삼키지 않던 **기존 잠재 버그**를 고쳤다.
- `store.py`: `pull_writing_participation` / `upload_writing_participation`(clear + 전체 업로드.
  기존 행을 갱신하는 테이블이라 append 큐가 맞지 않음) / `writing_participation_dirty` 플래그를
  `upload_queue` 가 20초마다 flush. 실패 시 플래그 되살려 재시도.
- `store.restore_missing_tables()`: **없거나 0바이트인 테이블만** 시트에서 복원. 파일이 있으면
  절대 덮어쓰지 않는다 (무조건 `pull_all` 은 최근 쓰기를 되감아 유실을 만듦). startup 에서 호출,
  실패해도 봇은 뜨고 관리자에게 알린다.
- `keepalive.py`: `ping_self()` 5분마다 `KOYEB_URL` GET. sigongbot-mini 에서 검증된 패턴. 예외 안 냄.

TDD: 신규 17종 (store 10 · keepalive 4 · client 2 · 이벤트 1). RED 확인 후 구현. 전체 277 passed.

## 남는 한계 (정직하게)

- 재시작 직전 **20초 안의 쓰기**는 큐가 메모리라 어디에도 못 도착한다. 기존 특성이며 이번 범위 밖.
- `_checked_notice` 등은 사용자 결정으로 동기화하지 않는다. 디스크 초기화 시 공지 확인 포인트가 중복될 수 있다.

## 사용자 검증 방법

1. **정상**: 슬랙에서 글쓰기 참여 신청 → 20초 내 시트 `writing_participation` 탭에 행이 생김.
   탭이 없었다면 부팅 로그에 "시트 탭 생성: writing_participation".
2. **복원**: `store/writing_participation.csv` 삭제 후 재시작 → 파일이 시트 내용으로 복원되고
   로그에 "시트에서 복원한 테이블: ['writing_participation']".
3. **무손상**: 파일이 있는 채로 재시작 → 복원 로그 없음, 파일 그대로.
4. **self-ping**: `KOYEB_URL` 설정 시 5분마다 "self-ping 성공: 200". 미설정 시 부팅 때 경고 1회.
5. 20초 유실 창은 재현이 어렵다. 위 한계 항목으로 갈음.

| 날짜 | 내용 |
| --- | --- |
| 2026-09-07 | writing_participation 시트 동기화 · restore_missing_tables · self-ping 추가 |
