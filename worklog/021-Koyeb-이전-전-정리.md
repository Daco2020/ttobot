# 021 - Koyeb 이전 전 정리 (KST · 북마크 user_id · 공지 중복판정 · 인프런 제거 · 복원 fail-closed)

## 왜

020 교차검증(서브에이전트 3종)이 낸 결정 사항 5개를 사용자가 확정했다 (2026-09-08).
모두 Koyeb(UTC 컨테이너 · 디스크 초기화 · 롤링 배포) 환경에서 드러나는 것들이다.

## 1. KST 명시 (`ts_to_dt`)

- 문제: `datetime.fromtimestamp(ts)` 가 naive 라 프로세스 TZ 를 따른다. 옛 서버는 KST, Koyeb 는 UTC
  → 00~09시 KST 이벤트의 BigQuery `tddate` 가 하루 어긋나고 커피챗 인증 날짜 표시도 어긋난다.
- 해결: `utils.ts_to_dt` 가 명시적 KST 로 계산한 뒤 tzinfo 를 떼어 **KST 벽시계 naive** 를 돌려준다.
  옛 서버 출력과 같은 값·같은 타입(BigQuery DATETIME/DATE). `log.py` 의 6곳이 이걸 쓴다.
  3일/1일 창 비교(`log.py:86,125`)는 양변이 같은 TZ 라 결과가 TZ 와 무관하므로 그대로 둔다.
- TDD: 개발 Mac 이 KST 라 옛 코드로도 통과하므로 프로세스 TZ 를 UTC 로 강제해 검증. 5종.

## 2. `update_bookmark` 가 user_id 를 무시

- 문제: `content_ts` 만으로 갱신해 같은 글을 북마크한 **다른 사용자** 북마크까지 DELETED. 시트는
  (user_id, content_ts) 로 갱신하므로 로컬과도 어긋났다 (기존 데이터 버그).
- 해결: `user_id AND content_ts` 로만 갱신. 서비스가 user_id 를 넘긴다. 저장소 4종 + 연결 1종.

## 3. 복원 실패 시 fail-closed (`__init__.py` startup)

- 문제: 019 는 복원 실패를 삼키고 봇을 띄웠다. Koyeb 는 새 배포가 healthy 면 옛 배포를 죽이므로,
  데이터 없는 봇이 healthy 로 뜨면 정상이던 옛 배포가 사라진다.
- 해결: 관리자 알림 뒤 `raise`. unhealthy → 옛 배포 유지, Koyeb 재시작 3회. 트레이드오프: 옛 배포가
  없는 주간 재배치에서 시트 API 장애면 재시작 3회 뒤 멈추고 사람이 redeploy 해야 한다(외부 핑이 잡음).
  fail-open 이어도 그 봇은 모든 핸들러가 FileNotFoundError 라 사실상 죽은 것과 같았다.
- 테스트: prod 전용 블록이라 단위 테스트 대신 `ENV=prod` 임포트 스모크로 배선을 확인했다.

## 5. 인프런 쿠폰 기능 제거

- 문제: `_inflearn_coupon.csv` 는 어디에도 없고 쿠폰은 2025-03-30 만료. Koyeb 에선 종이비행기를
  보낼 때마다 관리자 알림 1건 + `/v1/inflearn/coupons` 500.
- 해결: 라우터·핸들러 분기·헬퍼·타입 제거. 종이비행기 전송은 DM 2건으로 끝난다. 제거 테스트 2종.

## 사용자 검증 방법

1. **KST**: BigQuery `comments_log.tddate` 가 KST 자정 직후(00~09시) 댓글에서 당일 날짜인지.
   커피챗 인증 내역 모달의 날짜.
2. **북마크**: 두 계정이 같은 글을 북마크 → 한 계정이 취소 → 다른 계정 목록에 그대로 남는지.
3. **공지**: 공지에 noti-check → 포인트 1회 → 지우고 다시 달기 → 지급 없음 → **재배포 뒤** 다시 달기 → 지급 없음.
4. **인프런**: 종이비행기 보내기 → 관리자 채널에 쿠폰 알림이 없고 DM 2건.
5. **fail-closed**(선택): 시트 권한을 잠깐 뺀 뒤 redeploy → 배포 unhealthy + 관리자 알림, 옛 배포 유지.

| 날짜 | 내용 |
| --- | --- |
| 2026-09-08 | KST 명시 · 북마크 user_id · 복원 fail-closed · 공지 중복판정 · 인프런 제거 |
