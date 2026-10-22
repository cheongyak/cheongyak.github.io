# 수집 → 검증 → 경고 흐름 (2026-10-22 정리)

'베타 · 참고용 — 최근 자동 검증에서 공고문과 다른 값이 발견돼 확인 중이에요' 경고가 반복된 원인을 찾으며 코드로 확인한 흐름.
경고 이력·원인: `python -m tools.qa.warn_history` → `evidence/qa/warn-history.json` (원인은 사람이 확인한 것만 `warn-causes.json`).

## 1. 단계별 데이터

| 단계 | 코드 | 만드는 것 | 갱신 |
|---|---|---|---|
| 공고 수집 | `app/pipeline.run` ← `app/sources/applyhome.iter_open_listings` | 청약홈 공고·주택형 | 매일 05:30 collect.yml, app/** 바뀌면 바로 |
| 원문 확보 | `pipeline.apply_notice` → `_fetch_text` (pypdf, 두 번째 도구 `ALT_TEXT`), 실패 시 `evidence/notices/<번호>.txt` 사본 | 공고문 글 | 공고마다 `PARSER_VERSION` 이 바뀔 때만 다시 읽음, 아니면 `docs/notice-cache.json` |
| 추출 | `app/notice_pdf.parse_notice` (표·문장 규칙), `merge_alt`(두 도구 대조 → conflicts) | found{residence, pub_limits, sp_table, supply_scale, …, quotes} | 위와 같음 |
| 분류·연결 | `pipeline.build_listing` + `apply_notice` (주택형 id `공고번호-주택형`) | `Listing` (from_notice, notice_quotes, notice_conflicts) | |
| 저장 | `docs/listings.json` (0건이면 `keep_previous` 로 보관 기간 안 지난 결과만) | 화면·판정 입력 | |
| 공고별 검증 | `app/validate.py` (날짜·금액·추정·conflicts) | `Listing.checks` → 상세 '데이터 확인 필요' | 수집마다 |
| 원문 대조 | `app/crosscheck.py` (공고문 숫자 ↔ 화면 고정 수치·분양가) | run-log `[검증·공고문 불일치]` | 수집마다 |
| 정답 데이터 | `tests/golden/notices.json` (사람이 원문 확인) ↔ 수집값 | run-log `[검증·정답 불일치]` | 수집마다 |
| 판정 사례 | `tools/make_judge_cases.py`(법령·공고문 표를 따로 옮긴 계산) → `tools/judge_check.cjs`(화면 함수) | `docs/judge-status.json` | verify.yml |
| QA 검사 25가지 | `tools/qa/*` → `evidence/qa/*.json` + 지문 `_data`(`tools/qa/stamp.py`) | 결과 파일 | collect·verify·LH·SH 워크플로 |
| 요약 | `tools/verify_status.build` | `docs/verify-status.json` {ok, banner, flagged, pending, …} | 각 워크플로 끝 |
| 화면 | `docs/index.html` `betaBanner`·`verifyFlags`·`verifyCard` | 경고·공고별 표시·검증 현황 | 페이지 열 때 |

## 2. 질문별 답 (코드·데이터 근거)

1. **경고 조건**: 예전 `betaBanner` — `VERIFY.ok === false` 하나. 지금(기능 `verify_scope`) — `VERIFY.banner` 가 있을 때만, 글은 banner.kind 에 맞게.
2. **검증 파일·함수**: `tools/verify_status.build` 가 `judge-status.json`, run-log 의 `[검증·공고문…]`·`[검증·정답 불일치]`, `evidence/qa/*.json` 25개를 모아 AND.
3. **원문 비교 여부**: 섞여 있다. 원문 대조(crosscheck)·정답 데이터(golden)·임대 못 읽음은 원문 기준, 판정 사례는 법령·공고문 표를 따로 옮긴 기대값, 나머지 다수(화면 스냅샷·e2e·입력 버튼·교차 규칙·단조성…)는 **화면 코드 검사**라 공고문과 무관 — 그런데 예전 경고 글은 모두 '공고문과 다른 값'이었다.
4. **값이 만들어지는 곳**: 추출값 `notice_pdf.parse_notice`, 대조값 `notice_pdf.notice_facts`(같은 원문, 다른 정규식)·`index.html` 고정 수치, 정답 `tests/golden`.
5. **정답의 독립성**: golden 은 사람이 원문을 읽은 값(독립). 판정 사례는 생성기가 화면 코드를 실행하지 않음(독립). crosscheck 는 같은 원문을 다른 규칙으로 읽음(반독립). 불변식은 데이터 자체 규칙(정답 아님). 재공급 특공 세대수는 이번에 공급규모 문장이라는 두 번째 근거를 더함.
6. **검증 대상**: 지금 목록 전부(불변식·validate·crosscheck), 정답 데이터가 있는 공고(golden), 고정 공고 16개(스냅샷), 공고 40개(입력 버튼).
7. **불일치 때 저장되는 것**: run-log 줄, `evidence/qa/*.json` 결과, `verify-status.json`, 공고의 `checks`·`notice_conflicts`, Actions 실패 → 이슈.
8. **해소 시점**: 다음 실행에서 그 검사가 다시 돌아 0이 될 때. 검사마다 돌리는 워크플로가 달라(예: input-nav 는 verify 만, coverage 는 collect 만) 다른 워크플로의 지난 결과가 남았었다 → 10-21 지문(stamp)으로 지난 결과는 세지 않음.
9. **수정이 덮어써지는가**: 공고문 값은 `PARSER_VERSION` 이 같으면 보관 기록을 쓰므로 규칙을 고치면 버전을 올려야 다시 읽힌다(올리지 않으면 고친 규칙이 적용 안 됨). 0건 수집은 지난 결과를 다시 씀(→ 보관 기간 거름, v1.71.3).
10. **지난 결과 재사용**: 10-21 전에는 그랬다(10-21 06:05 경고). 지금은 `_data` 지문이 다르면 세지 않고 `pending`(재검증 대기)로 보여 줌 — 통과로 치지 않음.
11. **검증 데이터 = 화면 데이터**: 지문이 `docs/listings.json`·`docs/index.html` 해시라 같은 파일임을 확인한다.
12. **공고 하나 → 전체 경고**: 예전엔 그랬다(10-22 06:18 영흥숲 한 주택형 → 245개 공고 전체). 지금은 공고 id 가 있는 검사(불변식·임대 불변식·임대 못 읽음·시세 대조·계약금 대조·글 바뀐 값)는 그 공고에만 표시, id 를 모르는 실패만 전체로.
13. **현재 오류냐 과거 기록이냐**: 지문 도입 뒤로는 현재. `pending` 이 남은 검사는 화면 검증 현황에 '재검증 대기'로 보인다.
14. **공통 원인 묶기**: `warn_history` 가 구간·검사·원인 종류를 모으고, 같은 원인 반복(예: 재공급 특공 표 모양 5번)은 원인 종류별 건수로 보인다.

## 3. 경고 상태 (verify-status.json)

| 상태 | 필드 | 화면 |
|---|---|---|
| 모든 판정에 영향 있는 불일치 | `banner.kind = notice` (공고문 대조·정답·여러 도구 읽기) | 모든 화면 빨간 경고 |
| 판정·화면 계산 불일치 | `banner.kind = judge` | 빨간 경고('판정 계산이 기대와 달라') |
| 검증을 끝내지 못함 | `banner.kind = unverified` (판정 결과 없음·공고문 대조 못 함·다시 돌리지 못한 검사) | 빨간 경고('끝까지 마치지 못해') |
| 특정 공고 문제 | `flagged{id: [이유]}` | 그 공고 상세·임대 상세 '데이터 확인 필요', 이용 안내 검증 현황 '공고 N건 확인 중' |
| 재검증 대기 | `pending[]` | 검증 현황 '재검증 대기' (통과로 치지 않음) |
| 정상 차이로 확인 | 허용 목록 `tools/qa/lh_unread_allow.json`(이유 필수), 불변식 예외(신혼희망타운) | 표시 안 함 |
| 통과 | `ok = true`, banner·flagged·pending 없음 | 일반 베타 안내 |

`ok` 는 예전과 같다(하나라도 실패면 false → Actions 실패·이슈). 스위치 `verify_scope` 를 끄면 화면도 예전처럼 ok 하나로.
