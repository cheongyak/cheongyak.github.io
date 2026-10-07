"""분양대금 비율 독립 점검 (기능 contract_from_notice, 2026-10-08 사용자 '앞으로 이런 실수 없도록 대책').

공고문 읽기(app/notice_pdf.pay_terms)와 따로 만든 계산 — 표 머리 글자는 보지 않고, 공고문 전체의 '집값 크기 금액 줄'만으로 계약금 % 를 거꾸로 구한다:
  금액이 셋 이어진 곳 (T, a, b) 에서 T ≥ 5천만 원이고 a / T 가 5·10·15·20·30% 중 하나(만 원 절사 허용)면 그 % 의 줄,
  a < T × p 이고 (a + b) / T 가 그 % 면 '1차 + 2차로 나눈' 줄.
읽은 비율과 비교해 아래를 찾는다:
  misread  — 읽은 계약금 % 를 뒷받침하는 줄이 하나도 없음 (머리 글자만 보고 읽었을 때 생기는 실수 — 실패로 셈)
  dominant — 다른 % 의 줄이 읽은 % 의 줄보다 3배 넘게 많음 (다른 표를 읽었을 가능성 — 실패로 셈)
  missed   — 읽지 못했는데 줄들이 한 가지 % 를 강하게 보여 줌 (읽기 규칙을 넓힐 후보 — 참고만)
대상: evidence/notices·evidence/qa/notices 의 공고문 원문. 결과: evidence/qa/pay-audit.json, verify-status qa.pay_audit_bad (실패 수).
실행: python -m tools.qa.pay_audit"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "pay-audit.json"
AMT = r"\d{1,3}(?:,\d{3})+"
RATES = (5, 10, 15, 20, 30)


def originals() -> dict[str, Path]:
    out = {}
    for d in (ROOT / "evidence" / "qa" / "notices", ROOT / "evidence" / "notices"):
        if d.exists():
            for f in sorted(d.glob("*.txt")):
                out[f.stem] = f
    return out


def row_rates(text: str) -> Counter:
    """공고문 전체 금액 줄에서 계약금 % 별 줄 수 (단위: 원·천원·만원 셋 다 시도 — 표마다 단위가 달라 셋 중 집값 크기가 되는 것만)"""
    t = re.sub(r"[ \t]+", " ", text)
    cnt: Counter = Counter()
    for r in re.finditer(r"(?<![\d,])(?=(" + AMT + r")\s+(" + AMT + r")\s+(" + AMT + r"))", t):
        T0, a0, b0 = (int(x.replace(",", "")) for x in r.groups())
        for unit in ((1,) if T0 >= 1_000_000 else (1000, 10000)):   # 천원·만원 단위 표의 집값은 여섯 자리 이하(409,523 천원) — 원 단위 옵션 금액(5,160,000)을 천 배로 보지 않게
            T, a, b = T0 * unit, a0 * unit, b0 * unit
            if not (50_000_000 <= T <= 20_000_000_000) or b >= T:   # 낼 돈 다음 칸은 집값보다 작다 — 건축비·부가세(10%)·합계 줄(b = 합계 > T)을 계약금 10% 로 세지 않게
                continue
            for p in RATES:
                want = T * p / 100
                if abs(a - want) <= max(10_000, unit):
                    cnt[p] += 1
                    break
                if 0 < a < want * 0.9 and abs(a + b - want) <= max(10_000, unit):
                    cnt[p] += 1
                    break
            else:
                continue
            break
    return cnt


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from app.notice_pdf import parse_notice
    items, bad = [], 0
    for n, f in originals().items():
        text = f.read_text(encoding="utf-8", errors="replace")
        r = parse_notice(text)
        pr = r.get("pay_ratio")
        rr = row_rates(text)
        top = rr.most_common(1)[0] if rr else (None, 0)
        it = {"id": n, "read": pr and round(pr["contract"] * 100), "mid": pr and round(pr["mid"] * 100), "rows": dict(rr), "flag": None}
        if pr:
            c = round(pr["contract"] * 100)
            if rr.get(c, 0) == 0:
                it["flag"] = "misread"
            elif top[0] != c and top[1] > 3 * rr.get(c, 0):
                it["flag"] = "dominant"
        elif top[1] >= 5 and (len(rr) == 1 or top[1] > 3 * sorted(rr.values())[-2]):
            it["flag"] = "missed"
        if it["flag"] in ("misread", "dominant"):
            bad += 1
        items.append(it)
    res = {"date": date.today().isoformat(), "notices": len(items), "read": sum(1 for x in items if x["read"]),
           "bad": bad, "flags": {k: [x["id"] for x in items if x["flag"] == k] for k in ("misread", "dominant", "missed")}, "items": items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[QA 계약금 비율] 공고문 {res['notices']}건 · 읽음 {res['read']} · 표 줄과 안 맞음 {bad}건"
          + (f" ({', '.join(res['flags']['misread'] + res['flags']['dominant'])})" if bad else "")
          + f" · 못 읽었지만 줄은 한 가지 %(참고) {len(res['flags']['missed'])}건")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
