"""판정 엔진이 웹 프로토타입과 같은 숫자를 내는지 확인 (강변역 센트럴 아이파크 실제 공고 기준)."""
from app.engine import eligibility, funding, grade, jeonse_check, judge
from app.models import Listing, PlanOptions, Profile

GANGBYEON = Listing(
    id="2026930040-084.9811C", name="강변역 센트럴 아이파크", address="서울특별시 광진구 구의동 592-39번지 일원",
    region="서울", sigungu="광진구", kind="불법행위 재공급", category="remainder", unit="84C", area=84.98,
    notice="2026-09-23", apply="2026-10-06", contract="2026-10-23", balance="2026-11-30",
    price=12.2202, ext=0.2178, mkt_low=20, mkt_base=22, jeonse=7,
    capital=True, regulated=True, land_permit=True, price_cap=False, residence_duty=0,
    need_head=True, need_account=False,
)
# 대화에서 알려주신 조건
ME = Profile(seoul=True, household="parents", parents60=True, parentsOwn=True, married=False,
             cash=32500, income=4000)


def test_grade_is_lotto():
    g = grade(GANGBYEON)
    assert g["grade"] == "lotto"
    assert round(g["cost"], 2) == 12.85
    assert round(g["lo"], 2) == 7.15 and round(g["hi"], 2) == 9.15


def test_not_eligible_because_not_head():
    e = eligibility(GANGBYEON, ME)
    assert not e["ok"]
    assert "세대주" in e["reason"]
    assert "60세" in e["fix"]
    homeless = next(i for i in e["items"] if i["k"] == "무주택 세대")
    assert homeless["s"] == "ok"   # 60세 이상 부모 주택 예외


def test_head_after_notice_date_fails():
    p = ME.model_copy(update={"household": "head", "headSince": "2026-09-25"})
    assert not eligibility(GANGBYEON, p)["ok"]
    p2 = ME.model_copy(update={"household": "head", "headSince": "2026-09-01"})
    assert eligibility(GANGBYEON, p2)["ok"]


def test_funding_matches_prototype():
    f = funding(GANGBYEON, ME, PlanOptions(mode="jeonse"))
    assert f["loan"]["limit_by"] == "DSR(소득)"
    assert round(f["loan"]["loan"], 1) == 2.0
    assert round(f["gap_jeonse"], 1) == 2.6
    assert round(f["gap_live"], 1) == 7.6
    assert f["contract_ok"]


def test_jeonse_rules_by_region():
    assert jeonse_check(GANGBYEON)["status"] == "cond"
    duty = GANGBYEON.model_copy(update={"residence_duty": 3, "price_cap": True})
    assert any("실거주 의무 3년" in r["t"] for r in jeonse_check(duty)["reasons"])
    local = GANGBYEON.model_copy(update={"region": "지방", "capital": False, "regulated": False, "land_permit": False})
    assert jeonse_check(local)["status"] == "ok"
    f = funding(local, ME)
    assert f["loan"]["ltv_rate"] == 0.7 and f["loan"]["cap"] is None


def test_regulated_loan_cap_by_price():
    rich = ME.model_copy(update={"income": 50000})
    f = funding(GANGBYEON, rich)
    assert f["loan"]["loan"] == 4.0 and f["loan"]["limit_by"] == "한도 4억"


def test_unknown_market():
    L = GANGBYEON.model_copy(update={"mkt_low": None, "mkt_base": None})
    assert grade(L)["grade"] == "unknown"
    assert judge(L, ME)["verdict"] == "신청 불가"


def test_grade_skip_name(tmp_path, monkeypatch):
    """스위치 grade_skip: '패스' 등급 이름만 '스킵'으로, 끄면 '패스' (등급 기준은 그대로)"""
    from app import engine as E
    cfg = tmp_path / "config.json"
    cfg.write_text('{"features": {"grade_skip": true}}', encoding="utf-8")
    monkeypatch.setattr(E, "CONFIG_PATH", cfg)
    assert E.grade_name("pass") == "스킵" and E.grade_name("lotto") == "로또"
    cfg.write_text('{"features": {"grade_skip": false}}', encoding="utf-8")
    assert E.grade_name("pass") == "패스"
