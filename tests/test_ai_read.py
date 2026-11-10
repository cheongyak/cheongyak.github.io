"""AI 가 대신 읽기 (기능 ai_read, app/ai_read.py, 2026-11-11) — AI 를 실제로 부르지 않고(가짜 응답) 검사기와 채우기 규칙을 본다.
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


def _post(answer, calls=None):
    def f(key, body):
        assert key == "k" and body["model"] == ai_read.MODEL and "<공고문>" in body["messages"][0]["content"]
        if calls is not None:
            calls.append(1)
        return {"content": [{"type": "text", "text": "```json\n" + json.dumps(answer, ensure_ascii=False) + "\n```"}], "usage": {"input_tokens": 30000, "output_tokens": 500}}
    return f


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


def test_fill_only_missing_and_caches(tmp_path):
    strict = {"relaxed": False, "groups": [{"key": "일반", "name": "일반", "homeless": None, "income_pct": None, "asset_manwon": None, "car_manwon": None, "age_min": None, "age_max": None}],
              "quotes": {}, "regions": ["경기"], "account": None}
    calls = []
    out, log = ai_read.fill("T1", strict, {"pypdf": JC}, "공공임대", "제천장락1", "충청북도", ai_read.Budget(2), post=_post(GOOD, calls), api_key="k", cache_dir=tmp_path)
    assert out is not strict and strict["account"] is None                      # 원래 객체는 그대로(채우기 전 값으로 되돌릴 수 있게)
    assert out["regions"] == ["경기"]                                           # 규칙이 읽은 값은 AI 값(충북)으로 바꾸지 않는다
    assert out["account"] == {"months": 6, "count": 6, "rank2_any": True} and out["groups"][0]["homeless"] == "household"
    assert sorted(out["ai"]["fields"]) == ["account", "일반.homeless"] and out["ai"]["model"] == ai_read.MODEL
    assert (tmp_path / "T1.json").exists() and len(calls) == 1
    out2, _ = ai_read.fill("T1", strict, {"pypdf": JC}, "공공임대", "제천장락1", "충청북도", ai_read.Budget(0), post=None, api_key="", cache_dir=tmp_path)
    assert out2["ai"]["fields"] == out["ai"]["fields"]                         # 같은 공고문은 저장해 둔 답을 쓴다(다시 부르지 않음, 키 없어도 됨)


def test_fill_skips_without_key_or_budget_or_gaps(tmp_path):
    strict = {"groups": [], "quotes": {}}
    out, log = ai_read.fill("T2", strict, {"pypdf": JC}, "공공임대", "", None, ai_read.Budget(2), api_key="", cache_dir=tmp_path)
    assert out is strict and "ANTHROPIC_API_KEY 없음" in log[0]
    out, log = ai_read.fill("T2", strict, {"pypdf": JC}, "공공임대", "", None, ai_read.Budget(0), post=_post(GOOD), api_key="k", cache_dir=tmp_path)
    assert out is strict and "호출 수 한도" in log[0]
    full = parse_lh_terms(JC, "공공임대", "", "충청북도")
    out, log = ai_read.fill("T2", full, {"pypdf": JC}, "공공임대", "", "충청북도", ai_read.Budget(2), post=_post(GOOD), api_key="k", cache_dir=tmp_path)
    assert out is full and log == []                                            # 규칙이 다 읽었으면 AI 를 부르지 않는다


def test_fill_keeps_unread_when_ai_fails_checks(tmp_path):
    strict = {"groups": [], "quotes": {}}
    lie = {"groups": [{"key": "일반", "homeless": "household", "homeless_quote": "공고문에 없는 지어낸 문장입니다 무주택세대구성원"}], "regions": None, "account": None}
    out, log = ai_read.fill("T3", strict, {"pypdf": JC}, "공공임대", "", "충청북도", ai_read.Budget(1), post=_post(lie), api_key="k", cache_dir=tmp_path)
    assert out is strict and any("탈락" in x for x in log) and any("공고문 확인' 그대로" in x for x in log)


def test_call_failure_does_not_leak_key(tmp_path):
    def boom(key, body):
        raise RuntimeError("claude 401 authentication_error: invalid x-api-key SECRETKEY")
    out, log = ai_read.fill("T4", {"groups": [], "quotes": {}}, {"pypdf": JC}, "공공임대", "", None, ai_read.Budget(1), post=boom, api_key="SECRETKEY", cache_dir=tmp_path)
    assert "호출 실패" in log[0] and "SECRETKEY" not in log[0]
