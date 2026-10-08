"""재공급 공고 자동 검증·특공 세대수 읽기 (2026-10-08 사용자 제보: 세종 리더스포레 나릿재마을 1단지 2026930041 84D
'데이터 확인 필요 2건(근거 거래 2건뿐·마진율 107%)'·'재공급 일반 몫 0세대'인데 특별공급 1세대(다자녀)가 안 보임)."""
import json
from datetime import date
from pathlib import Path

from app import validate
from app.models import Listing
from app.notice_pdf import parse_notice

ROOT = Path(__file__).resolve().parents[1]
D = date(2026, 10, 8)
COMPS2 = [{"apt": "나릿재마을1단지", "area": 84.96, "amount": 7.9, "date": "2026-08-05", "kind": "매매"},
          {"apt": "나릿재마을1단지", "area": 84.93, "amount": 8.57, "date": "2026-07-06", "kind": "매매"}]


def L(**kw):
    base = dict(id="2026930041-084.9649D", name="세종 리더스포레 나릿재마을 1단지", address="세종특별자치시 나성동 835", region="지방",
                kind="불법행위 재공급", category="remainder", unit="84D", price=3.432, mkt_low=7.41, mkt_base=8.23, mkt_basis="same_complex",
                mkt_count=2, mkt_comps=COMPS2, households=0, special_units={"multichild": 1, "total": 1}, sido="세종",
                apply="2026-10-12", notice="2026-10-07", url="https://www.applyhome.co.kr/x")
    base.update(kw)
    return Listing(**base)


def test_resupply_original_price_margin_not_flagged():
    """불법행위 재공급은 처음 분양가(2017년)로 공급해 마진율 107% 가 정상 — 같은 단지 실거래 근거면 이례적으로 보지 않음"""
    c = validate.listing_checks(L(), D)
    assert not any("마진율" in x for x in c) and not any("건뿐" in x for x in c), c


def test_margin_still_flagged_elsewhere():
    assert any("마진율" in x for x in validate.listing_checks(L(kind="무순위"), D))                         # 무순위(지금 분양가)는 100% 넘으면 이례적
    assert any("마진율" in x for x in validate.listing_checks(L(mkt_basis="district_newbuild"), D))        # 같은 단지 근거가 아니면 그대로
    assert any("마진율" in x for x in validate.listing_checks(L(mkt_low=13.5, mkt_base=14.5), D))          # 재공급이어도 250% 넘으면


def test_two_trades_need_same_complex_and_close():
    far = [dict(COMPS2[0], amount=6.0), dict(COMPS2[1], amount=8.57)]                                     # 두 거래가 15% 넘게 다르면
    assert any("2건뿐" in x for x in validate.listing_checks(L(mkt_comps=far), D))
    assert any("2건뿐" in x for x in validate.listing_checks(L(mkt_basis="district_newbuild"), D))
    assert any("1건뿐" in x for x in validate.listing_checks(L(mkt_count=1, mkt_comps=COMPS2[:1]), D))


def test_resupply_without_special_units_flagged():
    c = validate.listing_checks(L(special_units=None), D)
    assert any("재공급 물량" in x for x in c)


def test_sp_table_header_with_spaces():
    """공급대상 표 머리글이 '기관 추천 다자녀 가구 신혼 부부 노부모 부양 생애 최초 신생아 계'처럼 띄어 쓰여도 읽는다 — 원문 3건(정답: 공고문 '공급규모' 문장)"""
    gold = {"2026930041": {"084.9649D": {"multichild": 1, "total": 1}},                                       # '불법행위재공급 1세대 [특별공급 1세대(다자녀가구 1세대)]'
            "2026930033": {"106.9500A": {"elder": 1, "total": 1}, "124.0000": {"elder": 0, "total": 0}},     # '특별공급 1세대(노부모부양), 일반공급 2세대'
            "2026930034": {"084.9400A": {"first": 1, "total": 1}, "059.9800": {"first": 0, "total": 0}},    # '특별공급 1세대(생애최초), 일반공급 3세대'
            "2026930039": {"059.9901A": {"first": 2, "total": 2}, "074.8177A": {"first": 1, "total": 1}}}    # '불법행위재공급 3세대 [특별공급 3세대(생애최초 3세대)]' — 계·일반공급 칸 없는 표
    for n, want in gold.items():
        got = parse_notice((ROOT / "evidence/notices" / f"{n}.txt").read_text(encoding="utf-8"))["sp_table"]
        for ty, row in want.items():
            assert {k: v for k, v in got[ty].items() if v or k == "total"} == {k: v for k, v in row.items() if v or k == "total"}, (n, ty, got[ty])


def test_invariant_resupply_without_units():
    from tools.qa.invariants import check
    row = json.loads(L(special_units=None).model_dump_json())
    v = check([row], "2026-10-08", live=True)["violations"]
    assert "재공급 일반 0세대인데 특공 세대수 없음" in v
    ok = json.loads(L().model_dump_json())
    assert "재공급 일반 0세대인데 특공 세대수 없음" not in check([ok], "2026-10-08", live=True)["violations"]
