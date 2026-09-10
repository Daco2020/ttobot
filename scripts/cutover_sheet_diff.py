"""컷오버 전 검증: 로컬 store/*.csv 의 행이 시트에 전부 있는지 키 기준으로 비교한다.

옛 서버(옛 코드)에서도 실행된다. get_values / bulk_upload 만 쓴다.
1회성 운영 도구라 테스트는 없다. app 을 import 하므로 .env 와 시트 접근이 필요하다.

    uv run python scripts/cutover_sheet_diff.py            # 보고만. 빠진 행 있으면 exit 1
    uv run python scripts/cutover_sheet_diff.py --upload   # 빠진 행만 1회 append (전체 재업로드 금지)
"""

import csv
import sys
from pathlib import Path

# `uv run python scripts/x.py` 로 실행하면 sys.path[0] 이 scripts/ 라 app 을 못 찾는다
# (pyproject package = false 라 프로젝트가 설치돼 있지 않음). 프로젝트 루트를 넣어 준다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.client import SpreadSheetClient  # noqa: E402

# 테이블별 행 식별 키. 갱신 테이블(bookmark 등)은 값 변경까지는 비교하지 않는다.
KEYS = {
    "contents": ["ts"],
    "bookmark": ["user_id", "content_ts"],
    "coffee_chat_proof": ["ts"],
    "point_histories": ["id"],
    "paper_plane": ["id"],
    "subscriptions": ["id"],
}


def main(upload: bool) -> int:
    client = SpreadSheetClient()
    total_missing = 0
    for table, key_cols in KEYS.items():
        with open(f"store/{table}.csv", encoding="utf-8") as f:
            local = list(csv.DictReader(f))
        header, *rows = client.get_values(table)
        idx = [header.index(k) for k in key_cols]
        sheet_keys = {tuple(r[i] if i < len(r) else "" for i in idx) for r in rows}
        missing = [r for r in local if tuple(r[k] for k in key_cols) not in sheet_keys]
        print(
            f"{table:18s} local={len(local):6d} sheet={len(rows):6d} "
            f"missing_in_sheet={len(missing)}"
        )
        for r in missing[:5]:
            print("    ", {k: r[k] for k in key_cols})
        total_missing += len(missing)
        if upload and missing:
            client.bulk_upload(table, [[r.get(h, "") for h in header] for r in missing])
            print(f"     -> {len(missing)}행 append 완료. 다시 실행해 0 을 확인할 것")
    return 1 if total_missing and not upload else 0


if __name__ == "__main__":
    sys.exit(main("--upload" in sys.argv))
