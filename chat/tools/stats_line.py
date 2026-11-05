"""청약봇 /stats 응답(최근 7일 하루 합계)을 run-log 한 줄로. 표준 입력 → 표준 출력. (collect.yml 이 부른다)

하루 합계 키는 서버(chat/worker/src/index.js)가 정한다:
- /chat·/free: q·follow_up·ai_calls·rejected·fallback·in_tokens·out_tokens, verdict 종류별('free' = 자유 질문)
- /v2/llm(공고 찾기 AI): v2_explain(질문 1건 = 설명 1번)·v2_extract(조건 읽기)·v2_error·v2_capped·tokens_in·tokens_out
  (2026-11-05 전에는 v2 키를 읽지 않아 공고 찾기 AI 사용량과 그 비용이 기록 줄에 빠졌다)
"""
import json, sys
from datetime import datetime, timedelta, timezone

HAIKU = (1, 5)   # Haiku 4.5: 입력 $1, 출력 $5 / 100만 토큰 (chat/worker/src/llm.js PRICE)


def line(d, day):
    s = d.get(day) or {}
    week = sum(v.get("q", 0) for v in d.values())
    week_v2 = sum(v.get("v2_explain", 0) for v in d.values())
    # in_tokens 에는 /free(Sonnet, 단가 더 비쌈) 토큰도 섞여 있어 나눌 수 없다 → Haiku 단가로 센 '추정'이라 실제보다 적게 나올 수 있다
    tok_in = sum(v.get("in_tokens", 0) + v.get("tokens_in", 0) for v in d.values())
    tok_out = sum(v.get("out_tokens", 0) + v.get("tokens_out", 0) for v in d.values())
    cost = tok_in / 1e6 * HAIKU[0] + tok_out / 1e6 * HAIKU[1]
    fb = s.get("fb_reason") or {}
    free = (s.get("verdict") or {}).get("free", 0) if isinstance(s.get("verdict"), dict) else 0
    return (f"[청약봇] {day} 질문 {s.get('q', 0)}건(되물음 {s.get('follow_up', 0)}, 자유 질문 {free}) · AI 호출 {s.get('ai_calls', 0)} · 검사기 거절 {s.get('rejected', 0)} · 고정 문구 대체 {s.get('fallback', 0)}"
            f" · 개인정보 가림 {s.get('pii', 0)} · 제한 {s.get('limited_user', 0)}/{s.get('limited_global', 0)} · 👍{s.get('fb_up', 0)} 👎{s.get('fb_down', 0)}"
            + (" (" + ", ".join(f"{k} {v}" for k, v in fb.items()) + ")" if fb else "")
            + f" · 공고 찾기 AI 설명 {s.get('v2_explain', 0)}건(조건 읽기 {s.get('v2_extract', 0)} · 실패 {s.get('v2_error', 0)} · 월 한도 막힘 {s.get('v2_capped', 0)})"
            + f" · 7일 질문 {week}건 · 7일 공고 찾기 AI {week_v2}건 · 7일 추정 비용 ${cost:.2f}")


if __name__ == "__main__":
    day = (datetime.now(timezone(timedelta(hours=9))) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(line(json.load(sys.stdin), day))
