"""임대 공고 '공고문에서 못 읽음' 전수검사 (2026-10-20 사용자 '임대공고에도 공고문에서 못읽는것들이 잇네 … 다시는 안뜨도록 전수검사해').
값은 evidence/lh·evidence/sh 공고문 원문을 직접 읽고 확인한 것 (WORK.md 2026-10-20 11:52 항목).
매 수집 전수검사는 tools/qa/lh_unread.cjs (화면 판정에서 '읽지 못함' 항목 → 허용 목록 밖이면 검증 실패)."""
import json
import re
from pathlib import Path

from app.lh_terms import parse_lh_terms
from app.sh_terms import parse_social

ROOT = Path(__file__).resolve().parents[1]


def _lh(nid, kind, name="", region=None):
    return parse_lh_terms((ROOT / "evidence/lh" / f"{nid}.txt").read_text(encoding="utf-8", errors="replace"), kind, name, region)


def _g(T):
    return {g["key"]: g for g in T["groups"]}


def test_local_with_resident_registration_and_sido_prefix():
    # 홍성 903 '현재 주민등록상 홍성군에 거주하는 성년자인 무주택세대구성원' · 아산읍내 868 '현재 충남 아산시에 거주하는 성년자인'
    T = _lh("2015122300020903", "영구임대", "", "충청남도")
    assert {k: T["local"][k] for k in ("name", "sido", "sigun")} == {"name": "홍성군", "sido": "충남", "sigun": "홍성군"} and not T.get("local_unread")
    T = _lh("2015122300020868", "영구임대", "", "충청남도")
    assert {k: T["local"][k] for k in ("name", "sido", "sigun")} == {"name": "아산시", "sido": "충남", "sigun": "아산시"} and not T.get("local_unread")
    # 앞머리 시·도가 공고 시·도와 다르면 추측하지 않는다
    from app.lh_terms import parse_local
    assert parse_local("신청자격 입주자 모집공고일(2026.10.06.) 현재 충남 아산시에 거주하는 성년자인 무주택세대구성원", "경기도") is None


def test_public_rental_construction_area_is_not_unread():
    # 음성금왕1 879 '주택건설지역(음성군 또는 충청북도)에 거주하는 무주택세대구성원' → 신청 가능 거주지역 충북으로 이미 읽음
    T = _lh("2015122300020879", "공공임대", "", "충청북도")
    assert T["regions"] == ["충북"] and not T.get("local_unread")


def test_relaxed_happy_income_uses_rank3_cap():
    # 광주우산 887: '100%이하 (【완화조건】 120%이하 (2순위), 150%이하 (3순위))', 1인 120%(140·150), 2인 110%(130·150), 맞벌이 120%(130·150)
    G = _g(_lh("2015122300020887", "행복주택", "입주자격완화"))
    assert G["청년"]["income_pct"] == {"1": 150, "2": 150, "3+": 150}
    assert G["고령자"]["income_pct"] == {"1": 150, "2": 150, "3+": 150}
    assert G["신혼부부·한부모"]["income_pct"] == {"1": None, "2": 150, "3+": 150} and G["신혼부부·한부모"]["dual_add"] == 0
    # 의령동동 910: 대학생 문장은 일반조건만, 금액표에 3순위 칸(1인 5,720,045 · 2인 8,799,405 · 3인 12,252,644 = 150%)
    G = _g(_lh("2015122300020910", "행복주택", "정례"))
    assert G["대학생"]["income_pct"] == {"1": 150, "2": 150, "3+": 150}
    assert G["청년"]["income_pct"] == {"1": 150, "2": 150, "3+": 150}
    # 고령자 '자동차가액이 45,420만원 이하'(오기) — 같은 절 가산 표 '0인 … 345,000,000원 45,420,000원'으로 4,542만원
    assert G["고령자"]["car_manwon"] == 4542 and G["고령자"]["asset_manwon"] == 34500


def test_relaxed_global_table_and_asset_wording():
    # 천안·아산 888 '① 소득기준 소득기준 적용배제 ② 총자산 기준 자산기준 적용배제 ③ 자동차 기준 4,542만원 이하'
    G = _g(_lh("2015122300020888", "행복주택", "자격완화"))
    for k in ("청년", "신혼부부·한부모", "고령자"):
        assert (G[k]["income_pct"], G[k]["asset_manwon"], G[k]["car_manwon"]) == ("excluded", "excluded", 4542), k
    assert (G["대학생"]["income_pct"], G["대학생"]["asset_manwon"], G["대학생"]["car_manwon"]) == ("excluded", "excluded", 0)
    # 양산 909 '총 자산요건을 배제하나, … 자동차가액이 4,542만원 이하' · 대학생 '총자산 요건은 배제하나, 신청자 본인이 … 자동자를 소유하고 있지 않을 것'
    G = _g(_lh("2015122300020909", "행복주택", "입주자격완화"))
    assert (G["청년"]["asset_manwon"], G["청년"]["car_manwon"]) == ("excluded", 4542)
    assert (G["대학생"]["asset_manwon"], G["대학생"]["car_manwon"]) == ("excluded", 0)


def test_youth_section_not_startup_section():
    # 광주첨단 919: '3-1. 청년 창업인'(총자산 34,500만원)과 '3-3. 청년 계층'(25,100만원)이 따로 — 청년은 청년 계층 절, 창업인은 판정 안 하는 계층
    T = _lh("2015122300020919", "행복주택")
    G = _g(T)
    assert G["청년"]["asset_manwon"] == 25100 and "청년 창업인" in T["unknown_groups"]
    # 신혼부부 '월평 균소득의 100퍼센트 이하(맞벌이 부부 120퍼센트 이하) … 2인인 경우에는 110퍼센트' (PDF 글 띄어쓰기)
    assert G["신혼부부·한부모"]["income_pct"] == {"1": None, "2": 110, "3+": 100} and G["신혼부부·한부모"]["dual_add"] == 20


def test_sh_social_unclear_homeless_and_asset_typo():
    # 유니버설디자인하우스_장안 311375 '서울시에 거주하는 무주택자로서' · 청년 '2억5,4000만 원 이하'(오기)
    T = parse_social((ROOT / "evidence/sh/311375.txt").read_text(encoding="utf-8"))
    assert {g["key"]: g["homeless"] for g in T["groups"]} == {"청년": "self_unclear", "신혼부부": "self_unclear", "1인가구": "self_unclear"}
    y = _g(T)["청년"]
    assert y["asset_manwon"] is None and y["asset_typo"] == "2억5,4000만 원"
    assert "무주택 범위(본인·세대) 못 읽음" not in T["issues"]


def test_screen_self_unclear_rule_present():
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "'self_unclear'" in html and "asset_typo" in html


def test_unread_sweep_wired_into_verify():
    wf = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
    assert "tools/qa/lh_unread.cjs" in wf
    assert "lh_unread" in (ROOT / "tools/verify_status.py").read_text(encoding="utf-8")
    allow = json.loads((ROOT / "tools/qa/lh_unread_allow.json").read_text(encoding="utf-8"))
    assert all(re.search(r"원문 확인", v) for v in allow.values())   # 허용은 원문을 읽고 이유를 적은 것만


def test_stale_unread_result_not_counted(tmp_path, monkeypatch):
    """2026-10-21: 전날 LH 수집 때의 전수검사 결과(그 뒤 SH 를 다시 수집해 이미 고쳐짐)를 아침 수집의 검증 요약이 그대로 세어 '베타 참고용'(검증 실패)이 떴다.
    결과에 검사한 데이터 시각(data)을 남기고, 지금 데이터와 다르면 세지 않는다. 수집·검증·SH 수집 모두 요약 전에 지금 데이터로 다시 돌린다."""
    import tools.verify_status as vs
    now = vs.lhu_data_now()
    assert set(now) == {"lh", "sh"}
    src = (ROOT / "tools/verify_status.py").read_text(encoding="utf-8")
    assert 'lhu.get("data") != lhu_data_now()' in src
    for wf in ("collect.yml", "verify.yml", "sh-rental.yml", "lh-rental.yml"):
        t = (ROOT / ".github/workflows" / wf).read_text(encoding="utf-8")
        assert "tools/qa/lh_unread.cjs" in t and "evidence/qa/lh-unread.json" in t, wf
    assert "const data = { lh: stamp('lh-rental.json'), sh: stamp('sh-rental.json') }" in (ROOT / "tools/qa/lh_unread.cjs").read_text(encoding="utf-8")
