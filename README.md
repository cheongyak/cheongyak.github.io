# 밤 자동 개선 루프 — 상태 (데이터만, 서비스에 영향 없음)

절차: main 의 `.claude/skills/cheongyakpass-ops/IMPROVE.md`. 예약 작업 '청약패스 밤 자동 개선'이 매일 밤 읽고 고친다.

| 파일 | 내용 |
| --- | --- |
| backlog.json | 고칠 거리 목록(근거·점수 재료·상태: open / in_pr / merged / merged_effective / merged_no_effect / rejected / parked / gone) |
| weights.json | 영역별 가중치(합침 +, 닫음 −로 스스로 바뀜)·점수 표·탐색 주기 |
| ledger.jsonl | 밤마다 한 줄: 무엇을 왜 골랐고 결과가 어땠는지 |
| lessons.md | 배운 것(운영자 댓글·닫힌 이유·효과 없던 고침) |
| ideas.md | 신호에 안 잡히는 아이디어(운영자가 직접 더해도 됨) |

운영자가 할 일은 PR 을 '합치기' 또는 '닫기'(이유 한 줄 댓글)뿐이에요. 그 결과로 루프가 고르는 법을 바꿔요.
