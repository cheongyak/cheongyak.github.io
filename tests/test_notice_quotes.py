"""값마다 근거 원문 문장 (기능 notice_quotes, 2026-10-02 미뤄둔 일 9번).
공고문에서 읽은 값에는 그 값을 읽은 원문 문장이 붙어야 하고, 그 문장에 실제로 그 값이 들어 있어야 한다 (엉뚱한 문장을 근거로 보이지 않게)."""
import json
import re
from pathlib import Path

from app import notice_pdf, pipeline

ROOT = Path(__file__).resolve().parents[1]
NOTICES = sorted((ROOT / "evidence" / "notices").glob("*.txt"))


def _has_value(k, v, q):
    f = re.sub(r"\s+", "", q)
    if k == "need_head":
        return ("세대주" in f) if v else ("세대구성원" in f or "세대주요건" in f)   # 민영 신청자격 표 '세대주 요건 - - …' (2026-10-09)
    if k == "price_cap":
        return "분양가상한제" in f
    if k == "residence_duty":
        return "거주의무" in f and (str(v) in f if v else ("없음" in f or "미적용" in f))
    if k == "rewin_years":
        return "재당첨" in f and (str(v) in f if v else "않" in f)
    if k == "account_months":
        return str(v) in f or (v % 12 == 0 and f"{v // 12}년" in f)
    if k == "deposit_count":
        return f"{v}회" in f
    if k == "balance":
        y, m, d = v.split("-")
        return y in f and str(int(d)) in f
    if k == "residence":   # 해당지역 이름(또는 전국·지역 목록)이 문장에 있어야 (2026-10-09)
        a = v.get("area") or {}
        names = [a.get("sigungu"), a.get("name"), a.get("sido")] + list(v.get("others") or [])
        return any(n and n.replace(" ", "") in f for n in names) or "전국" in f or "국내" in f
    if k == "duty_from":
        return v.replace("-", ".")[:7] in f
    return True


def test_every_read_value_has_a_quote_containing_it():
    assert len(NOTICES) >= 30
    n = 0
    for p in NOTICES:
        out = notice_pdf.parse_notice(p.read_text(encoding="utf-8"))
        qs = out.get("quotes", {})
        for k in pipeline.QUOTE_LABELS:
            if k in out:
                assert k in qs, f"{p.name} {k}={out[k]!r} 근거 문장 없음"
                assert _has_value(k, out[k], qs[k]), f"{p.name} {k}={out[k]!r} 문장에 값이 없음: {qs[k]}"
                assert len(qs[k]) <= 175, (p.name, k, len(qs[k]))
                n += 1
        assert set(qs) <= set(out), f"{p.name} 읽지 않은 값의 문장이 남음"
    assert n > 200


def test_golden_quote_cheolsan_duty_sentence():
    # 2026910236 철산자이 더 헤리티지 무순위 공고문: '본 아파트의 거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용됩니다'
    out = notice_pdf.parse_notice((ROOT / "evidence" / "notices" / "2026910236.txt").read_text(encoding="utf-8"))
    assert out["residence_duty"] == 2
    assert "거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용됩니다" in out["quotes"]["residence_duty"]
    assert "2025.05.30" in out["quotes"]["duty_from"]


def test_quote_maps_flat_match_back_to_original_spacing():
    text = "안내\n■ 입주지정기간 : 2026년 9월 7일 ~ 2026년 11월 30일 (예정)\n끝"
    out = notice_pdf.parse_notice(text)
    assert out["balance"] == "2026-11-30"
    assert "입주지정기간 : 2026년 9월 7일 ~ 2026년 11월 30일" in out["quotes"]["balance"]


def test_merge_alt_takes_quote_with_value():
    found, alt = {}, {"rewin_years": 10, "quotes": {"rewin_years": "재당첨제한 10년"}}
    notice_pdf.merge_alt(found, alt)
    assert found["rewin_years"] == 10 and found["quotes"]["rewin_years"] == "재당첨제한 10년"


def test_previous_run_quotes_are_restored():
    prev = {"from_notice": ["실거주 의무"], "residence_duty": 3, "notice_quotes": {"실거주 의무": "거주의무 3년"}}
    found, _ = pipeline._from_previous(prev)
    assert found["quotes"] == {"residence_duty": "거주의무 3년"}
