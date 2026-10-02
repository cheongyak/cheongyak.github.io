# 청약봇 답 품질 — 재고, 고치고, 올라가기만 하게

2026-10-03 사용자 요청: "답변 품질 검증 알고리즘 → 높일 방법 → 지속적으로 진화". 챗봇·LLM 평가에서 널리 쓰는 방법을 조합했어요.

| 층 | 무엇을 재나 | 방법 (출처) | 파일 | 언제 |
|---|---|---|---|---|
| 1. 조건 해석 | 질문에서 조건을 맞게 뽑았나 | 슬롯 F1 · Joint Goal Accuracy (대화형 검색 봇 표준, MultiWOZ DST) | `quality/rubric.mjs` condMatch | 매번 (CI) |
| 2. 행동 테스트 | 말만 바꿔도 같은 해석인가(INV), 조건을 더하면 후보가 줄기만 하나(DIR) | CheckList (Ribeiro 외, ACL 2020) | `quality/checklist.mjs` | 매번 |
| 3. 근거 충실도 | 답의 숫자·판정·과거 공고 표시가 실제 데이터와 같은가 | Faithfulness / Groundedness (RAGAS·TruLens) — 코드 검사, 틀리면 0점 | `llm.mjs` checkAnswer | 매번 |
| 4. 답 모양 | 결론부터·이유·출처·추정 표시·대안·좁혀 줄 질문·해요체·길이 | 채점표 7차원 (STYLE.md 원칙) | `quality/rubric.mjs` score | 매번 |
| 5. 사람 같은 판단 | 도움 됨·자연스러움·예시 수준인지 | LLM-as-a-judge: G-Eval 절대 평가 + MT-Bench 짝 비교(자리 바꿔 두 번) | `quality/judge.mjs`, `run_ai.mjs` | 운영자가 `ai-run.json` round 올릴 때 (비용 약 0.5~1달러/20문항) |
| 6. 버전 고르기 | 새 답 틀·프롬프트가 기존보다 나은가 | Bradley-Terry / Elo (Chatbot Arena) — 이긴 쪽만 채택 | `judge.mjs` bradleyTerry | 5와 같이 |
| 7. 실제 사용자 | 👎 이유 7가지 | 데이터 플라이휠 — 같은 약점 이름으로 순위에 더함 | `run.mjs` FB_MAP, `evidence/chat-v2/feedback.json` | 공개 뒤 |

## 진화 순환
1. `node chat/v2/quality/run.mjs` → `evidence/chat-v2/quality-report.md`: 점수, **약점 순위**(고치면 가장 많이 오르는 순), **말 바꾸면 깨지는 표현**, **못 읽은 낱말 후보**.
2. 위에서부터 고친다 — 해석기(extract.mjs NORM·lexicon), 답 틀(answer.mjs), 사실 묶음(llm.mjs).
3. 다시 재서 기준선(`quality/baseline.json`)보다 낮으면 CI 실패. 높으면 `--ratchet` 으로 기준선을 올린다 (내려가지 않음).
4. 질문 재료는 계속 는다: 사용자 샘플 → `golden/questions.json`, 새 말투 → `checklist.mjs` PARA, 생성기 조각 → `generate.mjs`. 재료가 늘면 점수가 다시 내려가고, 그걸 고치며 올라간다.

## 첫 회차 (2026-10-03)
- 처음 잰 값: JGA 57.5% → '무주택 4인 가족', '아이 둘'을 못 읽음 → 고친 뒤 100%.
- INV 77.7% → '최대 9억', '전용 84', '신특', '생애 최초', '분당은 싫고', '최소 500세대', '역에서 가까우면' 등 13가지 → 정규화 표·무게 판정 범위 고친 뒤 99.3%.
- 답: '방3화2'만 물으면 "청약은 없어요"라고 잘못 말함(데이터가 없을 뿐) → '확인하면 되는 후보'로. 결과 없음 때 대안이 비는 62건 → '조건에 가장 가까운 곳'. 검사기가 새 문장('예산보다 N억 여유')의 숫자를 사실 묶음에 없다고 막아 사실 묶음을 보강.
- 코드 채점 평균 99.8 — 코드로 잴 수 있는 것은 거의 다 통과. 다음 개선은 5·6층(AI 심사)과 7층(실제 사용자), 그리고 사용자 샘플로 시험지를 늘려 찾는다.
