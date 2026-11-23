"""행복주택 자격완화 공고의 맞벌이 괄호 '…150%(3순위)이하)' 꼴 (2015122300021130 수원 호매실21·고등2, 2026-11-24 아침 자동 고치기).
고치기 전에는 이 꼴을 몰라 일반 문장 규칙이 일반조건(1순위) 맞벌이 120% − 3순위 150% = −30 을 맞벌이 가산으로 읽었다(불변식 dual_add_range)."""
from app.lh_terms import _happy_groups, _relaxed_happy_income

HEAD = ("3-2. 신혼부부·한부모가족 계층 입주자모집공고일 현재, 무주택세대구성원으로서 ③ 해당세대의 월평균소득이 전년도 도시근로자 가구원수별 가구당 "
        "월평균소득의 100%(【완화조건】120%(2순위),150%(3순위))이하 ")
SENT = HEAD + ("(맞벌이 부부 120%(【완화조건】130%(2순위),150%(3순위)이하)일 것 ※ 단, 가구원수가 2인인 경우 110% (【완화조건】 130%(2순위), 150%(3순위)) 이하, "
               "맞벌이 2인가구의 경우 130% (【완화조건】 140%(2순위), {d2}%(3순위)) 이하일 것 ")


def _dual(text):
    r = _relaxed_happy_income(text, "신혼부부·한부모")
    return r and r[2]


def test_reads_dual_with_iha_before_paren():
    r = _relaxed_happy_income(SENT.format(d2=150), "신혼부부·한부모")
    assert r[0] == {"1": None, "2": 150, "3+": 150}
    assert r[2] == 0 and "맞벌이 부부 120%" in r[3]


def test_rejects_when_two_person_dual_disagrees():
    # 맞벌이 2인 3순위가 일반 2인 3순위와 가산이 다르면(160 − 150 = 10 ≠ 0) 읽지 않는다
    assert _dual(SENT.format(d2=160)) is None


def test_rejects_unordered_ratios():
    t = SENT.format(d2=150).replace("120%(【완화조건】130%(2순위),150%(3순위)이하)", "140%(【완화조건】130%(2순위),150%(3순위)이하)")
    assert _dual(t) is None


def test_plain_rule_does_not_subtract_relaxed_base():
    # 완화 괄호가 붙은 맞벌이 숫자(일반조건)를 3순위 상한에서 빼지 않는다 — 괄호를 못 읽는 꼴이면 가산을 비워 둔다
    t = HEAD + "(맞벌이 부부 120%(【완화조건】130%(2순위)…150%(3순위)이하)일 것 ※ 단, 가구원수가 2인인 경우 110% (【완화조건】 130%(2순위), 150%(3순위)) 이하일 것 "
    groups, _ = _happy_groups(t)
    g = next(x for x in groups if x["key"] == "신혼부부·한부모")
    assert g["income_pct"] == {"1": None, "2": 150, "3+": 150}
    assert "dual_add" not in g


def test_plain_unrelaxed_dual_still_read():
    t = ("3-2. 신혼부부·한부모가족 계층 ③ 월평균소득의 100퍼센트 이하(맞벌이 부부 120퍼센트 이하) 가구원 수가 2인인 경우에는 110퍼센트 이하 ")
    groups, _ = _happy_groups(t)
    g = next(x for x in groups if x["key"] == "신혼부부·한부모")
    assert g.get("dual_add") == 20
