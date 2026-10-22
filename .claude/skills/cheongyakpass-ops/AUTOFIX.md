# 매일 아침 자동 고치기 (2026-10-22 운영자 결정: '조건 맞으면 바로 올림')

예약 작업 '청약패스 아침 자동 고치기'가 매일 아침 수집이 끝난 뒤 이 절차를 그대로 따른다. 사람이 없다고 가정한다.
먼저 저장소 `HANDOFF.md` → `CLAUDE.md` → 이 파일을 읽는다. CLAUDE.md 규칙(백업·WORK.md·검증·버전·기능 스위치)은 그대로 지킨다.

## 0. 준비
- 저장소가 없으면 받는다(`cheongyak/cheongyak.github.io`, push 권한). `git pull --rebase origin main` (autostash 금지).
- **수집이 아예 안 돌았는지 먼저 본다 (2026-10-23 GitHub 예약 실행이 밤새 하나도 안 돎 — 청약 05:30·06:50, LH·SH·GH·민간임대·지방 공사 모두 시작조차 안 됨).**
  `docs/daily-run.txt` 가 오늘(한국 날짜)이 아니고 collect.yml 이 지금 돌고 있지도 않으면(`gh api repos/cheongyak/cheongyak.github.io/actions/workflows/collect.yml/runs?per_page=1`),
  collect.yml 과 임대 수집(lh-rental·sh-rental·gh-rental·pvt-rental·local-rental.yml)을 `gh api -X POST …/actions/workflows/<파일>/dispatches -f ref=main` 로 시작한다.
  각 임대 수집도 오늘 실행 기록(`…/workflows/<파일>/runs?per_page=1` 의 created_at)이 없으면 같이 시작한다. 보고 맨 앞에 '예약 수집이 안 돌아 손으로 시작함'을 적는다.
- 오늘 아침 수집(청약 공고 수집 collect.yml)이 끝났는지 확인한다. 아직 돌고 있으면 끝날 때까지 기다린다(최대 60분).
- 같은 날 다른 세션이 같은 공고를 고치고 있으면(WORK.md 오늘 항목·최근 커밋) 그 공고는 건너뛴다.

## 1. 할 일 모으기
- `python -m tools.qa.unread_queue` → `evidence/qa/unread-queue.json`. '할 일 없음'이고 열린 이슈도 없으면 4번(관찰 검사 승격)만 하고 끝낸다.
- 원문이 없는 공고(missing_original)는 '근거 자료 모으기'(probe.yml)를 돌려 `evidence/notices/<번호>.txt` 를 받는다(이 작업 환경은 청약홈에 직접 못 닿는다). 그래도 없으면 그 공고는 '원문 없음'으로 보고만 한다.

## 2. 공고마다 (한 공고 = 한 커밋)
1. 원문을 직접 읽고, 화면이 '못 읽음·대조'라고 한 값이 원문 어디에 어떤 꼴로 있는지 찾는다. 값이 원문에 아예 없으면(공고문이 그 값을 안 적음) 읽기 규칙이 아니라 표시 문제 — 고치지 말고 보고만.
2. 공고문 대조·법령 불일치·정정(값 바뀜)은 **사람 판단이 필요한 일**이다. 읽기 실수가 분명할 때(원문 숫자를 잘못 옮김)만 고치고, 원문끼리 다르거나 법령과 다르면 고치지 말고 보고한다.
3. 백업 브랜치 → `app/notice_pdf.py`(분양)·`app/lh_terms.py`/`app/sh_terms.py`(임대) 에 **그 꼴을 읽는 규칙을 더한다**. 기존 규칙은 지우지 않는다. 숫자가 서로 맞는지(합계·칸 수) 확인하고 안 맞으면 읽지 않게 만든다(추측 금지).
4. 정답 데이터: `tests/golden/notices.json` 에 그 공고 값(원문 문장 인용·`verified_from`·`verified_at`)을 넣고 정답 시험에 번호를 더한다. 새 꼴만 떼어 낸 짧은 시험도 하나 만든다(안 맞는 숫자는 거부하는지까지).
5. `PARSER_VERSION` 을 받은 뒤 최댓값 +1 로 올리고 이유를 적는다.

## 3. 올리는 조건 (하나라도 아니면 올리지 않는다)
- [ ] 새로 읽은 값이 원문에 그대로 있다(근거 문장 인용 가능)
- [ ] `python -m tools.qa.parse_snapshot` 차이가 **고친 공고에만** 있다 — 다른 공고 값이 바뀌면 규칙이 너무 넓은 것
- [ ] `python -m pytest -q` 오류·실패 0 (2026000502 같은 '모든 저장 원문' 시험 포함)
- [ ] `node tools/judge_check.cjs` 전부 일치, `node tools/qa/snapshot.cjs` 바뀐 곳 0(판정이 바뀌면 의도한 변경인지 WORK.md 에 근거), `node tools/qa/e2e.cjs` 실패 0
- [ ] 충돌 표시 없음 `grep -rn '^<<<<<<< ' app tools docs tests`

모두 맞으면: WORK.md(요청 '아침 자동 고치기'), changelog '수정', VERSIONS, 버전 올림 → 커밋 → `git pull --rebase` → push → `bash tools/qa/release.sh X.Y.Z`.
올린 뒤 collect.yml 이 다시 돈다(app/** 변경) — 끝나면 그 공고의 checks 가 없어졌는지, verify-status ok 인지 확인한다. 나빠졌으면 `git revert` 하고 보고한다.

## 4. 관찰 중 검사 승격
- `docs/config.json` qa_observe 의 검사 중 시작일에서 7일 넘게 지났고, 그 사이 verify-status 판(git 이력)의 observe 실패가 모두 0 이면 qa_observe 에서 빼고 `tools/verify_status.py` GATED 에 더한다(WORK.md 기록, 버전 안 올림).
- 실패가 있었으면 그 실패가 거짓 경보인지 원문으로 확인해 검사를 고치고 시작일을 오늘로 다시 적는다.

## 5. 보고 (항상)
대화에 한글로, 결론 먼저: 올린 것(공고·값·원문 문장·버전), 올리지 않은 것과 이유(사람이 볼 것), 원문 없음, 관찰 검사 승격. 할 일이 없었으면 한 줄로 '오늘 못 읽은 공고 없음'.
`HANDOFF.md` '진행 중인 일'에 사람이 볼 것을 남긴다.
