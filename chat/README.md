# 청약봇 '이 공고 물어보기' (기능: chatbot)

공고 상세의 **이 공고 물어보기**가 쓰는 서버와 검사 도구예요. 2026-10-01 저장소 밖 시제품(Phase 1)을 가져와 붙였어요.

- **판정은 하지 않아요.** 브라우저가 화면 판정 함수(cpExplain·myScore·grade·itemBasis)를 읽기만 해서 그 결과와 질문을 보내고, 서버는 공고문 근거를 붙여 Claude 에게 '설명'만 맡겨요.
  판정 함수가 바뀌지 않았는지는 `tools/engine_lock.py`(pytest `tests/test_engine_lock.py`)가 함수별 지문으로 확인해요.
- **검사기를 통과한 답만** 내보내요(`worker/src/validate.js`): 판정 불일치, 결론·특공 뒤집기, 근거에 없는 숫자, 금지 표현, 근거 번호 없는 규정, 개인정보 다시 쓰기.
  두 번 막히면 엔진 결과만으로 만든 고정 문구 답(`fallback.js`). 화면도 답의 판정이 화면 판정과 다르면 보여주지 않아요.
- **저장하지 않아요.** 대화는 화면 메모리에만 있고, 서버(KV)에는 하루 이용 횟수(소금 섞은 해시, 다음 날 만료)와 개인 식별 없는 하루 합계(`stats.js`)만 둬요.

## 파일

| 파일 | 하는 일 |
| --- | --- |
| `worker/src/index.js` | 서버 본체 (Cloudflare Worker). `/chat` 질문, `/feedback` 평가, `/stats` 하루 합계(토큰 필요), `/health` |
| `worker/src/validate.js` | 답변 검사기 |
| `worker/src/evidence.js` | 근거 지도: 공고문 발췌를 태그별로 나누고 엔진 항목·질문 낱말에 맞는 조각을 고름 |
| `worker/src/prompt.js` | 시스템 프롬프트 (버전 `PROMPT_VERSION`, 바꾸면 올리고 골든셋을 다시 돌림) |
| `worker/src/fallback.js` | AI 없이 엔진 결과만으로 만드는 고정 문구 답 |
| 운영 명령 | 미리보기 코드 기기에서 대화창에: `!점검`·`!오픈`·`!상태`, `!무료`(운영자 질문만 AI 안 부르고 제한 없음)·`!AI`(복귀) |
| `worker/src/limits.js` | 사람마다 하루 2건(되물음 답은 질문 1건당 2번까지 세지 않음), IP 하루 6건, 전체 하루 100건 |
| `worker/src/stats.js` | 하루 합계(질문 수·분류·판정·검사기 거절·대체·토큰·평가 이유)와 평가 이유 7가지 |
| `worker/src/redact.js` | 주민번호·전화·이메일·동호수·계좌 가리기 (화면도 보내기 전에 같은 규칙으로 가림) |
| `worker/src/intent.js` | 질문 분류(판정·일정·서류·규정·범위 밖). 범위 밖은 AI 를 부르지 않음 |
| `worker/wrangler.toml` | 배포 설정. `CHAT_OPEN = "0"` 이면 미리보기 코드를 아는 기기만 답을 받음 |
| `tools/split_evidence.mjs` | `docs/rules-evidence.txt`(2.4MB)를 공고별 `docs/chat-evidence/<번호>.json` 으로 나눔 (Worker CPU 한도 때문). probe.yml 이 실행 |
| `tools/stats_line.py` | `/stats` → run-log `[청약봇]` 한 줄 (collect.yml) |
| `tools/engine_payload.cjs` | 화면 판정 엔진을 Node 에서 돌려 브라우저와 같은 엔진 결과를 만듦 (시험용) |
| `golden/golden_v0.json` | 골든셋 270문항 (판정 사례 256 + 오픈카톡 실제 질문·범위 밖·개인정보·조작 시도 14) |
| `test/chat.test.mjs` | 검사기·서버 시험 30개 |

화면 쪽은 `docs/index.html` 의 '청약봇' 묶음(chatEntry·chatRender·chatSend·chatEnginePayload), 끝에서 끝 검사는 `tools/qa/chatflow.cjs`.

## 실행

```bash
cd chat
node --test test/chat.test.mjs                               # 시험 30개
node golden/eval.mjs                                         # 골든셋 (AI 없이)
node golden/eval.mjs --fixtures golden/fixtures_good.json    # 골든셋 (미리 쓴 AI 답)
ANTHROPIC_API_KEY=... node golden/eval.mjs                   # 실제 Claude 로 (키는 대화·기록에 적지 않음)
cd .. && NODE_PATH=... node tools/qa/chatflow.cjs 40 /tmp/shots   # 화면 → 실제 서버 코드 → 화면
```

## 배포·공개

1. GitHub Secrets: `ANTHROPIC_API_KEY`, `CHAT_PREVIEW_CODE`, `CHAT_STATS_TOKEN` (Cloudflare 값은 알림 서버와 같음) → `.github/workflows/chat-worker.yml` 이 배포하고 `chat/deployed.json` 에 주소를 남김.
2. `docs/config.json` 의 `chat_api` 에 그 주소 → 운영자가 `?chat=preview` + 미리보기 코드로 확인.
3. 방침 개정 시행일(10-09, 기능 legal_notice) 이후: `chat_legal_date`, `wrangler.toml` 의 `CHAT_OPEN = "1"`, 스위치 `chatbot: true`.

## 아직 남은 것

- 실제 Claude 답의 품질: 키가 생기면 골든셋 270문항을 실제로 돌려 검사기 거절률·대체율을 보고 프롬프트를 고침.
- 근거 조각 고르기: 공고문 발췌가 키워드 주변을 잘라 둔 것이라 관련 없는 조각이 섞임 (다음 단계).
- `docs/rules-evidence.txt` 는 probe.yml 이 돌 때만 갱신돼요. 새 공고는 근거 조각 없이 엔진 결과로만 답해요 (다음 단계: 매일 수집에 넣기).
