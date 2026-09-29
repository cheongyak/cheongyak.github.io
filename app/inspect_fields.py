"""처음 키를 연결할 때 한 번 돌려서 실제 응답 필드명을 확인하는 스크립트.

    python -m app.inspect_fields

각 API 에서 1건씩 받아 키 목록을 출력하고, 코드가 기대하는 필드가 있는지 표시한다.
'없음' 이 뜨면 app/sources/applyhome.py 의 FIELD 후보에 실제 키를 추가한다.
"""
from __future__ import annotations

from datetime import date

from .sources.applyhome import ENDPOINTS, FIELD, ApplyhomeClient
from .sources.rtms import RtmsClient
from .market import months_back

EXPECT_DETAIL = ["notice_no", "name", "address", "kind", "notice", "apply", "apply_end", "winner", "contract",
                 "url", "speculative", "adjusted", "price_cap"]
EXPECT_MODEL = ["house_ty", "price", "households"]


def show(title: str, raw: dict, expect: list[str]):
    print(f"\n== {title} ==")
    print("키:", ", ".join(sorted(raw.keys())))
    for k in expect:
        hit = next((c for c in FIELD[k] if c in raw), None)
        print(f"  {k:<12} {'→ ' + hit if hit else '없음 (후보: ' + ', '.join(FIELD[k]) + ')'}")


def main():
    ah = ApplyhomeClient()
    for cat, (dpath, _) in ENDPOINTS.items():
        rows = ah._get(dpath, perPage=1).get("data", [])
        if not rows:
            print(f"\n== {cat}: 데이터 없음 ==")
            continue
        show(f"{cat} 공고 개요", rows[0], EXPECT_DETAIL)
        no = rows[0].get("PBLANC_NO")
        if no:
            ms = ah.models(cat, str(no))
            if ms:
                show(f"{cat} 주택형", ms[0], EXPECT_MODEL)
    rt = RtmsClient()
    ym = months_back(date.today(), 2)[1]
    for kind in ("trade", "presale", "rent"):
        try:
            rows = rt.fetch(kind, "11215", ym)  # 광진구
        except Exception as e:
            print(f"\n== 실거래 {kind}: 실패 → {e}")
            continue
        print(f"\n== 실거래 {kind} (광진구 {ym}) : {len(rows)}건 ==")
        if rows:
            print(" 예:", rows[0])


if __name__ == "__main__":
    main()
