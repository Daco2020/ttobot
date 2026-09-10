"""옛 서버의 store/writing_participation.csv 로 시트 writing_participation 탭을 시드한다.

새 인스턴스의 **첫 부팅 전에** 로컬(HEAD 코드, 운영 시트 .env)에서 1회 실행한다.
옛 코드는 이 파일을 시트에 올린 적이 없고, 새 코드는 첫 부팅에서 빈 탭을 만들어 그대로 복원한다.
1회성 운영 도구라 테스트는 없다.

    uv run python scripts/seed_writing_participation.py /path/to/old/writing_participation.csv
"""

import csv
import shutil
import sys
from pathlib import Path

# `uv run python scripts/x.py` 로 실행하면 sys.path[0] 이 scripts/ 라 app 을 못 찾는다
# (pyproject package = false 라 프로젝트가 설치돼 있지 않음). 프로젝트 루트를 넣어 준다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.client import WRITING_PARTICIPATION_HEADER, SpreadSheetClient  # noqa: E402
from app.store import Store  # noqa: E402


def main(src: str) -> int:
    dst = Path("store/writing_participation.csv")
    if dst.exists():
        shutil.copy(dst, dst.with_suffix(".csv.bak"))
    shutil.copy(src, dst)

    with dst.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f, quoting=csv.QUOTE_ALL))
    assert rows and rows[0] == WRITING_PARTICIPATION_HEADER, f"헤더 불일치: {rows[:1]}"
    flags = {r[3] for r in rows[1:] if len(r) > 3}
    # 시트에서 복사한 값은 불리언 TRUE 가 되어 코드가 미신청으로 본다. 문자열 "True" 만 허용.
    assert flags <= {"True", "False"}, f"is_writing_participation 값 이상: {flags}"

    client = SpreadSheetClient()  # 탭이 없으면 헤더만 있는 탭을 만든다
    Store(
        client=client
    ).upload_writing_participation()  # 시트와 합집합 → resize + update
    back = client.get_values("writing_participation")
    print(f"seeded: local={len(rows) - 1} sheet={len(back) - 1} flags={sorted(flags)}")
    return 0 if len(back) >= len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
