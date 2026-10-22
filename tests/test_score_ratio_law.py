"""가점제 비율 두 번째 근거 = 법령 (기능 score_ratio_law, 2026-10-22 '아직 남은 것' — 표 하나에서만 읽는 값).
주택공급에 관한 규칙 제28조②·④ 원문(docs/chat-law.json 제28조-2·3)으로 공고문 비율을 대조하고, 표를 못 읽었는데 법령 값이 하나로 정해지면 '법령 기준(추정)'으로 채운다.
2026-10-22 확인: 지금 민영 144개·저장소 이력 246개 주택형 모두 공고문 비율이 이 법령 규칙과 맞음(위반 0)."""
import json
import pathlib

from app.models import Listing
from app.pipeline import law_score_ratio, reg_kind, score_ratio_law
from app import validate

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_law_text_is_what_the_rule_says():
    raw = (ROOT / "docs" / "chat-law.json").read_text(encoding="utf-8")
    for s in ("투기과열지구 및 청약과열지역에서 입주자를 선정하는 경우: 40퍼센트", "투기과열지구 및 청약과열지역에서 입주자를 선정하는 경우: 70퍼센트",
              "3. 투기과열지구: 80퍼센트", "4. 청약과열지역에서 입주자를 선정하는 경우: 50퍼센트", "40퍼센트 이하의 범위에서 시장ㆍ군수ㆍ구청장이 정하여 공고하는 비율"):
        assert s in raw, s


def test_law_table():
    assert law_score_ratio(59.9, "투기과열", True) == ("exact", 40)
    assert law_score_ratio(84.9, "투기과열", True) == ("exact", 70)
    assert law_score_ratio(114.0, "투기과열", True) == ("exact", 80)
    assert law_score_ratio(114.0, "조정", False) == ("exact", 50)
    assert law_score_ratio(84.9, "비규제", False) == ("max", 40)
    assert law_score_ratio(84.9, "비규제", True) == ("max", 70)      # 수도권 공공주택지구일 수 있어 상한만
    assert law_score_ratio(114.0, "비규제", False) == ("exact", 0)
    assert law_score_ratio(114.0, "비규제", True) == ("max", 80)
    assert law_score_ratio(84.9, None, True) is None and law_score_ratio(None, "투기과열", True) is None


def test_reg_kind_does_not_guess():
    assert reg_kind({"speculative": True, "adjusted": True}) == "투기과열"
    assert reg_kind({"speculative": False, "adjusted": True}) == "조정"
    assert reg_kind({"speculative": False, "adjusted": False}) == "비규제"
    assert reg_kind({"speculative": None, "adjusted": False}) is None


def _L(area, kind, capital=True, sr=None):
    return Listing(id=f"2026000999-{area:08.4f}A", name="시험", address="경기 수원시", unit="84A", category="general", house_dtl="민영", need_account=True,
                   area=area, reg_kind=kind, capital=capital, score_ratio=sr, price=5.0, sido="경기", region="경기", kind="APT")


def test_match_mismatch_fill():
    rows = {"rows": [{"over": 60, "upto": 85, "score": 70, "lottery": 30}, {"over": 85, "upto": None, "score": 80, "lottery": 20}]}
    a = _L(84.9, "투기과열", sr=rows)
    assert score_ratio_law(a, []) == "대조 일치" and a.notice_conflicts == []
    b = _L(84.9, "조정", sr={"rows": [{"over": 60, "upto": 85, "score": 40, "lottery": 60}]})
    log = []
    assert score_ratio_law(b, log) == "대조 불일치" and "법령(조정·전용 84.9㎡) 70%" in b.notice_conflicts[0] and log
    c = _L(84.9, "비규제", capital=False, sr={"rows": [{"over": 60, "upto": 85, "score": 70, "lottery": 30}]})
    assert score_ratio_law(c, []) == "대조 불일치"                    # 비수도권 비규제는 40% 이하
    d = _L(114.0, "조정", sr={"unknown": True})
    assert score_ratio_law(d, []) == "법령으로 채움" and d.score_ratio == {"rows": [{"over": 85, "upto": None, "score": 50, "lottery": 50}], "law": True}
    from datetime import date
    assert any("법령 기준" in t and "추정" in t for t in validate.listing_checks(d, date(2026, 10, 22)))
    e = _L(84.9, "비규제", capital=True, sr={"unknown": True})
    assert score_ratio_law(e, []) is None and e.score_ratio == {"unknown": True}    # 범위만 알면 채우지 않음
    f = _L(84.9, "투기과열", sr=None)
    f.house_dtl = "국민"
    assert score_ratio_law(f, []) is None                              # 국민주택은 가점제 비율 없음
