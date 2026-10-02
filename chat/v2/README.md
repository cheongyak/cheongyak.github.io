# 청약봇 V2 엔진 (개발 중 · 청약패스 화면·서버와 아직 연결 안 함)

질문 하나를 아래 순서로 처리해요. 지금 청약패스(화면·수집·청약봇 서버)에는 영향을 주지 않고, 나중에 스위치 하나(`chatbot_v2`)로 심을 수 있게 따로 만들었어요.

```
사용자 질문
  ↓ extract.mjs      자연어 조건 추출 (규칙 해석 → 있으면 AI 해석, 형식 검사 통과한 것만)
  ↓                  필수(required) / 선호(preferred) / 탐색(explore) 분리 + 이번 질문만의 가정(assume) + 못 보는 조건(unsupported)
  ↓ search.mjs       실제 데이터 검색 (지금 공고 + 지난 1년 공고) → 후보군
  ↓                  조건 걸러내기: 필수 불통과는 빼고 '빠진 이유별 개수', 데이터 없는 필수 조건은 '확인 필요 후보'로 따로
  ↓                  내 자격: 청약패스 화면 판정 함수(eligBucket·spJudge) 그대로 — 여기서 자격을 새로 계산하지 않음
  ↓                  추천 점수·관점별 1등(가격·시세 차익·당첨 길·출퇴근지 거리), 결과 없으면 완화안(조건 하나 늦추면 몇 곳)
  ↓ answer.mjs       기본 답 (AI 없이도 완성된 답) + 비교(단지 이름 → 공고)
  ↓ llm.mjs          AI 설명 (사실 묶음 FACTS 만 받아 다듬기) → 검사기(checkAnswer) 통과한 것만, 막히면 기본 답
```

## 원칙
- **판정은 청약패스 화면과 같다.** `engine.cjs`(Node)·`browser.mjs`(화면) 모두 `docs/index.html` 의 판정 함수를 불러 쓴다. 저장된 내 조건이 없으면 판정하지 않는다(질문 속 '신혼부부' 같은 가정만으로 단정하지 않음).
- **값마다 상태**: 확인(청약홈·모집공고문·판정 엔진) / 추정(시세·전세·직선거리 도보) / 확인 불가. 데이터가 없는 것(방·욕실 수, 출퇴근 시간, 급지·호재·주차·학군)은 지어내지 않고 '확인 불가'·'청약패스에 데이터가 없어요'라고 쓴다.
- **AI 는 두 번까지**(조건 해석·설명). 검색·판정·점수는 코드. AI 가 실패하거나 한도를 넘으면 기본 답이 그대로 나간다.
- 답 모양은 `STYLE.md`(사용자가 보여 준 예시 답 두 개에서 뽑은 원칙).

## 파일
| 파일 | 하는 일 |
|---|---|
| `extract.mjs` | 규칙 조건 해석 `extract(q)`, 후속 질문 `applyDelta(state, q)` ('송파 포기할게', '10억으로', '나홀로는 빼줘') |
| `lexicon.mjs` | 지역(시·도, 시·군·구 근사 좌표, 생활권: 분당·판교·위례·광교…), 출퇴근 장소, 특별공급 낱말, 말투(필수/선호/탐색) |
| `search.mjs` | 사실(factsOf)·조건 평가(evalCond)·검색(search)·관점별 1등·완화안·인접 지역(좌표 거리)·비교 대상 찾기 |
| `answer.mjs` | 기본 답(compose): 질문 받기 → 이렇게 이해했어요 → 결론부터 → 후보별 핵심 지표 → 이런 분께는 이곳 → 확인하지 못한 것 → 다음에 해볼 것 |
| `llm.mjs` | AI 프롬프트 2개, AI 조건 해석 검사(parseExtraction), 설명 검사(checkAnswer: 없는 숫자·판정 뒤집기·과거 공고를 지금처럼·급지/호재 단정) |
| `index.mjs` | `ask({D, question, profile, state, llm})` — Node·브라우저 어디서나 (fs 안 씀) |
| `node.mjs`·`node-data.mjs`·`engine.cjs` | Node 입구: docs/ 를 읽어 데이터 묶음을 만듦 (CLI·시험) |
| `browser.mjs` | 화면 입구 `fromScreen(window, {raw})` — 심을 때 씀 |
| `cli.mjs` | `node chat/v2/cli.mjs "질문" [--profile 파일.json] [--today 2026-10-02] [--json]` |
| `golden/questions.json` | 시험지 1차 (41문항 + 후속 질문 3) — 기대 조건은 사람이 질문을 읽고 정함 |
| `test/` | `node --test chat/v2/test/v2.test.mjs` — 조건 해석, 검색 검산(`oracle.mjs` 따로 옮긴 계산), 판정 = 화면 엔진, 결과 없음·비교·확인 불가, 검사기 |

## 아직 없는 것 (V2 실행 계획 STEP 0·1)
- 방·욕실 수(0-4), 동 단위 좌표 41곳 정밀화(0-5), 출퇴근 시간 경로 API(0-7 — 카카오 REST 키·네이버 Directions 5 필요), 인접 지역 표(0-8, 지금은 lexicon 근사 좌표)
- 실제 AI 연결: 청약봇 서버에 `/v2/llm` 길을 만들고(키는 Worker 비밀값), 화면이 `browser.mjs` 로 ask 를 부름. 실제 AI 답 시험은 운영자가 누를 때만(비용).
- 제도 설명 질문(가점제·추첨제 차이 등)은 지금 기존 청약봇 경로로 넘긴다(`legacy`). 검증한 설명집은 STEP 3.

## 심는 방법 (나중에)
1. `docs/config.json` 에 `chatbot_v2: false` 스위치를 추가하고 FEATURES.md 에 적는다.
2. 화면 청약봇 보내기(chatSend)에서 `on('chatbot_v2')` 이면 `import('/chat/v2/browser.mjs')` → `ask({ D: fromScreen(window, { raw }), question, profile: S.profile, state, llm })`. (chat/v2 를 docs/ 로 옮기거나 빌드해 넣음)
3. 서버에 `/v2/llm`(AI 호출만, 프롬프트는 llm.mjs) 추가 — 횟수·월 한도·운영 명령은 지금 서버 것을 그대로.
4. 시험지 통과 + 운영자 미리보기 확인 뒤 공개 (공개 기준: V2 실행 계획 11항).
