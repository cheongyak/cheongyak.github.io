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

## 5. 자주 하는 답

- "자동으로 돌아가?" → 수집은 GitHub Actions 가 매일 05:30, 사이트는 GitHub Pages. Claude 세션과 무관하게 돈다. 실패·불일치는 이슈로 메일이 간다.
- "경쟁률·숫자 출처?" → 청약홈 화면(경쟁률 팝업·특별공급 접수 현황)과 모집공고문. 링크는 숫자가 보이는 화면으로.
- 오픈카톡 청약봇 질문 답변은 별도 스킬(cheongyak-bot-answer)이 있으면 그것을 따른다.
