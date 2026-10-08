---
name: cheongyakpass-ops
description: 청약패스(cheongyakpass.kr, 저장소 cheongyak/cheongyak.github.io) 개발·운영 작업 방식. 이 서비스의 화면·판정·수집·알림·광고·문서를 고치거나, 운영 질문에 답하거나, 새 세션에서 작업을 이어갈 때 먼저 읽는다.
---

# 청약패스 운영·개발 작업 방식

청약패스는 실제 서비스다. 판정이 틀리면 사용자가 부적격 당첨이나 계약금 손실을 볼 수 있다. 신뢰가 가장 중요하다.

## 1. 세션 시작 (매번)

1. **저장소 준비**: `/home/claude/cheongyak.github.io` 가 없으면 저장소를 세션에 붙이고(add_repo, owner `cheongyak`, repo `cheongyak.github.io`, 쓰기 권한) 그 경로로 클론한 뒤 등록한다.
   있으면 `git pull --rebase origin main` (Actions 가 매일·변경마다 커밋하므로 항상 먼저 받는다).
2. **읽는 순서**: `HANDOFF.md`(진행 중인 일·사용자와 일하는 방식·도구) → `CLAUDE.md`(규칙 1~8항, 반드시 지킴) → `WORK.md` 최근 5개 → 열린 이슈
   (`curl -s "https://api.github.com/repos/cheongyak/cheongyak.github.io/issues?state=open"`). 이슈가 열려 있으면 그것부터 처리한다 (CLAUDE.md 4-8항).
3. **환경**: `pip install -r requirements.txt` (pip 가 막히면 GitHub 에서 pytest·pluggy·iniconfig 를 클론해 PYTHONPATH 로).
   화면 검사는 playwright(전역 node_modules 가 있으면 `NODE_PATH` 로) + 크로미움 `/opt/pw-browsers/chromium`.
   `gh` 가 없으면 GitHub 공개 API 를 curl 로 읽는다. 태그 push 는 막혀 있어 백업은 브랜치로.

## 2. 사용자와 대화

- 사용자는 운영자이고 개발자가 아니다. **한국어 해요체**, 결론 한두 줄 먼저, 전문 용어·파일 경로·코드 이름은 꼭 필요할 때만.
- 사용자가 직접 할 일(가입·결제·비밀값·콘솔 설정)은 **번호 단계 + 실제 메뉴 이름**(한국어 화면이면 한국어, 괄호에 영어)으로. 휴대폰 웹 기준으로 안내하고,
  버튼이 안 보이면 '데스크톱 사이트'를 알려준다. 받을 값이 있으면 무엇을 보내 달라는지 끝에 목록으로.
- 비밀값(API 키·토큰)은 대화로 받지 않는다. GitHub Secrets 에 넣게 한다. 개인 정보는 공개 저장소에 적지 않는다.
- 사용자가 화면 캡처로 물으면: 원인이 데이터인지 표기인지 먼저 가리고(CLAUDE.md 4-4항), 쉬운 말로 설명한 뒤 고칠지 묻거나 고친다.
- 틀린 안내를 했으면 바로 인정하고 고친다 (예: 'Cloudflare 는 해외 업체가 아니다'라고 했다가 국외 이전 고지가 필요하다고 정정).

## 3. 작업 순서 (코드·설정·화면을 한 줄이라도 바꿀 때)

1. **백업 브랜치**: `git fetch origin main && git push origin "origin/main:refs/heads/backup/$(TZ=Asia/Seoul date +%Y%m%d-%H%M)-<이름>"`. 그 시각을 WORK.md 에 쓴다.
2. **기능 = 스위치**: 새 기능은 `docs/config.json` features 에 스위치를 두고 **명시적으로 false 부터** (적혀 있지 않으면 켜진 것으로 봄). 꺼지면 이전과 똑같이 동작해야 한다.
3. **고치기**. 화면은 `docs/index.html` 한 파일(정적 SPA). 판정 함수: eligibility·spJudge·myScore·grade 등.
4. **검증** (전부 통과해야 올린다)
   - 스크립트 문법: index.html 마지막 `<script>` 를 빼서 `node --check`
   - `python -m pytest -q`
   - `node tools/judge_check.cjs` → 144/144 (판정을 바꿨으면 `tools/make_judge_cases.py` 에 경계값 사례를 추가하고 다시 생성. 기대값은 공고문·법령 표로 따로 계산, 화면 코드로 얻지 않는다)
   - `bash tools/qa/regress.sh` → 의도하지 않은 판정 차이 0, 화면 오류 0
   - 바뀐 화면을 playwright 로 열어 **390px 폭, 밝은·어두운 화면** 스크린샷을 직접 보고 가로 넘침·오류 0 확인
   - 공고문에서 읽는 값을 바꿨으면 원문 대조·정답 데이터(`tests/golden/`)와 crosscheck
5. **기록**: WORK.md 항목(요청·변경·파일·확인·기능·백업), 새 기능이면 FEATURES.md 줄, 사용자에게 보이는 변경이면 `docs/changelog.json` 한 줄(판정이 바뀌면 '수정').
   서로 다른 기능은 커밋을 나눈다.
5-1. **버전** (CLAUDE.md 9항): 사용자에게 보이는 변경이면 changelog 항목에 `version`, VERSIONS.md 맨 위 줄, WORK.md `- 버전:`. 새 기능은 스위치로만.
6. **올리기**: `bash tools/qa/ship.sh <스위치|-> '<FEATURES 줄>' <WORK 항목 파일> "<메시지>" <파일...>` 그다음 FEATURES 커밋 번호 커밋.
7. **올린 뒤**: 버전을 올렸으면 `bash tools/qa/release.sh X.Y.Z` 로 release 브랜치를 남긴다. 그리고 Actions(수집·판정 검증·pages) 결과를 기다려 확인하고 `git pull` 후 `docs/run-log.txt` 의 `[검증]`·`[검증·공고문 불일치]`·`[경고]` 와
   `docs/verify-status.json` 의 `ok: true` 를 확인한다.
8. **HANDOFF.md '진행 중인 일' 갱신** 후 사용자에게 결과를 짧게 알린다 (무엇이 바뀌었나, 확인한 것, 사용자가 할 일).

## 4. 알아 둔 함정
- 새 '확인 필요'·'입력 필요' 문구를 만들면 바로 답하기(inline_fix)의 질문 매핑(FIX_KEYS·SP_FIX·PEND_FIX)에도 넣고 `node tools/qa/fixflow.cjs` 로 답한 뒤 판정되는지 확인한다. 사용자가 '입력했는데 계속 확인 필요'라고 하면 이 매핑부터 본다.
- 판정 정확도 점검은 블라인드 감사로: tools/qa/audit/README.md (검토자는 공고문·법령 원문만 보고, 앱 코드·결과는 안 봄). 불일치는 원문으로 누가 맞는지 가린 뒤 앱이 틀렸을 때만 사례 추가·수정.
- 판정 사례 기대값은 공고문 문장으로 따로 계산한다. 생성기 기본 프로필끼리 모순(예: 노부모 부양함 + 같은 등본 부모 0명)이 있으면 사례가 엉뚱하게 실패하니 먼저 의심.
- 문구 점검: tools/qa/textsweep.cjs → 문장 묶음 → 검토. 표 행·flex 칸이 붙어 보이는 것(예: '공고청약홈')은 추출 착시라 고치지 않는다. 약관·방침은 '-합니다'체가 맞다.
- ship.sh 가 '받기(pull) 실패'로 멈추면 커밋은 로컬에만 있다. 남은 변경(대개 tools/static_fragments.json)을 버리고 `git pull --no-rebase origin main && git push` 로 올린 뒤에 release.sh 를 실행한다 (release.sh 는 이제 올라가지 않은 커밋이면 멈춘다).
- 법제처 API 는 `Referer: https://cheongyakpass.kr/` 헤더가 없으면 '필수입력요소 검증 실패'. 별표와 서식은 번호가 겹쳐 `별표구분` 으로 가른다.

- index.html 템플릿 문자열 안에서 `//` 주석을 쓰면 뒤 코드가 주석이 된다. `/* */` 를 쓴다.
- 정적 페이지는 `node tools/snapshot_docs.cjs && python -m tools.build_static` (스크립트 경로로 실행하면 import 오류). verify.yml 도 다시 만든다.
  정적 /about/ 의 '마지막 검증' 시각, docs/notice/ 의 '데이터 수집' 시각만 바뀌는 diff 는 버린다 (`git checkout docs/about/index.html docs/notice tools/static_fragments.json`).
- 커밋 안 한 변경이 있으면 ship.sh 의 `pull --rebase` 가 실패한다. 먼저 정리하거나 stash.
- collect.yml 은 app/** 변경에도 돈다. 그 실행에서는 접수 전날 알림을 보내지 않는다(중복 방지). 수집 실행끼리는 concurrency 로 줄 선다.
- crosscheck 반올림은 half-up (파이썬 round 의 은행가 반올림 쓰지 않음). 예치금 표 열 순서는 공고문마다 다르니 머리글에서 읽는다.
- **출처 링크는 숫자가 실제로 보이는 화면**으로 (청약홈 경쟁률·특별공급 접수 현황 팝업, 모집공고문 PDF). API 안내 페이지 금지. 새 주소는 열어서 숫자 확인 후.
- 작업 환경에서 workers.dev·raw.githubusercontent.com 등이 막힐 수 있다. 배포 확인은 Actions 의 확인 단계와 커밋된 기록(push/deployed.json)으로.
- 웹 푸시: 알림 서버 `push/worker.js`(Cloudflare Workers, 무료 한도: 호출당 외부 요청 50·CPU 10ms → 10명씩 이어 받기). 바꾸면 `node push/test.mjs`
  + pytest(암호문을 따로 풀어 봄). push/ 를 올리면 push-worker.yml 이 자동 재배포. 미리보기는 `?push=preview`.
- 개인정보처리방침·이용약관 문구는 스위치(광고 `adsOn()`, 알림 `pushOn()`)가 켜질 때만 바뀌게 짜고, 시행일(`ads_legal_date`·`push_legal_date`)과 개정 이력을 같이 바꾼다. 개정은 7일 전 예고.

- 공고문에서 새 항목을 읽을 때(예: score_ratio): notice_pdf 에 parse_* 추가 → parse_notice 에 넣기 → pipeline 의 _from_previous·labels·from_notice 필터·L.<필드> 대입 → models 필드 → PARSER_VERSION 올림(모든 공고문 다시 읽음) → evidence/notices/*.txt 전체에 돌려 읽힘/unknown/None 개수 확인 → 원문 표를 직접 읽은 정답을 tests/golden 에(정답 비교는 model_dump 필드 이름으로 자동) → 화면 데이터 연결(index.html 의 LISTINGS 매핑 `x.<필드>`). 로컬 listings.json 에는 아직 없으니 브라우저 검사는 정답 값을 LISTINGS 에 넣어서 본다.
- 청약봇(chatbot): 판정 함수는 읽기만 한다 — tests/test_engine_lock.py 가 지문을 본다. 판정 규칙을 일부러 고쳤으면 판정 사례·회귀 후 `python -m tools.engine_lock --update`.
  청약봇 화면을 고치면 `node tools/qa/chatflow.cjs 40`(실제 서버 코드로 끝에서 끝), 서버를 고치면 `cd chat && node --test test/chat.test.mjs && node golden/eval.mjs`. 서버 답의 판정이 화면과 다르면 화면이 막는다.
  Worker 무료 CPU 10ms — 큰 파일을 서버에서 풀지 말 것(근거는 docs/chat-evidence/<번호>.json). 되물음 공짜는 질문 1건당 2번까지.
- 방침·약관 개정 예고는 config.json legal_notice(date·posted·privacy[]·terms[]) — '바뀐 뒤 전문'은 LEGAL_AS 로 알림·청약봇이 켜진 상태를 그린다. 새 기능 문구는 pushOn()/chatOn() 처럼 기능 값에 묶는다.
- 공고문 PDF 받기: 청약홈 첨부 서버가 Referer 없는 요청에 PDF 대신 짧은 HTML 을 줄 때가 있다(2026-10-02 여의재 1단지) — notice_pdf 가 Referer 로 다시 받는다. 한 번도 못 읽은 공고문은 `[경고] 공고문을 읽지 못한 공고` 로 이슈가 열린다. 실패 이유(스캔 PDF·HWP·HTML 내용)는 [공고문] 줄에 있다.
- 가점 비교 문구: 민영 1순위는 지역 순서가 먼저다. 가점 비교 점수(scoreTarget)는 reside(해당/기타)를 같이 들고 다니고, regionScore(L,p) 로 지역 순서·비율·경고를 만든다.

- 판정 규칙을 고칠 때 함정 (2026-10-01 감사):
  - 미입력값을 '없음'으로 보지 않는다 — DEFAULT_PROFILE 의 false 기본값(recentWin·spouseOwn)과 '' (hhHomes)는 '안 답함'일 수 있다. 판정에 쓰면 '확인 필요'로.
  - 특별공급(spJudge)은 eligibility 결과를 일부만 읽는다 — 일반공급에 새 요건을 넣으면 특공에도 필요한지 따로 본다 (재당첨·통장 종류·세대주 r1 이 빠졌었다).
  - 신혼희망타운은 순위·세대주가 없다 (regulatedItems·세대주 항목 제외). 소득 자격 상한(pub_limits.eligible)과 우선공급 기준(cap)이 다르다.
  - 판정 사례 기본 프로필에 everWin:'none' 이 있어야 재당첨 '입력 필요'가 안 생긴다. 테스트용 규제지역 변형 공고는 tests/judge/listings.json 의 '-REG'.
  - 변이 검사(tools/qa/mutation.cjs)의 허용 예외: 생애최초 단독세대 60㎡ (세대원이 되면 풀리는 게 규칙대로).

- 판정을 보여주는 곳이 여러 개다 (2026-10-02 과천 84D: 카드 '특별공급 확인 필요' ↔ 상세 '신청 불가'): 목록 카드 meLine·필터 eligBucket·상세 맨 위 rhero·
  지난 공고 '그때 넣었다면'·주택형 점. 새 판정 경로(예: gen_none)를 만들면 **모든 표시가 같은 함수(eligBucket)를 쓰게** 하고 `node tools/qa/consistency.cjs`(지금 공고 × 조건 40개) 로 확인한다.
  판정 사례는 '해당하는 사람'만이 아니라 '공통 조건(거주지·재당첨)에서 떨어지는 사람'도 넣는다.
- 원문 대조로 '틀렸다'고 보이면 고치기 전에 필드의 뜻부터 확인한다 (need_head = 공급 전체 대상이 세대주. 투기과열 1순위 세대주는 규제지역 규칙) — 판정 사례가 잘못된 수정을 잡아 줌.
- MASTER QA 검사 묶음(기능 qa_gate, 매 수집·화면 변경): supply_type.cjs · invariants.py · filter_check.cjs · consistency.cjs → verify-status. 손으로: code_mutation.cjs(판정 코드 바꿀 때), spotcheck_compare.py(원문 대조).

- 같은 판정을 여러 문장(spHeadPlain·spHeadline·spHowPlain·spPosition·spMinePlain·wsPlan)이 따로 말한다 — 뽑는 방식·세대수 문구를 고치면 전부 같이 고치고 `node tools/qa/sp_text.cjs` (2026-10-02: 공공 신혼 2단계를 한 줄 요약만 '점수 순', 노부모 90%를 70%로).
- `ship.sh … | tail && release.sh` 처럼 파이프 뒤에 && 를 붙이면 테스트가 실패해도 release 가 돈다 (release/v1.42.1 이 이전 상태로 만들어짐, 원격 브랜치 삭제는 막혀 있음). ship 결과는 파일로 받고 종료 코드를 본 뒤 release.
- evidence/pages·evidence/notices 일부는 Actions(근거 자료 모으기)가 매일 새로 받는다 — 테스트는 고정본(tests/qa/pages/)을 읽게 한다 (2026-10-02 LH 목록에서 계양 A6 가 밀려 수집 Actions 의 pytest 가 실패).
- 공공임대 공고는 공고문 <표4> 금액이 공공분양 '3인 이하' 표와 다르다 — 금액은 공고문 표 그대로(pub_limits.amounts·sp), 공통 표(spBase)를 쓰지 않는다. 정답 데이터는 <표5> 퍼센트 표에서 따로 계산해 대조.
- 원자료(국토부·청약홈)는 작업 환경에서 받을 수 없다. 원자료 대조 도구(market_check)는 Actions 에서만 돈다 — 로컬은 원자료 XML 모양 테스트로 계산만 확인.

- **모름(null)을 거짓으로 읽지 않는다** (2026-10-02 과천 벨라르테: `L.residenceDuty ? … : '실거주 의무 없음'` 이 null 을 '없음'으로, 다른 곳은 '있을 수 있음'으로 — 한 값이 세 가지 사실이 됨).
  화면에서 사실 필드는 `== null`(모름) · `=== 0/false`(없음) · 값(있음)을 따로 쓰고, 모름은 결과(전세·자금·판정)까지 '확인 필요'로 전파한다.
- 교차 규칙 검사 `node tools/qa/cross_rule.cjs`(규칙·근거·의존 그래프: evidence/qa/CROSS_RULES.md). 새 기능·새 필드를 만들면 '이 결과를 무효화할 수 있는 조건'을 규칙으로 추가한다(완료 조건).
- pytest 가 docs/chat-notice/*.json 을 다시 쓴다 — ship.sh 가 되돌리게 했지만, 손으로 커밋할 때도 pull 전에 `git checkout -- docs/chat-notice`.

- 입력값을 거르는 코드(cleanProfile 등)는 '나쁜 값이 지워지는지'뿐 아니라 '정상 값이 남는지'를 같이 검사한다 — 개수 칸을 0~30 으로 묶어 납입 인정 회차 170회가 새로고침 때 지워졌다 (2026-10-02). `node tools/qa/profile_keep.cjs`

- 스냅샷 기준을 처음 쓸 때 화면 글자를 사람이 한 번 읽는다 — v1.41.1 기준에 '납입 120회'인 조건이 '납입 인정 횟수 확인 필요'로 찍혀 있었는데(저장 값 정리 버그) 그대로 기준이 됐다.
- 거주의무 '모름'은 이유를 나눈다: 공고문 받기·읽기 실패 / 읽었지만 공고문에 거주의무가 아예 없음(duty_silent, LH 일부) / 문장 형식이 새로움(→ 규칙 추가, run-log [공고문] 줄로 원문 확인).

- 판정 범위 밖(judgeScope none)은 분양 규칙의 '불가'도 확정으로 쓰지 않는다. 새 공급유형·새 임대 유형을 받으면 먼저 judgeScope 에 넣고, 공고문 표를 읽어 정답 데이터를 만든 뒤 partial/full 로 올린다.
- `node tools/qa/monotonic.cjs` — 판정 코드를 바꾸면 돌린다. 위반이 나오면 먼저 검사 가정(예: 공고일 뒤 전입은 '모름'이 맞음, 모순 입력 해소)인지 판정 오류인지 가린다.
- `node tools/qa/past_chat.cjs` — 지난 공고 판정 줄·청약봇에 보내는 판정 요약(chatEnginePayload)이 상세 화면과 같은지. 상세 맨 위 판정 문구를 새로 만들면 HERO_TO_VERDICT 와 chatVerdict() 를 같이 고친다.
  chat/tools/engine_payload.cjs 는 화면 함수를 그대로 부른다 — 요약 모양을 따로 옮겨 적지 않는다.
- 공고문 값의 근거 문장(notice_quotes): parse_notice 에서 값을 넣을 때 `cite(키, 매치)` 를 같이 부른다. tests/test_notice_quotes.py 가 "문장에 그 값이 들어 있는지"를 원문 전부로 본다.
  ship.sh 가 git add 에서 실패하면 WORK.md·FEATURES.md 는 이미 고쳐진 상태 — `git checkout -- WORK.md FEATURES.md` 뒤 다시.

- 공고문 PDF 는 작업 환경에서 받을 수 없다 — 실제 PDF 점검은 probe.yml 의 tools/qa/pdf_audit.py 결과(evidence/qa/pdf-audit.json)로 본다. pypdfium2 는 여러 스레드에서 동시에 쓰면 깨진다(잠금 _PDFIUM_LOCK).
- Actions 작업 로그는 인증 없이 못 읽는다 — 실패하면 단계 이름과 로컬 재현으로 원인을 찾는다.

- **LH 임대: 기본값 0·false 칸은 '입력 안 함'일 수 있다 (2026-10-05 R3~R5)**: DEFAULT_PROFILE 의 소득·배우자 소득·현금·금융·보증금·배우자 주택(spouseOwn) 등은 0/false 로 시작해
  저장값만으로는 '0원이라고 답함'과 구분이 안 된다 → 입력 경로(data-field·data-set·날짜·답하기)가 `markSet` 으로 `_set` 에 적고, 임대 판정은 `entered()/pv()` 로만 읽는다(분양은 그대로).
  새 입력 경로를 만들면 markSet 을 꼭 부를 것(profile_keep.cjs 3번이 소득 칸으로 확인). 임대 판정에 새 칸을 쓰면 `pv()` 로 읽고, 모르면 check.
- **LH 임대 안전 검사**: `node tools/qa/lh_qa.cjs` 5번 '정보 감소 안전성'(내 조건 칸을 지우거나 공고문 기준을 못 읽은 것으로 바꿔도 새로 '가능'이 생기면 실패).
  세대 무주택은 hhHomes '0' 또는 1인 미혼 세대일 때만 확정, 무주택 완화 '2호 이상 제외'는 주택 수 '1'을 알아야 함, 완화 아닌 공고의 '미적용'은 믿지 않음, 모르는 계층은 판정 안 함(check).
  판정 사례 기본 프로필(lh_base)은 hhHomes '0' — 집이 있다고 한 사례는 생성기가 hhHomes '1' 로 맞춘다(어긋난 입력은 check). 파서 실패 모의는 tests/judge/lh_synthetic.json(생성기가 만듦).
  파서를 고친 뒤 화면 검사를 새 데이터로 돌리려면 `python -m tools.qa.lh_reparse`(docs/lh-rental.json 을 다시 만듦 — 끝나면 `git checkout docs/lh-rental.json`).

- **SH 공고(sh_rental)**: 게시판 첨부는 자바스크립트라 주소가 화면에 없다 — initParam.downList + /com/file/innoFD.do 로 받는다(tools/qa/sh_probe.py). 공고문 일정은 표(공고 ▶ 주택공개 ▶ 청약접수 …)로 된 것이 많아 '접수' 뒤 첫 날짜를 잡으면 틀린다 — 물결표 바로 앞 날짜만, 애매하면 비우고 정답(tests/golden/sh_rental.json)으로 고정. 작업 환경 WebFetch 는 innoFD 주소를 못 열어서 링크 확인은 Actions(sh_links.py)로.
- 로컬 전체 QA(e2e·변이 등)는 10분을 넘으니 백그라운드로 돌리고 기다린다. 끝나면 evidence/qa·docs/judge-status.json 바뀐 것은 되돌리고 커밋한다(결과물은 Actions 가 만든다).

- **SH 자격 판정(sh_judge)**: 엔진은 LH 의 rentalGroup 을 그대로 쓰고 SH 만의 칸이 있을 때만 다르게 돈다 — 새 규칙을 넣을 때 LH 공고 결과가 바뀌지 않게 '칸이 있을 때만' 조건으로. 판정 사례 생성기(make_judge_cases 18)도 같은 칸을 따로 옮겨야 하고, 검사 도구(lh_qa 답하기 채우기·cross_rule 소득 상한)도 새 질문·새 가산을 알아야 한다(모르면 '고리'·'충돌'로 거짓 경보). 애매한 공고 문장은 블라인드 검토자에게 원문만 주고 판정시켜 대조(evidence/audit/2026-10-06-sh/compare.cjs).
- **SH 장기전세·사회주택(sh_jeonse·sh_social, 10-07)**: 같은 엔진에 칸만 더함(terms.income_birth = 출산 소득 가산·맞벌이와 중복 없음, local.extra·others_check, terms.ref_date = 공고문 모집 공고일, 계층 일반·60이하/60초과·신혼부부·1인가구). 판정 결과는 계층 key 로 모으므로 한 공고에 같은 key 를 두 번 쓰면 덮어쓴다(장기전세 면적 묶음은 key 를 다르게). 사회주택 공고문은 운영기관마다 형식이 다르고 소득표 오기·지난해 표가 흔함 — 표를 도시근로자 2025 × % 와 대조해 다르면 비우고, 읽을 수 없는 공고는 None(판정 미지원)으로 두는 게 맞다. 게시일(posted)과 공고문 모집 공고일이 다를 수 있다.
- **되돌림 요청**: 사용자가 '원복'이라 하면 git revert --no-commit 후 기록 파일(WORK·changelog·VERSIONS·FEATURES)은 HEAD 로 되돌려 기록은 남기고, 코드가 추가 직전 커밋과 같은지 git diff 로 확인(10-07 draw_path).
- **실거래가 쪽 넘기기**: 해제 거래를 걸러 낸 뒤 건수로 마지막 쪽을 판단하면 꽉 찬 쪽 다음을 놓친다 — 응답 원래 건수로(app/sources/rtms.py parse_page). market_check(독립 대조)가 이런 차이를 잡는다.

- **빈칸 = 모름(2026-10-06)**: 기본값이 0·false 인 칸(ZERO_KEYS)은 entered()/pv() 로만 값으로 본다(_set). 새 판정 규칙에서 `p.x || 0`·`p.x > 0` 으로 쓰면 빈칸을 값으로 보게 된다 → tools/qa/zero_default.cjs 가 잡음. 판정 사례·QA 고정 조건은 '모두 입력함'(_set)으로 만들고, 빈칸을 보는 사례만 _set 을 빼서 준다.

- **입력 버튼 → 칸 (2026-10-07)**: '입력하기·바로 답하기'는 확인 문구 낱말로 칸을 고른다(FIX_TARGETS). 문구에 다른 칸 이름이 섞이면(예: '배우자 명의'→명의, '집 보유와 세대 구성'→세대 구성) 엉뚱한 칸으로 간다. 판정 칸이 정해져 있으면 항목에 fk 를 달 것. 확인은 tools/qa/input_nav.cjs.

- **공고문 표 값은 표 머리 글자만 믿지 말고 그 아래 금액 줄로 교차확인한다 (2026-10-08 계약금 비율).** 한 공고문에 본 표·발코니 확장·플러스옵션·가전 표가 모두 '계약금(10%) 중도금(..)' 머리를 가진다. 제목 낱말(확장·옵션)로 거르면 진짜 표를 버리고(제목이 본 표 머리 근처에 섞임) 옵션 표를 고른다. 대신 '집값 T · 계약금 a' 줄이 a = T × % 인지, 다음 칸이 중도금 % 와 맞는지로 확인하고, 서로 다른 비율이 남으면 읽지 않는다(추정 표시). 단위(원·천원·만원)와 만 원 절사를 허용한다. 새로 읽는 표 값에는 머리를 보지 않는 독립 점검(tools/qa/pay_audit.py 처럼)을 함께 만들어 verify_status 관문에 건다. 정답은 파서 결과를 보지 않은 에이전트에게 원문을 읽혀 블라인드 대조한다

- **collect 를 손으로 돌리면 그날 예약 수집이 건너뛸 수 있다 (2026-10-08).** 예약 실행은 docs/daily-run.txt 가 오늘이면 gate 만 돌고 '성공'으로 끝난다(실제 수집 없음). 05시 전 손 실행은 이제 표시를 적지 않지만, 05시 뒤에 손으로 돌리면 그날 표시가 적힌다. 실행 목록의 '성공'만 보지 말고 docs/updated.txt 시각을 확인한다

- **지금 목록에 없는 공고 종류를 판정하려면 지난 원문부터 모은다 (2026-10-08 SH 행복주택·청년안심).** tools/qa/sh_archive.py(SH 임대 원천 점검)가 게시판을 80쪽 넘겨 종류별 원문을 evidence/qa/sh-archive/ 에 둔다. 정답은 올해 공고(소득표가 도시근로자 2025 와 같은 것)로, 지난 공고는 '소득 비움(확인)'이 되는지만 본다. 화면 확인은 docs/sh-rental.json 에 그 공고를 임시로 넣고(커밋하지 않음) #/rdetail/SH-<글번호> 를 390px 로 연다. 같은 법령 기준(행복주택)은 LH 읽기 규칙을 그대로 쓰고 SH 모양(절 제목·'만 원')만 맞춘다. 순위마다 기준이 다르면(청년안심 청년) 묻지 않는 값(부모 소득)으로 갈리는 쪽은 '확인'으로 둔다

- **공고문 표 머리글은 낱말이 띄어 쓰일 수 있다 (2026-10-08 '기관 추천 다자녀 가구 신혼 부부').** 머리글 낱말로 칸을 셀 때는 공백을 빼고 찾는다. 칸 수가 하나라도 틀리면 '조용히 버림'이 되므로, 버린 결과가 화면에 '없음'으로 보이는 항목(재공급 물량 등)에는 불변식을 함께 둔다. 자동 검증 경고(마진율·근거 건수)는 공급 종류(처음 분양가로 공급하는 재공급)를 고려해 정상을 이상으로 띄우지 않게 한다

## 5. 자주 하는 답

- "자동으로 돌아가?" → 수집은 GitHub Actions 가 매일 05:30, 사이트는 GitHub Pages. Claude 세션과 무관하게 돈다. 실패·불일치는 이슈로 메일이 간다.
- "경쟁률·숫자 출처?" → 청약홈 화면(경쟁률 팝업·특별공급 접수 현황)과 모집공고문. 링크는 숫자가 보이는 화면으로.
- 오픈카톡 청약봇 질문 답변은 별도 스킬(cheongyak-bot-answer)이 있으면 그것을 따른다.
- 청약홈 일반공급 세대수(households)가 0 인 주택형이 있다: 신혼희망타운(전 물량이 특공 칸), 특공만 있는 주택형, 사전청약 당첨자 몫으로 이번 공급 0, 재공급(특공만). 일반공급 자격만 보고 '신청 가능'을 내면 틀림 → genNone/no_supply(기능 gen_none). 판정 바꿀 때 regress 의 'bucket changes' 로 목록 판정 변화를 본다.
- Actions 실패 원인: 로그는 인증이 필요하지만 `curl https://api.github.com/repos/cheongyak/cheongyak.github.io/check-runs/<job id>/annotations` 로 exit code 를 볼 수 있다(139 = 세그폴트). job id 는 runs/<run id>/jobs.
- C 라이브러리(pypdfium2 등)는 수집 프로세스 안에서 부르지 않는다 — 죽으면 수집 전체가 멈춘다. 따로 띄운 프로세스로.
- Actions concurrency: 수집(collect) 묶음에 다른 워크플로를 넣지 않는다 — 대기 실행이 하나만 남아 수집이 취소된다(2026-10-03). 데이터를 쓰는 워크플로는 자기 묶음 + `tools/qa/wait_collect.sh` 로 수집이 끝나길 기다린다.
- 이전 정상값 지키기 (2026-10-03 사용자 '최신 수정이 이전 정상값에 영향을 주지 않게'):
  ① 공고문 읽기 규칙(app/notice_pdf.py)을 고치면 tests/test_parse_snapshot.py 가 원문 109건+ 읽기 결과를 기준(tests/qa/parse_snapshot.json)과 비교 — 다르면 실패. `python -m tools.qa.parse_snapshot` 로 바뀐 값을 보고, 원문과 대조해 모두 의도한 변경일 때만 `--update` 하고 WORK.md 에 바뀐 공고·값을 적는다.
  ② 수집·지역·시세·판정에 닿는 변경을 올린 뒤에는 `git show <수정 전 데이터 커밋>:docs/listings.json > /tmp/base.json && NODE_PATH=$(npm root -g) node tools/qa/verdict_diff.cjs /tmp/base.json` — 주택형×판정 사례 내 조건 전부의 판정 전후 비교, 데이터가 그대로인데 판정이 바뀐 곳(예상 밖)이 0이어야 한다.
- notice_pdf.py 안에 같은 이름 도우미가 이미 있을 수 있다(_ymd 는 parse_residence 가 씀) — 새 도우미는 접두어를 붙인다(_rs_ymd). 새 parse_* 를 넣으면 parse_notice 전체를 원문 109건에 한 번 돌려 본다.
- ship.sh 는 추적하지 않는 새 파일(??)이 있어도 pull --rebase 에서 멈춘다 — 다른 작업 파일은 `git stash push -u -- <파일>` 로 치운 뒤 올리고 `git stash pop`.
- 화면 '당첨되면 걸리는 제약' 값 칸은 좁다(390px) — 값은 '6개월 (~27.03.22)'처럼 짧게, 자세한 문장은 공고문 문장(notice_quotes)으로.
- 모델에 새 필드를 넣으면 test_notice_retry 의 '다른 공고 한 글자도 안 바뀜'이 새 칸(null) 때문에 깨진다 — 그 시험은 원래 있던 칸만 비교하게 고쳐 둠.
- 법령: 주택공급에 관한 규칙은 evidence/law/, 공공주택 특별법 시행규칙(청년·공공임대 자격 별표 6의2~6의6 등)은 evidence/law/public/ (법령 원문 받기 Actions). rule.xml 은 CDATA 를 먼저 벗겨야 본문이 보인다.
- index.html 은 한 스크립트라 같은 이름 함수를 다시 선언하면 오류 없이 앞의 것을 덮는다(2026-10-05 rentalCard 충돌 — 스냅샷 검사가 잡음). 새 함수는 접두어(lh…)를 붙이고 tests/test_index_names.py 가 겹침을 본다.
- LH 임대(기능 lh_rental)는 분양과 완전히 따로: 수집 app/lh_rental.py·읽기 app/lh_terms.py·화면 rentalJudge. 공고문 정답은 tests/golden/lh_rental.json, 판정 사례 lhrent-*. LH 첨부(apply.lh.or.kr)는 작업 환경에서 못 받는다 — Actions 가 받은 글(evidence/lh/)로 작업.
- PDF 표에서 숫자가 붙어 나오는 일이 흔하다('1,259,7882,099,646'). 공백으로 칸을 세지 말고 천 단위 쉼표 규칙 `\d{1,3}(?:,\d{3})+` 로 떼고, 다른 칸과의 관계(30% 칸 ÷ 0.3 = 100% 칸, 총공급 = 특공 합 + 일반)로 확인한다. 정답 데이터에 값이 있으면 **테스트가 그 칸을 실제로 비교하는지** 본다 — 2026-10-05 기준 중위소득 표는 정답에 맞는 값이 있었는데 테스트가 비교하지 않아 110% 열을 쓰고 있었다.
- LH 공고문은 세 도구로 읽는다(기능 lh_pdf_multi): 읽기 규칙(app/lh_terms)을 고치면 `python -m tools.qa.lh_pdf_tools` 로 도구별 맞음·틀림을 본다 — 규칙이 pypdf 글에만 맞춰져 pdfplumber 글에서 틀리면 합칠 때 과반으로 걸러지지만, 두 도구가 같이 틀리는 규칙은 안 된다. 다른 도구 글은 Actions 만 만들 수 있다(LH 첨부는 이 작업 환경에서 403). 임대조건 표는 줄 단위로 섞지 않는다(도구마다 주택형·구분 이름이 달라 다른 줄끼리 짝지어짐).
- LH 임대 QA 묶음(일반분양과 같은 수준): lh_invariants.py · lh_qa.cjs · lh_rental.cjs · cross_rule.cjs(LH-*) · `E2E_ONLY=lh node tools/qa/e2e.cjs`(빠른 LH 흐름만) · textsweep · blind_sample(lh_samples). 함정: ① 임대 상세는 S.id 가 아니라 S.rid — 주소·history 에 따로 넣어야 새로고침이 됨 ② textsweep 처럼 localStorage.clear() 하면 미리보기(cy-lh-preview)도 꺼져 임대 화면이 안 그려진다 ③ e2e 에서 '공고명이 보이면 상세'로 보면 안 됨 — 목록 카드에도 이름이 있다(상세 = [data-ropen] 없음) ④ 교차 규칙은 '가능'일 때만 보므로, 다른 조건은 다 충족하는 프로필을 넣어야 규칙이 실제로 걸린다(변이로 확인)
- LH 임대 판정을 고치면 `node tools/qa/lh_qa.cjs`(퍼징·단조성·답하기 고리·카드=상세)와 judge_check 를 돌린다. 새 요건은 블라인드 감사(evidence/qa/lh-audit/README.md 방식: 공고문·별표만 읽는 검토자)로 확인 — 10-05 감사에서 영구임대 신청자격 거주 요건('○○시에 거주하는 성년자인'), 지원주택 직업기준 주민등록 같은 빠진 요건이 나왔다.
- 임대 '확인' 항목은 q(답할 칸)를 붙여야 화면에서 '답하기'가 생긴다. q 없이 남는 확인은 lh_qa 의 '답할 칸 없는 확인' 목록에 나온다.
