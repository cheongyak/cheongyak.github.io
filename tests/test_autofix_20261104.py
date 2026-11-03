"""2026-11-04 아침 자동 고치기: 광교 자연앤 센트레빌 A17BL (2026000527 지분적립형 · 2026000528 공공분양).
① '■ 공급신청 자격자 성년자인 무주택세대구성원 : 주택공급 신청은 무주택세대구성원 중 • 인만 1 가능합니다' (콜론 위치·'1인만' 뒤섞임) → 세대주 요건 false
② 527 <표5> 일반공급 소득(금액 사이 '원' 없이 붙음)·<표2> 총자산 362백만원·<표3> 출산가구 397,000·431,000천원 → pub_limits kind total.
정답 tests/golden/notices.json 2026000527·2026000528."""
import json
import re
from pathlib import Path

from app import notice_pdf as N

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _t(no):
    return (ROOT / f"evidence/notices/{no}.txt").read_text(encoding="utf-8")


def test_golden_gwanggyo_need_head_and_equity_limits():
    for no in ("2026000527", "2026000528"):
        o = N.parse_notice(_t(no))
        assert o["need_head"] is GOLD[no]["fields"]["need_head"] is False, no
        assert "공급신청 자격자" in o["quotes"]["need_head"], no
    assert N.parse_pub_limits(_t("2026000527")) == GOLD["2026000527"]["fields"]["pub_limits"]
    assert N.parse_pub_limits(_t("2026000528")) is None   # 공공분양 84㎡ 공고는 이 표가 없다


def test_need_head_scrambled_lh_form():
    s = "■적용대상다자녀가구특별공급및일반공급신청자:·····■공급신청자격자성년자인무주택세대구성원:주택공급신청은무주택세대구성원중•인만1가능합니다."
    r = N.need_head_general(s)
    assert r and r[0] is False
    assert N.need_head_general(s.replace("성년자인무주택세대구성원:", "성년자인무주택세대주:")) is None   # 다른 대상이면 읽지 않음


def test_equity_limits_reject_wrong_amounts():
    t = _t("2026000527")
    # 한 칸 금액이 % 계산과 다르면(옮겨 적기 실수) 읽지 않는다
    bad = t.replace("15,067,526 17,604,404 18,653,970 19,812,526 20,971, 082 22,129,638", "15,067,526 17,604,404 18,653,970 19,812,526 20,917, 082 22,129,638")
    assert bad != t
    assert N._parse_equity_total_limits(bad) is None
    # 칸이 하나 빠져도 읽지 않는다
    f = re.sub(r"\s+", "", t)
    i = f.find("추첨공급(20%)", f.find("일반공급신생아우선공급(50%)"))
    assert f[i:i + 60].count("7,533,7638,802,202") == 1
    assert N._parse_equity_total_limits(f[:i] + f[i:i + 60].replace("7,533,7638,802,202", "7,533,763") + f[i + 60:]) is None
    # 지분적립형이 아닌 공고문은 건드리지 않는다
    assert N._parse_equity_total_limits(t.replace("지분적립형", "공공분양")) is None
