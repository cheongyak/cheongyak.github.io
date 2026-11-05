"""청약봇 하루 합계 기록 줄(chat/tools/stats_line.py) — 공고 찾기 AI(v2) 사용량·비용이 빠지지 않는지 (2026-11-05)"""
import importlib.util, json, subprocess, sys
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "chat" / "tools" / "stats_line.py"
spec = importlib.util.spec_from_file_location("stats_line", P)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

D = {"2026-11-04": {"q": 2, "in_tokens": 1000, "out_tokens": 100, "fb_down": 1,
                    "v2_explain": 3, "v2_extract": 3, "v2_error": 1, "tokens_in": 600000, "tokens_out": 60000, "verdict": {"free": 1, "가능": 1}},
     "2026-11-03": {"q": 1, "v2_explain": 2}}


def test_v2_counts_shown():
    s = m.line(D, "2026-11-04")
    assert "공고 찾기 AI 설명 3건(조건 읽기 3 · 실패 1 · 월 한도 막힘 0)" in s
    assert "7일 공고 찾기 AI 5건" in s
    assert "자유 질문 1" in s


def test_v2_tokens_in_cost():
    # (1000+600000)/1e6*1 + (100+60000)/1e6*5 = 0.601 + 0.3005 = 0.9015
    assert "7일 추정 비용 $0.90" in m.line(D, "2026-11-04")


def test_old_shape_and_down_signal_kept():
    s = m.line({"2026-11-04": {"q": 4, "in_tokens": 1e6, "out_tokens": 0, "fb_down": 2, "verdict": {"가능": 4}}}, "2026-11-04")
    assert s.startswith("[청약봇] 2026-11-04 질문 4건(되물음 0, 자유 질문 0)")
    assert "👎2" in s and "7일 질문 4건" in s and "$1.00" in s


def test_empty_and_cli():
    assert "질문 0건" in m.line({}, "2026-11-04")
    out = subprocess.run([sys.executable, str(P)], input=json.dumps(D), capture_output=True, text=True, check=True).stdout
    assert out.startswith("[청약봇] ") and "공고 찾기 AI" in out
