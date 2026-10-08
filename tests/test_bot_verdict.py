"""청약봇·콘텐츠 엔진(tools/bot/cy.js)의 결론 = 화면 맨 위 판정 (2026-10-09 사용자 제보: 세종 리더스포레 나릿재마을 1단지 2026930041 84D 는
다자녀 특별공급 1세대뿐(일반공급 0)인데 cy.js 가 일반공급 판정을 그대로 내보내 자녀 없는 미혼에게 '가능').
고정본 tests/fixtures/listing-2026930041-84D.json(2026-10-09 수집 값: households 0, special_units 다자녀 1) 과 실제 화면 코드(docs/index.html)로 돌린다."""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = {"homeSido": "세종", "household": "head", "selfOwn": False, "spouseOwn": False, "hhHomes": "0", "income": 4000, "cash": 10000}


def _run(tmp, prof):
    d = tmp / "docs"
    d.mkdir(exist_ok=True)
    for f in ("index.html", "config.json"):
        shutil.copy(ROOT / "docs" / f, d / f)
    shutil.copy(ROOT / "tests/fixtures/listing-2026930041-84D.json", d / "listings.json")
    out = subprocess.run(["node", str(ROOT / "tools/bot/cy.js"), str(d), json.dumps(dict(BASE, **prof)), "--all"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["results"][0]


def test_special_only_unit_uses_special_result(tmp_path):
    r = _run(tmp_path, {"birth": "1995-03-01", "married": False, "kidsMinor": 0, "hhSize": 1})
    assert r["specialOnly"] is True and r["generalUnits"] == 0
    assert r["verdict"] == "불가", r                       # 일반공급 판정('가능')이 아니라 다자녀 특공 결과
    r = _run(tmp_path, {"birth": "1985-03-01", "married": True, "kidsMinor": 2, "hhSize": 4})
    assert r["verdict"] == "가능", r                       # 세종 거주·무주택·미성년 자녀 2명 → 다자녀 특공 가능


def test_other_region_not_ok(tmp_path):
    r = _run(tmp_path, {"birth": "1985-03-01", "married": True, "kidsMinor": 2, "hhSize": 4, "homeSido": "대전"})
    assert r["verdict"] == "불가", r                       # 공고일 현재 세종 거주자만
