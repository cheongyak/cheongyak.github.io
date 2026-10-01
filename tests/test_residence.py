"""거주 지역 요건 (기능: residence_v2) — 실제 모집공고문 원문으로 확인한 정답과 추출 결과 비교.

정답(tests/golden/notices.json 의 fields.residence)은 evidence/notices/*.txt(공고문 PDF 원문 텍스트)의
'해당지역·기타지역' 표, LH '지역우선 공급기준' 표, 무순위 '대상자' 문장을 읽고 확인한 값이다.
"""
import json
import pathlib

from app import notice_pdf, pipeline
from app.models import Listing

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
RES = {k: v for k, v in GOLD.items() if "residence" in v["fields"]}


def text(no):
    return (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")


def test_golden_residence_from_real_notices():
    assert len(RES) >= 15
    for no, g in RES.items():
        assert notice_pdf.parse_residence(text(no)) == g["fields"]["residence"], no
        assert notice_pdf.parse_notice(text(no)).get("residence") == g["fields"]["residence"], no


def test_residence_quotes_in_originals():
    """정답이 기대는 원문 문장이 실제 공고문에 있다 (공백만 정리)."""
    q = {
        "2026000399": "서울특별시 2년 이상 계속 거주자 (2024.08.28. 이전부터 계속 거주) 서울특별시 2년 미만 거주자, 경기도 및 인천광역시 거주자",
        "2026000437": "경기도 6개월 이상 거주자 (2026.03.11. 이전부터 계속 거주) 경기도 6개월 미만 거주자 및 전국 거주자",
        "2026000445": "전주시 1년 미만 계속 거주자 및 전북특별자치도 거주자",
        "2026820008": "해당 주택건설지역 (성남시) 100%",
        "2026910220": "입주자모집공고일 현재 전국에 거주하는 무주택세대구성원",
        "2026910234": "입주자모집공고일 현재 부산광역시 및 울산광역시, 경상남도에 거주하는 무주택세대구성원",
    }
    import re
    for no, s in q.items():
        assert s in re.sub(r"\s+", " ", text(no)), no


def test_every_evidence_notice_reads_or_none():
    """모아 둔 공고문 56건 모두 오류 없이 읽고, 읽은 값은 형식이 맞다 (못 읽으면 None — 추측하지 않음)."""
    n = 0
    for f in sorted((ROOT / "evidence" / "notices").glob("*.txt")):
        r = notice_pdf.parse_residence(f.read_text(encoding="utf-8"))
        if r is None:
            continue
        n += 1
        assert r["area"] is None or r["area"].get("sido") or r["area"].get("sigungu"), f.name
        assert r["months"] in (0, 6, 12, 24, 36), f.name
        assert (r["since"] is None) == (r["months"] == 0), f.name
        assert all(x in ("전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
                         "전북", "전남", "경북", "경남", "제주") for x in r["others"]), f.name
    assert n >= 50


def test_pipeline_keeps_residence_from_previous_run():
    prev = {"from_notice": ["거주 지역 요건"], "residence": {"area": {"name": "서울특별시", "sido": "서울"}, "months": 24}}
    found, _ = pipeline._from_previous(prev)
    assert found["residence"]["months"] == 24


def test_listing_has_residence_field():
    assert "residence" in Listing.model_fields


def test_special_supply_shares_residence_requirement():
    """특별공급 신청자격 ①도 일반공급과 같은 거주 지역 요건이다 (기능: supply_summary) — 원문 문장 확인."""
    import re
    t103 = re.sub(r"\s+", " ", text("2026000103"))
    for kind in ("신혼부부", "생애최초", "신생아", "다자녀가구", "노부모부양자"):
        assert (kind + " 특별공급 신청자격 ① 최초 입주자모집공고일 현재 경기도 성남시에 거주하거나 "
                "수도권(서울시, 경기도, 인천시)에 거주하는") in t103, kind
    assert "경쟁이 있을 경우 해당 주택건설지역인 경기도 성남시 2년 이상 거주자" in t103      # 해당지역은 순서(우선)
    t409 = re.sub(r"\s+", " ", text("2026000409"))
    assert "신혼부부ㆍ생애최초ㆍ노부모부양ㆍ신생아 특별공급 및 일반공급 지역 우선공급 기준" in t409
    assert "다자녀 특별공급 지역 우선공급 기준" in t409                                         # 다자녀는 표가 따로


MC = {k: v for k, v in GOLD.items() if "mc_quota" in v["fields"]}


def test_golden_mc_quota_from_real_notices():
    """다자녀 특별공급 지역별 배정 (기능: mc_quota) — 공고문 원문으로 확인한 정답과 같다."""
    import json
    gold = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))
    mc = {k: v for k, v in gold.items() if "mc_quota" in v["fields"]}
    assert len(mc) >= 10
    for no, g in mc.items():
        assert notice_pdf.parse_mc_quota(text(no)) == g["fields"]["mc_quota"], no
        assert notice_pdf.parse_notice(text(no)).get("mc_quota") == g["fields"]["mc_quota"], no


def test_mc_quota_quotes_in_originals():
    import re
    q = {
        "2026000399": "다자녀가구 특별공급 해당시도(서울특별시) 거주자 (50%)",
        "2026000453": "다자녀가구 특별공급 해당시·도(광명시 및 경기도) 거주자(50%)",
        "2026000431": "기타지역(서울, 인천) 거주자(50%)",
        "2026000416": "① 경기도 50% ․ 공고일 현재 해당 주택건설지역(양주시) 1년 이상 거주자에게 우선 공급. 단, 남는 물량은 경기도 6개월 이상 거주자에게 공급",
        "2026000437": "② 기타지역(전국) 50%",
    }
    for no, s in q.items():
        assert s in re.sub(r"\s+", " ", text(no)), no


def test_household_count_rules_in_originals():
    """가구원수 산정 기준 원문 (기능: hh_count). 민영: 무주택세대구성원 전원 + 태아 수 + 직계존속은 최근 1년 이상 같은 등본.
    공공(LH): 신혼부부·다자녀·신생아 = 무주택세대구성원 전원(태아 포함), 생애최초 = 직계존속은 1년 이상 등재만."""
    import re
    t453 = re.sub(r"\s+", " ", text("2026000453"))
    assert ("(가구원수 산정 기준) 무주택세대구성원 전원으로 산정. 단, 임신 중인 태아는 태아 수만큼 인정하되, 공급신청자의 직계존속"
            "(공급신청자의 배우자의 직계존속을 포함)은 입주자모집공고일을 기준으로 최근 1년 이상 계속하여 공급신청자 또는 그 배우자와 "
            "같은 세대별 주민등록표에 등재되어 있는 경우에만 포함") in t453
    t409 = re.sub(r"\s+", " ", text("2026000409"))
    assert "신혼부부·다자녀·신생아 특별공급, 일반공급 10페이지의 ‘무주택세대구성원’에 해당하는 자 전원을 포함하여 산정" in t409
    assert ("생애최초 특별공급 10페이지의 ‘무주택세대구성원’에 해당하는 자 전원을 포함하여 산정. 단, 직계존속은 주택공급신청자 또는 "
            "주택공급신청자의 배우자와 1년 이상 같은 주민등록표등본상 등재되어 있는 경우에만 가구원수에 포함") in t409
    assert "노부모부양 특별공급 10페이지의 ‘무주택세대구성원’에 해당하는 자 전원과 피부양자 및 피부양자의 배우자를 포함하여 산정" in t409


def test_golden_schedule_from_real_notices():
    """공급유형별 접수 일정 (기능: notice_schedule) — LH 공고문 '신청일정' 표·'신청시간' 문장으로 확인한 정답과 같다."""
    sch = {k: v for k, v in GOLD.items() if "schedule" in v["fields"]}
    assert len(sch) >= 3
    for no, g in sch.items():
        assert notice_pdf.parse_schedule(text(no)) == g["fields"]["schedule"], no
        assert notice_pdf.parse_notice(text(no)).get("schedule") == g["fields"]["schedule"], no
    # 신청시간 문장이 없거나(민영·청약홈 접수 LH) 특별공급이 없는 공고(신혼희망타운)는 읽지 않는다
    for no in ("2026000437", "2026000454", "2026000453", "2026820008", "2026820011"):
        assert notice_pdf.parse_schedule(text(no)) is None, no


def test_schedule_quotes_in_originals():
    import re
    q = {
        "2026000409": "(특별공급) 2026.09.14.(10:00) ~ 2026.09.15.(17:00), (일반공급) 2026.09.16.(10:00) ~ 2026.09.17.(17:00)",
        "2026000414": "(특별공급) 2026.09.30.(10:00~17:00), (일반공급) 2026.10.01.(10:00) ~ 2026.10.02.(17:00)",
        "2026000416": "(특별공급) 2026.9.14. 10:00 ~ 2026.9.15. 17:00, (일반공급) 2026.9.16. 10:00 ~ 2026.9.17. 17:00",
    }
    for no, s in q.items():
        assert s in re.sub(r"\s+", " ", text(no)), no


def test_schedule_checked_against_applyhome_dates():
    """공고문 접수 일정과 청약홈 날짜가 어긋나면 자동 검증에 걸린다 (기능: notice_schedule)."""
    import datetime
    from app import validate
    def mk(**kw):
        base = dict(id="2026000414-0", name="인천계양", address="인천광역시 계양구", region="인천", sigungu="계양구",
                    unit="84", price=4.0, mkt_low=4.0, mkt_base=4.0, url="https://www.applyhome.co.kr/x")
        base.update(kw)
        return Listing(**base)
    today = datetime.date(2026, 9, 30)
    L = mk(kind="국민", category="general", apply="2026-09-17", apply_end="2026-10-02", special_apply="2026-09-30",
           special_apply_end="2026-09-30", schedule=GOLD["2026000414"]["fields"]["schedule"])
    assert not [c for c in validate.listing_checks(L, today) if "청약홈(" in c]
    L.special_apply = "2026-09-29"
    assert any("특별공급 접수일" in c for c in validate.listing_checks(L, today))
    L.special_apply, L.apply_end = "2026-09-30", "2026-10-03"
    assert any("접수 마감일" in c for c in validate.listing_checks(L, today))


def test_pipeline_keeps_schedule_from_previous_run():
    prev = {"from_notice": ["접수 일정"], "schedule": GOLD["2026000414"]["fields"]["schedule"]}
    found, _ = pipeline._from_previous(prev)
    assert found["schedule"]["special"] == ["2026-09-30", "2026-09-30"]


def test_golden_pub_limits_from_real_notices():
    """공공분양 일반공급 소득·자산 기준 (기능: pub_general_limits) — LH 공고문 원문으로 확인한 정답과 같다."""
    pl = {k: v for k, v in GOLD.items() if "pub_limits" in v["fields"]}
    assert len(pl) >= 3
    for no, g in pl.items():
        assert notice_pdf.parse_pub_limits(text(no)) == g["fields"]["pub_limits"], no
        assert notice_pdf.parse_notice(text(no)).get("pub_limits") == g["fields"]["pub_limits"], no
    # 60㎡ 초과만 있어 일반공급 소득 기준이 '해당 없음'인 공고, 민영, 신혼희망타운(총자산 기준)은 읽지 않는다
    for no in ("2026000437", "2026000438", "2026000453"):
        assert notice_pdf.parse_pub_limits(text(no)) is None, no
    # 신혼희망타운은 소득·총자산 기준 (기능: town_rules)
    for no in ("2026820008", "2026820009", "2026820011"):
        assert notice_pdf.parse_pub_limits(text(no))["kind"] == "town", no


def test_pub_limits_quotes_in_originals():
    import re
    q = {
        "2026000414": ["(세대) 월평균소득 100% 이하 (맞벌이 200%) * 전용면적 60㎡ 이하만 적용",
                       "1순위자로서 무주택세대구성원 전원의 월평균소득이 “<표4> 전년도 도시근로자 가구당 월평균소득”의 100%(본인 및 배우자가 모두 소득이 있는 경우 140%) 이하인 자",
                       "부동산 (건물+토지) 215,500천원 이하", "자동차 45,420천원 이하"],
        "2026000409": ["(세대) 월평균소득 100% 이하 (맞벌이 200%) 자산", "부동산 (건물+토지) 215,500천원 이하"],
        "2026000416": ["(세대) 월평균소득 100% 이하 (맞벌이 200%) * 전용면적 60㎡ 이하만 적용"],
    }
    for no, ss in q.items():
        t = re.sub(r"\s+", " ", text(no))
        for s in ss:
            assert s in t, (no, s)


def test_pipeline_keeps_pub_limits_from_previous_run():
    prev = {"from_notice": ["공공 일반공급 소득·자산"], "pub_limits": GOLD["2026000414"]["fields"]["pub_limits"]}
    found, _ = pipeline._from_previous(prev)
    assert found["pub_limits"]["cap"] == [100, 200]


def test_town_limits_quotes_in_originals():
    """신혼희망타운 신청 유형·소득·총자산 문장이 공고문 원문에 있다 (기능: town_rules)."""
    import re
    for no in ("2026820008", "2026820009", "2026820010", "2026820011"):
        t = re.sub(r"\s+", " ", text(no))
        assert re.search(r"혼인 중인 자로서 혼인기간이 7년 이내 또는 6세 이하\s*(\(태아 포함\)\s*)?자녀(\(태아 포함\))?를 둔 경우", t), no
        assert "예비신혼부부 혼인을 계획 중이며, 입주 전까지 혼인사실을 증명할 수 있는 자" in t, no
        assert re.search(r"한 부 모 가 족 6세 이하 자녀(\(태아 포함\))?를 둔 부 또는 ?모", t), no
        assert "우선·일반공급 전년도 도시근로자 가구당 월평균소득의 130%" in t, no
        assert re.search(r"합계액에서 ⑤를 차감한 금액이 (362,000천원|362백만원) 이하", t), no
        assert "시세차익(주택매각금액- 분양금액)의 최소 10%~최대 50%" in t or "최소 10%~최대 50%" in t, no


def test_town_total_asset_items_in_originals():
    """신혼희망타운 총자산 산정 항목 (기능: town_assets) — 화면 계산식이 기대는 공고문 <표3> 문장이 원문에 있다.
    ②금융자산에 보험·연금보험 해약환급금·IRP, ③기타자산에 임차보증금, ⑤부채에 임대보증금(해당 부동산 가액까지)·마이너스통장 제외."""
    import re
    for no in ("2026820008", "2026820010", "2026820011"):
        t = re.sub(r"\s+", " ", text(no))
        for q in ("보험증권 : 조사기준일 당시 해약하는 경우 지급받게 될 환급금", "연금보험 : 조사기준일 당시 해약하는 경우 지급받게 될 환급금",
                  "개인형퇴직연금(IRP) : 조사기준일 당시 잔액", "주택·상가 등에 대한 임차보증금(전세금을 포함한다)",
                  "임대보증금(단, 해당 부동산가액 이하의 금액만 반영)", "유동성 한도대출금은 부채로 인정되지 않으며"):
            assert q in t, (no, q)
        assert re.search(r"①\+②\+③\+④ 합계액에서 ⑤를 차감한 금액이 (362,000천원|362백만원) 이하", t), no


def test_public_special_selection_method_in_originals():
    """공공분양 특별공급 선정 방식 (기능: ws_reco_v2 · 상세 설명) — 화면이 기대는 '당첨자 선정방법' 문장이 원문에 있다.
    생애최초 1단계는 추첨, 신혼부부 1단계는 선정순위 안에서 가점 순·2단계는 선정순위 안에서 추첨, 신생아 1·2단계 점수 순, 낙첨자는 다음 단계로."""
    import re
    for no in ("2026000409", "2026000414", "2026000416"):
        t = re.sub(r"\s+", "", text(no))
        assert re.search(r"공급량의70%\(소수점이하는올림\)를우선공급하며,경쟁이있는경우추첨의방법", t), (no, "생애최초 1단계 추첨")
        assert re.search(r"공급량의70%\(소수점이하는올림\)를“신혼부부특별공급입주자선정순위”에따라공급", t), (no, "신혼 1단계 선정순위")
        assert re.search(r"공급량의70%\(소수점이하는올림\)를공급하며,경쟁이있는경우아래점수항목다득점순", t), (no, "신생아 1단계 점수")
        assert "1단계우선공급낙첨자전원을대상으로" in t, (no, "낙첨자 다음 단계")
    t = re.sub(r"\s+", "", text("2026000414"))
    assert "동일순위내에서경쟁이있는경우아래가점항목다득점순" in t
    assert "인천광역시거주자가50%우선공급에서낙첨될경우,50%물량의기타지역(수도권)거주자와다시경쟁" in t


def test_public_points_table_in_originals():
    """점수 내역·올리는 방법 (기능: score_tips) — 화면의 항목 기준이 공공 신혼부부·신생아 점수표 원문과 같다."""
    import re
    for no in ("2026000409", "2026000414"):
        t = re.sub(r"\s+", "", text(no))
        for q in ("3명이상3", "24회이상3", "12회이상24회미만2", "6회이상12회미만1", "3년이상3", "1년이상3년미만2", "1년미만1",
                  "3년이하3", "3년초과5년이하2", "5년초과7년이하1"):
            assert q in t, (no, q)
        assert "80%이하인경우(본인및배우자가모두소득이있는경우100%)" in t, no


def test_public_special_birth_relax_in_originals():
    """특별공급 출산가구 완화 (기능: sp_birth_relax) — 가산 폭과 완화 자산 기준이 공공분양 공고문 원문에 있다."""
    import re
    for no in ("2026000409", "2026000414"):
        t = re.sub(r"\s+", "", text(no))
        assert "’23.3.28.이후출생한자녀(태아포함)가1명만있는경우10%p,2명이상(’23.3.28.이후출생한자녀가1명이고,’23.3.27.전출생한자녀가있는경우포함)인경우20%p가산하여소득기준완화" in t, no
    t = re.sub(r"\s+", "", text("2026000414"))
    assert "부동산(건물+토지)237,050천원이하258,600천원이하" in t and "자동차49,960천원이하54,510천원이하" in t
    assert "적용대상:다자녀․노부모부양․생애최초․신혼부부․신생아특별공급및전용면적60㎡이하일반공급" in t
