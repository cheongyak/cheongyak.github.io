"""2026-11-25 익산어양4단지 50년 공공임대(2015122300021129): 신청자격 첫 문장의 지역 칸이 서식 안내글 그대로
'주택건설지역(주택공급에 관한 규칙 제4조제3항 각 호 해당지역 기재)에 거주하는 무주택세대구성원' 이라 거주지역·소득·자산을 못 읽음(판정 검증 실패 #167·#168).
지역 이름은 순위 결정기준 '해당 주택건설지역(익산시)의 거주자에게 우선 공급하고, 남은주택이 있을 경우 다른지역(익산시외 전북특별자치도) 거주자에게 공급' 에서만 읽는다."""
from app.lh_terms import parse_lh_terms

HEAD = ("4. 신청자격\n입주자모집공고일( 2026. 11. 25. ) 현재 주택건설지역(주택공급에 관한 규칙 제4조제3항 각 호 해당지역 기재)에 거\n주하는 무주택세대구성원으로서 아래의 기준을 충족하는 사람\n"
        "■ 순위\n1순위 입주자모집공고일(2026. 11. 25.) 현재 주택청약종합저축(청약저축 포함)에 가입하여 6개월이 지난 자로서 매월 약정납입일에 월납입금을 6회 이상 납입한 자\n"
        "2순위 주택청약종합저축(청약저축 포함)에 가입되어 있고 1순위에 해당되지 아니하는 자\n5. 모집일정\n")
RANK = "■ 수도권외 지역 순위 결정기준\n • 동일순위내 경쟁시 해당 주택건설지역(익산시)의 거주자에게 우선 공급하고, 남은주택이 있을 경우 다른지역(익\n산시외 전북특별자치도) 거주자에게 공급\n"


def test_template_region_read_from_rank_rule():
    r = parse_lh_terms(HEAD + RANK, "공공임대", "익산어양4단지", "전북특별자치도")
    assert r["regions"] == ["전북"] and r["local"]["sigun"] == "익산시"
    assert "익산시 외 전북특별자치도" in r["local"]["sigun_others_check"]
    g = r["groups"][0]
    assert (g["income_pct"], g["asset_manwon"], g["car_manwon"]) == ("excluded", "excluded", "excluded")


def test_template_without_rank_sentence_stays_unread():
    # 순위 결정기준 문장이 없으면 지역을 지어내지 않고, 소득·자산도 '없음'으로 보지 않는다
    r = parse_lh_terms(HEAD, "공공임대", "익산어양4단지", "전북특별자치도")
    assert r.get("regions") is None and r["groups"][0]["income_pct"] is None


def test_filled_region_still_read_as_before():
    r = parse_lh_terms(HEAD.replace("주택공급에 관한 규칙 제4조제3항 각 호 해당지역 기재)에 거\n주하는", "익산시)에 거주하는") + RANK, "공공임대", "익산부송3", "전북특별자치도")
    assert r["regions"] == ["전북"] and r["local"]["sigun"] == "익산시"
