"""느슨한 읽기 (기능 loose_read, app/loose_re.py·app/loose_read.py, 2026-11-11).
띄어쓰기만 다른 문장은 같은 문장으로 읽되, 엄격하게 읽은 값은 절대 바꾸지 않는다."""
import copy
import json
import re
from pathlib import Path

import pytest

from app import lh_terms, loose_read
from app.loose_re import loose, loosen

ROOT = Path(__file__).resolve().parents[1]
REGION = {n["id"]: n.get("region") for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8"))}
GOLD = {g["id"]: g for g in json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]}


def test_loosen_rules():
    assert loosen(r"입주자모집공고일\s?현재") == r"입\s?주\s?자\s?모\s?집\s?공\s?고\s?일\s?현재"   # 3자 이상만 풀고 2자('현재')는 그대로
    assert loosen(r"소득 배제") == r"소득\s?배제"                         # 적힌 빈칸은 없어도 됨
    assert loosen(r"(?<![가-힣])고령자") == r"(?<![가-힣])고\s?령\s?자"     # 글자 묶음은 그대로
    assert loosen(r"(?<!예비입주자)모집") == r"(?<!예비입주자)모집"         # 뒤돌아보기 안은 건드리지 않음(길이가 정해져야 함)
    assert loosen(r"자동[차자]를") == r"자동[차자]를"
    assert loosen(r"가액이?\s?([\d,]+)") == r"가액이?\s?([\d,]+)"           # 횟수가 붙은 글자는 그대로
    assert re.search(loosen(r"무주택세대구성원"), "무주택 세대 구성원") and re.search(loosen(r"무주택세대구성원"), "무 주 택 세 대 구 성 원")
    assert not re.search(loosen(r"일반"), "기준일 반드시")                  # 2자 낱말은 풀지 않아 엉뚱한 곳에 맞지 않음


def test_loose_context_restores_module():
    before = {k: v for k, v in vars(lh_terms).items() if v is re or isinstance(v, re.Pattern)}
    with pytest.raises(RuntimeError):
        with loose(lh_terms):
            assert lh_terms.re is not re
            raise RuntimeError("안에서 오류가 나도")
    assert all(getattr(lh_terms, k) is v for k, v in before.items())


def _core(r):
    r = copy.deepcopy(r)
    r.pop("quotes", None); r.pop("loose", None)
    if isinstance(r.get("local"), dict):
        r["local"].pop("quote", None)
    return r


# (공고, 원문 낱말, 띄어 쓴 꼴) — 실제 저장 원문(evidence/lh)의 낱말 하나를 띄어 쓰면 엄격한 규칙은 못 읽고, 느슨한 읽기는 원래 값 그대로 읽는다
CASES = [("0000061176", "무주택세대구성원", "무주택 세대 구성원"), ("0000061184", "입주자 모집공고일", "입주자 모집 공고일"),
         ("2015122300020735", "총자산가액", "총자산 가액"), ("2015122300020780", "월평균소득", "월평균 소득"),
         ("2015122300020765", "주택건설지역", "주택 건설 지역")]


@pytest.mark.parametrize("nid,a,b", CASES)
def test_spacing_variant_is_read_like_original(nid, a, b):
    g = GOLD[nid]
    text = (ROOT / "evidence/lh" / f"{nid}.txt").read_text(encoding="utf-8", errors="replace")
    args = (g["type"], g.get("verified_from", ""), REGION.get(nid))
    base = lh_terms.parse_lh_terms(text, *args)
    spaced = text.replace(a, b)
    strict = lh_terms.parse_lh_terms(spaced, *args)
    assert _core(strict) != _core(base)                      # 엄격한 규칙은 띄어 쓴 꼴을 못 읽는다
    got = loose_read.parse_lh_terms(spaced, *args)
    assert got.get("loose")                                  # 채운 칸 이름이 남는다
    assert _core(got) == _core(base)                         # 원래 공고문과 같은 값


def test_strict_values_never_change_on_stored_notices():
    """저장된 원문 전부: 느슨한 읽기를 켜도 엄격하게 읽은 값은 그대로다(채우기만 한다)."""
    for nid, g in GOLD.items():
        f = ROOT / "evidence/lh" / f"{nid}.txt"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        args = (g["type"], g.get("verified_from", ""), REGION.get(nid))
        strict, got = lh_terms.parse_lh_terms(text, *args), loose_read.parse_lh_terms(text, *args)
        sg, gg = {x["key"]: x for x in strict["groups"]}, {x["key"]: x for x in got["groups"]}
        for key, x in sg.items():
            for f_, v in x.items():
                if v is not None:
                    assert gg[key][f_] == v, (nid, key, f_)
        for k, v in strict.items():
            if k not in ("groups", "quotes") and v is not None and k != "local_unread":
                assert got[k] == v, (nid, k)


def test_fill_notice_only_missing():
    found = {"need_head": True, "score_ratio": {"unknown": True}, "quotes": {"need_head": "…"}}
    lo = {"need_head": False, "residence": {"months": 0}, "score_ratio": {"60": [40, 60]}, "quotes": {"residence": "해당지역 …"}, "facts": {}}
    got = loose_read.fill_notice(found, lo)
    assert sorted(got) == ["residence", "score_ratio"]
    assert found["need_head"] is True and found["residence"] == {"months": 0} and found["quotes"]["residence"] == "해당지역 …"


def test_sale_residence_spacing_2026000553():
    """의정부역 펠리스타워(2026000553, 11-07): 요약 표 '입주자 모집공고일 현재 …' 띄어 쓴 꼴 — 그 규칙이 없던 때의 패턴도 느슨하게는 읽는다."""
    old = r"(?:입주자모집공고일 ?현재 ?)?(?:기존 ?)?"
    assert not re.match(old, "입주자 모집공고일 현재 기존").group(0)
    assert re.match(loosen(old), "입주자 모집공고일 현재 기존").group(0) == "입주자 모집공고일 현재 기존"
