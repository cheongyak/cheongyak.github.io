# 이어서 작업하기 (새 세션용 인수인계)

새 세션은 이 파일 → `CLAUDE.md` → `WORK.md` 최근 항목 5개 → 열린 이슈 순서로 읽고 시작한다.
작업 순서·검증·함정 같은 노하우는 `.claude/skills/cheongyakpass-ops/SKILL.md` 에 있다.
작업을 마칠 때마다 아래 **진행 중인 일**을 최신으로 고친다 (CLAUDE.md 8항).
이 저장소는 공개 저장소다. 인증키·개인 연락처·계정 명의 같은 개인 정보는 여기에 적지 않는다.

## 사용자와 일하는 방식

- 사용자는 서비스 운영자다. 개발자가 아니므로 **쉬운 한국어**로, 결론 먼저, 필요한 것만 설명한다.
- 계정 가입·결제·비밀값 입력처럼 사용자가 직접 해야 하는 일은 **화면 메뉴 이름(한국어 화면이면 한국어, 괄호에 영어)까지 단계별로** 안내한다.
  비밀값은 GitHub Secrets 에만 넣게 하고, 대화로 받지 않는다.
- 사용자는 휴대폰으로 확인하는 경우가 많다. GitHub 화면 안내는 휴대폰 웹 기준으로 한다 (버튼이 안 보이면 '데스크톱 사이트').
- 신뢰가 가장 중요하다: 판정·수치는 공고문·법령 원문으로 검증한다 (CLAUDE.md 4항).

## 새 세션에서 환경 준비

```bash
pip install -r requirements.txt            # 테스트: python -m pytest -q
npm i --no-save playwright@1.56.0          # 화면 검사용. 크로미움이 /opt/pw-browsers/chromium 에 있으면 그걸 쓴다
```

- `gh` CLI 가 없을 수 있다. Actions 실행 결과는 공개 API 로 본다:
  `curl -s "https://api.github.com/repos/cheongyak/cheongyak.github.io/actions/runs?per_page=6"`
- 이 작업 환경은 태그 push 가 막혀 있어 백업은 브랜치(`backup/YYYYMMDD-HHMM-이름`)로 한다.
- 외부 사이트(workers.dev, raw.githubusercontent.com 등)는 작업 환경에서 막힐 수 있다. 배포 확인은 Actions 결과로 한다.

## 도구

| 하는 일 | 명령 |
|---|---|
| 커밋 (테스트 → WORK.md·FEATURES.md 기록 → 커밋 → 올리기) | `bash tools/qa/ship.sh <스위치\|-> '<FEATURES 줄>' <WORK 항목 파일> "<메시지>" <파일...>` |
| 버전 브랜치 남기기 (올린 뒤) | `bash tools/qa/release.sh X.Y.Z` (VERSIONS.md·changelog 에 그 버전이 있어야 함) |
| 화면 회귀 (origin/main 과 판정 1,030개 조합 비교 + 화면 1,287개 오류) | `bash tools/qa/regress.sh` |
| 판정 검증 사례 144건 (화면 판정 함수) | `node tools/judge_check.cjs` (기대값 생성: `python -m tools.make_judge_cases`) |
| 검증 현황 모으기 | `python -m tools.verify_status` → `docs/verify-status.json` 의 `ok` |
| 정적 페이지 다시 만들기 (/story/ /guide/ 등) | `node tools/snapshot_docs.cjs && python -m tools.build_static` (verify.yml 도 자동으로 함) |
| 알림 서버 검증 | `node push/test.mjs` (pytest `tests/test_webpush.py` 가 결과 암호문을 따로 풀어 본다) |
| 화면 스크립트 문법 | index.html 마지막 `<script>` 를 파일로 빼서 `node --check` |

## GitHub Actions

| 워크플로 | 언제 | 하는 일 |
|---|---|---|
| 청약 공고 수집 (collect.yml) | 매일 05:30, app/ 변경 시 | 수집·시세·등급 → 공고문 대조 → 판정 검증 → 알림 발송 → 문제 있으면 이슈 |
| 판정 검증 (verify.yml) | 화면·판정 파일 변경 시 | 판정 검증 사례, 정적 페이지 재생성 |
| 근거 자료 모으기 (probe.yml) | 변경 시 | tools/rules_probe.py |
| 알림 서버 배포 (push-worker.yml) | push/ 변경 시, 수동 | Cloudflare Workers 배포 → push/deployed.json |
| 알림 테스트 발송 (push-test.yml) | 수동 | 구독한 모든 기기에 테스트 알림 한 통 |
| 법령 원문 받기 (law-probe.yml) | 매주 월 06:10, 도구 변경 시, 수동 | 법제처 OPEN API 로 주택공급에 관한 규칙 본문·별표 1·2 → evidence/law/ (Referer 헤더 https://cheongyakpass.kr/ 필수) |

GitHub Secrets (이름만): `DATA_GO_KR_KEY`, `NCP_MAPS_CLIENT_ID`, `NCP_MAPS_CLIENT_SECRET`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `PUSH_SEND_TOKEN`, `LAW_OC`(법제처 API, 2026-10-01 사용자 등록)

## 진행 중인 일 (2026-10-01 기준, 최신이 위)

-2. **화면 개선 5가지 (2026-10-01 밤, 사용자 휴대폰 캡처 요청)** — v1.21.0 money_echo(금액 칸 아래 '= 2억 1,550만원'), v1.22.0 date_select(날짜를 년·월·일 드롭다운),
   v1.23.0 score_lottery_split(일반공급을 1순위 가점제 N%·추첨제 M% 두 줄로, 가점 낮아도 추첨 물량 있으면 '추첨제 가능'; 무주택 우선 75%는 규제지역·수도권·광역시만 — 공고문 25건 대조),
   v1.24.0 type_group(목록에서 같은 공고 주택형을 카드 하나+주택형 칩, 상세 제목 아래 주택형 칩). 사용자가 '되돌리자' 하면 각 스위치 false.
   후보: 주택형 칩이 많은 공고(7개 이상)에서 칩 줄이 길면 면적대(59·84) 묶음 검토.
   v1.24.1: 일반공급 표시를 '신청 가능 → ① 가점제 먼저 → 떨어지면 자동으로 ② 추첨제' 순서 + 내 가점 위치 + 근거(공고문·HUG). v1.25.0 search_icon: 검색을 맨 위 돋보기 버튼으로.
   급매캐치 앱 참고 UI (사용자 선택, 2026-10-01 밤): v1.26.0 alerts_tab(알림을 하단 탭으로 — 알림 공개 전엔 미리보기 기기만 보임), v1.27.0 top_filters(필터를 검색 아래 맨 위에 펼침),
   v1.28.0 detail_cta(상세 아래 고정 '모집공고문·청약홈 공고 보기'), v1.29.0 price_compare(상세 가격 비교 카드), v1.30.0 type_rank(이 공고 주택형 중 마진 순위), v1.31.0 grade_medal(목록 원형 등급 배지).
   사용자가 ⑥ 배지 뜻 안내는 하지 말라고 함.
   v1.32.0 top_compact(맨 위 필터 지역·분양가·면적·상세 + ↻ 초기화, 칩 32px, 내 조건·요약 작게), v1.33.0 dismiss_notes(목록 베타·개정 안내 ✕ — 상세·방침 안내는 그대로).
   v1.34.0 detail_tidy(2026-10-02, 사용자 '기능을 막 추가해 복잡함 — 중복 통합'): 상세 위 링크 버튼·타일·마진 칸·주택형 카드·체크리스트 요약·특공 세대수 숨기고 판정 칸(가점·자금·특별공급)·가격 비교 카드(주택형 순위·마진 계산 자세히)로 합침. 상세 구역 탭 '마진' 없어짐.
   v1.34.1 아래 고정 버튼에 자금 플랜, v1.35.0 supply_split(자격 → 일반공급·특별공급 카드, 탭도), v1.36.0 score_in_general(내 가점·근처 경쟁률을 일반공급 칸 안으로, '가점·경쟁률' 탭 없앰),
   v1.36.1 무순위(needAccount=false)는 가점 안내 대신 '청약통장·가점 없이 추첨'(판정 칸·일반공급 칸·가점 컷 카드), 탭 이름은 공고 종류대로·특별공급 없으면 탭 없음.
   다음 (사용자와 상의 중): 가점 컷 탭 개편 — 안: '내 가점' 탭(내 점수·오르는 날 / 관심 공고 한 줄 요약 / 지역별 당첨 컷에 내 점수 표시).
-1. **청약봇 '이 공고 물어보기' (chatbot, v1.20.0) + 방침·약관 개정 예고 (legal_notice, v1.19.0) — 2026-10-01 밤**
   - 개정 예고 게시 2026-10-01, **시행 2026-10-09** (config.json legal_notice). 내용: 새 공고 알림(4-2)·AI 질문 답변(4-3) 처리 위탁·국외 이전, 약관 제4·6조. 시행일이 지나면 예고 카드는 저절로 사라짐.
   - **10-09 에 할 일 (사용자 확인 후)**: ① 알림 공개 — `push_legal_date: "2026-10-09"`, 스위치 `web_push: true`, `push_preview` 제거, changelog '새 기능'.
     ② 청약봇 공개(미리보기에서 괜찮다고 했을 때만) — `chat_legal_date: "2026-10-09"`, chat/worker/wrangler.toml `CHAT_OPEN = "1"`(푸시하면 재배포), 스위치 `chatbot: true`, changelog 의 1.20.0 internal 해제 또는 새 항목.
     청약봇이 늦어지면 ①만 하고 chat_legal_date 는 청약봇을 켤 때 넣는다 (예고는 이미 했으므로 다시 예고할 필요 없음 — 단, 개정안에 적은 처리 내용(4-3항)을 바꾸면 다시 예고).
   - **사용자가 할 일 (아직 안 함)**: Anthropic 콘솔(platform.claude.com) 가입·크레딧 $5~10·Spend limits 월 $30·API 키 발급 → GitHub Secrets `ANTHROPIC_API_KEY`, `CHAT_PREVIEW_CODE`(본인이 기억할 코드), `CHAT_STATS_TOKEN`(긴 무작위).
     비밀값이 들어오면 Actions '청약봇 서버 배포'를 다시 실행(workflow_dispatch) → chat/deployed.json 의 주소를 docs/config.json `chat_api` 에 넣고 올림 → 사용자에게 `https://cheongyakpass.kr/?chat=preview` 안내.
   - 키가 생기면 `cd chat && ANTHROPIC_API_KEY=… node golden/eval.mjs`(Actions 에서, 키를 대화에 쓰지 않게 — 필요하면 eval 워크플로를 만든다)로 실제 답 270문항: 검사기 거절률·대체율 보고 프롬프트 v2.
   - 구조: 화면은 판정 함수를 읽기만(tools/engine_lock.py 가 28개 함수 지문 확인 — 판정 규칙을 일부러 고치면 `python -m tools.engine_lock --update`). 서버 chat/worker(검사기 통과 답만, 두 번 막히면 고정 문구), 근거 docs/chat-evidence(probe.yml 이 나눔).
     검사: `cd chat && node --test test/chat.test.mjs` · `node golden/eval.mjs` · `NODE_PATH=… node tools/qa/chatflow.cjs 40`. 하루 합계는 run-log `[청약봇]`.
   - 다음 단계 후보: 근거 조각 고르기 개선, 새 공고 근거를 매일 수집에 넣기(지금은 probe.yml 실행 때만), 평가 '정보가 틀렸어요' 많으면 원인 분석, 캐시는 하루 수백 건이 되면.

0. **버전·전략 실행 현황 (2026-10-01 오후)** — 지금 버전 v1.36.1 (VERSIONS.md, release/v1.0.0~v1.36.1 브랜치). v1.3.1~1.3.3 은 사용자 지적 수정: 관심 공고 유주택 '추첨제만', 시·도 검색, 이용 안내 '업데이트 소식'(검증 현황·상세 내역은 운영자용 — 사용자가 물으면 verify-status.json·changelog.json·VERSIONS.md 로 답함).
   v1.6.2~v1.7.3 (2026-10-01 오후): 출산가구 완화 범위(+10%p 확인 가구는 +20%p 가능 → 그 사이 '확인 필요'), 가점 부양가족 설명 법령대로, score_scope(2순위·규제지역 유주택은 가점 안 쓰임 안내),
   세대 주택 명의 모름 → 공공·특공 무주택 '확인 필요', 노부모부양 같은 등본 요건, 화면 문구 전체 점검. 판정 검증 사례 165건.
   판정 정확도 블라인드 감사(tools/qa/audit/, 결과 evidence/audit/2026-10-01/): 무작위 40건 일반공급 34/40 → 원인 분석 후 앱 오류 1건(A40) 고침, 나머지는 감사 프로필 모호함·검토자 오해(가점 무주택기간은 신청자·배우자 기준이 맞음).
   특별공급 경계 16건: 일반 16/16·가점 12/12·특공 14/16(2건 고침). v1.7.4 에서 청약통장 미입력 + 1순위만 막힘은 '확인 필요'로 고침(rank2Need). v1.8.0: 바로 답하기 inline_fix(공고 상세에서 필요한 질문만 펼쳐 답하면 바로 판정, 검사 tools/qa/fixflow.cjs — 질문 매핑 FIX_KEYS·SP_FIX·PEND_FIX, 새 '확인 필요' 문구를 만들면 매핑도 추가하고 fixflow 로 확인). v1.7.5: 세대 주택 명의 질문 hhOwner(만 60세 이상 부모님/그 밖의 세대원) 추가, 특공이 명의 모름을 무주택으로 보던 오류 수정(사용자 지적).
   문구 점검 도구 tools/qa/textsweep.cjs (무작위 프로필로 전 화면 문장 수집) — 화면 문구를 크게 바꾸면 다시 돌려 검토.
   UX 점검(2026-10-01 저녁, 사용자가 공유한 UX 법칙 Hick·Fitts·Jakob·Proximity·Von Restorff): v1.10.0 feed_compact(목록 첫 화면에 공고), v1.11.0 detail_result_first(상세 맨 위 내 판정), v1.12.0 tap_targets(누르는 영역 44px), v1.13.0 detail_nav(구역 탭·순서), v1.14.0 beta_compact(베타 안내 한 줄). 사용자가 '별로면 되돌리자'고 함 — 되돌리기는 각 스위치 false.
   v1.15.0 region_first_score (2026-10-01 저녁, 사용자 질문 '가점이 우선이야, 거주지역이 우선이야?'): 민영 1순위는 ①지역 → ②가점(공고문 '당첨자 선정 순서'). 일반공급 줄·관심 카드·가점 카드에 '해당지역(먼저) → 그 안에서 가점', 비교 점수를 '해당지역/기타지역 당첨선'으로, 공고문 '전용면적별 가점제/추첨제 적용비율' 표를 새로 읽음(score_ratio, PARSER_VERSION 10, 정답 4건), 기타지역 경고. 비율을 못 읽은 민영 공고는 [검증] 에 남음(예: 2026000436 표 글자 뒤섞임 — 사람이 원문 확인 후 규칙 보완 후보).
   v1.16.0 tap_affordance (사용자: 접힌 줄이 글자처럼 보여 눌러야 하는지 헷갈림): details 펼치기 줄을 테두리 버튼 + 화살표로. 새 접힘 칸을 만들 때 details 를 쓰면 자동 적용(.sprow·.scitem·.menudet 는 각자 모양).
   v1.16.1 판정엔진 감사(2026-10-01 밤, 사용자 요청 '판정 알고리즘을 해부해 공식 기준과 대조, 경계값·변이·실제 공고 정답 테스트, 감사보고서'): 보고서 evidence/audit/2026-10-01-engine/REPORT.md
     (사용자에게는 Claude 문서 '청약패스 판정엔진 감사보고서'로 전달). 법령·공고문 대조 검토자 3명 + 블라인드 검토자 4명(공고 40건 × 프로필 160건) → 29건 수정(CRITICAL 2·HIGH 8),
     판정 사례 175 → 236건, 변이 검사 도구 tools/qa/mutation.cjs(위반 0), 블라인드 FP·FN 0, 가점 76/76. 다시 감사할 때: tools/qa/audit/audit_gen2.cjs(층별 사례) → 검토자에게 brief2.md + cases(앱 판정 파일은 숨김)
     → tools/qa/audit/rejudge.cjs 로 지금 앱 판정 → 비교. 생성기의 통장 ''는 앱에서 '미입력'이라 'none'으로 바꿔 다시 판정(noacct).
     남은 위험 O1~O4 는 v1.17.0 optional_inputs 로 처리(주택 소유 예외·공유지분 문구·소득 시점 안내·배우자 처분일·당첨 종류 질문).
   v1.17.0 optional_inputs — 사용자 방침(2026-10-01): 드물게 해당하는 질문은 '해당하는 분만', 비우면 해당 없음으로 판정(optDefaults). 필수/조건부/선택 구분은 질문의 skip 표시와
     optDefaults 목록이 기준. 새 질문을 만들 때 드문 경우면 skip:'해당 없음' 과 OPT_NONE 에 기본값을 함께 넣는다. 판정이 바뀌는 쪽(비우면 '가능'이 될 수 있는 것)은 넣지 않는다.
   v1.18.0 fix_focus: 바로 답하기에서 필요한 칸을 빨간 테두리로 맨 위·포커스, 닫기 대신 저장(pointerdown 처리). 새 '확인 필요' 문구를 만들면 FIX_TARGETS 에 질문 키를 연결하고 tools/qa/fixfocus.cjs 로 빨간 칸이 다 나오는지 확인.
   사용자 방침(2026-10-01): 이용 안내는 메뉴(about_menu)만 — 업데이트 소식·청약 기준 가이드는 공개하지 않고 changelog.json·VERSIONS.md·WORK.md 로 내부 관리. 사용자가 물으면 그 기록으로 답한다.
   사용자 방침(2026-10-01): 서비스는 '입력한 정보 기준으로 신청 가능/불가'만 판정한다. 부적격(실제 정보와 다르게 신청)은 본인이 검토 — 공지성 카드는 만들지 않음. inelig_check 는 v1.8.2 에서 끔.
   v1.6.0: 신청 전 부적격 방지 체크 inelig_check (공고 상세 카드, 근거는 법령 원문 제2·4·28·53·55·58조, tests/test_law.py 가 원문과 대조). v1.5.0: '확인 필요' 원인별 다음 행동 unsure_actions (내 조건 카드 '확인 필요를 줄이려면' + 항목별 버튼). v1.4.2: 답하면 판정되는 항목(가구원수)을 '판정하지 않는 항목'과 분리.
   판정 개선 후보(아직 안 함, 판정 사례 추가 필요): 공공 일반공급 소득 '출산가구 완화 확인 필요' — 미성년 자녀 1명·임신 아님이면 최대 +10%p 라 +10%p 초과분은 '불가'로 확정 가능.
   v1.4.1: 2순위만 가능한 공고를 빨간 '불가' 대신 노란 '2순위만'으로(사용자 지적). 상세 '내 청약 가점'은 2순위(추첨)에도 가점 비교를 보여 줌 — 사용자가 또 헷갈려 하면 rank2 일 때 가점 카드에 '2순위는 추첨' 안내를 검토.
   v1.4.0: 청약 기준 가이드를 법령 원문(주택공급에 관한 규칙 별표 1·2, evidence/law/rule.xml)으로 다시 엶. 소득 기준표는 공고마다 달라 만들지 않음. 법령이 개정돼 값이 앱 수치(ACCOUNT_DEPOSIT·가점표)와 달라지면 tests/test_law.py 가 실패 → 원문 확인 후 앱·판정 사례를 고친다.
   - 끝남: 확인 필요 행동 버튼(v1.5.0), 부적격 방지 체크(v1.6.0), 버전 관리(v1.0.1), 사용 측정 usage_metrics(v1.1.0, GoatCounter 이벤트 m/…), 안 쓰는 코드 정리(ntfy 삭제), 공고별 페이지 notice_pages(v1.2.0, /notice/), 빠른 시작 quick_start(v1.3.0)
   - 사용자 결정(2026-10-01): '내 청약 현황'은 만들지 않음, 내 조건 카드 '확인 필요를 줄이려면'(unsure_summary)은 끔(v1.6.1).
   - 다음 후보(보고서 순서): 가점 오르는 날 → (사용자 결정) '비추천' 등급명 → _v2 이전 분기 정리 → 엔진 분리·청약봇(오픈카톡 질문 로그 필요)
   - 측정 확인: 1~2주 뒤 GoatCounter 대시보드에서 m/visit·m/profile·m/quick·m/verdict·m/unsure 이벤트를 보고 다음 우선순위를 정한다

1. **웹 푸시 알림 (`web_push`) — 운영자 미리보기 중**
   - 알림 서버 배포됨: `push/deployed.json` 의 주소, `docs/config.json` 의 `push_api`. `push_preview: true`, 스위치 `web_push: false`.
   - 사용자는 휴대폰에서 `https://cheongyakpass.kr/?push=preview` 로 열어 알림을 켜고 확인하는 중. 테스트는 Actions '알림 테스트 발송'.
   - 2026-10-01 12:45 사용자 확인: 안드로이드 휴대폰에서 알림이 잘 옴. 아이폰은 아직 확인 안 함 — 홈 화면 앱이 Safari 와 저장 공간이 달라
     미리보기 표시(`cy-push-preview`)가 안 넘어갈 수 있음 → 사용자가 알려주면 홈 화면 앱에서도 켤 방법을 만든다.
   - 공개 순서: 개인정보처리방침 개정(4-2 처리 위탁·국외 이전 등, 이미 만들어 둠) **시행 7일 전 예고** → `push_legal_date` 설정 →
     시행일에 `web_push: true`, `push_preview` 제거, `docs/changelog.json` 에 '새 기능' 줄. 개정 예고 배너 기능은 아직 없음(만들어야 함).
2. **광고 (`ads`) — 꺼 둠, 사용자가 2026-10-01 오후 애드센스 신청 진행 중**
   - 사용자가 `ca-pub-…` 게시자 ID 를 주면: 애드센스 확인 메타 태그와 `docs/ads.txt` 추가, `adsense_client` 설정(스위치는 승인 전까지 끔).
   - 승인 뒤 슬롯 ID 2개(목록·상세) → `adsense_slot_feed`·`adsense_slot_detail`, 카카오 애드핏은 `DAN-…` 단위 ID·크기 → `adfit_units`.
   - 광고를 켜면 방침·약관이 바뀌므로 `ads_legal_date`(시행일) 7일 전 예고. 알림 개정과 날짜가 가까우면 한 번에 묶는다.
   - 서치 콘솔·네이버 서치어드바이저 확인 메타 값을 주면 index.html 머리에 넣는다. sitemap.xml 은 이미 10개 주소.
3. **제품 전략 (2026-10-01 보고서, 사용자 Claude Docs 문서 '청약패스 제품 전략 보고서')** — 결론: 판정 자체는 은행·대형 플랫폼도 시작해 흔해지는 중,
   차별점은 '내 조건으로 모든 공고를 계속 감시 + 근거 + 부적격 방지'. 3개월 순서(사용자 결정 전 제안 단계):
   ① 측정(프로필 완료율·첫 판정까지 질문 수·'확인 필요' 원인별·재방문, 입력값은 재지 않음) ② 공고별 검색 유입 정적 페이지 ③ 첫 방문 질문 4개로 줄이기·'내 청약 현황'·확인 필요 원인별 행동 버튼·부적격 방지 체크·가점 오르는 날
   ④ 판정 함수 모듈 분리 후 청약봇(오픈카톡 질문 로그 상위 5유형만) ⑤ 조건 맞춤 알림. 정리 후보: _v2 이전 분기 46곳, ntfy 코드, app/api.py(미사용), '비추천' 등급명.
   측정치: 입력 없는 방문자는 '확인 필요' 100%, 프로필 완료 시 2~4%(대부분 신혼희망타운 총자산).
4. 개인정보 보호책임자는 `privacy_officer` 에 들어가 있다 (방침·약관·이용 안내에 표시).

## 최근 끝난 일 (자세한 것은 WORK.md)

- 2026-10-01: 알림 버튼 '알림 켜짐' 표시, 알림 서버 연결·미리보기, 웹 푸시 기능, 이용약관 제5조 수정, 정적 페이지·청약 기준 가이드,
  광고 준비(꺼 둠), 공고문 원문 ↔ 앱 수치 대조, 판정 검증 사례 144건, 베타 업데이트 내역
