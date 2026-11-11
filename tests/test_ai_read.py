"""AI 가 대신 읽기 (기능 ai_read, app/ai_read.py, 2026-11-11) — 검사기와 채우기 규칙을 본다.
2026-11-12 부터 수집은 Claude API 를 부르지 않는다(키는 청약봇 전용): 세션이 공고문을 읽어 답 파일을 쓰고(save_answer·tools/ai_answer.py), 수집은 그 답만 쓴다.
원칙: 근거 문장이 원문에 그대로 있고 값이 그 문장 안에 있는 것만, 규칙이 못 읽은 칸에만 채운다."""
import json
from pathlib import Path

from app import ai_read
from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
JC = (ROOT / "evidence/lh/2015122300020975.txt").read_text(encoding="utf-8")   # 제천장락1 50년 공공임대 (2026-11-10 규칙이 처음에 못 읽은 공고)
Q_REGION = "입주자 모집공고일(2026.11.09.) 현재 주택건설지역(제천시,충청북도)에 거주하는 무주택세대구성원으로 아래의 기준에 해당되는 자"
Q_ACC = "주택청약종합저축(청약저축 포함)에 가입하여 6개월이 지난 자로서 매월 약정납입일에 월납입금을 6회 이상 납입한 자"
GOOD = {"groups": [{"key": "일반", "homeless": "household", "homeless_quote": Q_REGION, "income_pct": None, "asset_manwon": None, "car_manwon": None}],
        "regions": ["충북"], "regions_quote": Q_REGION, "account": {"months": 6, "count": 6, "rank2_any": True}, "account_quote": Q_ACC, "local": None}


def test_gaps():
    assert ai_read.gaps(None, "행복주택") == ["계층"]
    assert ai_read.gaps({"groups": [{"key": "일반", "homeless": "household", "income_pct": "excluded", "asset_manwon": "excluded", "car_manwon": "excluded"}], "regions": ["충북"], "account": None}, "공공임대") == ["account"]
    assert ai_read.gaps({"groups": [{"key": "주거급여수급자", "homeless": "household", "income_pct": None, "asset_manwon": None, "car_manwon": None}]}, "행복주택") == []
    full = parse_lh_terms(JC, "공공임대", "", "충청북도")
    assert ai_read.gaps(full, "공공임대") == []   # 지금 규칙은 이 공고를 다 읽는다 → AI 를 부르지 않는다


def test_checker_passes_real_sentences():
    t, dropped = ai_read.to_terms(GOOD, [JC], "충청북도")
    assert dropped == []
    assert t["regions"] == ["충북"] and t["account"] == {"months": 6, "count": 6, "rank2_any": True}
    assert t["groups"][0]["homeless"] == "household" and t["quotes"]["일반"]["account"] == Q_ACC


def test_checker_drops_what_it_cannot_confirm():
    bad = json.loads(json.dumps(GOOD))
    bad["regions"] = ["충북", "서울"]                                   # 문장에 서울특별시가 없음
    bad["account"] = {"months": 12, "count": 12, "rank2_any": True}     # 문장의 숫자(6개월·6회)와 다름
    bad["groups"][0].update(income_pct="excluded", income_quote=Q_REGION,           # 문장에 소득을 안 본다는 말이 없음
                            asset_manwon=34500, asset_quote="총자산 34,500만원 이하인 자에 한하여 신청할 수 있습니다",   # 원문에 없는 문장(지어냄)
                            car_manwon=45420, car_quote=Q_REGION)                     # 범위 밖
    t, dropped = ai_read.to_terms(bad, [JC], "충청북도")
    assert "regions" not in t and "account" not in t
    g = t["groups"][0]
    assert g["homeless"] == "household" and g["income_pct"] is None and g["asset_manwon"] is None and g["car_manwon"] is None
    assert len(dropped) == 5 and any("원문에 없음" in x for x in dropped)


def test_checker_values():
    c = ai_read._check_value
    assert c("income_pct", {"1": 90, "2": 80, "3+": 70}, "월평균소득의 70% 이하인 자 (1인 가구 20%p, 2인 가구 10%p 가산)", None) is None
    assert c("income_pct", {"1": 120, "2": 110, "3+": 100}, "월평균소득의 70% 이하인 자", None)          # 문장에 없는 퍼센트
    assert c("income_pct", {"1": 70, "2": 80, "3+": 90}, "소득 70% 80% 90%", None)                       # 순서가 거꾸로
    assert c("asset_manwon", 34500, "총자산가액 합산기준 34,500만원 이하", None) is None
    assert c("asset_manwon", 34500, "총자산 345,000,000원 이하", None) is None
    assert c("asset_manwon", 34500, "총자산 3억4,500만원 이하", None) is None
    assert c("asset_manwon", 34500, "총자산가액 합산기준 33,700만원 이하", None)
    assert c("car_manwon", 0, "신청자 본인이 자동차가액 산출대상 자동차를 소유하고 있지 않을 것", None) is None
    assert c("car_manwon", "excluded", "자동차가액 4,542만원 이하", None)
    assert c("regions", [], "국내에 거주하는 성년자인 무주택세대구성원", None) is None
    assert c("regions", [], "현재 현재 성년자인 무주택세대구성원", None)                                  # 남원노암(2015122300021022): 거주지역 문구가 빠진 공고문 — '제한 없음'으로 읽지 않는다
    assert c("regions", ["전북"], "주택건설지역(익산시)에 거주하는 무주택세대구성원", "전북특별자치도") is None
    assert c("regions", ["전북"], "주택건설지역(익산시)에 거주하는 무주택세대구성원", "충청북도")          # 공고의 시·도와 다르면 거부
    assert c("account", "none", "청약저축 가입여부, 과거당첨사실여부, 소득 및 자산요건 충족 여부와 관계없이 신청 가능", None) is None
    assert c("local", {"name": "제천시", "sido": "충북", "sigun": "제천시"}, "모집공고일 현재 제천시에 거주하는 성년자인 무주택세대구성원", "충청북도") is None
    assert c("local", {"name": "제천시", "sido": "서울", "sigun": "제천시"}, "모집공고일 현재 제천시에 거주하는 성년자인 무주택세대구성원", "충청북도")


def test_checker_lessons_from_probe_20261111():
    """11-11 정확도 시험(정답 데이터 15건을 실제 Claude 로 읽힘)에서 검사기를 통과한 틀린 값 — 다시 통과하지 못하게."""
    c = ai_read._check_value
    q = "무주택세대구성원(혼인 중이 아닌 경우로서 단독세대주로 입주하려는 사람의 경우에는 무주택자)으로서 다음의 요건을"
    assert c("homeless", "household", q, None)                                      # 992·993·912 고령자: 단독세대주 예외가 붙은 문장을 '세대원 전원'으로 읽음
    assert c("homeless", "household_or_single_self", q, None) is None
    assert c("homeless", "household", "현재 무주택세대구성원", None, after="(단,혼인중이아닌경우로서단독세대주로입주하려는사람은무주택자)으로서")   # 예외 괄호가 문장 바로 뒤에 있어도
    assert c("homeless", "self", "청년 계층의 주택소유여부는 신청자 본인에 한하여 검증합니다.", None) is None
    assert c("account", "none", "금회 공고는 청약저축 가입여부, 과거당첨 사실여부, 소득기준 및 자산기준 충족여부와는 상관없으며", None) is None
    text = JC + " 소득 배제 총자산가액 배제 무주택세대구성원(청년은 입주자 본인, 예비신혼부부는 혼인으로 구성될 세대원)으로서 직업요건을 충족한 자 "
    ans = {"groups": [{"key": "일반", "homeless": "household", "homeless_quote": "무주택세대구성원(청년은 입주자 본인, 예비신혼부부는 혼인으로 구성될 세대원)으로서 직업요건을 충족한 자"}],
           "local": {"name": "제천시", "sido": "충북", "sigun": "제천시"}, "local_quote": Q_REGION, "other_groups": ["장기종사자"]}
    t, dropped = ai_read.to_terms(ans, [text], "충청북도", "공공임대")
    assert t["groups"] == [] and "local" not in t and t["unknown_groups"] == ["장기종사자"]   # 905 '일반' 계층 지어냄 · 975 공공임대 local(제천시만으로 좁힘)
    t, _ = ai_read.to_terms({"groups": [{"key": "일반", "income_pct": "excluded", "income_quote": "소득 배제", "asset_manwon": "excluded", "asset_quote": "총자산가액 배제"},
                                        {"key": "주거급여수급자", "income_pct": "excluded", "income_quote": "소득 배제"}]}, [text], None, "국민임대")
    assert t["groups"][0]["income_pct"] == "excluded" and t["groups"][0]["asset_manwon"] == "excluded"   # 962 표 칸의 짧은 글은 '미적용'일 때만 받는다
    assert len(t["groups"]) == 1                                                     # 주거급여수급자 계층은 행복주택에서만 (912 통합공공임대에 이 계층을 만듦)
    t, _ = ai_read.to_terms({"groups": [{"key": "청년", "homeless": "self", "homeless_quote": "청년 계층의 주택소유여부는 신청자 본인에 한하여 검증합니다."},
                                        {"key": "주거급여수급자", "income_pct": "excluded", "income_quote": "소득 배제"}]},
                            [text + " 청년 계층의 주택소유여부는 신청자 본인에 한하여 검증합니다."], None, "행복주택")
    assert [(g["key"], g["homeless"], g["income_pct"]) for g in t["groups"]] == [("청년", "self", None), ("주거급여수급자", "household", None)]   # 칸은 AI 값으로 채우지 않는다


# ── 분양 (기능 ai_read_sale): 판정에 쓰지 않는 참고 내용 ─────────────────────────────────────────
UJB = ("주택유형 해당지역 기타지역 규제지역여부 민영 입주자 모집공고일 현재 경기도 의정부시 거주자 경기도 및 서울특별시, 인천광역시 거주자 비규제지역 "
       "재당첨제한 전매제한 거주의무기간 분양가상한제 택지유형 없음 당첨자 발표일로부터 1년 없음 미적용 민간택지 ") + "가" * 600   # 의정부역 펠리스타워(2026000553) 요약 표 꼴
Q_RES = "입주자 모집공고일 현재 경기도 의정부시 거주자 경기도 및 서울특별시, 인천광역시 거주자"
SALE_GOOD = {"residence": {"area": "경기도 의정부시", "months": 0, "since": None, "others": ["서울", "인천", "경기"]}, "residence_quote": Q_RES,
             "residence_duty_years": 0, "residence_duty_quote": "재당첨제한 전매제한 거주의무기간 분양가상한제 택지유형 없음 당첨자 발표일로부터 1년 없음 미적용 민간택지"}


def test_sale_hints_checker():
    h, dropped = ai_read.sale_hints(SALE_GOOD, [UJB])
    assert h["residence"]["text"] == "해당지역 경기도 의정부시 거주자 · 기타지역 서울·인천·경기" and h["residence"]["quote"] == Q_RES
    assert "residence_duty" not in h and any("거주의무가 없다는 말이 없음" in x for x in dropped)   # 표 머리와 값이 떨어진 글('…거주의무기간 … 없음 … 1년 없음')은 '없음'으로 단정하지 않는다
    bad = json.loads(json.dumps(SALE_GOOD))
    bad["residence"].update(area="경기도 양주시")                                    # 문장에 없는 지역
    assert "residence" not in ai_read.sale_hints(bad, [UJB])[0]
    bad = json.loads(json.dumps(SALE_GOOD))
    bad["residence"].update(months=12)                                               # 문장에 없는 거주기간
    assert "residence" not in ai_read.sale_hints(bad, [UJB])[0]
    bad = json.loads(json.dumps(SALE_GOOD))
    bad["residence"].update(others=["서울", "인천", "경기", "강원"])                  # 문장에 없는 기타지역
    assert "residence" not in ai_read.sale_hints(bad, [UJB])[0]
    t = "해당지역 기타지역 제주특별자치도 1년 이상 계속 거주자 (2025.10.27. 이전부터 계속 거주) 제주특별자치도 1년 미만 거주자 및 전국 거주자 " + "나" * 600
    a = {"residence": {"area": "제주특별자치도", "months": 12, "since": "2025-10-27", "others": ["전국"]},
         "residence_quote": "제주특별자치도 1년 이상 계속 거주자 (2025.10.27. 이전부터 계속 거주) 제주특별자치도 1년 미만 거주자 및 전국 거주자",
         "residence_duty_years": 5, "residence_duty_quote": "거주의무 최초 입주가능일부터 5년 「주택법」제57조의2"}
    h, _ = ai_read.sale_hints(a, [t + " 거주의무 최초 입주가능일부터 5년 「주택법」제57조의2"])
    assert h["residence"]["text"] == "해당지역 제주특별자치도 거주자 · 1년 이상 계속 거주(2025-10-27 이전부터) · 기타지역 전국" and h["residence_duty"]["text"] == "거주의무 5년"
    a["residence"]["months"] = 0                                                      # 문장에 '1년 이상'이 있는데 기간 없음으로 답함
    assert "residence" not in ai_read.sale_hints(a, [t])[0]


def test_sale_hints_lessons_from_probe_20261111():
    """11-11 분양 정확도 시험 1차(12건): 무순위 공고 '부산광역시 및 울산광역시, 경상남도에 거주하는 …'을 해당지역 부산+기타지역으로 나눈 답이 통과했다."""
    q = "본 주택은 무순위(사후) 입주자모집공고일 현재 부산광역시 및 울산광역시, 경상남도에 거주하는 무주택세대구성원을 대상으로 공급합니다."
    t = q + "다" * 600
    bad = {"residence": {"area": "부산광역시", "months": 0, "since": None, "others": ["울산", "경남"]}, "residence_quote": q}
    h, dropped = ai_read.sale_hints(bad, [t])
    assert "residence" not in h and "똑같이 받는 문장" in dropped[0]
    good = {"residence": {"area": None, "months": 0, "since": None, "others": ["부산", "울산", "경남"]}, "residence_quote": q}
    assert ai_read.sale_hints(good, [t])[0]["residence"]["text"] == "부산·울산·경남 거주자(우선하는 지역 없음)"
    q2 = "■ 입주자모집공고일 현재 서울특별시에 거주하는 무주택세대의 세대주"
    only = {"residence": {"area": "서울특별시", "months": 0, "since": None, "others": []}, "residence_quote": q2}
    assert ai_read.sale_hints(only, [q2 + "라" * 600])[0]["residence"]["text"] == "서울특별시 거주자만 신청"
    only["residence_quote"] = "민영 투기과열지구/청약과열지역 경기도 광명시 거주자 10년"       # 표 줄 — 기타지역이 없다고 볼 문장이 아니다
    only["residence"]["area"] = "경기도 광명시"
    assert "residence" not in ai_read.sale_hints(only, [only["residence_quote"] + "마" * 600])[0]
    q3 = "본 주택은 무순위 사후 입주자모집공고일 현재 충청북도에 거주하는 무주택세대구성원을 대상으로 공급합니다"
    one = {"residence": {"area": None, "months": 0, "since": None, "others": ["충북"]}, "residence_quote": q3}       # 2차 시험 2026910243: 한 시·도만 others 에 적은 답
    h = ai_read.sale_hints(one, [q3 + "바" * 600])[0]["residence"]
    assert h["text"] == "충청북도 거주자만 신청" and h["value"]["area"] == "충청북도" and h["value"]["others"] == []


def test_sale_excerpt_keeps_relevant_parts_and_is_short():
    """분양 공고문 전체(약 15만 자)를 보내면 1건 추정 $0.30 — 앞부분과 거주 요건·거주의무 둘레만 보낸다. 조각은 원문 그대로다."""
    body = "분양가 납부 안내 " * 20000                                   # 약 18만 자
    text = "요약 표 " + Q_RES + " " + body[:60000] + " 거주의무기간 : 최초 입주가능일부터 3년 " + body[60000:]
    ex = ai_read.sale_excerpt(text)
    assert len(ex) <= ai_read.SALE_MAX + 100 and Q_RES in ex and "거주의무기간 : 최초 입주가능일부터 3년" in ex
    assert all(part in text for part in ex.split("\n…\n"))
    assert ai_read.sale_excerpt("짧은 글") == "짧은 글"


# ── 답 파일 (2026-11-12: 수집은 API 를 부르지 않는다 — 세션이 읽어 써 둔 답만 쓴다) ─────────────────────
def test_module_has_no_network_or_key():
    src = (ROOT / "app/ai_read.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("#"))
    assert "httpx" not in code and "api.anthropic.com" not in code and "environ" not in code and "x-api-key" not in code
    for wf in ("collect.yml", "lh-rental.yml"):
        assert "ANTHROPIC_API_KEY" not in (ROOT / ".github/workflows" / wf).read_text(encoding="utf-8")   # 키는 청약봇 워크플로에만


def test_fill_uses_only_saved_answer(tmp_path):
    strict = {"relaxed": False, "groups": [{"key": "일반", "name": "일반", "homeless": None, "income_pct": None, "asset_manwon": None, "car_manwon": None, "age_min": None, "age_max": None}],
              "quotes": {}, "regions": ["경기"], "account": None}
    out, log = ai_read.fill("T1", strict, {"pypdf": JC}, "공공임대", "제천장락1", "충청북도", cache_dir=tmp_path)
    assert out is strict and "답 파일 없음" in log[0] and "tools.ai_answer lh T1" in log[0]        # 답 파일이 없으면 그대로('공고문 확인') — 부르지 않는다
    f = ai_read.save_answer("lh", "T1", GOOD, JC, cache_dir=tmp_path)
    assert json.loads(f.read_text(encoding="utf-8"))["model"] == "claude-session"
    out, log = ai_read.fill("T1", strict, {"pypdf": JC}, "공공임대", "제천장락1", "충청북도", cache_dir=tmp_path)
    assert out is not strict and strict["account"] is None                      # 원래 객체는 그대로(채우기 전 값으로 되돌릴 수 있게)
    assert out["regions"] == ["경기"]                                           # 규칙이 읽은 값은 답(충북)으로 바꾸지 않는다
    assert out["account"] == {"months": 6, "count": 6, "rank2_any": True} and out["groups"][0]["homeless"] == "household"
    assert sorted(out["ai"]["fields"]) == ["account", "일반.homeless"] and out["ai"]["model"] == "claude-session"
    out2, log2 = ai_read.fill("T1", strict, {"pypdf": JC + " 정정공고로 글이 바뀜"}, "공공임대", "제천장락1", "충청북도", cache_dir=tmp_path)
    assert out2 is strict and "답 파일 없음" in log2[0]                          # 공고문 글이 바뀌면(정정) 옛 답을 쓰지 않는다


def test_fill_skips_when_rules_read_everything(tmp_path):
    full = parse_lh_terms(JC, "공공임대", "", "충청북도")
    ai_read.save_answer("lh", "T2", GOOD, JC, cache_dir=tmp_path)
    assert ai_read.fill("T2", full, {"pypdf": JC}, "공공임대", "", "충청북도", cache_dir=tmp_path) == (full, [])


def test_fill_keeps_unread_when_answer_fails_checks(tmp_path):
    strict = {"groups": [], "quotes": {}}
    lie = {"groups": [{"key": "일반", "homeless": "household", "homeless_quote": "공고문에 없는 지어낸 문장입니다 무주택세대구성원"}], "regions": None, "account": None}
    ai_read.save_answer("lh", "T3", lie, JC, cache_dir=tmp_path)
    out, log = ai_read.fill("T3", strict, {"pypdf": JC}, "공공임대", "", "충청북도", cache_dir=tmp_path)
    assert out is strict and any("탈락" in x for x in log) and any("공고문 확인' 그대로" in x for x in log)


def test_fill_only_fields_the_screen_shows_unread(tmp_path):
    """남원노암(2015122300021022, 11-11): 못 읽은 칸(거주지역·소득·자산·자동차)은 못 채우고, 묻지 않은 나이(age_min 19)만 채워 'AI 가 읽은 공고'가 됐다 — 못 읽은 칸이 아니면 채우지 않는다."""
    strict = {"groups": [{"key": "일반", "name": "일반", "homeless": "household", "income_pct": None, "asset_manwon": None, "car_manwon": None, "age_min": None, "age_max": None}],
              "quotes": {}, "regions": None, "account": {"months": 6, "count": 6, "rank2_any": True}}
    text = JC + " 「민법」상 미성년자(만 19세 미만)는 공급 신청할 수 없습니다. "
    ans = {"groups": [{"key": "일반", "homeless": "household", "homeless_quote": Q_REGION, "age_min": 19, "age_quote": "「민법」상 미성년자(만 19세 미만)는 공급 신청할 수 없습니다."}],
           "regions": None, "account": {"months": 6, "count": 6, "rank2_any": True}, "account_quote": Q_ACC, "other_groups": ["장기종사자"]}
    ai_read.save_answer("lh", "T5", ans, text, cache_dir=tmp_path)
    out, log = ai_read.fill("T5", strict, {"pypdf": text}, "공공임대", "", "전북특별자치도", cache_dir=tmp_path)
    assert out is strict and strict["groups"][0]["age_min"] is None and "unknown_groups" not in strict


def test_sale_fill_uses_only_saved_answer(tmp_path):
    found = {"residence": {"area": {"name": "x"}}, "price_cap": True}                 # 거주 지역 요건은 규칙이 읽음 → 실거주 의무만 못 읽은 공고
    ans = json.loads(json.dumps(SALE_GOOD))
    ans.update(residence_duty_years=3, residence_duty_quote="거주의무기간 : 최초 입주가능일부터 3년")
    text = UJB + " 거주의무기간 : 최초 입주가능일부터 3년 "
    h, log = ai_read.sale_fill("S1", found, text, "시험단지", cache_dir=tmp_path)
    assert h == {} and "답 파일 없음" in log[0] and "tools.ai_answer sale S1" in log[0]
    ai_read.save_answer("sale", "S1", ans, text, cache_dir=tmp_path)
    h, log = ai_read.sale_fill("S1", found, text, "시험단지", cache_dir=tmp_path)
    assert list(h) == ["residence_duty"] and h["residence_duty"] == {"text": "거주의무 3년", "quote": "거주의무기간 : 최초 입주가능일부터 3년"}   # 규칙이 읽은 항목은 싣지 않는다
    assert ai_read.sale_fill("S2", {"residence": {"a": 1}, "residence_duty": 0}, text, "", cache_dir=tmp_path) == ({}, [])
    assert ai_read.sale_gaps({"residence": {"a": 1}, "duty_silent": True}) == []      # '공고문에 거주의무 말이 없음'으로 읽은 공고는 묻지 않는다

