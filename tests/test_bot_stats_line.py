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


def test_cost_marked_low_when_free_used():
    assert "실제는 이보다 많음" in m.line(D, "2026-11-04")
    assert "실제는 이보다 많음" not in m.line({"2026-11-04": {"q": 1}}, "2026-11-04")


def test_usd_used_when_server_sends_it():
    # 2026-11-08 서버부터 날마다 모델별 단가로 센 usd 가 온다 → 그날은 토큰×Haiku 대신 그 값, '실제는 이보다 많음' 표시도 없음
    d = {"2026-11-08": {"q": 1, "in_tokens": 10000, "out_tokens": 1000, "usd": 0.03, "verdict": {"free": 1}},
         "2026-11-07": {"q": 1, "in_tokens": 1e6, "out_tokens": 0, "verdict": {"가능": 1}}}
    s = m.line(d, "2026-11-08")
    assert "7일 추정 비용 $1.03" in s           # 0.03(usd) + 1.00(옛 날, Haiku)
    assert "실제는 이보다 많음" not in s
    # usd 없는 옛 날에 자유 질문이 있으면 그대로 '실제는 이보다 많음'
    d["2026-11-07"]["verdict"] = {"free": 1}
    assert "실제는 이보다 많음" in m.line(d, "2026-11-08")


def test_month_spend_shown_and_not_counted_as_day():
    d = dict(D)
    d["_month"] = {"month": "2026-11", "usd": 4.256, "cap": 18}
    s = m.line(d, "2026-11-04")
    assert "이번 달(2026-11) AI 사용액 $4.26 / 한도 $18" in s
    assert "7일 질문 3건" in s and "7일 추정 비용 $0.90" in s   # _month 는 날짜 칸으로 세지 않음
    assert "이번 달" not in m.line(D, "2026-11-04")            # 옛 서버(_month 없음)는 줄에 안 붙임
