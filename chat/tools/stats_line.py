"""청약봇 /stats 응답(최근 7일 하루 합계)을 run-log 한 줄로. 표준 입력 → 표준 출력. (collect.yml 이 부른다)"""
import json, sys
from datetime import datetime, timedelta, timezone

d = json.load(sys.stdin)
day = (datetime.now(timezone(timedelta(hours=9))) - timedelta(days=1)).strftime("%Y-%m-%d")
s = d.get(day) or {}
week = sum(v.get("q", 0) for v in d.values())
tok_in = sum(v.get("in_tokens", 0) for v in d.values()); tok_out = sum(v.get("out_tokens", 0) for v in d.values())
cost = tok_in / 1e6 * 1 + tok_out / 1e6 * 5   # Haiku 4.5: 입력 $1, 출력 $5 / 100만 토큰 (추정)
fb = s.get("fb_reason") or {}
print(f"[청약봇] {day} 질문 {s.get('q', 0)}건(되물음 {s.get('follow_up', 0)}) · AI 호출 {s.get('ai_calls', 0)} · 검사기 거절 {s.get('rejected', 0)} · 고정 문구 대체 {s.get('fallback', 0)}"
      f" · 개인정보 가림 {s.get('pii', 0)} · 제한 {s.get('limited_user', 0)}/{s.get('limited_global', 0)} · 👍{s.get('fb_up', 0)} 👎{s.get('fb_down', 0)}"
      + (" (" + ", ".join(f"{k} {v}" for k, v in fb.items()) + ")" if fb else "")
      + f" · 7일 질문 {week}건 · 7일 추정 비용 ${cost:.2f}")
