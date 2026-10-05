"""docs/index.html 은 한 파일 스크립트라 같은 이름 함수를 다시 선언하면 오류 없이 뒤의 것이 앞의 것을 덮는다
(2026-10-05 LH 임대 작업에서 rentalCard 가 기존 공공임대 상세 함수를 덮어 화면 스냅샷 검사가 깨짐). 맨 앞 함수 선언 이름이 겹치지 않는지 본다."""
import re
from collections import Counter
from pathlib import Path


def test_no_duplicate_top_level_functions():
    html = (Path(__file__).resolve().parents[1] / "docs/index.html").read_text(encoding="utf-8")
    names = re.findall(r"^(?:async )?function ([A-Za-z0-9_$]+)", html, re.M)
    dup = [n for n, c in Counter(names).items() if c > 1]
    assert not dup, dup
