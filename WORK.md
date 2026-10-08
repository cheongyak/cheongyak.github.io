# 작업 기록

최신 항목이 위에 있어요. 규칙은 [CLAUDE.md](CLAUDE.md) 를 따릅니다.
2026-09-29 12:55 이전 항목은 규칙을 만들기 전 작업을 커밋 기록으로 정리한 것이라 백업 브랜치가 없어요.
그 시점으로 되돌릴 때는 해당 커밋 번호로 `git revert` 를 써요.

## 2026-10-08 21:49 · SH 표 일정에서 접수 기간 읽기 (v1.63.1)
- 요청: "Abc 순차로 진행해줘" — B(SH 표 형식 일정 접수 기간 읽기)
- 원인(못 읽던 4건): ① 310673·310672(·309717) 일정이 '단계 ▶ 단계 ▶ …' 줄 뒤에 날짜가 차례로 나오는 표 — 어느 날짜가 접수인지 몰라 안 읽게 해 둠 ② 310258 pypdf 글에 낱말마다 빈 문자(\x00)가 끼어 '접수기간 ◻ 2026.10.1~10.2' 를 못 찾음 ③ 310976 게시판 등록일(10.7)이 접수 시작(10.2)보다 늦어 '등록일 3일 전보다 이른 시작'으로 버림
- 변경: app/sh_rental.py — 빈 문자를 공백으로, 표 일정 읽기 _arrow_table_period(접수 단계 차례 = 날짜 묶음 차례, 우편·방문·서류제출 단계 제외, 날짜가 차례대로일 때만, 묶음이 모자라면 안 읽음), _posted_ok(등록일 30일 전 시작이라도 등록일에 접수 중이면 인정). 기능 sh_schedule_table(true)
- 결과: 지금 공고 16건 중 접수 기간 읽음 9 → 13건(310976 10.2~10.11 · 310672 9.28~10.5 · 310673 10.6~10.8 · 310258 10.1~10.2). 남은 3건(311005·310575·310037)은 공고문에 날짜 없음(정답도 없음). 마감 지난 310672·310258 은 목록에서 빠지고 310976 은 접수 중으로 보임
- 확인: 정답 tests/golden/sh_rental.json — 표라 '안 읽어도 됨'이던 310673·310258·310672 을 '읽어야 함'으로, 310976·309717 새로 추가(원문 확인), 규칙 시험 test_schedule_table_rules·off(우편 단계·묶음 모자람·차례 거꾸로·늦게 올린 공고), pytest 226 통과, judge_check 782/782, 파싱 고정 112건 바뀐 값 0, SH 화면 점검(새 날짜로 임시 계산한 데이터 · 켜짐/꺼짐 · 밝은/어두운) 통과
- 파일: app/sh_rental.py, docs/config.json, tests/golden/sh_rental.json, tests/test_sh_rental.py, docs/changelog.json, VERSIONS.md, FEATURES.md, HANDOFF.md
- 백업: backup/20261008-2149-shkinds
- 기능: sh_schedule_table
- 버전: v1.63.1

## 2026-10-08 21:49 · SH 지난 모집공고 원문 모으기 도구 (조사, 화면 영향 없음)
- 요청: "Abc 순차로 진행해줘" — A(SH 청년안심주택·행복주택 판정)의 준비. 지금 SH 목록(최근 60일 16건)에 두 종류 공고가 없어 정답 데이터로 쓸 원문이 없음
- 변경: tools/qa/sh_archive.py(새) — SH 주택임대 게시판을 최대 80쪽 넘겨 행복주택·청년안심주택·국민임대·영구임대 모집공고를 종류별 최근 6건까지 공고문 글로 evidence/qa/sh-archive/ 에 저장. 'SH 임대 원천 점검'(sh-probe.yml)에서 실행
- 파일: tools/qa/sh_archive.py, .github/workflows/sh-probe.yml, WORK.md
- 확인: 문법·yaml 검사, Actions 실행 결과(evidence/qa/sh-archive/log.txt)
- 백업: backup/20261008-2149-shkinds
- 기능: 없음(조사 도구)

## 2026-10-08 11:32 · 새벽 손 수집 뒤 아침 예약 수집이 건너뛴 문제 고침
- 요청: "오늘 신규 예약건이 안돈거같아 갱신이안됏음"
- 원인: 10-08 01:23 손 실행(v1.63.0 확인용 collect)이 docs/daily-run.txt 에 '2026-10-08'을 적어, 05:30·06:50·08:50 예약 수집이 '오늘 이미 돎'으로 모두 건너뜀(실행은 성공 표시, gate 단계만 돌고 끝). 화면 갱신 시각이 01:37 에 멈춤
- 조치: 11:32 손 수집 바로 실행(01:23 실행은 웹 푸시 '보낼 이벤트 없음'이라 두 번 갈 알림 없음). collect.yml — 매일 수집 표시(daily-run.txt)는 예약 실행과 한국 05시 뒤 손 실행만 적음. 05시 전 손 실행은 웹 푸시를 보내지 않음(그날 05:30 수집이 보냄, 같은 날 두 번 가지 않게)
- 파일: .github/workflows/collect.yml, WORK.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: yaml 문법, 조건 분기 6가지(01시·11시 × 손·예약·push) 표시 여부 확인, pytest 224 통과. 올린 뒤 11:47 손 수집 성공(그때 국토부 실거래가 조회가 일시 시간 초과 → 지난 값 유지, 이슈 #12), 11:57 수집(코드 변경 실행)에서 실거래 702건 모두 성공·updated 11:57·verify ok true, #12 닫음
- 백업: backup/20261008-1132-dailygate
- 기능: 없음(수정)

## 2026-10-08 01:10 · 계약금 비율 읽기 개선 + 재발 방지 점검 + 스위치 켬 (v1.63.0)
- 요청: "켜주고 공고문 제대로 파싱하도록하는 개선안 반영하고 앞으로 이런 실수없도록 하는 대책마련해줘. 마지막으로 해당 개선안으로 검증해줘"
- 원인(지난 실수): v1.62.1 읽기는 표 머리 글자('계약금(N%)')와 제목 낱말(확장·옵션 등)로만 표를 골라, 발코니·옵션 표를 본 표로 읽거나(2026000437·438·020, 올리기 전 발견) 진짜 표를 낱말 때문에 버림(910233·910134·910240 등 30건 못 읽음)
- 변경: app/notice_pdf.py pay_terms — 표 머리마다 그 아래 금액 줄(집값 T · 계약금 a · 다음 금액 b)이 a = T × 계약금% 인지 확인한 머리만 씀(단위 원·천원·만원, 만 원 절사 오차 허용, 다음 금액이 중도금 % 와 맞는지로 발코니 표 제외, 융자금 칸 처리). 다른 표에 포함되는 줄만 가진 표·'옵션' 제목의 작은 금액 표는 제외. 서로 다른 비율이 남으면 읽지 않음(주택형마다 다른 2026000419, LH 표 둘 2026000409). 머리 형태 넓힘(괄호 없음, LH 중도금 여러 칸 합, 와/과, 중도금이자후불제대출). PARSER_VERSION 28
  재발 방지: tools/qa/pay_audit.py — 표 머리를 보지 않고 공고문 전체 금액 줄만으로 계약금 % 를 따로 구해, 읽은 % 를 뒷받침하는 줄이 없거나(misread) 다른 % 줄이 3배 넘게 많으면(dominant) 실패. verify_status qa.pay_audit_bad 가 0 이 아니면 검증 실패(Actions collect·verify 매번). 테스트 test_audit_finds_no_mismatch·test_header_alone_is_not_enough. 운영 노하우에 '표 값은 금액 줄로 교차확인, 제목 낱말로 거르지 말 것'
  스위치: docs/config.json contract_from_notice true
- 결과(저장된 공고문 112건): 읽음 82 → 103건(새로 21건: 2026000041·185·193·313·320·414·416·436, 2026820007·008·010·011, 2026910134·210·233·240·241·243, 2026930031·034·035). 전에 읽은 82건 값은 하나도 안 바뀜. 분포 10/60/30 37 · 5/60/35 29 · 10/0/90 27 · 20/0/80 3 · 10/20/70 3 · 기타 4 · 못 읽음 9(추정 표시). 계약금 나눔 48 → 56건
- 확인: ① 정답 23건(사람이 원문 금액 줄로 확인, 못 읽어야 맞는 409·419 포함) test_golden_pay_ratio 일치 ② 독립 점검 112건 표 줄과 안 맞음 0건 ③ 블라인드 대조 — 파서 결과를 보지 않은 별도 에이전트가 11건 원문을 읽음: 읽은 9건 비율·나눔 모두 일치, 2026820009(10/20/70)·930032(부대경비 포함 총액이라 %가 딱 안 맞음)는 못 읽음으로 남아 10% 추정 표시(계약금은 같음). 2026000193 은 에이전트가 '사전청약당첨자 대상(5%)/그 외(10%)' 두 표라 애매하다고 봄 — 새로 청약하는 사람은 '그 외' 표라 10% 로 읽는 것을 유지 ④ pytest 224 통과(test_pipeline fastapi 없음 제외) ⑤ judge_check 782/782 ⑥ 파싱 스냅숏 차이는 pay_ratio·contract_split·근거 문장뿐 ⑦ 전체 QA(아래) ⑧ 390px 납부 일정 화면
- 올린 뒤: Actions 수집·판정 검증 성공, run-log '[QA 계약금 비율] 112건 · 읽음 103 · 표 줄과 안 맞음 0건', 정답·공고문 불일치 0, verify-status ok true. 지금 목록 182 주택형 중 179 비율 읽음(10% 109 · 5% 63 · 20% 10), 계약금 나눔 101 · 계약금·중도금이 바뀐 공고 19곳(5% 14곳: 천안 아이파크 2단지·더샵 동인센트리체·쌍용 더 플래티넘 한강·향남역 그로브 스위첸·용인 양지 서희스타힐스·숭의역 노르웨이숲·에코델타시티 금강펜테리움·쌍용 더 플래티넘 센텀·화서역 호수공원 아너스빌·문수로 비스타 더파크·상동역 롯데캐슬·제일풍경채 첨단3지구·용인 동일하이빌 파크밸리·두산위브더제니스 부천 / 20% 5곳: 아이린8차·세종 리더스포레·고양 장항 아테라·과천 벨라르테·과천 라비엔오). 못 읽음 2026000409(2개 주택형)·930032 → 10% 추정 표시. 자정 0건 수집 이슈 #10·#11 닫음. release/v1.63.0
- 파일: app/notice_pdf.py, app/pipeline.py, docs/config.json, tools/qa/pay_audit.py(새), evidence/qa/pay-audit.json(새), tools/verify_status.py, .github/workflows/collect.yml, .github/workflows/verify.yml, tests/golden/notices.json, tests/test_contract_ratio.py, tests/qa/parse_snapshot.json, docs/changelog.json, VERSIONS.md, FEATURES.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 백업: backup/20261008-0110-payparse
- 기능: contract_from_notice(켬)
- 버전: v1.63.0

## 2026-10-08 00:00 · 계약금 비율을 공고문에서 읽기 (스위치 꺼둔 채) + 계약금 같은 금액 '부족' 오차 고침 (v1.62.1)
- 요청: 다른 세션(인스타 콘텐츠 작업)의 수정 요청서 3건 — ① 계약금 비율이 모든 공고 10% 고정 ② 빠른 시작 예치금 빈칸이 1순위 미충족 ③ 목록 '결과 N곳 · 주택형 N' 줄바꿈
- ②·③: 이미 v1.58.2·v1.58.3(10-06)에서 고쳐져 있음 — 다시 확인: 경기·세대주·집 1채·종합저축 2019 가입(예치금 빈칸) → 향남역 그로브 스위첸 '예치금 (민영) 예치금 입력 필요'(warn, 판정 확인 필요), 목록 '신청 가능' 필터 뒤 '결과 3곳 · 주택형 22' 한 줄(390·430px, 밝은·어두운). 새 작업 없음
- ① 원인: app/pipeline.py 가 contract_rate 0.10·mid_rate 0.6 을 고정, 공고문을 읽지 않음
- 변경: app/notice_pdf.py — 첫 분양대금 표 머리 '계약금(N%) 중도금(M%) 잔금(K%)'(잔금 % 없으면 100−N−M, 앞 40자 공급금액·분양가(격)·공급가, 앞 300자 확장·옵션·선택품목·유상 없음('발코니확장금액 별도' 제목은 제외), 설치위치·제조사·품목 표 제외, 대지비·건축비가 뒤따르는 다른 표가 다른 비율이면 안 읽음) → pay_ratio. 표 각 줄 '합계 T · a · b'에서 a + b = T × 계약금% 이고 a 가 모든 줄 같으면(나뉜 줄이 나뉘지 않은 줄의 2배 이상) contract_split {first_won, rest_within('30일'·'1개월')}
  app/pipeline.py — 데이터(pay_ratio·contract_split)는 늘 저장, 계산 값(contract_rate·mid_rate)은 기능 contract_from_notice 가 켜졌을 때만. PARSER_VERSION 27(모든 공고문 다시 읽음). docs/index.html — 스위치가 켜지면 화면이 바로 공고문 비율 사용, 납부 일정 '계약금 (5%)'·'계약 때 1,000만 · 계약 후 30일 안에 나머지 7,110만', 못 읽으면 '공고문에서 못 읽어 10%로 추정', 중도금 출처도 공고문
  함께 고침(스위치와 무관, 사용자에게 보임): 현금이 계약금과 정확히 같으면 소수 오차(4.45억 × 5% = 0.22250000000000003억)로 '부족'이던 것 — 비교에 오차 허용. 판정 사례 contract-10 이 잡음
- 조사 결과(저장된 공고문 112건): 비율을 읽은 공고 82건 — 10/60/30 29 · 5/60/35 27 · 10/0/90 19 · 20/0/80 3 · 5/0/95·5/45/50·10/40/50·20/60/20 각 1. 처음 규칙은 2026000437·438(고덕엘리스트)을 발코니 확장 표의 중도금 10% 로, 2026000020 을 가구 옵션 표 80% 로 잘못 읽어 고침. 못 읽은 공고는 LH 공공분양 표('계약금10%' 괄호 없음, 2026000409 등)·신혼희망타운·옵션 포함 표(2026910240) 등
  지금 목록 기준 스위치를 켜면 바뀌는 공고 20건(83개 주택형): 계약금 10→5% 16건(상동역 롯데캐슬 시그니처·향남역 그로브 스위첸·쌍용 더 플래티넘 한강·용인 양지 서희스타힐스·화서역 호수공원 아너스빌·천안 아이파크 시티 2·4단지·더샵 동인센트리체·숭의역 노르웨이숲·에코델타시티 금강펜테리움·쌍용 더 플래티넘 센텀·문수로 비스타 더파크·제일풍경채 첨단3지구 등), 10→20% 4건(제주 이도이동 아이린8차·과천 푸르지오 벨라르테·라비엔오·고양 장항 아테라), 중도금 60→40% 광명 시티프라디움(453). 같음 18건, 못 읽음 14건(그대로 10% + '추정' 표시)
- 검사: 정답 tests/golden/notices.json pay_ratio·contract_split 4건(2026910256·463·468·386, 원문 공급금액 표 줄로 확인), 시험 tests/test_contract_ratio.py 4개(정답·옵션 표 제외·정액 아니면 안 나눔·머리 못 읽으면 기본값), 판정 사례 contract-01~13(공고문 비율·현금 = 계약금 / 1만원 모자람 / 스위치 꺼짐 10%, 못 읽은 LH), 변이 2개(공고문 비율 무시·같은 금액 부족) 잡음. 공고문 읽기 기준(tests/qa/parse_snapshot.json) 갱신 — 바뀐 칸은 pay_ratio·contract_split·quotes 뿐
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, docs/index.html, docs/config.json(contract_from_notice false), tests/golden/notices.json, tests/test_contract_ratio.py, tests/judge/cases.json, tests/judge/contract_listings.json(새 고정본), tests/qa/parse_snapshot.json, tools/judge_check.cjs, tools/make_judge_cases.py, tools/qa/code_mutation.cjs, tools/engine_lock.json, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: pytest 222 통과, 판정 사례 782/782, 변이 75 못 잡음 0, cross 248,920회 충돌 0, e2e 34/34, 회귀·스냅샷·consistency·monotonic·profile_keep·filter·sptext·zero_default·fixflow·fixlink·score_input·spouse_fix·sh_screen 0. 스위치를 켠 사본으로 390px 밝은·430px 어두운 자금 플랜 확인(상동역 84A 계약금 (5%) 8,110만 · 계약 때 1,000만 · 계약 후 30일 안에 나머지 7,110만)
- 백업: backup/20261008-0000-contract
- 기능: contract_from_notice(꺼짐으로 올림) · 계약금 비교 오차는 없음(수정)
- 버전: v1.62.1

## 2026-10-07 16:39 · 교차 검사 거짓 경보 고침 — 사회주택 '일부 계층 판정 못 함' (이슈 #9)
- 요청: (자체 점검) v1.62.0 뒤 판정 검증 실패, 이슈 #9 — verify-status qa.cross_rule_fails 186 (LH-UI-001, 함께주택·망우)
- 원인: 판정이 틀린 게 아니라 검사 도구가 '공고 결론 = 가장 좋은 계층 결론'만 알았음. 사회주택은 판정하지 않는 계층(고령자 — 나이 기준이 공고문에 없음)이 있어, 아는 계층이 모두 불가면 화면은 '일부 계층 판정 못 함'(partial, rentalJudge 기존 규칙)을 보여줌. 로컬 검사 때는 새 수집 자료(사회주택 terms)가 아직 없어 드러나지 않았음
- 변경: tools/qa/cross_rule.cjs LH-UI-001 — unknown_groups 가 있고 가장 좋은 계층이 불가·해당 없음이면 기대값 partial. 나이 검사 기준일도 화면과 같게(terms.ref_date)
- 파일: tools/qa/cross_rule.cjs
- 확인: 새 수집 자료로 cross 248,920회 충돌 0(고치기 전 186), lh_qa·lh_screen·sh_screen 0, 판정 사례 769/769
- 백업: backup/20261007-1639-crossfix
- 기능: 없음(검사 도구 수정)

## 2026-10-07 16:06 · SH 사회주택 자격 판정 — C-2 (v1.62.0)
- 요청: C. SH 판정 넓히기 "둘 다" 중 사회주택
- 근거: 사회주택 공고문 7건(evidence/sh/311005·310672·310629·310575·310300·310037·309883)의 신청자격·소득·자산·자동차 절을 직접 읽음. 운영기관마다 형식이 다르고 틀린 값이 있음: 망우(310672) 소득표 2인 6,452,897원(110%)·3인 8,168,428원(100%)인데 '120%'라 적음, 청년 자산 '2억5,4000만 원'(오기), '무주택자'(본인·세대 불명) / 쌍문생활(310575) 소득표가 2024 기준(4,317천원) / 어울리(311005) 자산·자동차 표 글자가 섞여 짝을 알 수 없음 / 옥류서원(310629·310300·309883) 소득 70%(본인 소득)·신혼 120% 두 기준, 자산 기준 없음
- 변경: app/sh_terms.py parse_social — 확실한 것만 읽고 나머지는 비움(→ '확인'): 소득은 비율이 하나이고 1~3인 표가 도시근로자 2025 × % 와 같고(천원 단위는 1천원 안) 세대 전원 소득 문장이 있을 때만 / 무주택 '무주택세대구성원 … 적용' → 세대, 청년 예외 문장('직계존속이 주택을 소유해도 본인이 무주택자'·'본인 명의로 가진 주택이 아닐 경우 무주택자') → 청년 본인 / 서울 거주 + 서울 밖 신청 가능 문장이면 서울 밖은 확인 / 총자산 표 '청년 N억 M만원'·'신혼부부, 고령자, 1인가구 N억 M만원'(만 단위가 1만 이상이면 오기로 보고 비움) / 자동차 한 값 / 청년 미혼 요건은 문장이 있을 때만 / 모집 공고일(나이·혼인 기간 기준일). 계층을 하나도 못 읽으면 None(판정 미지원). 결과: 함께주택(310037)은 소득까지 판정, 망우·쌍문생활은 소득·무주택(망우) 확인·자산·자동차·나이·거주로 불가만 가림, 나머지 4건은 판정 미지원
  화면(docs/index.html): 기능 sh_social 스위치, 계층 '신혼부부'(혼인 N년·예비신혼부부, 한부모 없음)·'1인가구'(가구원 1명), local.others_check, 기준일 terms.ref_date, 기준 안내 줄
- 검사: 정답 3건 terms·social_unread 4건, 시험(읽지 않을 공고·소득표 1천원 다르면·본인 소득이면 비움), 판정 사례 37건(1인 120%·만 39/40세(공고일 09-04 기준)·부모님 집 있는 청년·혼인 7년 경계·예비신혼·총자산·자동차 ±1만원·서울 밖·본인 집·2인 미혼·가구원 모름 / 망우·쌍문생활 경계), 변이 4개(서울 밖 문장 무시·1인 가구 무시·게시일 기준·혼인 기간 하루) 모두 잡음
- 파일: app/sh_terms.py, docs/index.html, docs/config.json, tests/golden/sh_rental.json, tests/test_sh_terms.py, tests/judge/cases.json, tests/judge/sh_notices.json, tools/make_judge_cases.py, tools/qa/code_mutation.cjs, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: pytest 218 통과, 판정 사례 769/769, 변이 73 못 잡음 0, cross 232,315회 충돌 0, e2e 34/34, 회귀·스냅샷·consistency·monotonic·profile_keep·filter·sptext·zero_default·fixflow·fixlink·score_input·spouse_fix·sh_screen·lh_qa·lh_screen 0. 390px 함께주택 상세(밝은·어두운) 확인
- 백업: backup/20261007-1606-social
- 기능: sh_social
- 버전: v1.62.0

## 2026-10-07 15:46 · SH 장기전세 자격 판정 — C-1 (v1.61.0)
- 요청: "Abc순차로 진행해줘" C. SH 판정 넓히기 → 범위 질문에 "둘 다"(장기전세 → 사회주택)
- 근거: 제51차 장기전세주택 공고문(evidence/sh/309467.txt, 2026-08-31, 주택관리번호 2026000432·430) 4. 신청자격(20~24쪽)·입주자격 기준 요약(7~8쪽)·소득표를 직접 읽음
- 변경: app/sh_terms.py parse_jeonse — '현재 서울특별시에 거주하는 성년자인 무주택세대구성원', 면적 묶음 2개(일반·60이하 105%·맞벌이 +35%p / 일반·60초과 150%·+50%p — 어느 순위로든 신청 가능한 가장 넓은 기준, 순위는 안내만), 소득표(1~6인·맞벌이 2~6인)를 도시근로자 2025 × % 와 대조해 다르면 소득 비움, '출생자녀 가산과 중복적용되지 않음' 문장 없으면 소득 비움, 총자산 66,200만(72,800·79,400)·자동차 4,542만(4,996·5,451), '상계장암지구는 의정부시 거주자 포함'. 미리내집(장기전세Ⅱ)은 읽지 않음. jeonse_schedule — 일정표 '1순위 접수기간 ’26.09.14.(월) ~09.15.(화) 2순위 … 3·4순위 …' → 순위별 접수일(일반 접수 기간 읽기는 앞의 우편접수 안내 때문에 안 읽던 표). app/sh_rental.py 일정·마감일에 사용
  화면(docs/index.html): 기능 sh_jeonse 스위치(꺼지면 장기전세만 판정 미지원), 소득 출산가구 가산(T.income_birth, 맞벌이 가산과 중복 없음), 서울 밖 거주는 불가 단 경기 의정부시(또는 시·군 모름)는 확인, 기준 안내 줄(순위 안내·가산), 출산가구 설명 문장
- 검사: 정답 309467 terms·ranks(tests/golden/sh_rental.json), 시험 test_jeonse_schedule_golden·소득표 불일치·중복 문장 없음·미리내집, 판정 사례 40건(경계값: 105%/150%/140%/200%, 출산 115%/125%, 맞벌이+출산 중복 없음, 의정부·수원·부산, 총자산·자동차 표 금액 ±1만원, 집·배우자 집·만 18세 세대원), 변이 3개(출산 소득 가산 무시·의정부 예외 무시·면적 묶음 미인식) 모두 잡음
- 파일: app/sh_terms.py, app/sh_rental.py, docs/index.html, docs/config.json, tests/golden/sh_rental.json, tests/test_sh_terms.py, tests/judge/cases.json, tests/judge/sh_notices.json, tools/make_judge_cases.py, tools/qa/code_mutation.cjs, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: pytest 216 통과, 판정 사례 732/732, 변이 69 못 잡음 0, cross·e2e·consistency·monotonic·profile_keep·filter·sptext·snapshot·zero_default·fixflow·fixlink·score_input·spouse_fix·sh_screen·lh_qa·lh_screen·회귀 모두 0. 390px 밝은·어두운 화면(51차를 미래 날짜로 바꿔 넣은 사본) 확인 — 51차는 9-17 마감이라 실제 화면에는 다음 공고(52차)부터 보임
- 백업: backup/20261007-1546-jeonse
- 기능: sh_jeonse
- 버전: v1.61.0

## 2026-10-07 13:34 · 실거래가 쪽 넘기기 버그 고침 — 시세 원자료 대조 불일치 4건 (v1.60.2)
- 요청: (사진) 베타 상자 '최근 자동 검증에서 공고문과 다른 값이 발견돼 확인 중이에요' → "다른값 발견되어 확인중인거부터 해결해줘"
- 원인: verify-status qa.market_fails 4 (13:24 판정 검증). evidence/qa/market-check.json — 남양주(41360) 2026000431 4개 주택형의 시세·근거 거래 수가 원자료와 다름(예: 84㎡ 666건 vs 원자료 678건, 9.45억 vs 9.46억). app/sources/rtms.py 가 한 쪽(1,000건)에서 해제 거래를 뺀 뒤 1,000건 미만이면 마지막 쪽으로 보고 다음 쪽을 받지 않음 → 한 달 1,000건 넘는 지역에서 다음 쪽 거래 누락. 독립 대조 도구는 해제 포함 건수로 쪽을 넘겨 차이가 드러남 (이번 작업 A 와 무관한 예전 버그)
- 변경: parse_page 가 (거래 목록, 응답 원래 건수)를 돌려주고 fetch 는 원래 건수로 다음 쪽 판단. parse_items 는 그대로
- 파일: app/sources/rtms.py, tests/test_rtms_paging.py, docs/changelog.json, VERSIONS.md
- 확인: 새 시험 test_rtms_paging(고치기 전 코드에서 실패 재현 → 고친 뒤 통과), pytest 213 통과. 올린 뒤 수집 → 판정 검증 market_fails 0·verify-status ok 확인
- 백업: backup/20261007-1334-rtmspage
- 기능: 없음(수정)
- 버전: v1.60.2

## 2026-10-07 13:33 · '추첨으로 노릴 곳' 되돌림 (v1.60.1)
- 요청: "일단 미안한 이거 추첨으로 노릴곳 이거는 다시원복해줘. 엄청복잡해보여"
- 변경: 1e16c519(draw_path)·a1aee405(FEATURES 커밋 번호)를 git revert — docs/index.html·docs/config.json·tools/engine_lock.json·tools/qa/cross_rule.cjs 가 v1.59.0(624b8c1d)과 같아짐(차이 0 확인). 기록(WORK·changelog·VERSIONS·FEATURES)은 남김. cross_rule 의 FUND-007 번호(기존 FUND-006 과 겹치지 않게)는 다시 넣음
- 파일: docs/index.html, docs/config.json, tools/engine_lock.json, tools/qa/cross_rule.cjs, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: 판정 사례 692/692, 스냅샷 0, 엔진 잠금 시험 통과, 문법 검사
- 백업: backup/20261007-1333-undraw
- 기능: draw_path 되돌림
- 버전: v1.60.1

## 2026-10-07 13:28 · '추첨으로 노릴 곳' 표시·모아 보기 — B (v1.60.0)
- 요청: "Abc순차로 진행해줘" — B. '가능·추첨만' 카드: 가점이 낮아도 추첨으로 노릴 수 있는 공고를 한눈에
- 변경(docs/index.html): drawPath(L, p) — 판정 '신청 가능'(eligBucket ok)인 분양 주택형만, 이미 화면에 쓰는 근거로 이유를 고름: 무순위는 전부 추첨 / 규제지역 유주택 → 추첨제만(제28조) / 2년 내 가점제 당첨 → 추첨제만(제28조⑥) / 소득이 우선공급을 넘어 추첨공급만(공공·신혼희망타운 항목) / 공고문 가점제 0% 면적 / 내 가점 < 최근 당첨선이고 공고문 추첨제 비율 > 0 ('가점 N점 부족 · 추첨 M%'). 목록 카드에 '· 추첨으로 노릴 곳 (이유)', 내 조건 요약에 '그중 추첨으로 N'(누르면 그 공고만 — 판정 필터 draw). 판정·등급은 바꾸지 않음
- 검사: tools/qa/cross_rule.cjs DRAW-001(신청 가능이 아닌데 표시) CRITICAL, DRAW-002(가점 차이·추첨 비율이 계산과 다름, 무순위 아닌데 무순위 이유) HIGH. 일부러 망가뜨린 코드에서 DRAW-001 10건·DRAW-002 4건 잡힘. 같은 커밋에서 v1.58.7 의 FUND-006(시세 없음 대출 0원)을 기존 FUND-006(전세 카드)과 겹치지 않게 FUND-007 로 바꿈
- 판정 사례 586개 조건 × 공고 206개에서 이유별 건수: 무순위 9,776 · 가점제 0% 1,886 · 가점 부족 745 · 소득 추첨공급만 204 · 유주택 154 (2년 내 가점 당첨은 사례 조건에 없음)
- 파일: docs/index.html, docs/config.json, tools/qa/cross_rule.cjs, tools/engine_lock.json, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: pytest 210 통과(엔진 잠금 갱신 — 판정 묶음 이름표에 draw 추가), 판정 사례 692/692, cross 217,144회 충돌 0, 회귀 바뀐 판정 0, 스냅샷 0, e2e 34/34, 변이 66 못 잡음 0, consistency·monotonic·profile_keep·filter·sptext·zero_default·fixflow·fixlink·score_input·spouse_fix·sh_screen·lh_qa 0, 390px 요약 숫자·필터·카드 확인
- 백업: backup/20261007-1328-draw
- 기능: draw_path
- 버전: v1.60.0

## 2026-10-07 13:03 · 비슷한 면적 ㎡당 가격으로 시세 추정 — 시세 없던 공고 줄이기 A-2 (v1.59.0)
- 요청: "Abc순차로 진행해줘" — A. 시세 못 구하는 공고 줄이기 (A-1 부천 코드 다음)
- 근거: evidence/qa/market-probe.txt — 화성 향남역 그로브 스위첸 107A·B 는 같은 구 신축 ±3㎡ 거래 0건, ±10㎡ 12개월 21건(102.7·115.1㎡ 등). 큰 평형은 같은 평형 거래가 드물어 늘 '주변 거래 부족'
- 변경: 같은 평형 비교가 3건 미만이면 같은 구 준공 10년 이내 ±10㎡ 매매 5건 이상의 ㎡당 가격 중앙값(보수 = 하위 25%) × 전용면적(basis district_area_ppa). 기간·직거래 제외는 기존과 같음(최근 6개월). 화면 '비슷한 면적 ㎡당 추정' 표시·설명(mktHow). 독립 대조 market_check.expect 에도 따로 옮김
- 파일: app/market.py, app/rules.py, app/pipeline.py, tools/qa/market_check.py, tests/test_market_check.py, docs/index.html, docs/config.json, FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: pytest 211 통과(새 시험 2: 꺼짐 기본·독립 계산 일치·5건 미만/같은 평형 우선), 판정 사례 692/692, 스냅샷 0, e2e 34/34, 판정 일치 0, 390px 상세 설명 문구 확인. 올린 뒤 수집에서 107A·B 시세·market_check 일치 확인
- 백업: backup/20261007-1303-mktppa
- 기능: mkt_area_fallback
- 버전: v1.59.0

## 2026-10-07 13:01 · 부천시 실거래가 지역 코드 고침 — 시세 없던 공고 줄이기 A-1 (v1.58.9)
- 요청: "Abc순차로 진행해줘" — A. 시세 못 구하는 공고 줄이기
- 원인(evidence/qa/market-probe.txt, Actions '근거 자료 모으기' 2026-10-07): 마감 전 분양 주택형 중 시세 없는 12개 가운데 7개(상동역 롯데캐슬 시그니처)는 표의 부천시 코드 41190 이 원인 — 부천시가 2024-01 원미구·소사구·오정구로 나뉜 뒤 41190 은 최근 12개월 매매·분양권·전월세 모두 0건. 역지오코딩은 41192(경기도 부천시 원미구 상동), 41192 조회 매매 4,448건(상동 1,373)·같은 평형 신축 6개월 101건
  나머지 5개: 화성 향남역 그로브 스위첸 107A·B(±3㎡ 거래 0, ±10㎡ 12개월 21건), 147P·양평 123·146P·부천 187P(큰 평형·펜트하우스, 비교 거래 거의 없음)
- 변경: app/rules.py 경기 표 '부천시' 41190 → '부천시 원미구' 41192(확인한 것만), app/region.py 부천시 구(원미·소사·오정) 인식. 소사구·오정구와 구가 없는 부천 주소는 추측하지 않고 역지오코딩 기록(docs/lawd-cache.json)으로
- 파일: app/rules.py, app/region.py, tests/test_lawd_special_city.py, docs/changelog.json, VERSIONS.md
- 확인: pytest(이 변경 범위) 통과 — test_bucheon_gu_codes. 올린 뒤 수집에서 상동역 롯데캐슬 시그니처 시세가 채워지는지 확인
- 백업: backup/20261007-1301-bucheon
- 기능: 없음(수정)
- 버전: v1.58.9

## 2026-10-07 12:43 · 시세 없는 공고 점검 도구 (A 준비)
- 요청: "Abc순차로 진행해줘" — A. 시세 못 구하는 공고 줄이기 (마감 전 분양 52개 중 12개 주택형이 시세 없음: 부천 상동역 롯데캐슬 시그니처, 화성 향남역 그로브 스위첸, 양평 쌍용 더 플래티넘 한강)
- 변경: tools/qa/market_probe.py(새) — 시세 빈 주택형마다 실거래가(매매·분양권·전월세 12개월)를 표 코드·역지오코딩 코드로 다시 받아 지금 규칙(6개월·±3㎡·준공 10년)과 후보 규칙(12개월·±5·±10㎡·㎡당 가격)별 건수를 evidence/qa/market-probe.txt 에 남김. probe.yml(근거 자료 모으기)에 단계 추가
- 파일: tools/qa/market_probe.py, .github/workflows/probe.yml
- 확인: 문법 검사. 결과는 Actions '근거 자료 모으기'에서
- 백업: backup/20261007-1243-mktprobe
- 기능: 없음(도구)

## 2026-10-07 07:38 · LH 대구연호 통합공공임대 기준 중위소득 표 못 읽던 것 고침 (v1.58.8)
- 요청: (자체 점검) v1.58.7 올린 뒤 '판정 검증' 실패 — verify-status qa.lh_invariant_violations 1: 오늘 새로 수집된 2015122300020878 '[정정공고]대구연호 A-2BL, A-3BL 통합공공임대' 기준 중위소득 표를 읽지 못함
- 원인: 이 공고문 PDF 글에서 표 행 이름이 '1인 …'이 아니라 '인1 769,271 …'처럼 '인'이 숫자 앞에 나옴 → app/lh_terms.py income_table 이 행을 못 찾음(소득 기준 빈칸 → 화면 '공고문 확인')
- 변경: income_table 이 '1인'·'인1' 두 순서를 다 받음. 원문 '~100%' 열 1~8인 = 2026 기준 중위소득(MEDIAN_2026)과 같음을 공고문 글(evidence/lh/2015122300020878.txt 18쪽 표)에서 확인. 시험 test_median_table_label_after_number 추가
- 파일: app/lh_terms.py, tests/test_lh_terms.py (커밋 0159b2f3), 기록은 다음 커밋(WORK.md, docs/changelog.json, VERSIONS.md — 기록 스크립트 오류로 코드만 먼저 올라감)
- 확인: pytest 208 통과, 이 공고 parse_lh_terms → 기준 중위소득 1~8인 표 읽음·계층 4개. 올린 뒤 'LH 임대 수집'을 손으로 돌림
- 백업: backup/20261007-0738-lhmedian
- 기능: 없음(수정)
- 버전: v1.58.8

## 2026-10-07 06:37 · 시세 없는 공고의 잔금대출 0원·전세 0원 계산 고침 (v1.58.7)
- 요청: (자금 플랜 화면 사진) "근데 여기는 ltv 70%인데 왜 대출 0원으로 나와??"
- 원인: 잔금대출 집값 기준(LTV)을 min(분양가, 시세) × 70% 로 계산하는데, 주변 실거래 시세(mktBase)를 못 구한 공고는 시세가 비어 Math.min(분양가, null) = 0 → LTV 대출 0원. 전세 시나리오도 전세 시세가 없으면 보증금 0원으로 계산. 마감 전 분양 공고 52개 중 17개가 해당 — 자금 부족액이 크게 부풀려 보였음
- 변경(docs/index.html): funding — 시세가 없으면 분양가 기준 LTV(ltvEst), 규제지역 대출 한도 구간도 분양가로. 전세 시세가 없으면 jeonseUnk(0원으로 계산 안 함). fundUnsure: 전세 계획+전세 시세 없음 → '전세 보증금 입력 필요', 시세 미확인으로 LTV 가 한도를 정해 '가능'이면 '시세 확인 필요'(시세가 낮으면 대출이 줄 수 있어 단정 안 함). 목록 카드·상세 요약·납부 일정 점·시나리오 배지·비교표에 반영, LTV 줄에 '시세 미확인 · 분양가 기준' 표시, 전세 보증금 칸 '시세 없음'·부족분 줄 숨김, 전세 시세가 없으면 기본 계획은 잔금대출(실거주)
- 검사: tools/qa/cross_rule.cjs FUND-007(처음 FUND-006 으로 넣었다가 기존 번호와 겹쳐 v1.60.0 에서 바꿈) 추가 — 분양가가 있는데 LTV 대출 0원이면 CRITICAL, 전세 시세가 없는데 전세 시나리오가 부족분·여유분을 계산하면 HIGH. 고치기 전 코드에서 CRITICAL 로 잡힘, 고친 뒤 0
- 사진 사례(2026000463 107.9722A, 현금 5억·소득 6천만): 전 LTV 0원 → 잔금대출 1.9억 부족 / 후 LTV 4.75억(분양가 기준)·대출 3.01억(DSR 기준)·여유 1.11억 가능, 전세 끼고 잔금 = '전세 보증금 입력 필요'
- 파일: docs/index.html, tools/qa/cross_rule.cjs, tools/engine_lock.json, docs/changelog.json, VERSIONS.md, HANDOFF.md
- 확인: 판정 사례 692/692, cross 184,258회 충돌 0, 회귀 판정 바뀐 곳 0, 스냅샷 0, e2e 34/34, 변이 66(못 잡음 0), zero_default·consistency·monotonic·profile_keep·filter·sptext·fixflow·fixlink·spouse_fix·score_input·sh_screen·lh_qa 0, pytest 206 통과(엔진 잠금 갱신 전 1건 = 의도한 funding 변경), 390px 자금 플랜 화면 확인
- 백업: backup/20261007-0637-ltv
- 기능: 없음(수정)
- 버전: v1.58.7

## 2026-10-07 06:35 · 청약봇 V2 시험 실패 고침 (빈칸 규칙 뒤)
- 요청: (자체 점검, 사용자 "이제 뭐해야함" 전 상태 확인) Actions '청약봇 V2 시험(개발 중 — 배포 없음)'이 v1.58.3(76e3124d) 뒤로 계속 실패
- 원인: V2 봇이 받은 조건으로 내 조건을 만들 때 입력 표시(_set)를 달지 않아, 빈칸=모름 규칙(v1.58.3)에서 시험 조건의 배우자 집 '없음' 등을 빈칸으로 봄 → '신청 가능한 공고 추천'에 후보 0개 → 검사기 시험 TypeError
- 변경: chat/v2/engine.cjs·browser.mjs profileOf — 받은 조건에 적힌 칸을 넣은 칸으로(_set 이 없을 때만). 화면에 저장된 내 조건은 이미 _set 이 있어 그대로
- 파일: chat/v2/engine.cjs, chat/v2/browser.mjs
- 확인: node --test chat/v2/test/v2.test.mjs 94/94, chat/v2/quality/run.mjs 평균 99.8(기준선 99.8)·치명 0
- 백업: backup/20261007-0635-v2set
- 기능: 없음(수정 — 배포 안 된 개발 중 봇)

## 2026-10-07 00:22 · 입력 버튼 전수 검사·고침 (v1.58.6)
- 요청: "다른 입력조건들도 혹시 제대로 해당 칸에 접근하는지 전수검사해봐"
- 검사 도구: tools/qa/input_nav.cjs(새) — 조건 7개(빠른 시작 미혼·기혼 배우자 미답, 부모님 세대 청년, 다 넣은 신혼, 무작위 3) × 공고 상세(공고마다 1주택형, 상세 접힘 모두 펼침)·목록·내 조건·가점 컷·임대 상세(LH·SH 판정 공고)에서 입력 버튼(data-edit·data-fix·data-rq·restart·내 조건)을 하나씩 눌러, 커서·빨간 표시 칸이 보이는지와 그 칸에 실제 값을 넣으면 버튼이 가리키던 판정(그 항목·특별공급·가점·임대 계층)이 바뀌는지 확인(두 칸을 함께 답해야 하는 항목은 같이 표시된 빈칸을 채운 상태에서도). 내 조건이 있는데 처음부터 다시 시작하는 버튼도 문제로 봄
- 처음 결과(약 3,900번 누름): 문제 9종류 —
  ① 무주택 세대 '입력하기' → 이미 넣은 '세대 구성'(문구 '집 보유와 세대 구성')  ② 청약통장(통장 종류 비어 있음, 민영·국민) → 납입 회차  ③ '가구원수 입력 필요'·'특별공급 가구원수 산정' → 미성년 자녀 수·혼인 여부(가구원수는 같은 등본 자녀·부모님 수로 정함)
  ④ 해당지역 '전입일 입력 필요' → 시·도 전입일(광명 등 시 단위는 시·군 전입일)  ⑤ 특별공급 바로 답하기 → 무주택 확인인데 전입일  ⑥ 신혼희망타운 총자산 → 현금(빈 자동차 칸을 '0원'으로 보고 건너뜀)  ⑦ 모든 유형이 불가인 특별공급에 '비어 있는 정보 · 바로 답하기'  ⑧ 임대 고령자 '답하기' → 이미 답한 혼인 여부
- 고침(docs/index.html): 바로 답하기 — 가리키는 칸 중 아직 안 넣은 칸만 빨갛게·커서, 가리킨 순서대로 위에(fixPanel), FIX_TARGETS 에 집 보유·가구원수·통장 정보(먼저)·현금 묶음(끝), 항목이 판정 칸을 직접 알려 줌(거주지 fk: 해당지역 시·군/시·도 전입일), 가구원수 산정 → 같은 등본 자녀·부모님, 특별공급은 확인 문구 순서대로(무주택이면 본인·배우자 집 먼저), 청약통장 항목은 통장 종류가 비면 '통장 정보 입력 필요'. fieldValue: 비운 금액 칸은 '미입력'(내 조건 '부동산 0원' 표시도 고침). 특별공급 '비어 있는 정보' 안내는 불가가 아닌 유형이 있을 때만. 임대 답하기 커서는 첫 빈칸으로
- 고친 뒤: input_nav 3,885번 누름 문제 0. 매일 검사: verify.yml 에 input_nav(공고 40개), verify-status qa.input_nav_problems
- 파일: docs/index.html, tools/qa/input_nav.cjs, evidence/qa/input-nav.json, tools/verify_status.py, .github/workflows/verify.yml, tools/engine_lock.json, docs/changelog.json, VERSIONS.md, HANDOFF.md
- 확인: 판정 사례 692/692, 회귀 판정 바뀐 곳 0(항목 문구 183곳 = 빈 조건의 청약통장 '확인 필요' → '통장 정보 입력 필요'), e2e 34/34, 변이 66(못 잡음 0), fixflow 1085 모두 판정, fixlink·spouse_fix·score_input·zero_default·consistency·monotonic·profile_keep·filter·sptext·snapshot·sh_screen·cross·lh_qa 0, pytest 207 통과. 엔진 잠금 갱신(eligibility 문구·거주지 fk)
- 백업: backup/20261006-2320-inputnav
- 기능: 없음(수정)
- 버전: v1.58.6

## 2026-10-06 21:47 · 입력 버튼이 엉뚱한 곳으로 가던 것 고침 — 배우자 집·가점 입력하기 (v1.58.5)
- 요청: "배우자집 공고에서 입력할 때 제대로 입력이 안되거나 커서가 이상한 곳으로 가는데 확인 좀 해줘" · (21:56, 화면 2장) "통장가입일을 눌러도 이상한 곳이 떠" — 가점 칸 '통장 가입일을 넣으면 계산해요 · 입력하기' → 내 조건 1/15 '어디에 살고 계세요?'
- 재현(고치기 전 사이트, tools/qa/spouse_fix.cjs · score_input.cjs):
  ① 배우자 집 답하기 → 커서가 '두 분 모두 만 60세 이상인가요?'(parents60), 빨간 표시 2개, 배우자 질문은 '없어요'가 고른 상태로 '이미 넣은 값'에 접혀 누를 수 없음 → 판정 그대로 '배우자 명의 주택 입력 필요'.
     원인: 바로 답하기가 기본값 false 를 '답함'으로 봄(fieldValue·fieldHtml), 안내 문구의 '명의'가 다른 질문(hhOwner, 숨김)으로 연결
  ② 가점 '입력하기'(scoreCardV2·mcScore 칸·가점 컷 화면)와 1순위 요건 '입력하기'가 data-action=restart(처음부터 입력) → 늘 1단계
  ③ (점검 중 발견) 특별공급 바로 답하기의 무주택 질문 목록에 배우자 집이 없어 답해도 '무주택 확인 필요'가 남음(fixflow 1085개 중 140개)
- 변경: docs/index.html — fieldValue/fieldHtml: 넣지 않은 기본값 0·아니요 칸은 '미입력'·안 고른 상태. FIX_TARGETS: '배우자 명의 주택'→spouseOwn, '배우자 소득'→spouseIncome, '현금·예금·주식·전세보증금'→cash 등, hhOwner 는 '누구 명의·명의는 아니에요'일 때만. 판정을 가르는 칸을 알면 그 칸만 빨갛게. missEditBtn: 빠진 첫 항목(통장 가입일·생년월일·부양가족 등)이 있는 단계로 가서 그 칸에 커서·'이 칸을 넣으면 가점을 계산해요' 표시. SP_FIX 무주택에 married·spouseOwn
- 검사: tools/qa/spouse_fix.cjs(새), tools/qa/score_input.cjs(새) — verify.yml 에 추가. tools/qa/fixflow.cjs 자동 답이 기본값 칸도 채우게
- 파일: docs/index.html, tools/qa/spouse_fix.cjs, tools/qa/score_input.cjs, tools/qa/fixflow.cjs, .github/workflows/verify.yml, docs/changelog.json, VERSIONS.md, WORK.md
- 확인: spouse_fix 고치기 전 5건 문제 → 고친 뒤 통과(커서·빨간 표시 1개·없어요 → 충족), score_input 고치기 전 3가지 모두 1단계 → 고친 뒤 청약통장/가점 계산 단계의 그 칸, fixflow 1085개 모두 답하면 판정, fixlink 0, 판정 사례 692/692, e2e 34/34, 변이 66(못 잡음 0), consistency·monotonic·profile_keep·filter·sptext·snapshot·zero_default·sh_screen·회귀 0, pytest 207 통과
- 백업: backup/20261006-2147-spfix (가점 부분은 backup/20261006-2157-scorefix 이후 같은 커밋)
- 기능: 없음(수정)
- 버전: v1.58.5

## 2026-10-06 19:47 · 이용약관에 오픈카톡방 링크 (v1.58.4)
- 요청: "https://open.kakao.com/o/pKX5Z5Qi 이용약관에 오픈카톡 링크도 추가해서 연결되게끔해줘"
- 변경: docs/config.json open_chat_url = 사용자가 준 주소. docs/index.html 이용약관 제1조 운영 정보 표에 '오픈카톡 · 청약패스 오픈카톡방'(새 창, data-ev open-chat-terms) — 지금 약관과 10월 9일 바뀐 뒤 전문 모두. 약관 줄은 스위치와 관계없이 주소가 있으면 보임. 주소가 들어가면서 이미 만들어 둔 기능 community_link(true) 자리(이용 안내 오픈카톡방 카드·내 조건 줄)에도 나타남 — 끄려면 community_link false(약관 줄은 남음)
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, HANDOFF.md
- 확인: 390px 이용약관 — 운영 정보 표 맨 아래 '오픈카톡 청약패스 오픈카톡방', 누르면 새 창으로 open.kakao.com/o/pKX5Z5Qi, 화면 오류 0. 이용 안내·내 조건에도 링크 1개씩. 작업 환경에서 오픈카톡 페이지는 열 수 없음(카카오가 자동 접근 차단) — 방이 맞는지는 사용자 확인
- 백업: backup/20261006-1947-openchat
- 기능: community_link (약관 줄은 스위치 없이 주소 기준)
- 버전: v1.58.4

## 2026-10-06 19:06 · 입력하지 않은 기본값 0 칸 전부 점검·고침 (v1.58.3)
- 요청: "응 전부 점검한번해주고" (예치금 빈칸 0원 문제와 같은 원인 — 기본값 0·아니요 칸 전부)
- 점검 도구: tools/qa/zero_default.cjs(새) — 판정 사례 조건 6개 × 공고 105개 × 칸 9개(배우자 집·배우자 소득·배우자 대출·재당첨·예치금·현금·금융·보증금(한 묶음)·본인 소득·대출 월 상환)를 '넣지 않음'으로 바꾼 결과가 단정(가능·불가·2순위만·자금 부족/가능)인데 실제 값을 넣으면 달라지는지. 처음 26종류(배우자 집 88건 등) → 고친 뒤 0
- 원인과 고침 (docs/index.html):
  ① 혼인 중·배우자 명의 집 미답(기본값 false) → 무주택 '충족'. 빠른 시작에 '배우자' 단계가 없어 늘 미답 → 무주택 세대 '배우자 명의 주택 입력 필요'(확인), 빠른 시작에 '배우자' 단계(혼인 중일 때만)
  ② 배우자 소득 미입력(기본값 0) → 외벌이로 보고 '불가', 세대 소득도 없으면 본인 소득만으로 세대 소득을 추정해 '가능' → incKnown(혼인 중이면 세대 소득 또는 배우자 소득을 넣어야 소득을 앎, 본인 소득 0원이라고 넣으면 0원으로 앎)·dualUnknown(맞벌이 기준이면 될 수 있으면 확인). 신혼희망타운·공공 일반공급·총자산형·공공임대 특별공급·특별공급 소득 단계
  ③ 현금·예금·주식·보증금 하나도 미입력 → 총자산 계산에 0원 → 총자산 항목에 '현금·예금·주식·전세보증금' 빠짐으로 확인(하나라도 넣었으면 나머지 빈칸은 0, 같은 입력 단계)
  ④ 자금: 현금·소득 미입력이면 '자금 X억 부족'·계약금 '부족' 대신 '자금은 현금·예금·소득 입력 필요'(0원으로 계산해도 가능하면 '가능' 그대로). 목록 카드·상세 판정 상자·납부 일정·계획 화면·비교표
  - 재당첨(recentWin)은 거짓 경보: 당첨 이력 '없음'이라고 답하면 재당첨 제한 아님(syncV2), 당첨 이력을 비우면 '해당 없음'은 기능 optional_inputs(드문 질문은 비우면 해당 없음)의 원래 결정 — 그대로 둠
- 판정 사례: 생성기 add() 가 분양 사례 조건을 '모든 칸 입력함'(_set)으로 표시(기존 기대값 유지), 빈칸 사례 zero-00~10·zero-sp-* 15건 추가(배우자 집 미답/없음/있음, 2026000414 신혼부부 140% 초과 배우자 소득 미입력→확인·0원→불가·세대 소득도 없음→확인, 본인 소득만 100% 이하→확인, 공공 일반 100% 초과, 신혼희망타운 현금 미입력, 광명 민영 특공 예치금 미입력). edge-19 는 '소득 모름'을 입력 표시로 명시. 692건 일치. 변이 6개 추가(빈칸 4·예치금 경로 2), 패턴이 바뀐 LH 변이 3개 고침 → 66개 못 잡음 0
- 회귀·스냅샷 도구의 고정 조건도 '적어 둔 칸 = 넣은 칸'으로 표시(regress·snapshot). 스냅샷 기준 갱신: '인천 1인 세대원'(현금 칸 없음) 공고 3곳 총자산이 '확인'으로 — 의도한 변화
- 매일 검사: collect.yml·verify.yml 에 zero_default, verify-status qa.zero_default_violations(0 아니면 실패)
- 엔진 잠금 갱신(spJudge·accountItems·eligibility·funding 등 의도한 판정 수정)
- 파일: docs/index.html, tools/qa/zero_default.cjs, evidence/qa/zero-default.json, tools/make_judge_cases.py, tests/judge/cases.json, tools/qa/{code_mutation,regress,snapshot}.cjs, tests/qa/snapshots.json, tools/engine_lock.json, tools/verify_status.py, .github/workflows/{collect,verify}.yml
- 확인: 판정 사례 692/692, zero_default 0, 회귀(regress) 바뀐 곳 0, e2e 34/34, 변이 66(못 잡음 0), monotonic·consistency·profile_keep·filter·sptext·snapshot·cross·lh_qa 0, pytest 207 통과(test_pipeline 은 fastapi 없음). 빠른 시작(혼인 중) 재현: 배우자 단계가 나옴. 목록 카드 '기본 요건 충족 · 자금은 현금·예금·소득 입력 필요'
- 백업: backup/20261006-1906-zero
- 기능: 없음(수정)
- 버전: v1.58.3

## 2026-10-06 18:24 · 목록 '결과 N곳 · 주택형 N' 줄바꿈 깨짐 고침 (v1.58.2)
- 요청: "결과를 '신청 가능'으로 거르면 위쪽 '결과 3곳 · 주택형 22' 글자가 좁게 줄바꿈돼서 깨져 보여요"
- 원인: 결과 글자(.filterbar .count)가 flex:1·min-width:0 이라 옆에 '내 판정: 신청 가능 ×' 버튼이 붙으면 글자 칸이 줄어 낱말 중간에서 꺾임(390px 2줄, 320px 4줄)
- 변경: 결과 글자는 한 줄로(nowrap·필요한 폭 확보), 자리가 모자라면 옆 버튼이 다음 줄로. 업데이트 내역 v1.58.2 (예치금 고침과 함께)
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 신청 가능 거르기 재현 도구로 390·360·320px — 결과 글자 높이 40px(2줄)·141px(4줄) → 20px(1줄), 버튼은 다음 줄. 스냅샷·filter 검사 0
- 백업: backup/20261006-1822-deposit
- 기능: 없음(수정)
- 버전: v1.58.2

## 2026-10-06 18:22 · 예치금 빈칸을 0원으로 보던 판정 고침 (빠른 시작 '1순위 미충족·2순위만')
- 요청: "예치금 문제: 빠르게 시작하기는 예치금을 안 물어요(건너뛸 수 있음). 통장이 있는 사람도 예치금을 0원으로 계산해서 민영 공고 대부분이 '1순위 미충족, 2순위만'으로 나와요. 입력을 안 했을 뿐인데 '확인 필요'가 아니라 '안 된다'고 보여 줘요"
- 원인: 분양 판정의 민영 예치금이 (p.acctAmount || 0) — 기본값 0 과 '0원이라고 넣음'을 구분하지 않음(소득은 0 을 모름으로 보는데 예치금만 빠져 있었음). 재현: 빠른 시작(서울·세대주·무주택·종합저축 2018 가입, 예치금 비움) → 마감 전 민영 33건 예치금 모두 '내 0만 · 300만 필요' 미충족, 요약 '2순위만 22'
- 변경: docs/index.html accountItems·spJudge 예치금을 pv(p,'acctAmount')(입력 표시 _set 이 있을 때만 값)로 — 비워 두면 '예치금 입력 필요 · N만 필요'(확인 필요), 0원이라고 넣으면 미충족 그대로. 내 정보 예치금 '미입력', 내 조건 한 줄의 '현금 0원'도 현금·금융·보증금을 하나도 넣지 않았으면 '현금 미입력'. tools/bot/cy.js(청약봇)는 질문에 적힌 칸만 입력한 것으로 봄
- 판정 사례: acct 4건 추가(예치금 비워 둠 → 확인 / 0원 넣음 → 미충족 / 200만 → 충족 / 199만 → 미충족, 2026000453 경기 85㎡ 이하 200만원). 변이 '예치금 빈칸을 0원으로' 추가 — 잡힘. 엔진 잠금(tools/engine_lock.json) 갱신: spJudge·accountItems (의도한 판정 수정)
- 파일: docs/index.html, tools/make_judge_cases.py, tests/judge/cases.json, tools/qa/code_mutation.cjs, tools/bot/cy.js, tools/engine_lock.json
- 확인: 빠른 시작 재현 도구로 다시 — 예치금 33건 모두 '확인 필요', 요약 '2순위만 22' → '확인 필요 22'. 판정 사례 677/677, 회귀(regress) 판정 바뀐 곳 0(예치금을 넣은 조건은 그대로), 변이 61(못 잡음 0), monotonic·consistency·e2e 34/34·profile_keep·snapshot 0, pytest 207 통과(test_pipeline 은 fastapi 없음)
- 백업: backup/20261006-1822-deposit
- 기능: 없음(수정)

## 2026-10-06 18:20 · 이용약관 표기 공개 뒤 확인 · 인계 기록
- 요청: (작업 마무리) CLAUDE.md 8항
- 변경: HANDOFF.md 진행 중인 일에 약관 표기 항목
- 확인: '판정 검증' Actions 성공(0144cbde), 다시 만든 정적 /terms/ 에 실명 0건·'청약패스 운영자(이하' 2건, verify-status ok true, 열린 이슈 0
- 백업: backup/20261006-1807-terms (기록만 바뀜)
- 기능: 없음(기록)

## 2026-10-06 18:07 · 이용약관 운영자 표기 '청약패스 운영자'로
- 요청: "이용약관에 차진혁으로 되어있는곳 청약패스 운영자로 바꿔줘"
- 변경: docs/index.html 이용약관 제1조 '이 약관은 청약패스 운영자(이하 "운영자")가 제공하는…'과 제1조 아래 운영 정보 표 '운영: 청약패스 운영자 (개인)'. 지금 약관과 10월 9일 바뀐 뒤 전문 모두 같은 함수라 함께 바뀜. 개인정보처리방침(서두·9. 개인정보 보호책임자)과 config privacy_officer 는 그대로 — 요청 범위 밖이고, 개인정보 보호법상 보호책임자는 성명(또는 담당 부서)과 연락처를 적게 되어 있음
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 390px 이용약관 화면 — 펼친 글·접힌 '바뀐 뒤 전문' HTML 모두 실명 0건·'청약패스 운영자(이하' 2건, 개인정보처리방침은 실명 그대로, 화면 오류 0, 스냅샷 바뀐 곳 0, pytest 통과(test_pipeline 은 fastapi 없음 — 기존과 같음). 정적 /terms/ 페이지는 '판정 검증' Actions 가 다시 만듦
- 백업: backup/20261006-1807-terms
- 기능: 없음(수정)
- 버전: v1.58.1

## 2026-10-06 18:05 · 운영 스킬에 SH 판정 요령 기록 · 공개 뒤 확인
- 요청: (작업 마무리) CLAUDE.md 8항 — 새로 알게 된 요령을 스킬에
- 변경: .claude/skills/cheongyakpass-ops/SKILL.md 에 SH 판정 엔진·생성기·검사 도구를 함께 고쳐야 하는 점
- 확인: v1.58.0(1a769553) 뒤 '판정 검증' 성공, verify-status ok true(사례 673/673, lh_qa·lh_screen·e2e 실패 0), 열린 이슈 0
- 백업: backup/20261006-1751-shjudgeon (바로 앞 상태, 기록·스킬만 바뀜)
- 기능: 없음(기록)

## 2026-10-06 17:51 · SH 신혼·신생아·청년 매입임대 자격 판정 공개 (sh_judge 켬, v1.58.0)
- 요청: "2단계진행해줘" — 검증 뒤 켜기
- 변경: docs/config.json sh_judge true, 업데이트 내역 v1.58.0(접수 타일 고침 포함)
- 파일: docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md(sh_judge 커밋 번호), HANDOFF.md, WORK.md(17:28 항목 백업 이름 바로잡음 1728 → 1726)
- 확인: 끈 상태로 올린 9991d08c 뒤 Actions — 'SH 임대 수집' 기록 '[검증] 신청자격 정답 데이터 대조 일치 (자격 읽은 공고 5건)', '판정 검증' 성공(사례 673/673), verify-status ok true, lh_qa·lh_screen·e2e·cross 실패 0, 열린 이슈 없음. 켠 설정 로컬 전체 QA 는 17:25 항목
- 백업: backup/20261006-1751-shjudgeon
- 기능: sh_judge
- 버전: v1.58.0

## 2026-10-06 17:28 · 임대 상세 '접수' 타일 날짜 잘림 고침
- 요청: (자체 발견) SH 2단계 390px 화면 확인 중 임대 상세 판정 상자의 '접수 10.13~10.15' 타일이 세 칸일 때 '10.13~10.1' 로 잘려 보임 (LH·SH 공통)
- 변경: 접수 타일 날짜를 물결표(~) 뒤에서 줄바꿈할 수 있게(<wbr>) — 칸이 좁으면 '10.13~ / 10.15' 두 줄
- 파일: docs/index.html
- 확인: 390px 스크린샷(SH-310650 상세)에서 두 줄로 다 보임, 스크립트 문법, 스냅샷(글자) 바뀐 곳 0
- 백업: backup/20261006-1726-tile
- 기능: 없음(수정)

## 2026-10-06 17:25 · SH 2단계 — 신혼·신생아 매입임대·청년 매입임대 자격 판정 (sh_judge, 아직 꺼짐)
- 요청: "2단계진행해줘" (SH 공고 종류별 자격 판정 — 청년 매입임대·신혼·신생아 매입임대부터, 정답 데이터·감사·스위치)
- 원문 확인: 신혼·신생아 매입임대Ⅰ(310650)·Ⅱ(310653), 청년 특화형 매입임대(310950·309807·309802) 공고문의 신청자격·소득 및 자산 기준 절을 직접 읽음. Ⅰ 소득 70%(배우자 소득 있으면 90%)·2인 +10%p, 총자산 34,500만(출산 1명 37,900·2명 41,300), 자동차 4,542만(4,996·5,451), 신생아가구 '24.10.1. 이후 출생·태아(혼인 무관), 신혼 혼인신고일 '19.10.1.~, 6세 이하 자녀 '19.10.1. 이후 출생, 지원대상 한부모가족 소득·자산검증 불필요 / Ⅱ 130%(200%)·총자산 36,200만(39,600·43,100)·자동차 개별 기준 없음·혼인가구 / 청년 만19~39세·미혼·본인 무주택·세대 소득 100%(1인 120%·2인 110%)·세대 총자산 34,500만·자동차 4,542만, 출산 가산 없음. 공고문 소득표 금액 = 앱 도시근로자 2025(RENT_URBAN_2025) × 퍼센트 확인
- 변경:
  - app/sh_terms.py(새): 공고문에서 위 기준을 읽음. 소득표 금액을 도시근로자 2025 × 퍼센트와 대조해 다르면 소득 기준을 비움(→ '공고문 확인'), 면제 문장을 못 찾으면 면제로 안 봄
  - app/sh_rental.py: 신혼·신생아·청년 매입임대 공고에 terms·judge_type, 수집 기록에 계층·[검증·정답 불일치]
  - docs/index.html(판정 엔진, LH 공고에는 영향 없음 — 새 칸이 있을 때만 동작): 계층 신생아가구·지원대상 한부모가족·혼인가구, 신혼 날짜 하한(wed_from·kid6_from), 검증 면제(exempt), 출산가구 표 금액(asset_bonus·car_bonus)으로 바로 판정·소득 출산 가산 없음(birth_bonus), 자동차 개별 기준 없음, 청년 세대 소득·자산(income_household), 답하기 칸 '임신 중'·'지원대상 한부모가족'. 상세 '공고문 자격 기준'에 SH 기준 줄. 스위치 sh_judge 가 꺼져 있으면 SH 는 모두 '판정 미지원'(1단계와 같음)
  - 애매한 곳은 '확인': 청년 공고는 자격을 '무주택자(본인)'로 적지만 Ⅷ 에서 '세대구성원 전원을 대상으로 주택소유 여부를 확인' → 같은 세대(부모님)에 집이 있으면 판정하지 않음(블라인드 검토자가 짚은 점)
- 정답: tests/golden/sh_rental.json 에 terms 5건(원문 인용 포함), 309807 추가. tests/test_sh_terms.py(정답 일치·소득표 어긋나면 비움·면제 문장 없으면 면제 아님·미혼 문장)
- 판정 사례: tools/make_judge_cases.py 18) SH — 67건(경계값: 소득 2인 80%/100%·140%/210%·3인 70%/130% 이하·초과, 혼인신고 2019-10-01/09-30, 6세 자녀 출생 2019-10-01/09-30, 신생아 2024-10-01/09-30, 총자산·자동차 한도·출산 표 금액 ±1만, 청년 1986-10-03/02·2007-10-02/03 출생, 세대 소득·세대 집). 조건은 tests/judge/sh_notices.json(정답 데이터에서 생성). 사례 673건 전부 일치
- 블라인드 감사: evidence/audit/2026-10-06-sh — 코드를 보지 않은 별도 검토자가 공고문만 읽고 12개 조건 × 계층 31칸 판정(blind.json) ↔ 앱(compare.cjs) 다름 0
- 검사 도구: lh_qa 답하기 채우기에 sh*·pregnant, cross_rule LH-ELIG-001 맞벌이 상한을 공고문 dual_add(+70%p)까지, code_mutation SH 변이 8개(모두 잡힘), sh_screen 에 sh_judge 켬/끔
- 파일: app/sh_terms.py, app/sh_rental.py, docs/index.html, docs/config.json(sh_judge:false), tests/golden/sh_rental.json, tests/test_sh_terms.py, tests/judge/cases.json, tests/judge/sh_notices.json, tools/make_judge_cases.py, tools/judge_check.cjs, tools/qa/{lh_qa,cross_rule,code_mutation,sh_screen}.cjs, evidence/audit/2026-10-06-sh/
- 확인(로컬, sh_judge 켠 설정 + 저장된 공고문으로 다시 만든 sh-rental.json): pytest 207 통과(test_pipeline 은 fastapi 없음 — 기존과 같음), 판정 사례 673/673, lh_qa(퍼징·단조성·답하기 고리 0·정보 감소 새 '가능' 0), cross 0, e2e 34/34, 변이 60(못 잡음 0), consistency·monotonic·profile_keep·filter·sptext·snapshot·regress 0, sh_screen 통과, 390px 상세 화면 확인
- 백업: backup/20261006-1725-shjudge
- 기능: sh_judge

## 2026-10-06 16:04 · 판정 검증 실패(이슈 #6) 고침 — LH QA 카드 글자 비교
- 요청: (자체) v1.57.0 을 올린 뒤 '판정 검증' Actions 가 '검증 요약 저장'에서 실패, 이슈 #6
- 원인: tools/qa/lh_qa.cjs 의 '카드 = 판정' 비교가 옛 이름표(R_HEAD '판정 미지원 유형')로 비교 — 화면은 sh_rental 이 켜지면 '판정 미지원 · 공고문 확인'(rHead). SH 공고 8건이 '다름'으로 잡혀 lh_judge_qa_fails 8 → verify-status ok false. 화면·판정 오류가 아니라 검사 도구가 화면의 이름표 함수를 쓰지 않은 것
- 변경: lh_qa.cjs 가 화면의 rHead 로 비교(없으면 R_HEAD)
- 파일: tools/qa/lh_qa.cjs
- 확인: 켠 설정으로 lh_qa 카드 38 다름 0, past_chat·supply_type·lh_pdf_tools 0, verify_status 통과. 바로 앞 커밋(8d9a189f 운영 스킬에 SH 함정 기록)은 이 항목으로 기록을 대신함
- 백업: backup/20261006-1604-lhqa
- 기능: 없음(수정)

## 2026-10-06 15:50 · SH 임대 공고 공개 (sh_rental 켬, v1.57.0)
- 요청: "응 너가 추천하는방향으로 진행해줘" — SH 공고 1단계 마무리(검증 뒤 켜기)
- 변경: docs/config.json sh_rental true. 업데이트 내역 v1.57.0
- 파일: docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md(sh_rental 줄), HANDOFF.md
- 확인: 켠 설정으로 lh_rental.cjs 문제 없음(판정 분포에 unsupported 8 = 마감 전 SH 공고), e2e 34/34, sh_screen 통과. 끈 상태 전체 QA 는 바로 앞 커밋(15:44) 기록
- 백업: backup/20261006-1550-shon
- 기능: sh_rental
- 버전: v1.57.0

## 2026-10-06 15:44 · SH 임대 공고 화면 연결 (sh_rental, 아직 꺼짐)
- 요청: SH 공고 1단계 — 공공임대·청년 주택 탭에 SH 공고(기관 표시·유형·공고일·공고문·SH 링크), 접수 기간은 확실할 때만, 판정은 '판정 미지원 · 공고문 확인'
- 변경: docs/index.html — 기능 sh_rental 이 켜지면 sh-rental.json 을 LH 공고와 함께 불러 공고일 순으로 섞음(SH 를 못 불러도 LH 는 그대로). 접수 기간이 지난 SH 공고, 기간을 못 읽었고 공고일이 30일 넘은 SH 공고는 싣지 않음. 카드·목록 창 'SH' 표시, 유형 고르기에 SH 유형(청년안심주택·장기전세·사회주택·매입임대 등), 청년 대상 SH 공고는 청년 주택에도. 접수 기간을 못 읽은 SH 공고는 '접수 중'이 아니라 '일정 공고문 확인'(요약 '접수 중'에도 안 셈). 상세: 출처 'SH 인터넷청약시스템 공고', 판정 '판정 미지원'+공고문 확인 안내, 보증금·주택 목록은 공고문 확인, '(1순위)' 표시, 하단 버튼 'SH 공고 ↗'(SH 공고 화면)·모집공고문. 끄면 이전과 같음(sh-rental.json 도 안 부름)
- 링크 근거: evidence/qa/sh-links.txt (Actions, 쿠키 없는 새 연결) — 공고 화면 PC·모바일 200·제목 보임, 공고문 주소 바로 열면 PDF(내려받기)·수집한 접수 문구가 PDF 에 있음(310950·310653·310650)
- 파일: docs/index.html, tools/qa/sh_screen.cjs(새 화면 점검: 켜짐/꺼짐·밝은/어두운·SH 공고 전부 상세·버튼 주소·판정 문구·일정 배지·1순위), tools/qa/lh_rental.cjs(판정 값 unsupported·partial 허용, 하단 버튼 lh-/sh- 둘 다)
- 확인: 스크립트 문법, pytest 202 통과(test_pipeline 은 이 환경에 fastapi 없음 — 기존과 같음), 판정 사례 606/606, lh_qa·lh_inv·cross·e2e 34/34·변이 52(못 잡음 0)·consistency·monotonic·profile_keep·filter·sptext·snapshot·regress 모두 0, sh_screen 통과(마감 전 8/18건), 390px 스크린샷(목록·청년·상세 밝은/어두운) 확인 — '출처: 출처' 겹침 발견해 고침
- 백업: backup/20261006-1544-shui
- 기능: sh_rental

## 2026-10-06 15:15 · SH 공고 링크 점검 도구 (화면 연결 전 확인)
- 요청: SH 공고 1단계 — 공고문·SH 공고 화면 링크 달기 전에 실제로 열리는지 확인(CLAUDE.md 5 출처 링크 원칙)
- 변경: tools/qa/sh_links.py — 쿠키 없는 새 연결로 SH 공고 화면(PC·모바일)과 공고문 내려받기 주소를 열어, 제목이 보이는지·PDF 가 오는지·PDF 에 수집한 접수 기간 문구가 있는지 evidence/qa/sh-links.txt 에 남김. 'SH 임대 원천 점검' 워크플로에 추가. 화면·수집은 바꾸지 않음
- 파일: tools/qa/sh_links.py, .github/workflows/sh-probe.yml
- 확인: Actions 실행 결과(evidence/qa/sh-links.txt)
- 백업: backup/20261006-1515-shlink
- 기능: 없음(점검 도구)

## 2026-10-06 15:08 · SH 접수 기간 읽기 다듬기 + 정답 데이터 12건 (sh_rental, 아직 꺼짐)
- 요청: SH 공고 1단계 계속 — 접수 기간은 확실할 때만 보여주기
- 원인: 첫 수집 19건을 원문과 대조하니 표 형식 일정(공고 ▶ 주택공개 ▶ 청약접수 …)에서 '주택공개' 날짜를, '동시접수'·'우편접수' 안내에서 다른 날짜를 접수 기간으로 잘못 읽은 공고가 있었음(310673, 310258)
- 변경: app/sh_rental.py — 접수 낱말을 '청약(신청)접수·신청접수·서류접수·인터넷접수·접수기간'으로 좁히고, 물결표(~) 바로 앞 날짜를 시작일로 잡음. 화살표 일정표·우편/방문 접수 안내·시작일과 물결표 사이에 다른 날짜가 끼면 읽지 않음(빈칸 → 화면은 '공고문 확인'). 2자리 연도('26.9.29) 읽기, '1순위' 표시(rank1). 제목에 경쟁률·게시 들어간 글 제외
- 정답: tests/golden/sh_rental.json — 공고문 원문을 직접 읽은 12건(읽어야 하는 7건은 값 일치, 표·우편 형식 5건은 비우거나 정답과 같을 때만 허용)
- 파일: app/sh_rental.py, tests/test_sh_rental.py, tests/golden/sh_rental.json
- 확인: pytest test_sh_rental 5 통과(실제 공고문 글로 정답 12건 대조, 일정표·우편접수·1순위 사례 추가)
- 백업: backup/20261006-1508-sh2
- 기능: sh_rental

## 2026-10-06 14:58 · SH 임대 모집공고 수집 1단계 (sh_rental, 아직 꺼짐)
- 요청: "응 너가 추천하는방향으로 진행해줘" (SH 공고 1단계: 목록·접수 기간·공고문 연결, 판정 미지원 표시 → 2단계 종류별 판정)
- 변경: app/sh_rental.py — SH 인터넷청약시스템 주택임대 게시판(최근 60일, 최대 6쪽)에서 입주자 모집공고만(발표·결과·계약 안내·심사·재계약 등 제외) 골라 상세의 첨부 목록(downList)에서 공고문 PDF 를 받아(existFile → innoFD) 글을 evidence/sh/<글번호>.txt 에 한 번 저장. 종류(제목 낱말: 청년안심주택·장기전세·사회주택·신혼·신생아 매입임대·청년 매입임대·매입임대·행복·국민·영구·장기안심·공공임대), 청년 대상(제목), 접수 기간(공고문 '접수' 뒤 140자 안 날짜 범위, 등록일 뒤 120일 안·60일 이하만)을 docs/sh-rental.json 으로. 자격 판정은 하지 않음(judge_type false). 0건이면 지난 결과 유지. 워크플로 'SH 임대 수집'(매일 06:50, 다른 수집과 따로). 스위치 sh_rental 은 false — 정답 데이터 확인 뒤 화면 연결
- 파일: app/sh_rental.py, .github/workflows/sh-rental.yml, tests/test_sh_rental.py, docs/config.json(sh_rental:false)
- 확인: pytest test_sh_rental 5 통과(실제 받은 목록·상세 화면으로 줄·첨부 읽기, 종류·거르기, 접수 기간 규칙: 해 넘김·옛 날짜·너무 긴 범위 거름)
- 백업: backup/20261006-1458-sh
- 기능: sh_rental

## 2026-10-06 14:39 · SH 임대 공고 원천 점검 도구 (조사 단계)
- 요청: "이어서 할일은 3번 진행해야될꺼같네" (임대 범위 넓히기 — SH 공고 추가 조사). 같은 메시지에서 LH 청약플러스 공고 버튼(lh_cta)이 실제 공고로 열리는 것을 사용자가 확인함 "1번 정상적으로됨"
- 조사: 공공데이터포털·서울 열린데이터광장에 SH 임대 '모집공고' API 없음(서울 열린데이터 OA-12918 은 국민임대 공급계획 연간 파일). SH 인터넷청약시스템 '공고 및 공지 > 주택임대' 게시판은 공개(작업 환경 WebFetch 로 목록 확인: 신혼·신생아 매입임대, 청년안심주택, 장기전세 등)
- 변경: tools/qa/sh_probe.py + 워크플로 'SH 임대 원천 점검'(sh-probe.yml, 손으로·도구 바뀔 때만) — Actions 서버에서 목록·상세·첨부 PDF 를 받을 수 있는지, 목록 구조와 첨부 이름, PDF 글자를 evidence/qa/sh/ 에 남김. 화면·수집·판정은 바꾸지 않음
- 파일: tools/qa/sh_probe.py, .github/workflows/sh-probe.yml
- 확인(Actions 'SH 임대 원천 점검' 4회, evidence/qa/sh-probe.txt): ① 목록 list.do 200 — 글은 <a onclick="getDetailView('310653')"> 형식, 줄마다 글번호·제목·날짜 읽힘(10건) ② 상세 view.do?multi_itm_seq=2&seq=<글번호> GET 200, 첨부 목록은 initParam.downList(brdId·seq·fileSeq·oriFileNm) ③ 첨부 내려받기: innorix.config.js 의 existFile → POST /com/file/existFile.do(resultCode 1) → GET /com/file/innoFD.do?brdId&seq&fileSeq&fileTp=A 로 PDF(1.38MB, 19쪽) 받음, pypdf 로 글 읽힘(소득 기준·보증금·월세 표). 미리보기(htmlConverter)는 글이 없어 못 씀
- 백업: backup/20261006-1439-shprobe
- 기능: 없음(조사 도구)

## 2026-10-06 13:09 · 임대 요약 숫자 → 아래 목록 창 (lh_sheet)
- 요청: "청년임대 공공임대의 접수중 거기 란도 일반분양처럼 누르면 팝업처럼 뜨도록 해줘. 필터처럼 걸리게하지말구"
- 변경: 임대 목록 요약(접수 중·새 공고 7일·이번 주 마감)을 누르면 분양 summary_sheet 와 같은 모양의 아래 목록 창. 창에는 그 묶음의 공고(지금 탭·유형·지역 거르기 따름) — 이름(두 줄)·유형·지역·판정 글자·일정 배지, 누르면 상세, 배경·닫기·Esc 로 닫음. 목록은 걸러지지 않음. 판정 묶음(신청 가능·확인 필요·조건 밖)은 그대로 거르기
- 파일: docs/index.html(rentalSheet), docs/config.json(lh_sheet), tools/qa/lh_rental.cjs(창 공고 수 = 숫자, 뒤 목록 그대로, 닫힘), docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 390px 캡처(이름 잘림 → 두 줄·판정을 아래 줄로 고침), lh_rental.cjs 문제 없음, pytest 197, judge 606/606, lh_qa·cross_rule·e2e 34/34·code_mutation·consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 분양 1,125조합 변화 0·화면 1,401 오류 0
- 백업: backup/20261006-1309-lhsheet
- 기능: lh_sheet
- 버전: v1.56.0

## 2026-10-06 12:21 · '확인이 필요한 조건' 입력 버튼이 그 칸으로
- 요청: "여가 청약통장 가입기간 입력하기 누르면 청약통장 가입기간 입력하는곳으로 가게해줘" (일반공급 탭 '확인이 필요한 조건 1 · 내 조건 입력하기' 캡처)
- 원인: 머리의 '내 조건 입력하기' 버튼이 data-action="restart"(인터뷰 처음부터)라 필요한 칸을 찾아가야 했음
- 변경: 입력이 필요한 첫 항목(청약통장 1순위 요건 → 청약통장, 그 밖에 '입력 필요' 항목)에 바로 답하기 칸이 있으면 버튼 이름을 '<항목> 입력하기'(예: 청약통장 가입기간 입력하기)로 하고 누르면 그 항목의 바로 답하기를 열어 첫 칸(가입일)에 커서. 바로 답하기 칸이 없으면 예전처럼 처음부터 입력
- 파일: docs/index.html(checklistV2), tools/qa/fixlink.cjs(새 검사: 통장 가입일 비운 조건으로 공고 상세 → 버튼 → 바로 답하기 열림·가입일 칸 커서), docs/changelog.json, VERSIONS.md
- 확인: fixlink 공고 4개 문제 0, fixfocus 1,120 열림·표시·닫힘, pytest 197, judge 606/606, cross_rule·e2e 34/34·code_mutation·consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 판정 1,125조합 변화 0·화면 1,401 오류 0
- 백업: backup/20261006-1221-fixlink
- 기능: 없음(개선 — inline_fix 안)
- 버전: v1.55.1

## 2026-10-06 11:41 · 공공임대·청년 주택 화면 정리 (lh_ui_v2)
- 요청: "공공임대랑 청년주택 .. 뭔가 ui/ux가 좀 정신없는데.. 이거 최적화할 방법없을까?"
- 진단(390px 캡처): ① 목록 위 거르기 버튼이 두 줄(유형 7개·지역 13개 가로 스크롤) ② 카드마다 유형·완화 알약·지역·상태·'입력한 조건 기준'이 반복 ③ 상세가 같은 크기 카드 7개(머리·내 자격·자격 기준·일정·주택형·보증금·단지)를 나열해 판정이 작게 묻힘
- 변경: ① 유형·지역을 고르기 칸(select) 2개 + 초기화 ② 카드 = 위 줄(유형·지역·자격 완화 | 일정 배지: 접수 중·오늘 마감·D-n, 분양 dday 색) · 이름 · 전용·보증금·월세 한 줄 · 판정+계층 ③ 상세 = 머리(유형·지역 | 일정 배지, 이름) → 판정 상자(분양 rhero 와 같은 모양, 큰 글자 + 접수·보증금·월·계층 타일, 누르면 그 칸으로) → 내 자격 → '공고 한눈에'(일정·주택형·보증금 한 카드) → 접은 '공고문 자격 기준 보기'·'단지 정보' → 하단 버튼. 판정 함수·숫자는 그대로
- 파일: docs/index.html, docs/config.json(lh_ui_v2), FEATURES.md, docs/changelog.json, VERSIONS.md
- 확인: 스크립트 문법, lh_rental.cjs(밝은·어두운 390px 목록·청년·상세 30건, 가로 넘침·이상 글자 없음, 요약 거르기·하단 버튼 검사) 문제 없음, 캡처로 타일 글자 넘침 고침(보증금·월 두 줄), pytest 197, judge 606/606, lh_qa·cross_rule·e2e 34/34·code_mutation·consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 분양 1,125조합 변화 0·화면 1,401 오류 0
- 백업: backup/20261006-1141-lhux
- 기능: lh_ui_v2
- 버전: v1.55.0

## 2026-10-06 11:41 · 청년 주택 탭 새로고침하면 공공임대로 바뀜
- 요청: "청년주택에서 새로고침하면 공공임대로 가던데 이부분 수정해주고"
- 원인: 임대 목록 주소가 탭과 관계없이 #/rental 하나라 새로고침하면 기본 탭(공공임대)으로 열림. 탭을 바꿔도 같은 화면이라 주소를 바꾸지 않았음
- 변경: 청년 주택 탭은 #/rental/youth, 공공임대는 #/rental. 탭을 바꾸면 주소만 바꾸고(기록은 쌓지 않음), 새로고침·뒤로 가기·공유 주소로 열 때 탭을 되살림
- 파일: docs/index.html(navId·navUrl·navApply·탭 버튼), tools/qa/e2e.cjs(청년 주택 → 새로고침 → 그대로, 공공임대 탭 주소, 상세에서 뒤로 가면 탭 유지), docs/changelog.json, VERSIONS.md
- 확인: e2e LH 시나리오 통과(새 검사 포함)
- 백업: backup/20261006-1141-lhux
- 기능: 없음(수정)
- 버전: v1.54.1

## 2026-10-06 11:28 · 청약봇 답변 도구를 저장소에 (tools/bot/cy.js)
- 요청: "다른 세션에서도 청약봇에 접근해 ai 답변 전달받을수잇게 세팅해줘"
- 변경: 청약봇 스킬(cheongyak-bot-answer) 안에 글로만 있던 판정 엔진 실행 도구를 tools/bot/cy.js 로 저장소에 넣음(어느 세션이든 저장소를 받으면 바로 실행). LH 공공임대·청년 주택 판정(--rental, --youth)을 더함 — 조건 JSON 에 적은 칸만 '입력함'(_set)으로 표시해 적지 않은 소득·자산은 확인 필요. 화면·판정 코드는 바꾸지 않음
- 파일: tools/bot/cy.js, WORK.md
- 확인: 서울 신혼부부 무주택 현금 5억 → 마감 전 6주택형 판정(화면과 같은 함수), 인천 청년 1인 --rental --youth → 8건·계층별 항목(입력 필요/답 필요 구분)
- 백업: backup/20261006-1128-botcy
- 기능: 없음(도구)

## 2026-10-06 10:42 · 임대·청년 주택 목록 요약 (내 조건 판정 개수·접수 중 등)
- 요청: "임대랑 청년주택도 일반분양처럼 접수중이랑 내조건에 신청가능 확인필요 이런거 넣을수잇니?" (분양 목록 화면 캡처)
- 변경: 임대 목록(공공임대·청년 주택) 맨 위에 분양과 같은 모양으로 ① 내 조건 한 줄(사는 곳·집·세대·가구원·세대 소득)과 판정 개수 — 신청 가능(ok)·확인 필요(확인·일부 계층 판정 못 함·공고문 확인·판정 미지원)·조건 밖(불가·해당 계층 없음), 마감 전 공고만, 모르는 것은 조건 밖에 넣지 않음 ② 접수 중·새 공고 7일·이번 주 마감. 숫자를 누르면 그 공고만 목록에(다시 누르면 해제, '거르기 풀기'). 분양처럼 거르기·내 조건·요약이 먼저 보이게 안내 글은 목록 아래로(청년 주택 탭은 한 줄 안내만 위에)
- 파일: docs/index.html, docs/config.json(lh_summary), docs/changelog.json, VERSIONS.md, FEATURES.md, tools/qa/lh_rental.cjs(요약 숫자 = 누른 뒤 목록 건수, 판정 묶음 합 = 마감 전 공고 수, 판정 거르기 뒤 목록에 다른 판정 섞이지 않음, 해제 뒤 원래 목록)
- 확인: 스크립트 문법, lh_rental.cjs 문제 없음(밝은·어두운 390px 목록·청년·상세), 화면 캡처 확인, pytest 197, judge 606/606, lh_qa·cross_rule·e2e 34/34·code_mutation·consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 분양 1,125조합 변화 0·화면 1,401 오류 0
- 백업: backup/20261006-1042-lhsum
- 기능: lh_summary
- 버전: v1.54.0

## 2026-10-06 08:43 · LH 공공임대·청년 주택 공개 (lh_rental 켬)
- 요청: "이제 일반사람도 볼수잇게 오픈해줘"
- 변경: docs/config.json lh_rental false → true (미리보기 없이 모두에게 공고 탭 맨 위 '분양 청약 · 공공임대 · 청년 주택'). changelog v1.53.0, VERSIONS. e2e 'LH 임대 흐름'의 '스위치 꺼짐이면 임대 화면 안 열림' 검사를 스위치 상태에 맞게(켜짐이면 주소로 임대 목록이 열려야 함)
- 파일: docs/config.json, docs/changelog.json, VERSIONS.md, tools/qa/e2e.cjs, WORK.md, HANDOFF.md
- 확인: 켠 설정으로 pytest 197, judge 606/606, lh_invariants 0, lh_qa 문제 0, lh_rental.cjs(밝은·어두운 390px 목록·청년·상세 30건·하단 버튼) 문제 없음, cross_rule 0, e2e(고친 뒤 LH 2/2, 나머지 32 통과), code_mutation 못 잡음 0, consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 분양 판정 1,125조합 변화 0·화면 1,401 오류 0
- 되돌리기: docs/config.json 의 lh_rental 을 false 로 (화면에서 임대가 사라지고 분양은 그대로)
- 백업: backup/20261006-0843-lhopen
- 기능: lh_rental
- 버전: v1.53.0

## 2026-10-06 06:02 · LH 임대 공고 상세 하단 고정 버튼 (신청 바로가기)
- 요청: "공공임대 청년주택도 공고드가면 신청할수잇게 청약홈이든 어디든 일반분양처럼 아래에 이거 나오게 변경해줘" (분양 상세 하단 '모집공고문 · 자금 플랜 · 청약홈 공고 ↗' 화면 캡처)
- 변경: 임대 공고 상세(rdetail) 하단에 분양과 같은 고정 버튼 줄 — 모집공고문(PDF) · 문의 전화(공고 문의처에서 전화번호를 찾았을 때, tel:) · LH 청약플러스 공고 ↗. 주소는 LH 분양임대공고 API 의 상세 주소(DTL_URL_MOB, 없으면 DTL_URL)를 그대로 씀. 접수처가 관리사무소·주민센터인 공고가 있어 안내 문구는 '신청은 LH 청약플러스·공고문 접수처에서'. 맨 아래 안내에 접수처 주소 추가. 버튼만큼 아래 여백·청약 도우미 버튼 위치도 분양 상세와 같게
- 파일: docs/index.html, docs/config.json(lh_cta), FEATURES.md, tools/qa/lh_rental.cjs(상세 30건마다 버튼 주소 = API 주소·모집공고문 버튼·여백 확인)
- 확인: 스크립트 문법, lh_rental.cjs 밝은·어두운 화면 상세 30건×2 문제 없음(가로 넘침·이상 글자 없음), 390px 화면 캡처 확인. LH 청약플러스 주소는 이 작업 환경에서 열리지 않아(외부 사이트 차단) 화면 숫자 대조는 못 함 — 공고 화면 링크(숫자 출처 링크 아님)이고 API 가 주는 공식 상세 주소. 사용자 휴대폰에서 눌러 확인 요청
- 백업: backup/20261006-0602-lhcta
- 기능: lh_cta (lh_rental 이 꺼져 있어 미리보기에서만 보임 — 버전 올리지 않음)

## 2026-10-06 06:02 · LH 임대: 필수 요건 문장을 못 찾으면 '요건 없음'이 아니라 확인
- 요청: "2번해주고" (안전성 점검의 남은 위험 — 공고문에서 거주 요건·청약통장 요건 문장을 못 찾으면 그 요건이 없는 것으로 판정)
- 변경: 공고문 읽기(app/lh_terms.py)가 신청자격의 '공고일 현재 ○○에 거주하는 성년자/무주택세대구성원' 문장을 따로 찾아, 지역을 읽지 못했으면 local_unread 로 남김(세 도구 합칠 때 거주 요건을 어느 도구도 못 읽었을 때만). 화면은 local_unread 면 거주 요건 '확인', 공공임대는 거주지역(regions)·청약통장(account) 중 하나라도 못 읽으면 '확인'. 불변식 참고 항목(local_unread·public_unread)
- 파일: app/lh_terms.py, app/lh_pdf_merge.py, docs/index.html, tools/make_judge_cases.py, tests/judge/(cases·lh_synthetic).json, tests/test_lh_terms.py, tools/qa/(lh_qa·code_mutation).cjs, tools/qa/lh_invariants.py, docs/judge-status.json, evidence/qa/*.json
- 확인: 거주 문장 찾기를 지금 공고 30건에 돌려 거주 요건을 읽은 공고와 정확히 겹침(못 읽은 공고 0, '국내 거주'는 제외), 정답 공고에서 local_unread 0(test_local_unread_failsafe), 파서 실패 모의 공고 3개(거주 요건 못 읽음·공공임대 거주지역+통장·통장만) 판정 사례 606/606, lh_qa 공고문 기준 정보 감소 28,875회 새로 '가능' 0(거주 요건 못 읽음·공공임대 거주지역/통장 못 읽음 추가), code_mutation 52개 못 잡음 0, pytest 197, cross_rule·e2e 34/34·consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 1,125조합 변화 0·화면 1,401 오류 0
- 백업: backup/20261006-0602-lhcta
- 기능: 없음(수정 — lh_rental 안, 스위치 꺼짐이라 버전 올리지 않음)

## 2026-10-05 23:59 · LH 임대 판정 안전성 점검 — 모르는 값이 '가능'이 되지 않게 (외부 QA R3~R5)
- 요청: 첨부 지시서 "공공임대/청년주택 판정에서 '실제로 자격을 충족한다'와 '현재 입력된 정보만으로는 판단할 수 없다'를 절대로 혼동하지 않도록 … R3/R4/R5 수정, 같은 패턴 전수 점검, 정보 감소 안전성 테스트, 블라인드 재감사"
- 원인: ① 내 조건 기본값이 0·false 인 칸(본인·배우자 소득, 현금·금융·보증금, 배우자 주택)을 '0원·없음이라고 답함'과 구분할 수 없었음 → R3(1인 세대주 소득 빈칸 → 0원으로 가능)·R4(청년 세대원 본인 소득 빈칸)·R5(현금·금융·보증금 빈칸 → 총자산 가능)
  ② 판정이 '값이 있으면 확인된 것'으로 봄: 배우자 주택 기본 false = 없음, 본인·배우자 칸만으로 세대 전원 무주택 확정(같은 등본 부모·자녀 미확인), 생일 모름이면 성년자 확인 생략, 출산 여부 모름을 '아님'으로, 빈 글자('') 예/아니요를 통과, 청년 나이 한쪽 기준만 읽어도 통과, 모르는 계층을 다른 칸으로 판정
  ③ 공고문 읽기의 기본값: 맞벌이 가산을 유형별 기본값(20·30%p)으로 채움, 공공임대 '소득 글자 없음 → 소득·자산 미적용', 행복주택의 모르는 계층 제목을 조용히 버림
- 변경(화면 docs/index.html, 분양 판정은 그대로):
  - 입력 여부 `_set`(markSet/entered/pv): 입력·선택 경로가 '넣은 칸'을 적고 임대 판정만 읽음. 예전 저장분(_set 없음)의 0·false 는 임대에서 다시 물음
  - rentalGroup: 모르면 check(why: input 입력 필요 / notice 공고문 확인 / self 답 필요) — 소득(본인·세대 소득 모름), 총자산(빠진 칸 이름을 알려 줌, 넣은 값만으로 한도+출산 20% 를 넘고 부채를 알면 불가), 세대 무주택(세대 전체 주택 수 0채 또는 1인 미혼 세대만 확정, 0채인데 집 있다고 하면 '입력이 서로 달라요'), 무주택 완화 2호 이상(주택 수 1채를 알아야), 성년자(생일 모름), 대학생 혼인 모름, 신혼 자녀 수 모름, 출산가구 여부 모름(가산 가능성 열어 둠), 예비신혼부부(공고문에 있을 때만 묻고 예비 배우자를 배우자처럼), 사는 시·군 표기('경남 창원시 마산회원구'는 창원, 구만 쓰면 확인), 맞벌이 가산은 공고문에서 읽은 값만, 완화 공고가 아닌데 '미적용'이면 확인, 모르는 계층은 판정하지 않음, 빈 글자는 모름
  - 공고 결론: 대학생·주거급여 '예'라고 답하면 결론에 넣음(R1), 모르는 계층이 있고 아는 계층이 불가면 '일부 계층 판정 못 함'(partial), 판정하지 않는 유형 '판정 미지원'(unsupported). 판정 오류가 나도 목록·상세는 '공고문 확인'(rentalJudgeSafe)
  - 화면 문구: '입력한 조건 기준', 확인 항목에 입력 필요·답 필요·공고문 확인 구분, 청년 주택 = LH 임대 중 청년·대학생 계층 공고 거름망, 다루지 않는 공고(SH·GH 등 지방 공사, 청년안심주택, 장기전세, LH 매입·전세임대) 안내, 임대조건 ≠ 신청 자격, 모르는 계층 표시
  - 공고문 읽기(app/lh_terms.py·lh_pdf_merge.py): 맞벌이 가산을 원문에서 읽음(행복 '맞벌이 부부 120퍼센트' → +20, 통합 '맞벌이 우대비율 30%p', 742 '상기 비율에 30%p를 추가'(pypdfium2 글)), 예비신혼부부(prewed_ok), 행복주택 모르는 계층 제목(unknown_groups), 공공임대 '소득·자산 미적용'은 무주택·거주지역·청약통장을 함께 읽었을 때만, 통합공공임대 고령자 무주택 '혼인 중이 아닌 단독세대주는 본인'(household_or_single_self — 3차 감사에서 찾음, 정답 데이터 855 고침)
- 검사: lh_qa 5번 '정보 감소 안전성'(내 조건 칸 지우기 437,340회·공고문 기준 못 읽음/미적용/모르는 계층 27,825회 → 새로 '가능' 0; 처음 돌렸을 때 258건을 찾아 위 규칙으로 고침), 판정 사례 549 → 601건(R3~R5 와 입력함 대조, 경계값, 파서 실패 모의 공고 tests/judge/lh_synthetic.json 3개), code_mutation 안전 변이 14개 추가(모두 잡힘), cross_rule LH-MONO-001 확장(소득·총자산·세대 주택 수·성년), e2e 입력 퍼징 28칸(판정 함수 직접 호출로 오류 확인 — 생일에 숫자가 오면 오류 나던 것 고침), profile_keep 3번(소득 0 입력·지우기), 불변식 참고 항목(완화 아닌 미적용·모르는 계층·맞벌이 못 읽음)·안전 위반(공공임대 근거 없는 미적용·가산 범위), 정답 대조 test_golden_dual_add·test_public_excluded_needs_evidence
- 블라인드 3차(evidence/audit/2026-10-05-lh3, 모르는 칸 2~5개인 40사례·13공고): 79/87 → 80/87 일치, 앱 '가능'인데 검토자 아님 0건. 남은 7건은 원문 대조 결과 앱이 맞거나 앱이 더 보수적(README)
- 파일: docs/index.html, app/lh_terms.py, app/lh_pdf_merge.py, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/judge/(cases·lh_notices·lh_synthetic).json, docs/judge-status.json, tools/make_judge_cases.py, tools/judge_check.cjs, tools/qa/(lh_qa·lh_rental·cross_rule·code_mutation·e2e·profile_keep).cjs, tools/qa/lh_invariants.py, tools/qa/lh_reparse.py(새), tools/qa/audit/(audit_gen_lh·rejudge_lh).cjs, tools/qa/audit/brief_lh3.md, evidence/audit/2026-10-05-lh3/, evidence/qa/*.json, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest 196 통과(test_pipeline 은 Actions), 스크립트 문법, judge 601/601, lh_pdf_tools 합친 값 틀림 0, lh_invariants(새로 읽은 데이터) 0, lh_qa 문제 0·정보 감소 새로 가능 0, lh_rental.cjs 0, cross_rule 0, e2e 34/34, code_mutation 50개 못 잡음 0, consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 판정 1,130조합 변화 0·화면 1,407 오류 0(분양 regression 없음), 390px 밝은·어두운 화면 확인
- 백업: backup/20261005-2359-lhsafe
- 기능: 없음(수정 — lh_rental 안, 스위치 꺼짐·미리보기만이라 버전 올리지 않음)
- 올린 뒤: LH 수집 lh_invariants 0 · 판정 검증 601/601. 청약 공고 수집은 청약홈이 한밤에 0건을 줘(이 변경과 무관, 09-30 과 같은 현상) 지난 결과 유지 → verify ok=false·이슈 #4, 다음 정기 수집으로 확인

## 2026-10-05 21:02 · LH 임대 공고문 세 도구 읽기 합치기 (2단계)
- 요청: "임대/청년주택도 pdf를 잘못읽는 경우가 많으니, 일반분양처럼 pdf 읽는 방법을 여러가지로 해서 보완해줄수있게 만들어줘"
- 변경: app/lh_pdf_merge.py — 1단계에서 Actions 가 만든 세 도구 글(pypdf·pypdfium2·pdfplumber)을 같은 읽기 규칙으로 읽고 합침. 칸마다 같으면 그 값, 한 도구만 읽으면 채움, 다르면 과반, 과반 없으면 비워서 화면이 '공고문 확인'으로 묻고 [공고문·불일치] 기록 + 상세에 '데이터 확인 필요' 문구. 완화 문장 등은 하나라도 찾으면 참. 소득 100% 표는 앱 고정값과 맞는 도구 값 또는 pdfplumber 칸 단위 표. 임대조건 표는 한 도구에서 통째로(줄 단위로 섞으면 도구마다 주택형·구분·단지 이름이 달라 다른 줄끼리 짝지어지는 것을 확인 — 818·726). 수집(app/lh_rental.py)이 스위치 lh_pdf_multi 가 켜져 있으면 합친 값을 씀
- QA: tools/qa/lh_pdf_tools.py — 정답 30공고에서 도구별 맞음·틀림·못 읽음: pypdf 330/0/24(못 읽음 24 = 국민·영구임대 등 표를 안 읽는 소득표 칸), pypdfium2 330/0/24, pdfplumber 314/2/38, 합친 값 330/0/24, 임대조건 150/150. pdfplumber 가 틀린 2칸(453 총자산 배제, 856 2순위)은 과반으로 걸러짐. 고치기 전 기준 중위소득 읽기 규칙을 되살려도 합친 값은 pypdfium2·칸 단위 표 값으로 맞음(회귀 시험). 지금 30건은 합쳐도 판정 값 변화 0·도구끼리 다름 0. Actions LH 수집·판정 검증에서 매번 실행, verify-status qa.lh_pdf_merged_wrong, 화면 검증 현황 LH 줄에 합산
- 파일: app/lh_pdf_merge.py, app/lh_rental.py, tools/qa/lh_pdf_tools.py, tests/test_lh_pdf_merge.py, evidence/qa/lh-pdf-tools.json, tools/verify_status.py, docs/index.html, .github/workflows/lh-rental.yml, .github/workflows/verify.yml, FEATURES.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest 193 통과(test_pipeline 은 Actions), 스크립트 문법, judge 549/549, lh_invariants 0, lh_qa 문제 0, lh_rental.cjs 0, cross_rule 충돌 0, e2e 34/34, code_mutation 못 잡음 0, consistency·monotonic·profile_keep·filter·sp_text·snapshot 0, regress 변화 0·화면 1,407 오류 0, 390px 화면에서 도구끼리 다를 때 문구 확인
- 백업: backup/20261005-2102-lhpdf
- 기능: lh_pdf_multi

## 2026-10-05 21:02 · LH 임대 공고문을 세 도구로 읽어 저장 (1단계: 저장만)
- 요청: "임대/청년주택도 pdf를 잘못읽는 경우가 많으니, 일반분양처럼 pdf 읽는 방법을 여러가지로 해서 보완해줄수있게 만들어줘"
- 변경: LH 수집이 공고문 PDF 를 pypdf(기존, evidence/lh/<id>.txt) 외에 pypdfium2(evidence/lh/pdfium/<id>.txt, 일반분양 pdf_dual_read 와 같은 두 번째 도구)와 pdfplumber(evidence/lh/plumber/<id>.txt + 칸 단위 표 <id>.tables.json)로도 읽어 저장. 예전에 첫 도구로만 읽은 공고문은 한 번 다시 받아 만든다. 각 도구는 따로 띄운 프로세스에서 읽음(죽어도 수집 계속), 못 읽으면 빈 파일. 판정에는 아직 쓰지 않음 — LH 첨부는 이 작업 환경에서 받을 수 없어(403) Actions 가 만든 글로 도구별 정확도를 정답 데이터와 비교한 뒤 2단계에서 합치는 규칙을 넣는다
- 파일: app/notice_pdf.py(pdf_text_plumber, 분양 수집은 쓰지 않음), app/lh_rental.py, requirements.txt(pdfplumber), docs/config.json(lh_pdf_multi), FEATURES.md, .github/workflows/lh-rental.yml(제한 55분)
- 확인: pytest 통과(test_pipeline 제외 — 이 환경에 fastapi 없음, Actions 에서), 세 도구 읽기·저장·두 번 읽지 않음을 로컬 PDF 로 시험
- 백업: backup/20261005-2102-lhpdf
- 기능: lh_pdf_multi

## 2026-10-05 20:45 · 판정 검증이 LH 임대 수집을 기다리게 (올린 뒤 순서 때문에 난 실패)
- 요청: "여기서 남은 문제들 해결부탁해" 작업을 올린 뒤 확인 중 발견
- 원인: 판정 검증(verify.yml)은 청약 공고 수집만 기다리고 LH 임대 수집은 기다리지 않음 → 고친 읽기로 LH 데이터가 다시 만들어지기 전에 lh_invariants 가 옛 데이터(기준 중위소득 110%·120% 열)를 보고 14건 위반 → '검증 요약 저장' 실패, 이슈 #3 (판정 사례는 549/549 일치). 검사가 옛 오류를 정확히 잡은 것
- 변경: tools/qa/wait_collect.sh 두 번째 인자 lh → LH 임대 수집도 기다림. 판정 검증만 이 인자로 부름(LH 수집이 자기를 기다리지 않게)
- 파일: tools/qa/wait_collect.sh, .github/workflows/verify.yml, evidence/qa/blind/report.json(W40·W41 다름 0), HANDOFF.md
- 확인: bash -n, 로컬에서 실행해 '수집 실행 없음 — 시작', LH 데이터가 고쳐진 뒤 verify_status 통과(ok true), 판정 검증 다시 실행
- 백업: backup/20261005-2007-lhrest
- 기능: 없음(수정)

## 2026-10-05 20:07 · LH 임대 남은 확인 3가지 해결 + 기준 중위소득 표를 110%·120% 칸으로 읽던 오류
- 요청: "여기서 남은 문제들 해결부탁해" (미성년 세대주 예외·9인 이상 소득표·청약예금·부금)
- 찾은 오류(중요): 통합공공임대(전주동서학 742·대구연호 855) '가구원수별 기준 중위소득' 표가 PDF 글에서 앞 칸 숫자가 붙어 나와('2인 1,259,7882,099,646 …') 공백으로 칸을 세던 코드가 2~6인은 110% 열, 742 의 7·8인은 120% 열을 100% 로 읽었음 → 소득 기준이 10~20% 높게 잡혀 넘는 사람도 '가능'(예: 3인 100% 5,359,036원을 5,894,940원으로). 정답 데이터에는 맞는 값이 있었지만 테스트가 표를 비교하지 않아 놓침
- 변경: ① 표 숫자를 천 단위 쉼표 규칙으로 떼고 4번째(~100%) 칸, 30% 칸÷0.3 과 1% 안일 때만 받음 ② 8인 초과 = 8인 + 공고문 '1인 증가 시마다 959,198원'(income_add_per) → 9인 이상도 판정 ③ 2026 기준 중위소득(보건복지부 고시 제2025-135호) MEDIAN_2026 과 매 수집 대조 → 다르면 [검증·공고문 불일치], lh_invariants median_table, 정답 대조에 income_table_100·income_add_per ④ 미성년자: 공고문 '성년자' 예외(자녀가 있는 미성년 세대주·형제자매 부양 미성년 세대주·외국인 부모 한부모가족의 내국인 자녀 세대주 — 모든 공고 같음, 모두 세대주) → 세대원이면 불가, 세대주면 '답하기' 예/아니요(lhMinorHead) ⑤ 청약예금·부금: 공공임대(765·856) 1·2순위 모두 '주택청약종합저축(청약저축 포함)에 가입' → 불가(확정), 행복주택 '입주 전까지 주택청약종합저축(청약저축 포함) 가입 증명'은 예금·부금이면 '전환 필요' 확인(전에는 그냥 통과)
- 결과: lh_qa '답할 칸 없는 확인' 3종류 → 0종류
- 정답 데이터: 742·855 income_add_per 959,198 원문 확인. 판정 사례 lhrent 미성년 5(세대주 예/아니요·세대원·만 19세 되는 날·하루 전)·9인/10인 150% 경계 4·청약예금/부금/청약저축 4 + 장항 노부모부양 특별공급 sp 4(앞 커밋 fixture) → 549/549
- QA: code_mutation 변이 37(새 3: 미성년 세대원 허용·청약예금 허용·9인 가산 2배) 잡음 34 못 잡음 0, cross_rule LH-ELIG-004 에 미성년 세대주 예외 반영 → 충돌 0, lh_qa·e2e LH 퍼징에 새 칸
- 파일: docs/index.html, app/lh_terms.py, app/lh_rental.py, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/judge/lh_notices.json, tools/make_judge_cases.py, tests/judge/cases.json, tools/qa/lh_invariants.py, tools/qa/code_mutation.cjs, tools/qa/lh_qa.cjs, tools/qa/e2e.cjs, tools/qa/cross_rule.cjs, evidence/qa/CROSS_RULES.md, evidence/qa/(code-mutation·lh-qa·e2e·cross-rule·lh-invariants·lh-screen).json, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest 183 통과(test_pipeline 은 fastapi 를 이 환경에 설치할 수 없어 Actions 에서), 스크립트 문법, judge_check 549/549, lh_invariants 0(고친 읽기로 다시 만든 데이터 — 지금 올라간 데이터로는 median_table 14건을 잡는 것 확인), lh_qa 문제 0, lh_rental.cjs 0, cross_rule 144,460회 충돌 0, e2e 34/34, consistency·monotonic·profile_keep·filter·sp_text 0, snapshot 0, regress 변화 0·화면 1,407 오류 0, 390px 밝은(미성년 답하기 창)·어두운(9인 기준 17,150,319원) 화면
- 백업: backup/20261005-2007-lhrest
- 기능: lh_rental

## 2026-10-05 20:07 · 불법행위 재공급 특별공급 '계' 칸 없는 공급대상 표 읽기 (장항 노부모부양 3세대)
- 요청: "여기서 남은 문제들 해결부탁해" — 주간 블라인드 W41 에서 남은 '장항 재공급 노부모 특공 3세대를 앱이 모름'
- 원인: 재공급 특공 세대수는 공고문 공급대상 표에서 읽는데(기능 resupply_special), 고양 장항 아테라(2026930038) 표는 머리글이 '총공급 세대수 / 노부모 부양 특별공급 / 일반공급'으로 '특별공급 세대수'·'계' 칸이 없어 못 읽음 → 특공 판정이 빠지고 일반 1세대만 판정
- 변경: notice_pdf._sp_table_no_sum — 이 형식을 읽고 '총공급 = 특공 합 + 일반공급'일 때만 받음. PARSER_VERSION 26(모든 공고문 다시 읽기). 원문 109건 읽기 고정 비교에서 바뀐 값은 2026930038 sp_table 하나(의도). 블라인드 비교 도구에 신혼희망타운 특공 정의(청약홈 SPSPLY = 전체 물량) 반영
- 정답 데이터: tests/golden/notices.json 2026930038 sp_table(84A 노부모 3·84B 노부모 1, 원문 공급규모 문장·표 인용, 블라인드 검토자 값과 같음). 판정 사례 fixture 에 장항 84A 추가(사례는 다음 커밋 make_judge_cases)
- 파일: app/notice_pdf.py, app/pipeline.py, tests/golden/notices.json, tests/test_resupply_special.py, tests/qa/parse_snapshot.json, tests/judge/listings.json, tests/qa/snapshots.json, tools/qa/blind_sample.py, evidence/qa/blind/report.json, docs/changelog.json, VERSIONS.md
- 확인: test_resupply_special(새 형식·합이 안 맞으면 거부), parse_snapshot 바뀐 값 1(의도), snapshot 바뀐 곳 = 새로 넣은 장항 고정 공고뿐(기준 갱신), regress 조합 1,130 변화 0
- 백업: backup/20261005-2007-lhrest
- 기능: resupply_special
- 버전: v1.52.1

## 2026-10-05 19:17 · LH 임대 QA 를 일반분양 수준으로 — 데이터 불변식·교차 규칙·e2e·문구 훑기·주간 블라인드 표본·검증 현황
- 요청: "응 qa 일반분양 수준처럼 돌려줘"
- 변경: ① tools/qa/lh_invariants.py 새 도구(일정 순서·보증금/월세 범위·계층 못 읽음·소득%·자산·자동차 범위·소득 100% 표=앱 고정값·정답 데이터 대조 → evidence/qa/lh-invariants.json, '[검증·LH]' 줄) + tests/test_lh_invariants.py ② cross_rule.cjs 에 LH 규칙(LH-ELIG-001 소득·002 자동차·총자산·003 거주 지역·004 나이·성년, LH-HOME-001, LH-MONO-001, LH-UI-001)과 CROSS_RULES.md 표 ③ e2e.cjs 'LH 임대 흐름'(#/rental·#/rdetail 바로 열기·새로고침·뒤로·없는 번호·스위치 꺼짐)·'LH 임대 입력 퍼징'(답하기 칸 18개 × 이상한 값 10개, 답하기 창 전부 열기), E2E_ONLY=lh ④ textsweep.cjs 에 임대 목록·상세·답하기 창 ⑤ blind_sample.py 에 LH 표본 2건(lh_samples·LH_QUESTIONS)과 비교, 분양 비교에 정의가 같은 경우 2가지(규제지역 1순위 세대주는 따로 판정, 청약통장 불필요=0개월) ⑥ verify_status.py 가 lh-invariants·lh-qa·lh-screen 을 모아 ok 에 반영, verify.yml·lh-rental.yml 에서 매번 실행 ⑦ lh_qa.cjs 답하기 값에 세대 주택 수·등본 부모 수
- 결과: 불변식 위반 0, 교차 규칙 검사 140,428회 충돌 0(LH 판정에 오류를 일부러 넣은 변이 3개 — 소득·시도 거주·시군 거주·세대 집 — 모두 잡음), e2e 34/34(처음엔 상세 새로고침 오류를 잡아 앞 커밋에서 고침), 문구 훑기 임대 문장 431틀 이상 글자 0, 블라인드 W41: LH 2공고 답 전부 일치, 분양 5공고 다름 5 → 정의 차이 2개는 비교 도구에 반영, 남은 3(신혼희망타운 특공 정의 2·장항 재공급 노부모 특공 세대수 없음 1)은 HANDOFF 에 적음
- 파일: tools/qa/lh_invariants.py, tests/test_lh_invariants.py, tools/qa/cross_rule.cjs, evidence/qa/CROSS_RULES.md, evidence/qa/cross-rule.json, tools/qa/e2e.cjs, evidence/qa/e2e.json, tools/qa/textsweep.cjs, tools/qa/blind_sample.py, evidence/qa/blind/2026-W41.json, evidence/qa/blind/report.json, tools/verify_status.py, tools/qa/lh_rental.cjs, evidence/qa/lh-invariants.json, evidence/qa/lh-screen.json, .github/workflows/verify.yml, .github/workflows/lh-rental.yml, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 앞 커밋과 같은 검사 묶음 전부 통과, lh_invariants 0, verify_status 실행
- 백업: backup/20261005-1917-lhqa2
- 기능: lh_rental

## 2026-10-05 19:17 · LH 임대 판정 — 2차 블라인드 감사로 찾은 4가지 고침 + 새로고침하면 공고 상세가 사라지던 것
- 요청: "응 qa 일반분양 수준처럼 돌려줘" (일반분양과 같은 방식의 QA)
- QA: 2차 블라인드 감사(evidence/audit/2026-10-05-lh/README.md) — 무작위 40사례·24공고를 앱 코드를 보지 않은 검토자가 공고문·별표만으로 판정 → 75건 중 64 일치
- 찾은 오류·조치: ① 1인 단독세대주가 세대 소득을 비우면 '확인' → 본인 소득 = 세대 소득으로 판정 ② 같은 등본 부모님(직계존속) 집을 세대 주택으로 안 셈 → 반영(임대는 60세 이상 예외 없음), 답하기에 '같은 등본 부모·조부모 수' ③ 무주택 완화 공고의 '2호 이상 주택 소유자 제외'(삼척도계 581) → 공고문에서 읽고 세대 주택 수로 판정(답하기 '세대 전체 주택 수') ④ 성년자(만 19세) 요건 → 대학생·청년 외 계층은 미성년 불가 ⑤ 코드 변이 검사에서 혼인 7년 경계가 하루 어긋남(7년째 되는 날을 빼던 것) → 포함으로(분양 2026000409 와 같은 기준) ⑥ 화면 e2e 에서 찾음: 임대 공고 상세 주소에 공고 번호가 없어 새로고침·주소로 열기 하면 목록이 나옴 → '#/rdetail/<번호>' ⑦ 자동차 0원은 '자동차 없음'으로 표시
- 결과: 고친 뒤 67/75 일치, 남은 8건은 원문 대조로 앱이 맞거나(대학생 차량 보유, 계층 밖 '해당 없음') 사례 생성기 오류(고침) 또는 표시 방침(청년 청약통장 입주 전 가입)
- 정답 데이터: 581 homeless_max1 원문 인용 확인 후 추가. 판정 사례 lhrent-122~133 (단독세대주 소득, 부모님 집, 2호 이상, 미성년, 혼인 7년 경계 당일·하루 전) → judge_check 532/532
- 파일: docs/index.html, app/lh_terms.py, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/judge/cases.json, tests/judge/lh_notices.json, tools/make_judge_cases.py, tools/qa/code_mutation.cjs, evidence/qa/code-mutation.json, tools/qa/audit/(audit_gen_lh.cjs·brief_lh.md·audit_cmp_lh.py·rejudge_lh.cjs), evidence/audit/2026-10-05-lh/, tools/qa/lh_qa.cjs, evidence/qa/lh-qa.json
- 확인: pytest 181 통과(test_pipeline 은 이 작업 환경에 fastapi 를 설치할 수 없어 Actions 에서 확인), 스크립트 문법, judge_check 532/532, code_mutation 변이 34 · 잡음 31 · 못 잡음 0(동등 3), lh_qa 문제 0, lh_rental.cjs 문제 0, regress 조합 1,130 변화 0·화면 1,407 오류 0, snapshot 0, consistency 0, monotonic 0, profile_keep 0, filter 0, sp_text 0, 390px 밝은·어두운 화면(새로고침 뒤 상세 유지) 확인. 분양 판정은 그대로(regress 변화 0)
- 백업: backup/20261005-1917-lhqa2
- 기능: lh_rental

## 2026-10-05 18:01 · LH 임대 QA — 블라인드 감사로 찾은 빠진 요건 고침 + 임대 QA 도구
- 요청: "저것들도 제대로 된건지 qa한번돌려서 오류확인한번 해야될꺼같아"
- QA: (1) 블라인드 감사 — 앱 코드를 보지 않은 검토자가 공고문·별표만으로 10공고×8조건 184건 판정 → 처음 164건 일치 (2) tools/qa/lh_qa.cjs 새 도구 — 무작위 조건 300개×30공고 퍼징, 소득·자산·자동차 단조성 39,420회, 답하기 해소(같은 질문 고리), 목록 카드=상세
- 찾은 오류·조치: ① 영구임대 신청자격의 거주 요건('공고일 현재 부산시·창원시 등에 거주하는 성년자인 무주택세대구성원', 8건)을 안 봐서 다른 지역 사람도 '신청 가능'으로 나옴 → 읽어서 판정(시·도/시·군) ② 지원주택(742) 직업기준의 주민등록 요건(무형유산 전북·예술인 전주시)을 몰랐음 → 판정 ③ 장기종사자 '미성년 자녀 포함 3명 이상 세대'를 늘 '확인'으로 둠 → 내 조건으로 판정 ④ 행복주택 청년·신혼부부 '입주 전까지 주택청약종합저축 가입' 요건 추가(통장 없으면 확인) ⑤ 출산가구 가산을 늘 '확인'으로 둠 → '2023.3.28 이후 태어난 자녀 수'를 답하기로 물어 소득은 정확히 계산 ⑥ 9인 이상 가구 소득 기준(8인 + 1인당 579,278원) ⑦ 신혼부부 1인 가구 입력은 가구원 수를 다시 묻게
- 결과: 블라인드 감사 181/184 일치(남은 3건은 신혼부부·한부모가족을 한 계층으로 묶어 보여 생기는 표시 차이, 결론 같음), lh_qa 문제 0
- 정답 데이터: 신청자격 거주 요건 8건·청약통장 입주 전 요건·742 직업기준 주민등록을 원문 인용 확인 후 추가. 판정 사례 lhrent-99~123 → judge_check 520/520
- 파일: app/lh_terms.py, app/lh_rental.py, docs/index.html, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/qa/lh/rental_units.json, tests/judge/lh_notices.json, tests/judge/cases.json, tools/make_judge_cases.py, tools/qa/lh_qa.cjs, evidence/qa/lh-audit/, evidence/qa/lh-qa.json, HANDOFF.md
- 확인: pytest 204, judge_check 520/520, lh_qa 문제 0, lh_rental.cjs 문제 0, regress 변화 0·오류 0, snapshot 0, consistency 0, monotonic 0, profile_keep 0, 엔진 잠금 그대로
- 백업: backup/20261005-1801-lhqa
- 기능: lh_rental

## 2026-10-05 17:24 · LH 임대 공고에서 '확인 필요'를 바로 묻고 저장해 판정 (답하기)
- 요청: "임대랑 청년공급은 따로 내정보를 입력하는 부분은 넣지않는데 … 확인필요내용에 대해서는 해당 공고에서 바로 물어봐주고, 답을 하면 저장되서 판정" → 인터뷰 답: 분양과 같은 칸은 내 조건에 같이 저장 / 대학생·주거급여·한부모·창업인 추천·직업기준 같은 자격도 예·아니요로 묻고 반영 / 확인 항목 옆 '답하기' 버튼
- 변경: 임대 상세 '내 자격'의 확인 항목마다 '답하기' → 그 자리에서 필요한 칸만 입력(생년월일·혼인·혼인신고일·막내 생일·집 소유·사는 곳·청약통장·가구원 수·세대 소득·본인 총자산·총자산 항목·자동차, 임대 전용 예/아니요 8칸) → 이 기기의 내 조건에 저장 → 다시 판정. 예/아니요 자격은 '(내 답)'으로 표시. 대학생 소득(본인+부모 합계)을 판정에서 빠뜨리던 것도 예/아니요 질문으로 넣음. 분양 판정 함수는 그대로(엔진 잠금 그대로)
- 판정 사례: lhrent-86~98 (창업인 추천·대학생·주거급여·한부모·무주택 완화 답) → judge_check 495/495
- 파일: docs/index.html, tools/make_judge_cases.py, tests/judge/cases.json, tools/qa/lh_rental.cjs, HANDOFF.md
- 확인: 스크립트 문법, pytest 전체, judge_check 495/495, regress 변화 0·오류 0, snapshot 0, consistency 0, profile_keep 바뀐 칸 0, lh_rental.cjs(답하기 → 세대 소득 입력 → 판정 확인 필요→가능, 저장값 확인) 문제 0, 390px 화면 확인
- 백업: backup/20261005-1724-lhask
- 기능: lh_rental

## 2026-10-05 16:16 · LH 임대 '계층별 기준을 읽지 못함' 원인 5가지 고침
- 요청: "아직 공고문에서 계층별 조건? 뭐 이런걸 못읽는다고 나오는데 원인확인해줘"
- 원인·조치: (1) 공공임대 3건(50년 공공임대 2·10년 분양전환 1)은 읽기 대상이 아니었음 → 신청자격 절에서 거주지역(시·도)·청약통장 순위(1순위 6개월·6회/2순위 가입, 또는 불문)·소득·자산 기준 유무를 읽고 판정에 지역·통장 항목 추가 (2) 창업지원주택(인천논현 780)은 '3-1. 계층' 절이 없는 구조 → '창업지원(행복)주택 입주자격 ①~⑤' 규칙(혼인 중이면 세대원·아니면 본인 무주택, 소득 100%·1인 120%·2인 110%·맞벌이 +20%p, 총자산·자동차, 남동구 창업인 추천은 확인) (3) 일자리연계형 지원주택(전주동서학 742) '■ 신분기준 ❶~❹' 구조 → 청년·신혼부부·한부모·장기종사자 + 직업기준 확인 (4) 익산인화(870) 고령자: PDF 글 순서가 섞여 절 안에 값이 없음 → 공고 앞 '입주자격완화 내용' 표(모든 계층 적용)로 채움 (5) 태백철암1(735): 소득표에 가산 문장이 없음 → 표 70% 열 + 시행규칙 [별표 4] 1인 90%·2인 80%. 공고문에만 있는 추가 요건은 판정에서 '확인'
- 정답 데이터: 735·780 고침(메모 포함), 공공임대 3건 추가(지역·통장·임대조건, 원문 인용 확인) → 30건. 판정 사례 lhrent-65~85 추가(공공임대 지역·통장 경계, 창업지원 혼인·맞벌이·나이)
- 파일: app/lh_terms.py, app/lh_rental.py, docs/index.html, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/qa/lh/rental_units.json, tests/judge/lh_notices.json, tests/judge/cases.json, tools/make_judge_cases.py, tools/qa/lh_rental.cjs, HANDOFF.md
- 확인: 지금 공고 30건 모두 계층별 기준 읽음(못 읽음 0), pytest 전체, judge_check 482/482, regress 변화 0·오류 0, snapshot 바뀐 곳 0, lh_rental.cjs 문제 0, 창업지원·공공임대 상세 390px 스크린샷 확인
- 백업: backup/20261005-1616-lhfix
- 기능: lh_rental

## 2026-10-05 15:29 · LH 임대 보증금·월 임대료 읽기 (공고문 임대조건 표)
- 요청: "보증금 월세도 읽어주고, 미리보기도 켜줘 피드백줄께"
- 변경: app/lh_terms.parse_lh_rents — LH API 가 '공고문 참조'로만 주는 보증금·월세를 공고문 임대조건 표에서 읽음. 한 줄 '임대보증금 계·계약금·잔금·월 임대료' 중 계 = 계약금 + 잔금 이 맞는 네 숫자만 받음(추측 없음). 천원 단위 표(군산 7개 단지·양산 삼성파크빌), 계약금 칸이 합쳐진 표(익산제3일반산단), 주택형·단지·계층(영구임대 가군/나군, 행복주택 계층·청년 소득 유무, 통합공공임대 1~6구간·수급자 등 상한) 구분. 수집이 공고마다 rents 로 저장. 화면: 목록 카드 '보증금 ~ · 월 ~'(가군·상한·주거급여 제외 최저), 상세 '보증금·월 임대료' 표(출처 모집공고문 PDF 임대조건 표). 스위치 lh_rental 은 그대로 꺼짐(미리보기 ?lh=preview)
- 정답 데이터: tests/golden/lh_rental.json rents 145줄(공고문 원문 확인, 통합공공임대 2건의 '[주거급여 수급자가 아닌 경우] 상한 임대조건' 9줄 추가) ↔ 시험 test_golden_lh_rents: 모든 줄 같은 주택형으로 읽음, 정답에 없는 줄 0
- 파일: app/lh_terms.py, app/lh_rental.py, docs/index.html, tests/golden/lh_rental.json, tests/test_lh_terms.py, tests/qa/lh/rental_units.json, tools/qa/lh_rental.cjs, HANDOFF.md
- 확인: pytest 전체, 스크립트 문법, judge_check 461/461, regress 변화 0·오류 0, snapshot 바뀐 곳 0, tools/qa/lh_rental.cjs 문제 0, 390px 밝은·어두운 상세 전체 화면 스크린샷 확인
- 백업: backup/20261005-1529-lhrent
- 기능: lh_rental

## 2026-10-05 14:57 · LH 임대 화면·자격 판정 (스위치 꺼짐, 미리보기 ?lh=preview)
- 요청: "어 진행해줘" (LH 임대 목록 + 자격 판정, 기존 청약 판정 영향 없게 / 일반청약·공공임대·청년주택으로 나눠 보기)
- 변경: 화면에 LH 임대 목록·상세와 계층별 자격 판정(rentalJudge, 분양 판정 함수는 부르지도 바꾸지도 않음). 공고 탭 맨 위 '분양 청약 · 공공임대 · 청년 주택' 버튼(스위치 켜질 때만). 판정 규칙: 공공주택 특별법 시행규칙 별표 3·4·5·5의2 + 공고문 금액(청년 19~39세·미혼·본인 무주택, 고령자 65세 이상, 신혼 7년·6세 이하 자녀, 소득 1인·2인·3인 이상 퍼센트, 총자산·자동차 한도, 출산가구 가산은 확인 필요). 소득 100% 금액 RENT_URBAN_2025(2025 도시근로자) 를 공고문 표와 대조하는 시험·수집 기록 추가. 같은 이름 함수 겹침 검사(test_index_names) 추가
- 판정 사례: lhrent-01~64 (make_judge_cases 16절, 공고 조건은 tests/judge/lh_notices.json = 정답 데이터에서 만듦, 기대값은 생성기가 규칙을 따로 옮겨 계산) → judge_check 461/461
- 파일: docs/index.html, app/lh_terms.py, app/lh_rental.py, tools/make_judge_cases.py, tools/judge_check.cjs, tests/judge/cases.json, tests/judge/lh_notices.json, tests/test_lh_terms.py, tests/test_index_names.py, tools/qa/lh_rental.cjs, HANDOFF.md, FEATURES.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest 전체, 스크립트 문법, judge_check 461/461, regress(기존 판정 변화 0·화면 오류 0), snapshot 바뀐 곳 0, consistency·monotonic·cross_rule·sp_text 0건, 엔진 잠금 그대로, tools/qa/lh_rental.cjs(스위치 꺼짐: 버튼 없음 / 켜짐: 390px 밝은·어두운 목록·청년·상세 30건 가로 넘침·오류·NaN 0, 뒤로 가기) 스크린샷 직접 확인
- 백업: backup/20261005-1457-lhscreen
- 기능: lh_rental

## 2026-10-05 14:36 · LH 임대 공고문 자격 조건 읽기 + 정답 데이터 27건
- 요청: "어 진행해줘" (LH 임대 목록 + 자격 판정, 기존 청약 판정 영향 없게)
- 변경: app/lh_terms.py(새 파일, 분양 공고문 읽기 app/notice_pdf.py 와 분리) — 임대 공고문에서 자격 완화 여부, 무주택 요건 완화(주택건설지역·연접지역 무주택), 계층별(대학생·청년·신혼부부·한부모·고령자·주거급여수급자·일반) 무주택 범위·소득 퍼센트(또는 배제)·총자산·자동차 한도(만원 또는 배제)·소득 100% 금액표를 읽음. 수집(app/lh_rental.py)이 공고마다 terms 로 저장. 못 읽은 값은 None(화면은 공고문 확인)
- 정답 데이터: tests/golden/lh_rental.json — 지금 공고 27건(국민임대 10·영구임대 9·행복주택 6·통합공공임대 2)을 공고문 원문으로 확인(인용문 포함). 원문 문구가 애매한 것은 메모로 남김(태백소도 793 소득 퍼센트는 표 머리글 + '1인 20%p·2인 10%p 가산' 문장으로 정함, 태백철암1 735 는 가산 문장이 없어 비움)
- 파일: app/lh_terms.py, app/lh_rental.py, tests/test_lh_terms.py, tests/golden/lh_rental.json
- 확인: pytest 전체. 읽은 값은 정답과 전부 같음(틀린 값 0), 못 읽은 값만 있음(전주동서학 지원주택 742·인천논현 창업지원주택 780 계층 구조, 익산인화 870 고령자 — PDF 글 순서 섞임). 근거 법령 요약은 공공주택 특별법 시행규칙 별표 3·4·5·5의2(evidence/law/public/)
- 백업: backup/20261005-1436-lhterms
- 기능: lh_rental

## 2026-10-05 14:10 · LH 임대 공고 수집 (따로 도는 수집, 화면 스위치 꺼짐)
- 요청: "2번으로 하는데, 현재 청약판정에는 영향없도록 해줘" → "어 진행해줘"
- 변경: app/lh_rental.py — LH 목록·상세·공급 API 로 지금 공고(마감 전) 임대 공고를 docs/lh-rental.json 에, 공고문 PDF 글을 evidence/lh/<공고ID>.txt 에 저장. 기존 수집·판정 코드는 손대지 않음(따로 워크플로 'LH 임대 수집' lh-rental.yml, 매일 06:40). API 에 '공고문 참조'로 온 보증금·월임대료는 비워 둠(공고문에서 읽을 예정). 스위치 lh_rental 추가(false — 화면은 아직 없음)
- 파일: app/lh_rental.py, .github/workflows/lh-rental.yml, tests/test_lh_rental.py, tests/qa/lh/, docs/config.json
- 확인: pytest 전체, 실제 응답 고정본으로 변환 시험(일정·단지·주택형·금액 미기재), 파이프라인이 이 모듈을 가져오지 않음
- 백업: backup/20261005-1412-lh
- 기능: lh_rental

## 2026-10-05 13:23 · LH 임대 API 3종 승인 확인·설계 기록
- 요청: "2번으로 하는데, 현재 청약판정에는 영향없도록 해줘" (LH 임대 목록 + 자격 판정)
- 변경: 기록만. HANDOFF 진행 중인 일에 LH 상세·공급 API 승인(HTTP 200)과 수집·판정 설계 추가, 카카오맵 설정 필요 메모를 '이미 켜져 있음'으로 고침
- 파일: HANDOFF.md, WORK.md
- 확인: evidence/qa/lh-probe.txt(10-05 13:20) 상세·공급 유형별 HTTP 200, evidence/qa/lh/ 응답 필드 확인
- 백업: backup/20261005-1323-x
- 기능: 없음(기록)

## 2026-10-05 11:54 · LH 임대 원천 점검 확장 (목록·상세·공급정보)
- 요청: "2번(LH 임대 목록 + 자격 판정)으로 하는데, 현재 청약판정에는 영향없도록 해줘"
- 확인: 사용자 활용신청 뒤 목록 API(lhLeaseNoticeInfo1) 응답 정상 — 최근 60일 52건(행복주택·국민임대·영구임대·통합공공임대·공공임대 등)
- 변경: tools/qa/lh_probe.py 가 목록 전부와 유형별 공고중 1건씩의 상세·공급정보 API 응답을 evidence/qa/lh/ 에 저장(인증키 지움). 따로 도는 워크플로 'LH 임대 원천 점검'(lh-probe.yml), 근거 자료 모으기에서는 뺌
- 파일: tools/qa/lh_probe.py, .github/workflows/lh-probe.yml, .github/workflows/probe.yml
- 확인: 문법 검사. 결과는 Actions 커밋으로
- 백업: backup/20261005-1154-lhprobe
- 기능: 없음(도구)

## 2026-10-05 02:38 · 화면 글자 스냅샷 기준 갱신 + 진행 기록
- 요청: (6·7·8 이어서) v1.51.0 수집 실행이 '검증 요약 저장'에서 실패 — 원인 확인
- 원인: 화면 글자 스냅샷(tools/qa/snapshot.cjs, 고정 공고 tests/judge/listings.json)이 새 시험 공고 2026000414-YOUTH(청년 특별공급)와 2025000645(소득·자산 기준 없는 공공건설임대 — 이제 판정함)의 글자를 '바뀐 곳'으로 셈. 모두 의도한 변경(2026000307-NOLIM 1건은 끝 공백만 다름) → 기준 다시 씀
- 변경: tests/qa/snapshots.json 기준 갱신. HANDOFF '진행 중인 일' -24(6·7·8 결과·남은 것·사용자가 할 일), 운영 스킬 함정 5개
- 파일: tests/qa/snapshots.json, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: snapshot 다시 돌려 바뀐 곳 21개 내용 확인 뒤 --update, E2E 32/32, 지난 공고·청약봇 위반 0. LH 임대 API 점검 결과 SERVICE_KEY_IS_NOT_REGISTERED(활용신청 필요)
- 백업: backup/20261005-0204-rental
- 기능: 없음(수정)

## 2026-10-05 02:04 · 소득·자산 기준 없는 공공건설임대 일반공급 판정 (v1.52.0)
- 요청: (남은 일 8번) 민간 5·10년 공공건설임대 자격표 파서
- 근거: 2025000645 이천 카사펠리스 임차인모집공고 — 단지 주요정보 '국민주택(5년공공건설임대)', 신청자격 표 '소득 또는 자산기준' 다섯 칸 모두 '-', '이천시 또는 수도권(서울·경기·인천)에 거주 … 무주택세대구성원', 1순위 '12개월 경과·월납입금 12회 이상', 2순위 '가입', 1순위 경쟁 시 ①지역-②순차-③추첨
- 변경: 수집 — 위 두 표현이 모두 있으면 pub_limits {kind:'none'} (분양전환 후 잔여세대 2026000022 등 다른 공고는 그대로), PARSER_VERSION 25. 화면 — 판정 범위 '부분'(일반공급은 국민주택 규칙: 무주택·통장 순위·거주지, 특별공급은 확인 필요 그대로), 체크리스트에 '소득·총자산 (공공임대 일반공급) 기준 없음' 줄(출처 모집공고문). 공공임대 소득·총자산 항목 출처를 모집공고문으로
- 파일: app/notice_pdf.py, app/pipeline.py, docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, tools/make_judge_cases.py, tests/judge/cases.json, tests/judge/listings.json, tests/golden/notices.json, tests/test_notice_and_notify.py, tests/test_residence.py, tests/qa/parse_snapshot.json, tools/engine_lock.json
- 확인: 공고문 읽기 고정 바뀐 값은 2025000645 pub_limits 하나, 정답 데이터 추가, 판정 사례 397/397(2025000645: 조건 좋음 가능·유주택·통장 없음·다른 지역 불가, 특별공급 확인 필요 — 원래 '판정 범위 밖' 사례 8건을 바꿈), pytest 194, 회귀 판정 차이 0·화면 오류 0, 판정 일치 0건, 교차 규칙 충돌 0, 시험 공고로 390px 밝은·어두운 화면 확인
- 백업: backup/20261005-0204-rental
- 기능: rent_noincome
- 버전: v1.52.0

## 2026-10-05 02:04 · LH 임대 공고 받기 점검 도구
- 요청: (남은 일 8번) LH 임대 범위 넓히기 — 수집 원천부터
- 변경: tools/qa/lh_probe.py — 공공데이터포털 '한국토지주택공사_분양임대공고문 조회 서비스'(B552555/lhLeaseNoticeInfo1)를 같은 인증키로 불러 응답 코드·건수·필드 이름만 evidence/qa/lh-probe.txt 에 남김(인증키는 지움). 근거 자료 모으기(probe.yml)에서 실행
- 파일: tools/qa/lh_probe.py, .github/workflows/probe.yml
- 확인: 문법 검사. 결과(활용신청 필요 여부)는 근거 자료 모으기 커밋으로 확인
- 백업: backup/20261005-0204-rental
- 기능: 없음(도구)

## 2026-10-05 01:38 · 청년 특별공급 판정 (v1.51.0)
- 요청: (남은 일 7번) "6,7,8 진행해줘" — 청년 특별공급(공공임대·공공분양) 판정
- 근거: 공공주택 특별법 시행규칙 [별표 6의6] 가목(법령 원문 받기로 evidence/law/public/byeolpyo_6_6.txt), 모집공고문 2026000313(LH 이익공유형)·2026000307(LH 분양전환공공임대)·2026000041(SH 토지임대부) 신청자격 ①~④·<표2>·<표3>·<표4>. 자산 기준의 '부모'는 두 분 합계(2026000041 '신청자의 부모가 소유하고 있는 … 총합에서 부채를 차감한 금액을 각각 검증')
- 변경: 수집 — notice_pdf.parse_youth(1인 140% 금액, 본인·부모 총자산, 출산가구 완화 본인 금액; 천원·백만원 표기), L.youth(소득·자산 둘 다 읽은 것만), PARSER_VERSION 24. 화면 — youthJudge(만 19~39세·혼인 중 아님·본인 명의 집 없음·본인 주택 소유 이력 없음(세대원 집은 상관없음)·재당첨·거주지·통장 6개월 6회·본인 소득 ≤ 공고문 금액·본인 총자산·부모 총자산, 출산가구 완화는 계산하지 않고 확인 필요), 소득세 5년이면 1단계 우선공급(30%) 배점 순, 아니면 2단계 추첨. 청년 세대수가 있는 공공분양 주택형만 유형에 넣음. 새 질문 '청년 특별공급'(본인 주택 이력·본인 총자산·부모님 총자산, 만 19~39세 미혼만 보임)과 바로 답하기 연결, 뽑는 방식 문구, 이용 안내 '아직 판정하지 않는 것'에서 청년 뺌
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, tools/make_judge_cases.py, tests/judge/cases.json, tests/judge/listings.json(2026000414-YOUTH 시험 공고), tests/golden/notices.json, tests/test_notice_and_notify.py, tests/qa/parse_snapshot.json, tools/engine_lock.json
- 확인: 원문 3건 정답(소득·자산 금액 원문 대조) 일치, 공고문 읽기 고정 바뀐 값은 youth 추가 3건뿐. 판정 사례 393/393(청년 28건 새로: 나이 경계·혼인·이력·통장 6개월·소득 140% 경계·자산 경계·출산 완화·소득세 단계 — 기대값은 생성기에 원문 금액을 따로 옮겨 계산), pytest 통과, 회귀 판정 차이 0·화면 오류 0, 단조성 위반 0, 특공 문구·판정 일치 0건, 시험 공고를 넣어 390px 밝은·어두운 화면 확인(가능·확인 필요·바로 답하기). 지금 공고에는 청년 세대수가 있는 주택형이 없어 화면에 바로 보이지는 않음
- 백업: backup/20261005-0138-youth
- 기능: youth_special
- 버전: v1.51.0

## 2026-10-05 01:38 · 법령 원문 받기에 공공주택 특별법 시행규칙 추가
- 요청: (남은 일 7번) 청년 특별공급 판정 — 기준을 법령 원문으로 확인하려고
- 변경: tools/law_probe.py 가 주택공급에 관한 규칙에 더해 공공주택 특별법 시행규칙 본문·별표 전부를 evidence/law/public/ 에 받음 (법령 원문 받기 Actions, 작업 환경은 law.go.kr 에 못 붙음)
- 파일: tools/law_probe.py
- 확인: 문법 검사. 결과는 Actions(법령 원문 받기) 커밋으로 확인
- 백업: backup/20261005-0138-youth
- 기능: 없음(도구)

## 2026-10-05 01:30 · 전매제한 기간을 모집공고문에서 읽기 (v1.50.0)
- 요청: (남은 일 6번) "6,7,8 진행해줘" — 전매제한을 공고문 1쪽 표·본문에서 읽기
- 변경: notice_pdf.parse_resale — 민영 표준 문장('전매제한기간 [당첨자발표일(날짜)로부터] 6개월·1년·3년·없음·소유권이전등기시까지·등기일까지(다만 3년)'), LH 제한사항 표('전매제한 당첨자 발표일 3년')·문장('입주자로 선정된 날(날짜)로부터 3년간 전매가 금지'), 재공급·무순위('최초 입주자모집공고의 당첨자발표일(날짜)로부터 N년간 (단, 등기 시 해제) 적용[되어 현재 도과]'), 이익공유형 '전매 불가', PDF 글자 뒤섞임('로부터개월6', '년(날짜)1'), 1쪽 표만 있는 무순위. 결과 {months, base, registration, until_reg, passed, none, forbidden}. 1쪽 표 칸과 본문이 다르면 conflicts(지난 기간은 비교 안 함). PARSER_VERSION 23 → 모든 공고문 다시 읽음
  pipeline: L.resale, 제약 줄 ('전매 제한', '6개월 (~27.03.22)'·'3년(등기 시 풀림)'·'없음'·'이미 지남'·'등기 때까지'·'전매 불가(환매만)') — 끝나는 날은 기준일+기간 계산이라 '~'. 화면: 출처·공고문 문장(notice_quotes), 스위치 꺼지면 줄 숨김. 정답 비교(validate)는 정답에 적은 칸만
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, tests/golden/notices.json, tests/test_notice_and_notify.py, tests/test_notice_retry.py, tests/qa/parse_snapshot.json, tools/engine_lock.json
- 확인: 모아 둔 원문 109건 중 107건 읽음(못 읽은 2건은 원문에 전매제한이 없음 — 공공임대 2026000307, 2025000645), 정답 22건(원문 문장 직접 대조, 2026930036 은 본문 2020.11.10·1쪽 표 2020.11.20 로 공고문 자체가 다름 → 본문 기준·'지남'은 같음), 1쪽 표↔본문 불일치 0. 공고문 읽기 고정: 바뀐 값은 resale 추가 106건뿐(다른 값 0) → 기준 갱신. pytest 통과, 판정 사례 365/365, 회귀 판정 차이 0·화면 오류 0, 엔진 지문은 fromApi(제약 줄 거르기)만 바뀌어 갱신. 390px 밝은·어두운 화면 확인. test_notice_retry 는 모델 새 칸(빈 값)을 허용하게 고침
- 백업: backup/20261005-0130-resale
- 기능: resale_limit
- 버전: v1.50.0

## 2026-10-04 22:46 · 청약봇 V2 오픈카톡 실제 질문 20개로 조건 읽기·답 구조 개선
- 요청: "대화중에 특정질문에 대한 답변이 이게 맞다 라고 확신하는 경우에만 해당 케이스를 20개정도 골라서 청약봇이 그런 답변 퀄리티까지 올라올 수 있도록 개선해줘" → 사용자 선택 '실제 질문 20개로 개선'
- 개인정보: 카톡 내보내기 원문은 작업 공간에만 두고 저장소에 넣지 않음. 시험지는 질문 모양만 남기고 이름·장소·금액을 바꿔 씀(v2-kakao-01~20)
- 지금 V2 문제(20개 중): 직장·출근지를 지역 조건으로 읽음(마포·이천·잠실), '동탄 아파트 매도'·'거주지 성남 중원구'를 찾을 지역으로, '한정하지 말고 서울 전역'을 서울 제외로, '최대 6억 4천만 원'·'6억 예산에'·'예산 6.5'·'22억대까지'·'10억~10억5천' 금액 놓침, '25~34평'을 국평으로, 'top5' 무시, '오늘 기준'·'곧 태어날'·'입학예정'을 접수 상태로, '30분 컷'을 지난 공고로, '비교적'·'환금성 비교'를 단지 비교로, '서울성모병원'의 서울을 지역으로, 역 주변 질문 못 읽음
- 변경 (chat/v2 만): extract — 앞뒤 말로 직장 가리기(나열·앞뒤 전파, 셔틀 정류장 문장, 'X 접근성', 동 이름→그 역 근사), 지금 사는 곳(assume.home)·팔 집 제외, 역 주변 near_station(직선 1.5km), 서울 서남·서북·동북·동남·도심권·구성남, 금액·면적 범위 표기, C.limit, 접수 상태는 청약 말이 있을 때만, 신생아(assume.newborn)·막내 나이, 뉴타운→동 이름, 단지 비교의 주택형(C.targetArea), 답하지 않는 것(매물 등급·호가, 사고팔 시점, 대출 판단). search — 역 이름 좌표를 노선 자료로(resolvePlaces·stationPoint), near_station 판정·늦추기(3km), 가장 가까운 곳은 역·시도 중심·직장 기준, 셔틀 출근이면 정류장 거리. answer — '역 주변' 카드 줄, 위치 자료 없는 출퇴근지 '확인 불가', 출퇴근 미확인 한 줄로, 셔틀 정류장을 사람으로 세지 않음, 권역 설명·조사, 요청한 수까지 나머지 목록, 실거주 말 없으면 '찾으시면서'. llm — near_station 키·사실 묶음, AI 해석에 규칙의 역·셔틀·limit·plan 이어 붙임. index — 출퇴근지 좌표 채운 뒤 지오코딩
- 파일: chat/v2/{extract,search,answer,llm,index,lexicon}.mjs, chat/v2/golden/questions.json, chat/v2/test/v2.test.mjs, chat/v2/STYLE.md, HANDOFF.md
- 확인: 20개 원문 질문 해석 전후 대조(작업 공간), node --test 94/94(새 21개), 품질 평균 99.8(기준선 99.8)·치명 0·JGA 100%·INV 99.1%(기준 안)
- 백업: backup/20261004-2246-chatv2kakao
- 기능: 없음(수정)

## 2026-10-04 18:05 · 청약봇 V2 AI 회차 6 결과 반영 (질문 속 숫자 허용)
- 요청: (샘플 5 이어서) 품질 순환
- 회차 6: AI 8승 2패 10무(Elo AI 1054·기본 946). 샘플 5 는 AI 설명이 검사기에 막혀 기본 답(3.33)이 나감 — 이유 'FACTS 에 없는 숫자 17.5'(질문자가 말한 예산 17.5억)
- 변경: factsForLLM 에 question_numbers(질문 속 숫자) — 질문자가 직접 말한 숫자는 다시 써도 됨. 지어낸 숫자는 그대로 막음(시험: 17.5 통과·19.5 막힘)
- 심사 의견(반영 안 함, 기록): '이미 지어진 단지라도 5년/10년 보유 전략의 일반 원칙(재건축 조합원 지위양도 제한 등)을 짚어 주면 좋겠다' → 법령 근거(docs/chat-law.json)로 답하는 방식은 미리보기 연결 뒤 사용자와 상의
- 파일: chat/v2/llm.mjs
- 확인: node --test 73/73, 품질 평균 99.8·치명 0
- 백업: backup/20261004-1733-chatv2s5
- 기능: 없음(수정)

## 2026-10-04 17:33 · 청약봇 V2 사용자 샘플 5 반영 (보유 계획·가설 점검·비교 이름 자르기)
- 요청: (비교 표 이미지 + 첨부) "! 프라이어팰리스 vs 고덕센트럴푸르지오 vs 삼익그린2차 … 5년 후 상급지 갈아타기면 프라이어·고센푸, 10년 이상 장기보유+재건축이면 삼익그린이 나을까? … 환금성·하방방어·투자수익까지 고려해서 추천 순위"
- 지금 V2 문제: ① 세 번째 단지 이름이 질문 끝까지 붙음('생각하고 있어'의 '하고'를 구분 말로) ② '상급지'의 '급지'로 묻지 않은 '급지·호재' 표시 ③ 보유 계획(5년 뒤 갈아타기·10년 장기·실거주+투자)·환금성·하방 방어를 못 읽음
- 변경 (chat/v2 만): extract — 비교 이름은 첫 문장·vs 사슬 안에서만, 이름 뒤 꼬리말 자름(24자 넘으면 버림), (?<!상)급지, 보유 계획 C.plan {sell_after, long_hold, live, invest}, 환금성·하방 방어는 '이미 지어진 단지의 거래 지표라 없음(새 분양은 분양가·시세 차이로)'. search factsOf.limits(실거주 의무·재당첨 제한·분양가상한제 — 모집공고문 값). answer — 이해 블록 '보유 계획', 카드 '· 보유 계획  실거주 의무 … → N년 뒤 팔기: 가능/어려움 · 재당첨 제한이면 청약 갈아타기 어려움'(전매제한은 공고문 확인), '[보유 계획별로 보면]'(N년 뒤 팔기 / 오래 보유 순위, 제한이 모두 같으면 '순위가 갈리지 않아요'), 비교 대상이 기존 아파트면 가설을 받아 주고 데이터 없는 순위는 만들지 않음. factsForLLM 에 limits·plan. STYLE.md 샘플 5 원칙, golden 2문항, 시험 1개, ai-run 샘플·회차 6
- 파일: chat/v2/{extract,search,answer,llm}.mjs, chat/v2/STYLE.md, chat/v2/golden/questions.json, chat/v2/test/v2.test.mjs, chat/v2/quality/ai-run.json
- 확인: node --test 73/73, 품질 평균 99.8(기준선 그대로)·치명 0. AI 회차 6 은 Actions 결과
- 백업: backup/20261004-1733-chatv2s5
- 기능: 없음(수정)

## 2026-10-04 15:20 · 청약봇 V2 샘플 4 마무리 (실제 노선 자료로 확인·근거 충실도·AI 회차 5)
- 요청: (샘플 4 이어서)
- 노선 자료: .gitignore 고친 뒤 근거 자료 모으기가 chat/v2/data/lines.json 을 올림(24b8edf 실행) — 2호선 51역(인천 2호선 28역은 따로), 신분당선 16역
- 실제 답 확인: '[신분당선 역세권 공고 현황] 지금 접수 중·예정 공고 중 신분당선 역 직선 1km 안은 없어요' → 결론 바로 뒤로 옮김. '왜 없는지'가 역 거리마다 따로 세던 것을 '신분당선 역에서 1km 넘음 50개'로
- 근거 충실도: 노선 자료를 읽자 품질 검사 치명 4건(카드의 '○○역 직선 13.6km'가 사실 묶음에 없음) → factsForLLM 에 rail_line(후보별 노선 역·거리)·rail_lines(노선 현황)·outside(넓혀 보기 후보) 추가. AI 조건 해석이 line·expand·family·no_school 을 알게(KEYS·지시문), AI 해석이 빠뜨려도 규칙의 scope·assume·관점을 남김
- 파일: chat/v2/search.mjs, answer.mjs, llm.mjs, quality/ai-run.json(샘플 4·회차 5)
- 확인: node --test 70/70, 품질 평균 99.8·치명 0. AI 회차 5 는 Actions 결과
- 백업: backup/20261004-1419-chatv2s4
- 기능: 없음(수정)

## 2026-10-04 14:50 · 청약봇 V2 사용자 샘플 4 반영 (노선 역세권·경기남부)
- 요청: (첨부) "!경기남부 신분당선 라인에 20평대 9억 이하로 진입 가능한 단지 있음?"
- 지금 V2 문제: '신분당선'의 '분당'을 성남 분당 지역 조건으로 읽음 → '분당 · 9억 · 20평대' 로 엉뚱한 결과, 노선·'경기남부'를 모름
- 변경 (chat/v2 만): lexicon REGION_SETS(경기남부·경기북부 — 한강 남/북 경기 시·군), LINE_RE·normLine. extract — 노선 이름을 지역 찾기 전에 지우고 line 조건(역까지 직선 1km, 필수)으로, 노선 역세권이면 station_walk 는 만들지 않음. search — line 판정(단지 좌표 → 그 노선 가장 가까운 역 직선거리, 역 정보·좌표 없으면 확인 불가), 노선 역세권 공고 현황(공고 수·주변 역·가장 싼 주택형), 늦추기 버튼 '역까지 1km → 3km'. answer — 카드에 '· 신분당선  ○○역 직선 Nm (역 위치 OpenStreetMap, 추정)', 이해 블록에 '경기남부는 이렇게 봤어요: …', 확인 필요 결론 안내를 이유에 맞게(평면도 안내는 방·욕실일 때만). node-data/browser 가 chat/v2/data/lines.json 을 읽음
- 노선 자료: tools/subway_lines.py 첫 실행(fb215f8) — 신분당선 16역(신사~광교) 원문 노선과 일치 확인. '인천 도시철도 2호선' 역이 서울 2호선에 섞여 이름 정리 고침. .gitignore 'data/' 가 chat/v2/data 까지 막아 '/data/'(루트만)로 바꿈
- 파일: chat/v2/{lexicon,extract,search,answer,node-data,browser}.mjs, chat/v2/STYLE.md, chat/v2/golden/questions.json, chat/v2/test/v2.test.mjs, tools/subway_lines.py, .gitignore
- 확인: node --test 70/70(노선 판정 pass/fail/좌표 없음/역 정보 없음, 경기남부 정의 표시, '신분당선'≠분당), 품질 평균 99.8(기준선 그대로)·치명 0. 올린 뒤 근거 자료 모으기가 lines.json 을 다시 만들면 실제 질문 답 확인
- 백업: backup/20261004-1419-chatv2s4
- 기능: 없음(수정)

## 2026-10-04 14:20 · 수도권 노선별 역 좌표 모으기 (청약봇 V2 샘플 4 '신분당선 라인')
- 요청: (첨부 — 다른 서비스 매매 상담 답) "!경기남부 신분당선 라인에 20평대 9억 이하로 진입 가능한 단지 있음?"
- 지금 V2 문제: '신분당선'의 '분당'을 지역(성남 분당)으로 읽음, 노선·'경기남부'를 모름. 노선 조건에는 역 좌표가 필요하고 기억으로 적지 않으므로 수집과 같은 출처(OpenStreetMap Overpass)에서 모음
- 변경: tools/subway_lines.py — 수도권 범위 전철 노선(route relation)의 역 이름·좌표를 노선별로 모아 chat/v2/data/lines.json(출처 ODbL 표기)·evidence/chat-v2/lines-probe.txt. 근거 자료 모으기(probe.yml)에서 실행·저장(폴더 없으면 건너뜀)
- 파일: tools/subway_lines.py, .github/workflows/probe.yml
- 확인: 노선 이름 정리 함수(신분당선·2호선·수인·분당선→수인분당선)·역 이름 정리 로컬 확인. 결과 파일은 Actions 실행 뒤 신분당선 역 목록으로 검토
- 백업: backup/20261004-1419-chatv2s4
- 기능: 없음(수정)

## 2026-10-04 14:20 · 청약봇 V2 AI 회차 4 결과 반영
- 요청: (샘플 3 이어서) 품질 순환
- 회차 4 결과(evidence/chat-v2/ai-quality-report.md): 질문 20개, AI 설명 답 9승 3패 8무(회차 3 은 7·3·10), Bradley-Terry AI 1054 · 기본 946. 샘플 3 은 무승부(기본 4.0 · AI 3.67)
- 심사가 꼽은 샘플 3 고칠 점 → 반영: ① '저층 제외' 안내가 아래 '확인하지 못한 것'까지 가야 보임 → '이렇게 이해했어요'에 '따를 수 없는 것: 저층 제외 — 청약은 당첨 뒤 동·호수를 추첨으로 정해요' ② 매물(매매) 추천이 왜 없는지 → 첫 줄 아래에 '매물은 청약패스가 다루지 않아 같은 조건의 새 분양 공고로 찾았어요 + 실거래가 공개시스템'
- 파일: chat/v2/answer.mjs, evidence/chat-v2/ai-quality*.{json,md}(Actions 가 씀)
- 확인: node --test 66/66, 품질 평균 99.8(기준선 그대로)·치명 0
- 백업: backup/20261004-1358-chatv2s3
- 기능: 없음(수정)

## 2026-10-04 13:58 · 청약봇 V2 사용자 샘플 3 반영 (넓혀 보기·생활 조건 읽기·학군 안 따짐·저층 설명)
- 요청: (첨부 — 다른 서비스 매매 상담 답) "! 마포구 30평대 4인가족 … 가격 상승력·교통·실거주 만족도, 저층 빼고 21억까지, 학군지 필요없어, 마포구 말고도 동일한 조건으로" — 샘플 검토 후 미리보기 연결 예정 (10-03 사용자 '샘플 더 줄 테니 검토하고 미리보기로 연결')
- 지금 V2 로 돌려 본 문제: ① '마포구 말고도'를 '마포구 제외'로 읽어 '마포구 · 마포구 제외' 모순 조건 → 결과 0 ② 가격 상승력·교통·실거주 만족도를 못 읽음('가격'만 관점으로) ③ 학군 필요 없다는데 '초등학교가 가까워요'를 장점으로 ④ 저층 제외를 '데이터 없음'으로만 ⑤ 첫 줄이 일반 문장 ⑥ 대안 순서: 신청 불가 곳이 맨 위
- 변경 (chat/v2 만 — 서비스 화면·서버 영향 없음): extract — 넓혀 보기(말고도·외에도·말고 다른 곳·동일한 조건으로 → scope.expand, 지역은 포함), 교통 → 역 도보 10분(선호), 실거주 만족도 → 500세대 이상(선호)·관점, 가격 상승력 → 시세 차익(선호)·관점 growth(미래 가격 예측 안 함을 밝힘), N인 가족, 학군 필요없음(no_school), 저층 제외는 '청약은 당첨 뒤 동·호수 추첨이라 미리 뺄 수 없어요'. search — expand 면 지역만 푼 같은 조건 후보(그 지역 밖, 생활권 30km 안 → 신청 가능 → 우선순위 → 거리), 결과 없을 때 가까운 곳도 신청 가능 곳 먼저. answer — 첫 줄 상황 되짚기, 'A 밖 · 같은 조건' 블록·결론, 근거 거래 5건 미만 '참고만', 우선순위별로 먼저 볼 곳, 학교 줄 빼기, 이유를 적은 확인 불가 항목에 말 덧붙이지 않음. 채점표 unsupported-said 가 '예측하지 않아요·미리 뺄 수 없어요'도 인정. STYLE.md 에 샘플 3 원칙, golden 5문항, 시험 1개, ai-run.json 샘플·회차 4
- 파일: chat/v2/extract.mjs, search.mjs, answer.mjs, STYLE.md, golden/questions.json, test/v2.test.mjs, quality/rubric.mjs, quality/baseline.json, quality/ai-run.json, evidence/chat-v2/quality*.{json,md}
- 확인: node --test 66/66, 품질 회차(코드) 평균 99.8(기준선 그대로)·JGA 100%·INV 99.3%·DIR 100%·치명 0. AI 회차 4 는 올린 뒤 Actions(chat-v2-quality-ai.yml) 결과
- 백업: backup/20261004-1358-chatv2s3
- 기능: 없음(수정)

## 2026-10-04 08:55 · 새벽 수집 예약이 빠진 날 대비 (예비 예약 06:50·08:50)
- 요청: "이제 우리 뭐 해야지?" → 점검 중 발견: 10-04 05:30 예약 수집이 아예 실행되지 않음(Actions 실행 목록에 없음 — GitHub 가 예약 실행을 빠뜨림. 같은 날 공고문 재시도 예약도 몇 번 빠짐)
- 조치: 08:56 수집 손 실행(workflow_dispatch — 새 공고 알림·접수 전날 알림도 보냄)
- 변경: collect.yml 예약을 05:30·06:50·08:50(한국) 세 번으로. 앞에 gate 작업을 두어 예약 실행이면 docs/daily-run.txt(그날 매일 수집이 돈 날짜)를 보고 이미 돌았으면 수집 작업을 건너뜀 → 하루 한 번만 수집·알림(접수 전날 알림 두 번 안 감). daily-run.txt 는 예약·손 실행만 적고 코드 변경(push) 실행은 적지 않음
- 파일: .github/workflows/collect.yml
- 확인: YAML 구조(gate → collect needs/if, 예약 3개). 올린 뒤 손 실행 결과·내일 새벽 실행 확인
- 백업: backup/20261004-0855-cronbackup
- 기능: 없음(수정)

## 2026-10-03 23:50 · 공고문 읽기 고정 검사가 매일 수집을 막지 않게
- 요청: (위 항목 이어서) 이전 정상값 지키기
- 원인: 고정 검사는 수집 첫 단계 pytest 에서도 돈다. 원문 파일을 다시 받아 글자가 바뀌면(규칙 변경이 아닌데도) 실패해 수집이 멈출 수 있음
- 변경: 기준에 원문 글 지문(sha256 앞 16자)을 함께 두고, 글이 같은 원문만 비교(글이 바뀐 원문·새 원문은 건너뛰고 개수만 표시)
- 파일: tools/qa/parse_snapshot.py, tests/qa/parse_snapshot.json
- 확인: 거주기간 수정을 일부러 되돌리면 테스트 실패, 원문 글에 공백 한 칸 더하면 '글이 바뀐 원문 1'로 건너뜀, pytest 전체
- 백업: backup/20261003-2346-guard
- 기능: 없음(수정)

## 2026-10-03 23:44 · 오늘 수정의 영향 전수 대조 + 이전 정상값 지키는 검사 2개
- 요청: "최신 수정들이 이전에 정상값들에 영향을 주지 않도록 잘 계산해서 수정 부탁해"
- 대조 결과 (오늘 수정 전 새벽 데이터 d1a9b56·시세 정상이던 10:32 데이터 963ce98 ↔ 지금):
  · 공고 226건 그대로(빠지거나 생긴 공고 0). 공고문에서 읽은 항목(from_notice)은 174줄 순서만 바뀜, 빠진 항목 0 — 새로 생긴 건 새벽에 받기 실패한 3곳(0494·0444·0386)뿐
  · 10:32 이후 판정·데이터 필드가 바뀐 곳: 비율 4곳(0436·0444·0463·0498 score_ratio·checks), 향남역(0463) 시세·위치·시군구 — 모두 의도한 수정. 0253 여의재는 공고문 주소만 static↔www 로 바뀜(같은 파일, 읽은 값 같음)
  · 판정 재계산(tools/qa/verdict_diff.cjs): 주택형 × 판정 사례 내 조건 전부(66,896)를 화면 판정 함수로 전후 비교 → 판정이 바뀐 4,029곳은 모두 새벽에 공고문을 못 받던 3곳(거주 요건 '확인 필요' → '가능/불가', 다른 지역 사례 조건이라 대부분 불가). 데이터가 그대로인데 판정이 바뀐 곳 0, 가능↔불가 뒤집힘 0
- 변경: ① tools/qa/parse_snapshot.py + tests/qa/parse_snapshot.json + tests/test_parse_snapshot.py — 모아 둔 원문 109건의 공고문 읽기 결과를 기준으로 고정, 읽기 규칙을 고쳐 값이 하나라도 바뀌면 pytest 실패(어느 공고·어느 값 표시). 확인: 오늘 거주기간 수정을 일부러 되돌리자 정확히 3건(0046·0094·0444 residence)을 잡음 ② tools/qa/verdict_diff.cjs — 두 시점 데이터로 판정 전후 비교(예상 밖 있으면 종료 코드 1). 운영 스킬에 쓰는 법 기록
- 파일: tools/qa/parse_snapshot.py, tests/qa/parse_snapshot.json, tests/test_parse_snapshot.py, tools/qa/verdict_diff.cjs, evidence/qa/verdict-diff.json, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest 전체, 판정 전후 비교 예상 밖 0
- 백업: backup/20261003-2346-guard
- 기능: 없음(수정)

## 2026-10-03 23:08 · 가점제·추첨제 비율 표를 못 읽던 원인 고침
- 요청: (같은 상세 화면 '데이터 확인 필요 · 가점제·추첨제 비율 표를 공고문에서 읽지 못했어요') "그것도 원인 찾아봐"
- 원인: 지금 민영 공고 4곳(2026000463 향남역 그로브 스위첸·0498 천안 아이파크 시티 2단지·0444 제주 아이린8차·0436 더샵 시에르네) + 지난 공고 원문 3곳(0094·0146·0354)
  ① 줄에 주택형을 쉼표로 나열 '60㎡ 초과 85㎡ 이하 71, 84A, 84B… 40% 60%' — 규칙이 쉼표를 몰랐음(0463)
  ② 첫 도구가 표 글자 순서를 뒤섞음 '전용면적 초과 이하60 85㎡ ㎡ 40% 60%' — 예전엔 뒤섞이면 일부러 unknown(0498·0444·0436·0094·0146)
  ③ 낱말 사이 공백 '추 첨제'·'전용 면적'·'초 과'(0354)
  ④ 두 도구 합칠 때 첫 도구의 '못 읽음' 표시({'unknown': True})가 값으로 취급돼 두 번째 도구 값을 막았음(merge_alt)
- 변경: parse_score_ratio — 표를 '전용면적'으로 줄을 나눠 줄마다 면적(㎡ 앞 숫자·초과/이하 붙은 숫자)·초과/이하·비율을 읽고, 줄마다 합 100%·줄끼리 면적이 빈틈없이 이어질 때만 인정(아니면 unknown, 추측 안 함). 낱말 공백 정리. merge_alt 는 unknown 을 빈 값으로 봄. PARSER_VERSION 22 → 모든 공고문 다시 읽음
- 정답 데이터: 7곳 비율을 원문 표로 확인해 tests/golden/notices.json 에 넣음(규칙 별표와도 같음 — 비규제 85㎡ 이하 40·60, 85㎡ 초과 추첨 100, 투기과열 서울 40/70/80). 모아 둔 원문 모두 비율을 읽는지 테스트(test_every_saved_original_score_ratio_reads), 뒤섞인 줄이 안 이어지면 unknown 테스트, merge_alt 테스트
- 파일: app/notice_pdf.py, app/pipeline.py, tests/golden/notices.json, tests/test_notice_and_notify.py, docs/changelog.json, VERSIONS.md
- 확인: 원문 전체 재추출 전후 비교 — 바뀐 곳은 위 7곳(unknown → 원문과 같은 값)뿐, 못 읽음 0. pytest 188. 올린 뒤 수집에서 [검증] 비율 경고가 사라지는지 확인
- 백업: backup/20261003-2308-ratio
- 기능: 없음(수정)
- 버전: v1.49.2

## 2026-10-03 22:13 · 화성특례시 만세구 공고 시세 못 구하던 것 고침
- 요청: (휴대폰 상세 화면) "시군구 코드는 왜 확인 못하는 거야?" — 향남역 그로브 스위첸(2026000463) 시세 '확인 필요'
- 원인: ① 주소가 '화성특례시 만세구'라 경기 시군구 표('화성시')에서 못 찾음 ② 대신 쓰는 지도 좌표(네이버 지오코딩)도 '화성특례시'로는 0건 ③ 표의 화성시 코드 41590 은 화성시가 2026-02 만세구·효행구·병점구·동탄구로 나뉜 뒤 실거래가 0건이라, 찾았어도 시세가 비었을 것 (근거: tools/qa/lawd_probe.py 실행 결과 evidence/qa/lawd-probe.txt — '화성시 만세구'로 지오코딩 1건 → 역지오코딩 41591 '경기도 화성시 만세구 향남읍', 41591 매매 향남읍 2026-02~09 달마다 20~36건)
- 변경: region.norm_city('…특례시' → '…시', 법정 이름)로 시군구 찾기·지오코딩 검색어를 만듦(수원·고양·용인·창원 특례시 표기도 같은 처리). 화성시 구 목록 추가, 표에 '화성시 만세구' 41591(확인한 것만), 옛 '화성시' 41590 은 뺌 — 나머지 구·구 없는 화성 주소는 추측하지 않고 지도 좌표 역지오코딩(lawd-cache)으로 구함
- 파일: app/region.py, app/rules.py, app/geo.py, tests/test_lawd_special_city.py, docs/changelog.json, VERSIONS.md
- 확인: tests/test_lawd_special_city.py(만세구 41591, 지오코딩 검색어, 수원·고양·용인 특례시 표기, 확인 안 한 구는 코드 없음), pytest 186. 올린 뒤 수집에서 향남역 그로브 스위첸 시세가 나오는지 확인
- 백업: backup/20261003-2213-hwaseong
- 기능: 없음(수정)
- 버전: v1.49.1

## 2026-10-03 22:13 · 시군구 코드 점검 도구 (향남역 그로브 스위첸 시세 '시군구 코드 확인 못 함')
- 요청: (휴대폰 상세 화면) "시군구 코드는 왜 확인 못하는 거야?"
- 원인(1차): 주소가 '경기도 화성특례시 만세구 …'. 경기 시군구 표는 '화성시'라 못 찾고, 대신 쓰는 지도 좌표(네이버 지오코딩)도 새 이름으로 0건 → 코드 없음. 코드는 추측하지 않으므로, 실제로 어느 코드로 실거래가가 나오는지 먼저 확인
- 변경: tools/qa/lawd_probe.py — 코드 못 찾은 주소마다 주소 여러 형태(원문·특례시→시·구 뺀 것)로 지오코딩 → 역지오코딩 법정동 코드 → 후보 코드로 최근 9개월 매매·분양권 조회해 그 읍면동 거래 수. 근거 자료 모으기(probe.yml)에서 실행 → evidence/qa/lawd-probe.txt
- 파일: tools/qa/lawd_probe.py, .github/workflows/probe.yml
- 확인: 대상 3곳 뽑기·주소 형태 만들기 로컬 확인. 결과는 Actions 실행 뒤
- 백업: backup/20261003-2213-hwaseong
- 기능: 없음(수정)

## 2026-10-03 12:24 · 새 공고 알림 공개 + 알림 켜기 전 동의
- 요청: "알림은 일단 공개해주고" → 방침 개정(4-2항 처리 위탁·국외 이전) 시행일이 10-09라 그 전에 공개하면 시행 전부터 구독 정보를 받게 된다고 알림 → 사용자 선택 '지금 공개 + 화면에 동의 문구'
- 변경: docs/config.json push_legal_date 2026-10-09 → 2026-10-03 (모든 기기에 알림 탭·알림 켜기·받은 알림함 공개, 미리보기 표시는 저절로 사라짐). 새 기능 push_consent: 알림 켜기 버튼 위에 맡기는 항목(알림 주소·암호화 키·지역·종류·구독 날짜)·받는 곳(Cloudflare, 미국 등)·목적·보관 기간·보내지 않는 정보를 보여 주고 '동의(필수)'를 눌러야 버튼이 켜짐. 동의 날짜는 이 기기에만(cy-push-consent). 방침 4-2항과 같은 내용. 알림 서버(push/)는 그대로
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md
- 확인: 390px 밝은·어두운 화면(미리보기 주소 없이) — 아래 알림 탭 보임, 미리보기 표시 없음, 동의 전 '알림 켜기' 비활성 → 동의 누르면 활성, 가로 넘침 없음, 화면 오류 0. push_inbox.cjs·E2E·스냅샷·판정 사례·엔진 잠금, 스크립트 문법, pytest
- 백업: backup/20261003-1224-pushopen
- 기능: push_consent
- 버전: v1.49.0

## 2026-10-03 10:41 · 판정 검증·청약봇 V2 점검이 수집을 취소하던 문제 고침 (대기 줄 분리)
- 요청: (재시도 보고 때 알린 남은 문제) "이것도 진행해"
- 원인: verify.yml(판정 검증)·chat-v2-probe.yml 이 수집과 같은 concurrency 묶음(collect)이었음. GitHub 은 한 묶음에 대기 실행을 하나만 두므로, 코드를 올려 수집과 판정 검증이 같이 생기면 대기 중이던 수집이 취소됨(10-02 1bf91b2, 10-03 d6aaa8d 수집 cancelled)
- 변경: 판정 검증은 묶음 verify 로 나누고, 시작할 때 수집이 돌거나 대기 중이면 끝날 때까지(최대 45분) 기다린 뒤 최신 main 을 받아 검사(tools/qa/wait_collect.sh, 권한 actions: read). 청약봇 V2 점검은 공고 데이터를 안 쓰니 묶음만 분리. 공고문 재시도도 같은 스크립트로. 이제 collect 묶음에는 수집만 있음
- 파일: .github/workflows/verify.yml, .github/workflows/chat-v2-probe.yml, .github/workflows/notice-retry.yml, tools/qa/wait_collect.sh
- 확인: YAML 문법 4개, 올린 뒤 수집과 판정 검증을 같이 띄워 수집이 취소되지 않고 판정 검증이 기다렸다 도는지 확인
- 백업: backup/20261003-1041-queue
- 기능: 없음(수정)

## 2026-10-03 10:30 · 공고문 재시도가 수집 실행을 취소하던 문제 고침
- 요청: (위 재시도 작업의 올린 뒤 확인)
- 원인: notice-retry.yml 을 수집과 같은 concurrency 묶음(collect)에 뒀더니, 손으로 띄운 재시도가 대기 중이던 수집(d6aaa8d 코드 반영 실행)을 밀어내 취소시킴 (GitHub 은 한 묶음에 대기 실행을 하나만 둠)
- 변경: 재시도는 따로 묶음(notice-retry)으로, 시작할 때 수집이 돌거나 대기 중이면 끝날 때까지(최대 45분) 기다린 뒤 최신 main 에서 시작. 올리기가 막히면(그사이 수집이 올림) 덮어쓰지 않고 버림(-X theirs 제거)
- 파일: .github/workflows/notice-retry.yml
- 확인: YAML 문법, 올린 뒤 수집 다시 실행·재시도 손으로 실행해 둘 다 성공 확인
- 백업: backup/20261003-1020-retry
- 기능: 없음(수정)

## 2026-10-03 10:20 · 공고문 받기 재시도 (못 받은 공고만 낮 동안 2시간마다)
- 요청: "받기에 실패한 공고는 재시도하게 해줘"
- 변경: app/notice_retry.py — docs/listings.json 에서 공고문 PDF 를 못 받은(notice_pdf 없음) 공고만 apply_notice 로 다시 받아 그 공고 값만 채움. 공고 목록·시세·경쟁률은 다시 받지 않고 새 공고를 더하지 않으며 알림도 보내지 않음. 다시 읽은 공고만 검증(listing_checks·공고문 대조)을 새로 하고 정답 대조는 전체. 읽은 값은 docs/notice-cache.json 에 남겨 다음 새벽 수집이 그대로 씀. .github/workflows/notice-retry.yml — 한국 08:20~22:20 2시간마다, 새벽 수집과 같은 concurrency 묶음(collect). 받을 공고가 없거나 스위치가 꺼지면 파이썬 설치도 없이 끝남. 22시 마지막 재시도에도 못 받으면 '수집 알림' 이슈에 남김
- 파일: app/notice_retry.py, .github/workflows/notice-retry.yml, tests/test_notice_retry.py, docs/config.json, docs/changelog.json, VERSIONS.md
- 확인: tests/test_notice_retry.py — 못 받은 공고만 다시 받음·그 공고 거주 요건 채움·다른 공고는 그대로·공고 수 그대로·보관 기록에 남음 / 또 실패하면 데이터 안 씀 / 받을 공고 없으면 아무것도 안 씀 / 스위치 끄면 건너뜀. 실제 데이터로 실행: '다시 받을 공고 없음'(10:00 수집에서 226건 모두 받음). pytest 전체, 워크플로 YAML 문법
- 백업: backup/20261003-1020-retry
- 기능: notice_retry
- 버전: v1.48.0

## 2026-10-03 08:46 · 거주 요건 읽기 보강 (원문 109건 모두 읽기) · 제보 공고 정답 데이터
- 요청: (같은 제보) "못 읽는 게 없어야 정상 서비스. 무조건 읽을 수 있게"
- 원인: (1) 받기 실패 3곳은 v1.47.1 로 해결, 다시 받은 뒤 원문 대조에서 제주 아이린8차(2026000444)의 해당지역 거주기간을 놓친 것을 찾음 — pypdf 글이 '제주특별자치도 년 이상 계속 거주자1'처럼 숫자가 뒤로 밀리고 '계속'이 끼어 규칙이 못 잡음 → '제주 거주'만으로 해당지역 판정(원문은 1년 이상 계속 거주, 2025.10.02. 이전부터). 같은 원인 지난 공고 2건(2026000046 대전 1년·2026000094 서울 2년)도 기간을 놓쳤음. (2) 모아 둔 원문 109건 중 5건은 거주 요건을 아예 못 읽었음: 표 머리 '국민'(2026000081)·'규제 지역 여부'(2026000185)·'국민주택 (5년공공건설임대)'(2025000645), SH <표2> 지역우선 공급기준(2026000041), '국내에 거주하는'(2025910266)
- 변경: app/notice_pdf.py parse_residence — 위 변형 모두 읽기(SH 표2는 기준일에서 N년 역산해 since). PARSER_VERSION 21 → 모든 공고문 다시 읽음. 모아 둔 원문이 하나라도 못 읽으면 실패하는 테스트(test_every_saved_original_has_residence) 추가
- 정답 데이터: tests/golden/notices.json 에 원문을 직접 읽고 확인한 거주 요건 10건 추가(2026000444·0494·0386·0046·0094·0081·0185·2025000645·2025910266·2026000041, verified_at 2026-10-03). 군산 2026000274 는 읽는 규칙만 바뀌고 값 같음(해당 군산시·기타 전북)을 원문으로 확인
- 파일: app/notice_pdf.py, app/pipeline.py, tests/golden/notices.json, tests/test_residence.py, docs/changelog.json, VERSIONS.md
- 확인: 원문 109건 재추출 전후 비교 — 바뀐 곳은 위 8건(놓친 기간 3·못 읽던 5)과 군산(값 같음)뿐, 못 읽는 원문 0. pytest 178 통과, 판정 사례 365/365, 엔진 잠금 그대로
- 백업: backup/20261003-0846-pdffetch
- 기능: 없음(수정)
- 버전: v1.47.2

## 2026-10-03 08:46 · 원문 대조용 공고문 받기에 지금 공고 추가
- 요청: (위 거주지 제보의 4항 절차) 제보 공고 3곳 원문을 사람이 읽고 정답 데이터에 넣기 위해 원문을 받음
- 변경: tools/qa/fetch_notices.py 가 보관함에 없는 번호는 docs/listings.json(지금 공고)에서 공고 화면 주소를 찾음. evidence/qa/notice-ids.txt 에 2026000494·2026000444·2026000386 추가
- 파일: tools/qa/fetch_notices.py, evidence/qa/notice-ids.txt
- 확인: 근거 자료 모으기 실행 결과 evidence/qa/notices/<번호>.txt 생성 확인 예정
- 백업: backup/20261003-0846-pdffetch
- 기능: 없음(수정)

## 2026-10-03 08:46 · 공고문 PDF 받기 실패 고침 (첨부 서버 '찾을 수 없음' → 청약홈 본 서버에서 받기)
- 요청: (휴대폰 상세 화면) "공고문에서 거주지 자격요건 못 읽었다고 또 나오는데, 못 읽는 게 없어야 정상 서비스. 두 도구로 읽는다 했는데도 못 읽은 거야? 무조건 읽을 수 있게"
- 원인: 읽기 문제가 아니라 받기 문제. 10-02 공고 3곳(2026000494 더샵 동인센트리체·2026000444 제주 이도이동 아이린8차·2026000386 용인 양지 서희스타힐스 하이뷰)의 '모집공고문 보기' 링크(static.applyhome.co.kr)가 200·59바이트 'The requested URL was not found on this server.' 글을 줌 → PDF 를 못 받아 두 도구 모두 읽을 글이 없었음. 같은 주소를 www.applyhome.co.kr 로 받으면 PDF(0.5~1.5MB)가 옴 (점검 도구 tools/qa/pdf_fetch_probe.py, 근거 자료 모으기 08:53 실행 → evidence/qa/pdf-fetch-probe.txt). 순번을 바꾼 주소는 모두 500
- 변경: app/notice_pdf.py `_with_mirrors` — static 첨부 링크마다 본 서버 주소를 바로 뒤에 붙여 차례로 시도. 받은 주소를 notice_pdf 로 남겨 화면의 공고문 링크도 열리는 주소로. 실패 공고는 보관하지 않으므로 이 커밋으로 도는 수집에서 3곳을 다시 받음
- 파일: app/notice_pdf.py, tests/test_pdf_mirror.py, tools/qa/pdf_fetch_probe.py, .github/workflows/probe.yml(점검 단계, 직전 커밋 f0852e9), docs/changelog.json, VERSIONS.md
- 확인: tests/test_pdf_mirror.py (static 이 '찾을 수 없음'일 때 www 로 받고 그 주소를 남김), pytest 전체. 올린 뒤 수집 실행에서 3곳 [공고문] PDF 읽음·거주 요건 추출 확인 예정
- 백업: backup/20261003-0846-pdffetch
- 기능: 없음(수정)
- 버전: v1.47.1

## 2026-10-03 07:45 · 받은 알림함 (알림 탭 '받은 알림'·안 읽은 수·앱 배지 지우기)
- 요청: (앱 아이콘에 1 배지가 뜬 화면) "알람이 1로 떠있는데 이거 확인하는 기능 넣어줘"
- 원인: 10-03 새벽 수집의 웹 푸시(새 공고 8곳, 구독 1명에게 보냄)가 미리보기 기기에 도착해 배지 1이 생김. 지금까지는 알림창에서 놓치면 다시 볼 곳이 없었음
- 변경: sw.js 가 받은 알림을 이 기기 IndexedDB(cp-inbox)에 최근 30개 저장하고 안 읽은 수를 앱 배지(setAppBadge)로 표시. 알림 탭 맨 위 '받은 알림' 목록(이 기능 전에 받아 알림창에 남은 알림도 getNotifications 로 함께 표시), 누르면 해당 공고로 이동. 안 읽은 수를 아래 알림 탭(또는 위 알림 버튼)에 빨간 숫자로 표시. 알림 탭을 열면 읽음 처리·알림창의 청약패스 알림 닫기·배지 지우기(clearAppBadge). 알림 서버(push/)는 그대로, 서버로 보내는 것 없음
- 파일: docs/sw.js, docs/index.html, docs/config.json, tools/qa/push_inbox.cjs, docs/changelog.json, VERSIONS.md
- 확인: tools/qa/push_inbox.cjs — localhost 에서 sw.js 등록 후 CDP 로 실제 푸시 2건 전달, 390px 밝은·어두운 화면에서 저장 2·탭 숫자 2·목록 2(새 표시)·연 뒤 읽음 0·숫자 사라짐·눌러 공고 이동·스위치 끄면 목록 없음·화면 오류 0 모두 통과. 스크립트 문법 OK, E2E·스냅샷·엔진 잠금, pytest
- 백업: backup/20261003-0745-inbox
- 기능: push_inbox
- 버전: v1.47.0

## 2026-10-03 01:09 · 지난 공고 검색창 한글 조합 끊김 고침
- 요청: (휴대폰 화면) "지난 1년 공고에 검색어 입력할 때 단어가 완성이 안 되고 ㅊ ㅓㄴㅇ ㅏㄴ 이렇게 작성됨"
- 원인: 지난 공고 검색은 입력 0.2초 뒤 화면 전체를 다시 그려 입력칸이 새로 만들어졌고, 그때 한글 조합 중이던 글자가 끊김(공고 목록 검색은 검색창을 남기고 나머지만 다시 그려 문제 없음)
- 변경: 공고 목록 검색의 '검색창만 남기고 다시 그리기'를 renderKeep(view, 선택자)로 일반화해 지난 공고 검색(#pqwrap)에도 씀. 조합이 끝날 때(compositionend)도 한 번 더 거름
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 390px 밝은·어두운 화면에서 지난 공고 검색에 '천안' 입력 — 입력칸이 같은 요소로 남고 포커스 유지, 24건으로 걸러짐, 가로 넘침 없음. E2E 32/32, 스냅샷 차이 0, 엔진 잠금 그대로, 스크립트 문법 OK, pytest
- 백업: backup/20261003-0109-pqime
- 기능: 없음(수정)
- 버전: v1.46.3

## 2026-10-03 01:02 · 청약봇 V2 AI 품질 회차 3 결과 반영
- 요청: (이어서) 진화 순환
- 회차 3 결과(sonnet-5 심사): v2-0.2 가 기본 답에 7승 3패 10무, 절대 평가 기본 3.69 → AI 3.99 (5점 만점) — 챔피언 유지
- 고친 것(심사가 꼽은 점): 받침에 맞는 조사('송파구가 아닌 곳'), 비교에서 못 찾은 단지를 한 줄로 묶음, 대안 후보마다 '왜 여기: 말씀하신 지역에서 직선 약 N km'
- 파일: chat/v2/search.mjs, chat/v2/answer.mjs, chat/v2/llm.mjs, chat/v2/test/v2.test.mjs, chat/v2/QUALITY.md, HANDOFF.md, evidence/chat-v2/*
- 확인: V2 시험 60/60, 코드 품질 99.8·치명 0, pytest
- 백업: backup/20261003-0102-airound3b
- 기능: 없음(개발 중)

## 2026-10-03 00:52 · 청약봇 V2 AI 품질 회차 2 결과 반영 + 회차 3
- 요청: (이어서) 진화 순환
- 회차 2 결과: 프롬프트 v2-0.2(AI 다듬기)가 기본 답에 10승 3패 7무 → 챔피언 교체(ai-run.json champion). 절대 평가 20/20 읽음(기본 3.24 · AI 3.30 / 5). 심사 모델 claude-sonnet-5 는 temperature 를 받지 않아 400 → 빼고 보냄
- 고친 것(심사가 꼽은 점): 결론 문장을 '이렇게 이해했어요' 앞으로, 결론의 곳 수가 카드 수와 다르던 것('N곳 중 먼저 볼 3곳'), 기존 아파트 비교 질문은 첫머리에 '비교 못 함 + 국토부 실거래가 공개시스템' 안내와 이 동네 청약 공고 찾기 제안
- 파일: chat/v2/answer.mjs, chat/v2/quality/run_ai.mjs, chat/v2/quality/ai-run.json(round 3), chat/v2/QUALITY.md, evidence/chat-v2/quality*.{json,md}
- 확인: V2 시험 60/60, 코드 품질 99.8·치명 0, pytest. 회차 3 결과는 다음 기록
- 백업: backup/20261003-0052-airound3
- 기능: 없음(개발 중)

## 2026-10-03 00:40 · 청약봇 V2 AI 품질 회차 1 결과 반영 + 회차 2
- 요청: (이어서) AI 심사 회차 결과로 고치기
- 회차 1 결과(evidence/chat-v2/ai-quality-report.md): 짝 비교 기본 답 6승 · AI 다듬은 답(프롬프트 v2-0.1) 3승 · 무 11 → AI 다듬기는 채택하지 않음(챔피언=기본 답). 심사 모델 claude-sonnet-5 는 400 으로 막혀 haiku 로 대신 심사. 절대 평가는 JSON 을 못 읽어 2/20만 집계(고침)
- 심사위원이 찾은 결함을 고침: 물어본 특공 유형(생애최초 등)을 카드에 따로 한 줄, '특공 가능 없음'처럼 엇갈려 보이는 말 → '가능 … / 확인 필요 …', 카드 5→3곳 + 나머지 한 줄 목록('N곳 중 먼저 볼 3곳' — 개수 안 맞던 것), 원하신 선호 조건이 안 맞으면 '아쉬운 점' 줄, 질문에 적은 선호(초품아·역세권)를 시세 차익보다 앞에 정렬, 직장에서 40km 넘는 곳은 뒤로, 이유 줄이 지표 줄 숫자를 되풀이하지 않게. 설명 프롬프트 v2-0.2(카드·줄은 그대로, 첫머리와 '왜 이곳'만 다듬기, 표 금지)로 회차 2 (ai-run.json round 2)
- 파일: chat/v2/search.mjs, chat/v2/answer.mjs, chat/v2/llm.mjs, chat/v2/quality/judge.mjs, chat/v2/quality/run_ai.mjs, chat/v2/quality/ai-run.json, chat/v2/quality/baseline.json, evidence/chat-v2/quality*.{json,md}
- 확인: V2 시험 60/60, 코드 품질 99.8·치명 0(기준선 유지), pytest
- 백업: backup/20261003-0040-airound2
- 기능: 없음(개발 중)

## 2026-10-03 00:29 · 청약봇 V2 AI 품질 회차 1 시작
- 요청: "진행해줘" — AI 심사 회차(질문 20개, 약 0.5~1달러) 돌리기
- 변경: ai-run.json round 0→1 (chat-v2-quality-ai.yml 이 한 번 돎). 심사 모델(claude-sonnet-5)을 못 쓰면 설명 모델(haiku)로 바꿔 기록
- 파일: chat/v2/quality/ai-run.json, chat/v2/quality/run_ai.mjs
- 확인: 올린 뒤 evidence/chat-v2/ai-quality-report.md
- 백업: backup/20261003-0029-airun
- 기능: 없음(개발 중)

## 2026-10-03 00:09 · 청약봇 V2 답 품질 측정·진화 순환
- 요청: "답변품질 체크하는 검증 알고리즘 짜서 품질 검증하고, 더 높일 방법 보고, 지속적으로 진화시키는 알고리즘으로" + "챗봇·LLM 만들 때 많이 쓰는 유명한 알고리즘이면 그 방식 적용"
- 변경: chat/v2/quality/ — rubric.mjs(7차원 채점표, 치명 검사는 0점, 슬롯 F1·Joint Goal Accuracy), generate.mjs(조각을 섞어 정답을 아는 질문 생성), checklist.mjs(CheckList INV 말 바꾸기 15묶음·DIR 조건 더하기), run.mjs(시험지+생성 질문 × 내 조건 2종 324답 채점, 약점 순위·말 바꾸면 깨지는 표현·못 읽은 낱말, 기준선 래칫, 사용자 👎 이유 반영 자리), judge.mjs·run_ai.mjs·ai-run.json(AI 심사 G-Eval 절대 평가 + 자리 바꾼 짝 비교 + Bradley-Terry, round 0 이라 안 돎), QUALITY.md. 첫 회차에서 찾은 것을 고침 — 해석: '무주택 4인 가족'·'아이 둘'(JGA 57.5→100%), 같은 뜻 다른 표기 정규화 표(NORM)와 무게를 조건 가까이에서만 판정(INV 77.7→99.3%); 답: 방3화2만 물으면 '없어요'라고 하던 것 → 확인하면 되는 후보, 결과 없을 때 '조건에 가장 가까운 곳', 좁혀 줄 질문을 늘 하나, 이유 한 줄 보강(예산 여유 등), 아이 언급 없을 때 '아이 키우기에 좋아요' 안 씀, 비교 답에 좁혀 줄 질문; 검사기: 링크 속 숫자 무시, 사실 묶음에 직선거리·예산 여유·조건 값·공급 세대 추가. chat-v2.yml 에 품질 게이트, chat-v2-quality-ai.yml
- 파일: chat/v2/quality/*, chat/v2/QUALITY.md, chat/v2/extract.mjs, chat/v2/lexicon.mjs, chat/v2/search.mjs, chat/v2/answer.mjs, chat/v2/llm.mjs, chat/v2/test/v2.test.mjs, .github/workflows/chat-v2.yml, .github/workflows/chat-v2-quality-ai.yml, evidence/chat-v2/quality.json, evidence/chat-v2/quality-report.md, HANDOFF.md
- 확인: V2 시험 60/60, 품질 324답 평균 99.8·치명 0·JGA 100%·INV 99.3%·DIR 100%, 기준선 저장, pytest
- 백업: backup/20261003-0009-quality
- 기능: 없음(개발 중)

## 2026-10-02 23:53 · 청약봇 V2 직장 위치: 구 이름은 구청으로 찾기
- 요청: (자체 확인) 카카오 장소 검색이 켜진 뒤 첫 확인에서 '구로구' → 푸른수목원, '마포구' → 홍대걷고싶은거리처럼 구 안의 아무 장소가 잡힘. 판교역·가산디지털단지역·삼성전자 수원사업장은 정확
- 변경: 직장 위치가 구·시·군 이름뿐이면 '구로구청'처럼 구청·시청으로 검색
- 파일: chat/v2/index.mjs
- 확인: V2 시험 통과, 올린 뒤 sample-commute.txt 의 기준 장소 확인
- 백업: backup/20261002-2353-kakaoloc2
- 기능: 없음(개발 중)

## 2026-10-02 23:51 · 청약봇 V2 직장 위치를 카카오 장소 검색으로
- 요청: 사용자가 카카오 앱 '제품 설정 → 카카오맵' 사용 설정 ON ("햇음")
- 변경: ask(geocode) — 위치표에 없어 '구 중심 근사'로 잡힌 직장 위치를 카카오 장소 검색으로 실제 장소로 바꿈(답에 'OO 기준'), node.mjs 는 KAKAO_REST_KEY 가 있으면 사용. 확인 워크플로에 장소 검색 4건(구로구·마포구·가산디지털단지역·삼성전자 수원사업장) 추가
- 파일: chat/v2/index.mjs, chat/v2/node.mjs, chat/v2/tools/commute_probe.mjs
- 확인: V2 시험 57/57, pytest. 올린 뒤 chat-v2-probe 의 kakao_local 결과 확인
- 백업: backup/20261002-2351-kakaoloc
- 기능: 없음(개발 중)

## 2026-10-02 23:45 · 청약봇 V2 답에 실제 자동차 출퇴근 시간
- 요청: (이어서) 출퇴근 키 확인 결과 반영
- 확인 결과(chat-v2-probe 첫 실행): 네이버 Directions 5 자동차 10/10, 카카오모빌리티 자동차 10/10 (두 곳 시간 차이 2~35분, 거리 거의 같음). 카카오 장소 검색(로컬)은 403 'App disabled OPEN_MAP_AND_LOCAL service' — 카카오 앱에서 '카카오맵' 사용 설정이 꺼져 있음 → 사용자에게 켜 달라고 요청
- 변경: ask(commute) — 보여 줄 후보(상위 5·확인 필요·대안)만 실시간 조회(저장 안 함), 카드 '남편 구로구까지 자동차 약 N분(km, 출처 조회 시각)', 조회되면 자격 다음 순서를 평균 시간으로. 대중교통은 아직 '확인 불가'. node.mjs 는 환경 변수에 키가 있으면 조회. 시험(가짜 응답) 추가. 워크플로가 실제 시간이 들어간 답 샘플을 evidence/chat-v2/sample-commute.txt 로
- 파일: chat/v2/index.mjs, chat/v2/answer.mjs, chat/v2/llm.mjs, chat/v2/node.mjs, chat/v2/test/v2.test.mjs, .github/workflows/chat-v2-probe.yml, evidence/chat-v2/commute-probe.json
- 확인: V2 시험 57/57, pytest. 올린 뒤 sample-commute.txt 확인
- 백업: backup/20261002-2345-commute2
- 기능: 없음(개발 중)

## 2026-10-02 23:42 · 청약봇 V2 출퇴근 조회 코드 + 실제 확인 워크플로
- 요청: 사용자가 네이버 Directions 5 켜고 GitHub Secret KAKAO_REST_KEY 넣음 ("했다잉")
- 변경: chat/v2/commute.mjs — 자동차 네이버 Directions 5(trafast) → 실패하면 카카오모빌리티 길찾기, 결과 {분·km·출처·조회 시각}, 실패는 오류로(직선거리로 시간을 만들지 않음). 카카오 장소 검색으로 키 확인. 대중교통은 미정(카카오 공개 REST 경로 미확인 — 카카오 지도·로컬 결과는 저장 금지·실시간 호출만, devtalk 151435). chat/v2/tools/commute_probe.mjs + .github/workflows/chat-v2-probe.yml — 좌표 정확한 단지 5곳 × 판교역·의왕역을 실제로 조회해 evidence/chat-v2/commute-probe.json (키 값은 안 씀)
- 파일: chat/v2/commute.mjs, chat/v2/tools/commute_probe.mjs, chat/v2/test/v2.test.mjs, .github/workflows/chat-v2-probe.yml
- 확인: 가짜 응답 시험(네이버 성공·네이버 실패→카카오·키 없음) 통과, V2 시험 전부 통과, pytest. 올린 뒤 chat-v2-probe 결과 확인
- 백업: backup/20261002-2342-commute
- 기능: 없음(개발 중)

## 2026-10-02 22:24 · 청약봇 V2 비교 답 고침
- 요청: (자체 확인) 샘플 답을 만들어 보니 비교 질문에서 '도봉 한신'이 '의왕역 한신더휴'로 잡히고, 같은 이름의 지난 공고가 겹쳐 나오고, 이해한 조건 칸이 비었음
- 변경: 비교 대상은 낱말이 모두 단지 이름(지역 낱말은 주소)에 있어야 같은 단지, 지금 공고가 있으면 같은 이름 지난 공고는 뺌, 비교 대상 이름 뒤 요청 문장 자르기, 비교 답에 '비교할 단지'·'데이터가 없어 답하지 않는 것', 비교 답에는 일반 검색의 참고·다음 버튼을 붙이지 않음
- 파일: chat/v2/extract.mjs, chat/v2/search.mjs, chat/v2/answer.mjs
- 확인: node --test chat/v2/test/v2.test.mjs 55/55, 예시 1(은빛·도봉 한신·방학 청구)은 세 곳 모두 '찾지 못함 + 이유', pytest 통과
- 백업: backup/20261002-2224-chatv2b
- 기능: 없음(개발 중)

## 2026-10-02 22:04 · 청약봇 V2 엔진 1차 (chat/v2, 화면·서버 미연결)
- 요청: 2번(청약봇) — "지금 청약패스에 영향 안 주게 우선 개발, 추후 심을 수 있게. 청약패스 결과를 활용하면서 질문 → 조건 추출 → 필수/선호/탐색 → 실제 데이터 검색 → 후보 → 걸러내기 → 추천/비교 → LLM 설명". 품질 예시 2개(아파트 매매 상담 답) 첨부
- 변경: chat/v2/ 새 폴더 — extract(규칙 조건 해석·후속 질문 applyDelta: 지역·동·생활권·제외, 예산 범위·평수·국평, 세대수·나홀로, 방·욕실, 역·초등학교, 출퇴근(남편·아내 직장), 특공 유형, 무순위·신희타·공공·민영, 내 자격, 이번만의 가정, 형식 밖 조건), search(값마다 확인/추정/확인 불가, 필수 불통과는 이유별 개수, 데이터 없는 필수는 확인 필요 후보, 판정은 화면 eligBucket·spJudge 그대로, 저장된 내 조건 없으면 판정 안 함, 관점별 1등, 완화안·인접 지역(좌표 거리)·예산 조금 넘는 대안, 비교 대상 찾기), answer(질문 받기→이해한 조건→결론부터→후보별 핵심 지표·이유→이런 분께는 이곳→확인하지 못한 것→좁혀 줄 질문), llm(AI 프롬프트 2개·AI 조건 해석 검사·설명 검사기), engine.cjs/node-data/node(Node), browser.mjs(심을 때 화면 입구), cli, STYLE.md(예시 답에서 뽑은 원칙만, 원문은 저장소에 안 넣음), golden 시험지 43문항+후속 3, test(oracle.mjs 따로 옮긴 계산으로 검색 검산, 고정 데이터 test/fixture-listings.json), .github/workflows/chat-v2.yml(시험만, 배포 없음)
- 파일: chat/v2/**, .github/workflows/chat-v2.yml, HANDOFF.md
- 확인: node --test chat/v2/test/v2.test.mjs 55/55 (조건 해석 43·후속 3·검색 검산 100+주택형·판정=화면 엔진·결과 없음·비교·확인 불가·검사기·AI 거절 시 기본 답). docs/·chat/worker 변경 없음 → 화면·수집·청약봇 서버 영향 없음. pytest 통과
- 백업: backup/20261002-2204-chatv2
- 기능: 없음(개발 중 — 심을 때 chatbot_v2 스위치)

## 2026-10-02 21:34 · 수집이 PDFium 때문에 죽던 것 — 두 번째 읽기 도구를 따로 띄운 프로세스로
- 요청: (자체 확인) v1.46.0 을 올린 뒤 수집(6a60cf6)이 '공고 수집' 단계 3분 만에 실패
- 변경: 실행 주석(check-run annotations)에서 exit code 139(세그폴트) 확인. PARSER_VERSION 20 으로 공고문 전부를 다시 읽으면서 pypdfium2 를 수십 번 부르다 C 라이브러리가 프로세스째 죽음 — 잠금은 걸려 있었지만 페이지·텍스트 객체를 닫지 않아 다른 스레드에서 정리되며 죽는 것으로 봄(v19 이후 수집은 보관 기록을 써서 pdfium 을 거의 안 불러 드러나지 않았음). pdf_text_alt 를 따로 띄운 파이썬 프로세스에서 읽게 바꾸고(페이지·텍스트 객체도 닫음, 90초 제한) 실패하면 None → 수집은 첫 도구 값으로 계속
- 파일: app/notice_pdf.py, tests/test_notice_and_notify.py
- 확인: 법령 별표 PDF 로 따로 띄운 프로세스 읽기 2,858자·여러 스레드 같은 결과, 깨진 PDF·빈 데이터는 None. pytest 통과. 올린 뒤 수집 성공·listings.json notice_quotes 확인 예정
- 백업: backup/20261002-2134-pdfium
- 기능: 없음(수정)

## 2026-10-02 21:13 · 지난 공고·청약봇 판정 교차 검사 + 청약봇 판정 요약을 화면과 맞춤
- 요청: 미뤄둔 일 10번 — 교차 검사 밖인 청약봇 답변·지난 공고 화면
- 변경: tools/qa/past_chat.cjs 추가 (대표 조건 3개). A 지난 공고: 판정 줄 글자 ↔ 엔진(eligBucket·spJudge), 마감 카드에 'D-·신청 가능해요·넣어도 돼요' 없음, 2026.6.15 전 공고는 판정 줄 없음, 판정 범위 밖이 '신청 가능했어요' 아님. B 청약봇: 보내는 verdict ↔ 상세 맨 위 판정, 마감·판정 범위 밖이면 요약에 그 사실, 브라우저 요약 ↔ 시험용 Node 요약. 찾은 것: ① 일반 물량 없는 주택형(2026000414 인천계양 A6 59G·84B)은 화면이 특별공급 기준(verdict_one)인데 청약봇 요약은 일반공급 기준 → '화면 신청 불가 · 청약봇 가능' (인천 1인 세대원). chatVerdict() 로 화면과 같은 결론·이유('특별공급 결과로 판정', '판정하지 않아요', '접수가 끝난 공고')를 보냄 ② chat/tools/engine_payload.cjs 가 요약을 따로 옮겨 적어 화면과 갈라질 수 있었음 → 화면 함수 chatEnginePayload 를 그대로 부르게 함. collect.yml·verify.yml 에 단계 추가, verify_status past_chat_fails
- 파일: tools/qa/past_chat.cjs, evidence/qa/past-chat.json, docs/index.html, chat/tools/engine_payload.cjs, tools/verify_status.py, .github/workflows/collect.yml, .github/workflows/verify.yml, docs/changelog.json, VERSIONS.md
- 확인: past_chat 지난 공고 카드 1,608 · 판정 줄 1,713 · 청약봇 요약 576 · 위반 0 (고치기 전 4건). 청약봇 시험 38/38, 골든셋 270/270(AI 없음). 판정 사례 365/365, 엔진 잠금 그대로, 스냅샷 차이 0, 스크립트 문법 OK, pytest 통과
- 백업: backup/20261002-2113-pastchat
- 기능: 없음(수정)
- 버전: v1.46.2

## 2026-10-02 21:08 · 주택형 칩 면적대 줄 나누기(type_bands) 되돌림
- 요청: "4번은 원복해야될거같아. 너무헷갈려 공고마다 표기도 다다르고"
- 변경: v1.45.0 커밋 2e74dca 의 화면 코드(typeChips 면적대 줄·.tbands CSS)를 git revert 로 되돌리고 config 스위치 type_bands 삭제. 기록(WORK·FEATURES·VERSIONS·changelog)은 남기고 FEATURES 줄에 되돌림 표시
- 파일: docs/index.html, docs/config.json, FEATURES.md, VERSIONS.md, docs/changelog.json
- 확인: 주택형 16개 공고 상세에 면적대 줄 0·칩 16개 한 줄, 390px 밝은·어두운 가로 넘침 없음·화면 오류 없음. 스크립트 문법 OK, 엔진 잠금 그대로, 스냅샷 차이 0, pytest 통과
- 백업: backup/20261002-2108-untband
- 기능: type_bands (삭제)
- 버전: v1.46.1

## 2026-10-02 21:04 · 공고문에서 읽은 값마다 근거 원문 문장 저장·표시
- 요청: 미뤄둔 일 9번 — 값마다 원문 문장 저장 (지금까지는 1쪽 표 문장만)
- 변경: parse_notice 가 세대주 요건·분양가상한제·거주의무·거주의무 기준일·재당첨 제한·1순위 가입기간·납입 횟수·잔금일을 읽을 때 찾은 위치를 공백 없는 글에서 원문 위치로 되돌려 앞뒤 문장을 quotes 에 남김(_flat_pos·_quote_at, 잘린 낱말은 버리고 … 표시). 두 번째 읽기 도구로 채운 값은 그 도구 문장, 지난 실행 값을 되살릴 때는 지난 문장도 되살림. 수집이 Listing.notice_quotes(화면 이름 기준)로 내보내고, 화면은 출처 링크 옆 '공고문 문장'(펼침)으로 보여 줌 — 자격 체크리스트(세대주·가입기간·납입 인정), 당첨되면 걸리는 제약(실거주·재당첨), 자금 플랜 '지역 규제와 전세' 카드, 잔금 단계. 판정은 그대로(표기만). PARSER_VERSION 20 (모든 공고문을 다시 읽어 문장을 채움)
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, docs/index.html, docs/config.json, tests/test_notice_quotes.py, tools/engine_lock.json(fromApi 필드 추가)
- 확인: 원문 60건 전부 — 읽은 값 280여 개마다 문장이 있고 그 문장에 실제로 그 값(숫자·'세대주' 등)이 들어 있음(test_every_read_value_has_a_quote_containing_it). 정답 2026910236 철산자이 '거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용됩니다' 문장 고정. pytest 179 통과, 판정 사례 365/365, 스냅샷 차이 0, 스크립트 문법 OK, 390px 밝은·어두운 화면 상세·자금 플랜 확인(가로 넘침 없음)
- 백업: backup/20261002-2104-nquote
- 기능: notice_quotes
- 버전: v1.46.0

## 2026-10-02 20:51 · E2E·스냅샷을 매 수집·화면 변경 검사에 넣음
- 요청: 미뤄둔 일 8번 — E2E·스냅샷을 CI에 넣기
- 변경: collect.yml·verify.yml 에 `tools/qa/snapshot.cjs`(화면 글자 스냅샷, 고정 공고·고정 날짜)와 `tools/qa/e2e.cjs`(사용자 흐름 32개 + 저장 조건 퍼징) 단계 추가, 결과 evidence/qa/snapshot.json·e2e.json 커밋. verify_status 가 snapshot diffs·e2e fail 을 qa_ok 에 넣음(하나라도 있으면 Actions 실패·이슈). 시간 제한 collect 30→40분, verify 15→25분. verify.yml 실행 조건에 두 도구·tests/qa/** 추가
- 파일: .github/workflows/collect.yml, .github/workflows/verify.yml, tools/verify_status.py, evidence/qa/snapshot.json
- 확인: 로컬 스냅샷 차이 0, E2E 32개 PASS 32·FAIL 0, pytest 통과
- 백업: backup/20261002-2051-e2eci
- 기능: 없음(수정)

## 2026-10-02 20:49 · v1.45.0 주택형 칩 면적대 줄 나누기
- 요청: 미뤄 둔 일 4번 — 주택형 칩이 많은 공고(7개 이상) 면적대 묶음
- 변경: typeChips — 주택형 7개 이상이고 면적대가 둘 이상이면 '60㎡ 이하 · 60~85㎡ · 85㎡ 초과' 줄마다 칩(줄마다 옆으로 넘김, 줄 앞에 면적대·개수). 경계 60·85㎡는 청약 규칙이 갈리는 면적(공공 소득 기준·민영 가점제 비율). 목록 묶음 카드·상세 주택형 고르기 둘 다. 스위치 type_bands
  지금 공고 중 대상: 올 뉴 챔피언스시티 16·더샵 분당하이스트 13·인천계양 A6 11 등 7공고
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md
- 확인: 390px 라이트·다크(챔피언스시티 목록 카드·상세 — 60~85㎡ 6 · 85㎡ 초과 10 두 줄, 화면 오류 0), 스냅샷·필터·공급유형 검사, regress
- 기능: type_bands
- 버전: v1.45.0
- 백업: backup/20261002-2049-tband

## 2026-10-02 20:47 · v1.44.0 새 공고 알림 — 10월 9일 시행일에 저절로 공개
- 요청: 미뤄 둔 일 1번 — 10-09 방침·약관 시행일에 새 공고 알림 공개 (청약봇은 chat_off 로 운영자가 끈 상태라 이번엔 알림만, 청약봇은 운영자 확인 뒤)
- 변경: 화면 pushDateOk() — push_legal_date 가 있으면 그날 0시(한국) 전에는 web_push 스위치가 켜져 있어도 공개하지 않음(미리보기 기기는 그대로). config web_push true, push_legal_date "2026-10-09", push_preview 는 시행일 뒤 정리.
  보내기(수집 pipeline)는 원래 web_push 또는 push_preview 로 보냄 — 시행일 전 구독자는 미리보기 기기뿐
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md
- 확인: 시계 고정 브라우저 390px 라이트·다크 — 10-08 12:00 pushOn false·알림 탭 없음, 10-09 00:30 pushOn true·알림 탭 보임, 화면 오류 0. 판정 사례 365/365, engine_lock 그대로, pytest
- 기능: web_push
- 버전: v1.44.0
- 백업: backup/20261002-2047-pushdate

## 2026-10-02 20:45 · 주간 블라인드 표본 예약 작업
- 요청: 주간 블라인드 표본을 매주 자동으로 (사용자 '그렇게 진행해')
- 변경: 예약 작업 '청약패스 주간 블라인드 표본' — 매주 월 09:59(한국), 새 세션이 저장소를 받아 blind_sample pick → 블라인드 서브 에이전트 → compare → 일치 값 golden 추가·커밋 → 운영자에게 보고(앱 오류는 고치지 않고 보고만). HANDOFF 갱신
- 파일: HANDOFF.md
- 기능: 없음(수정)
- 백업: backup/20261002-2007-pdf2

## 2026-10-02 20:40 · 공고문 읽기 점검 마무리 기록
- 요청: 올린 뒤 확인 · HANDOFF (CLAUDE.md 8항)
- 확인: 수집(690563f) 성공 — [공고문·보완] 과천 벨라르테·라비엔오 재당첨 10년(두 번째 도구), 정답 불일치 0, verify-status ok. pdf_audit 다시: 쪽수 잘림 3→0, LH 공고 읽힘, 문제 4(받기 일시 실패 3 — 수집은 원문 사본 대체 · 벨라르테 마지막 쪽 그림 1)
- 변경: HANDOFF '진행 중인 일', 스킬 함정 2개
- 파일: HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 기능: 없음(수정)
- 백업: backup/20261002-2007-pdf2

## 2026-10-02 20:16 · 두 번째 읽기 도구 스레드 잠금 (v1.43.1 수집 실패 고침)
- 요청: 올린 뒤 확인 — v1.43.1 수집 '공고 수집 · 시세 · 등급' 단계 실패 (사이트는 이전 데이터 그대로)
- 원인: 수집이 공고문을 6개 스레드로 받는데 pypdfium2(PDFium)는 여러 스레드에서 동시에 쓰면 깨짐 — 로컬 재현: 8스레드 400번 'Failed to load document (Data format error)' (Actions 에서는 프로세스가 죽은 것으로 보임, 로그는 인증 없이 못 봄)
- 변경: notice_pdf._PDFIUM_LOCK — pdf_text_alt 를 한 번에 하나씩, 문서 닫기. 테스트(8스레드 60번 같은 결과)
- 파일: app/notice_pdf.py, tests/test_notice_and_notify.py
- 확인: 로컬 잠금 뒤 8스레드 40·60번 모두 같은 결과, pytest. 다음 수집 성공·930036/937 재당첨 10년 채워짐 확인 예정
- 기능: 없음(수정)
- 백업: backup/20261002-2007-pdf2

## 2026-10-02 20:07 · v1.43.1 공고문 읽기 보강 — 두 도구 읽기·쪽수 상한·두 곳 값 대조·주간 블라인드 표본
- 요청: 공고문에서 짧게 가져오는 등 잘못 가져오는 경우 점검 (제안 1~4단계 진행)
- 점검 결과(pdf_audit, Actions 실제 PDF 50공고): ① 쪽수 상한 80쪽 — 고덕 A12BL·A65BL 93쪽(뒤 13쪽 2만여 자)·두정역 83쪽 잘림 ② pypdf 가 글자 순서를 뒤섞어 값을 놓침 — 과천 벨라르테·라비엔오 '재당첨제한 10년'을 pypdfium2 는 읽음
  ③ 도구 오탐: LH 공고 6건 'PDF 없음'(수집은 LH청약플러스에서 받음), 확장비 차이(여러 주택형 공고는 원래 안 씀) → 점검 도구 고침. 첨부 고르기 문제·필수 단원 누락 0
- 변경: notice_pdf PAGE_CAP 300, pdf_text_alt(pypdfium2) + merge_alt — 한쪽만 읽힌 값은 채우고 둘 다 다르면 conflicts(데이터 확인 필요), run-log [공고문·보완]. 스위치 pdf_dual_read. requirements pypdfium2.
  공고문 두 곳 대조: 1쪽 '단지 주요정보' 표 ↔ 본문(거주의무·분양가상한제·재당첨) 다르면 conflicts → Listing.notice_conflicts → validate '공고문 안에서 값이 서로 달라요'(원문 101건 지금 0건). PARSER_VERSION 19.
  tools/qa/pdf_audit.py 보강(LH 경로, 확장비 오탐 제외, 수집과 같은 두 도구 합친 값으로 비교). tools/qa/blind_sample.py(pick·compare) + 2026-W40 표본 5개(민영·공공·신혼희망타운·무순위·재공급) — 앱 값을 보지 않은 검토자 답 38개: 읽기 오류 0, 표기 차이 3(도구 정규화), 정의 차이 1(신혼희망타운 본청약 78을 특공으로 보는지 — 청약홈 SPSPLY 값, 오류 아님)
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, requirements.txt, docs/config.json, tests/test_notice_and_notify.py, tests/test_residence.py, tests/golden/notices.json(블라인드 일치 값 13개, 930036·930037 재당첨 10년), tools/qa/pdf_audit.py, tools/qa/blind_sample.py, evidence/qa/blind/{2026-W40.json,report.json}, docs/changelog.json, VERSIONS.md
- 확인: pytest 168, 정답 데이터 ↔ 지금 수집 값 불일치 0(930036·937 재당첨은 이 커밋 수집에서 두 도구 읽기로 채워져야 함 — 확인 예정)
- 기능: pdf_dual_read
- 버전: v1.43.1
- 백업: backup/20261002-2007-pdf2

## 2026-10-02 19:57 · 공고문 PDF 읽기 점검 도구 (pdf_audit)
- 요청: 공고문에서 짧게 가져오는 등 잘못 가져오는 경우가 있는 것 같다 — 제대로 파싱하는지 점검 (제안한 점검 1·2단계)
- 변경: tools/qa/pdf_audit.py — 지금 공고마다 공고 화면의 PDF 첨부를 모두 받아 (1) 수집이 고르는 첨부(앞에서 첫 500자 넘는 PDF)보다 긴 모집공고문이 있는지
  (2) 쪽수·상한(80쪽)으로 잘린 글자·글자 없는 쪽 (3) 필수 단원 6개 (4) 두 번째 도구(pypdfium2)로 읽은 parse_notice 값과 차이 (5) 전체 쪽을 읽으면 값이 달라지는지 (6) 지금 수집 값과 차이.
  작업 환경은 청약홈 접속이 막혀 probe.yml(Actions)에서 실행 → evidence/qa/pdf-audit.json. 서비스 데이터는 안 바꿈. 법령 PDF 2개로 가짜 공고 화면을 만들어 동작 확인
- 파일: tools/qa/pdf_audit.py, .github/workflows/probe.yml
- 확인: 로컬 모의 실행(첨부 2개·상한 2쪽 → '3쪽 중 2쪽까지만 읽음' 등 검출), pytest. 실제 결과는 이 커밋으로 도는 '근거 자료 모으기'에서
- 기능: 없음(수정)
- 백업: backup/20261002-1957-pdfaudit

## 2026-10-02 19:30 · 단조성 검사(monotonic.cjs) + 교차 규칙 SCOPE·RENT
- 요청: 사용자 QA 피드백 — '임대 → 분양' · '확인 필요 → 가능' · '지원하지 않는 유형 → 가능'이 다시 생기면 자동으로 잡는 검사
- 변경: tools/qa/monotonic.cjs — 실제 공고 93개(공고마다 면적 양끝) × 판정 사례 조건 6개. A 정보 단조성: 내 조건 칸(46개)·공고 조건(13개) 하나를 모르게 하면 '가능'이 새로 생기면 위반(21,096회).
  B 값 단조성: 소득·부동산·자동차·금융자산↑ 나빠지기만, 통장 가입기간·납입 횟수·예치금·저축액·거주기간(공고일 전)↑ 좋아지기만, 혼인기간·막내 나이↑ 신혼·신생아 나빠지기만(128,619점).
  첫 실행 310건 → 원인 가림: 302건은 검사 가정 오류(공고일 뒤 전입은 '그때 주소 모름'이 맞음 → 공고일 전 날짜만), 18건은 모순 입력 해소(노부모 '3년 같은 등본 부양 예' + '같은 등본 부모 0명' — 질문 자체가 등본 요건을 물어 예외로 문서화). 판정 오류 0.
  일부러 넣은 오류: '확인 필요 1개면 가능' 148건 · 소득 경계 구간 뒤집기 82건 · 통장 기간 계산 오류 69건 모두 잡음.
  cross_rule.cjs SCOPE-001(판정 범위 밖 → 확인 필요만)·RENT-001(임대 → 공공임대 배지·시세 차익 없음·full 판정 금지, judge_scope 켰을 때). CROSS_RULES.md 에 SCOPE·RENT·MONO 규칙.
  collect·verify Actions, verify-status qa.monotonic_violations. HANDOFF·스킬 갱신
- 파일: tools/qa/monotonic.cjs, evidence/qa/{monotonic.json,cross-rule.json,CROSS_RULES.md,profile-keep.json}, tools/qa/cross_rule.cjs, .github/workflows/{collect,verify}.yml, tools/verify_status.py, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 단조성 위반 0, 교차 규칙 69,957회 충돌 0(judge_scope 끄면 RENT-001 3건), 저장 유지 0
- 기능: 없음(수정)
- 백업: backup/20261002-1903-scope

## 2026-10-02 19:03 · v1.43.0 판정 범위(judge_scope) — 판정하지 않는 공고를 분양 규칙으로 확정하지 않기
- 요청: 사용자 QA 피드백 — 임대/분양 오분류 방지, 지원하지 않는 유형·확인 필요 → 가능 과신 금지, 경계값, 2025000645·2026000307 재확인, 기존 기능 보호, 스위치
- 분석: evidence/qa/SUPPLY_SCOPE.md. 두 공고 모두 수집에서 rental=true(RENT_SECD_NM '분양전환 가능임대')로 이미 맞게 분류. 2026000307 은 공고문 표로 판정(partial). 2025000645 형(자격표 못 읽음)은 '가능' 0 이었지만 우연(소득·총자산 확인 필요 항목 하나)에 기댐 + 분양 규칙 '불가' 31/296 을 확정으로 씀.
  무순위 임대 이름 목록에 행복주택·국민임대 등 없음. 2026 데이터 임대 2공고 16주택형(0.7%).
- 변경: judgeScope(L) full/partial/none(이유) — none 이면 eligibility 가 분양 규칙의 불가를 '(분양 기준으로 보면)' 확인 필요로, 맨 위 '판정 범위' 항목, spJudge 도 확인 필요. 카드 '판정하지 않는 공고 · 모집공고문 신청자격 확인', 상세 맨 위 이유, 체크리스트 '분양 기준으로 보면 맞는 조건(참고)'. 스위치 judge_scope.
  수집 RENTAL_NAME 에 행복주택·국민임대·영구임대·통합공공임대·장기전세·민간임대·매입임대·전세임대·임대아파트('분양전환'은 제외 — 우선분양전환 후 잔여세대는 분양, 이름 2,284개 확인).
  회귀: 고정 공고 2025000645·2026000307-NOLIM, 판정 사례 scope-00~15 (조건 좋음·유주택·통장 없음·다른 지역 → 확인 필요, 특공 확인 필요)
- 파일: docs/index.html, docs/config.json, app/pipeline.py, tests/test_rental.py, tests/judge/{cases,listings}.json, tools/make_judge_cases.py, tools/engine_lock.json, tests/qa/snapshots.json, evidence/qa/snapshot.json, evidence/qa/SUPPLY_SCOPE.md, docs/changelog.json, VERSIONS.md
- 확인: 판정 사례 365/365(스위치 끄면 5건 불일치), 고치기 전·후 2025000645형 296조건 '불가' 31 → 0·'확인 필요' 296, 2026000307 그대로(가능 98·특공 가능 325), pytest 165, 판정 일치 7,680 다름 0, 특공 문구 0, 공급유형 0, 필터 0, 저장 유지 0, regress 0(지금 공고 판정 변화 없음),
  E2E 32/32, 스냅샷(새 고정 공고 2개만), 390px 라이트·다크(2025000645 카드 '판정하지 않는 공고', 상세 맨 위 이유)
- 기능: judge_scope
- 버전: v1.43.0
- 백업: backup/20261002-1903-scope

## 2026-10-02 18:53 · v1.42.6 실거주 의무 읽기 보강 (사용자 제보 철산자이 더 헤리티지 · 원인 질문)
- 요청: 철산자이 더 헤리티지 59 자금 플랜 '실거주 의무 확인 필요' — 공고문 PDF 를 열면 다 보일 텐데 왜 실패하는지, PDF 가 안 열리면 다른 방법은
- 원인 조사(지금 '모름' 11주택형 전부): PDF 는 모두 열려 읽었음(받기 문제 아님). (1) 철산자이 2026910236 — 원문 '본 아파트의 거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용됩니다'인데 규칙이 '거주의무기간 2년' 꼴만 읽음(날짜가 끼면 실패), 1쪽 표에는 택지유형 칸이 없어 표 규칙도 안 맞음.
  (2) LH 의정부우정 409·양주회천 416·시흥하중 820011 — 원문에 '거주의무' 낱말이 없음(제한사항 표 '구분 기준일 기간 관련 법령'에 재당첨·전매제한 두 줄만, 같은 양식의 414 는 '거주의무 - 없음' 줄이 있음) → 공고문만으로는 확정 불가, 없음으로 추측하지 않음.
  청약홈 API 에는 거주의무 필드가 없음(run-log [응답 필드]: PARCPRC_ULS_AT 상한제 여부만). 받기 실패 대비는 이미 LH청약플러스 대체 → 보관 기록 → 원문 사본(evidence/notices, 18:34 추가) 순.
- 변경: notice_pdf — '거주의무기간은 …(전매·재당첨 없는 40자 안)… N년간 적용' 규칙, 최초 입주가능일(duty_from), 거주의무 언급이 아예 없으면 duty_silent(값은 모름 그대로). PARSER_VERSION 17. 원문 101건 중 바뀐 것: 910236 거주의무 None→2, duty_silent 5건, 확정값 변화 0.
  화면: 입주 기한(최초 입주가능일 + 3년)이 잔금 + 2년보다 이르면 '전세 2년 다 못 줌 · 약 N개월', 지났으면 전세 불가. 모름 이유를 '공고문에 적혀 있지 않음(공급자에 확인)' / '확인하지 못함'으로 나눔. 교차 규칙 LEASE-006 추가
- 파일: app/notice_pdf.py, app/models.py, app/pipeline.py, app/engine.py, docs/index.html, tests/golden/notices.json(2026910236 새로 — 거주의무 2·최초 입주가능일, 409·416 duty_silent), tests/test_residence.py, tools/qa/cross_rule.cjs, evidence/qa/CROSS_RULES.md, tools/engine_lock.json(fromApi·jeonseCheck), tests/qa/snapshots.json, evidence/qa/snapshot.json, docs/changelog.json, VERSIONS.md, 스킬
- 확인: pytest 165, 판정 사례 349/349, 교차 규칙 0, 판정 일치 0, 저장 유지 0, 스냅샷 — v1.42.5 납입 회차 고침으로 '서울 신혼 세대주'(납입 120회) 국민주택 8곳이 '납입 인정 횟수 확인 필요' → 판정됨(의도, 기준 갱신; v1.41.1 기준에 이미 버그 증상이 찍혀 있었음 — 스킬에 함정 기록), 이번 변경 뒤 0곳.
  390px 라이트·다크(철산자이 '실거주 의무 2년 · 2028.05.30까지 · 약 19개월만', 의정부우정 '공고문에 적혀 있지 않아요 · 공급자 확인')
- 기능: 없음(수정)
- 버전: v1.42.6
- 백업: backup/20261002-1853-duty2

## 2026-10-02 18:45 · v1.42.5 납입 인정 회차가 새로고침 때 지워지던 것 (사용자 제보)
- 요청: 내 조건 '납입 인정 회차'가 저장되지 않음 — 새로고침하면 리셋 (가입일 2012.05.05, 예치금·인정 금액 1,570만원)
- 원인: v1.41.1 profile_clean 의 cleanProfile 이 개수 칸(P_COUNT)을 모두 0~30 정수로만 정상으로 봄 → 납입 인정 회차 31회 이상(2012년 가입이면 약 170회)은 불러올 때 기본값(null)으로 바뀜. 내 실수.
  놓친 이유: 퍼징(e2e.cjs)은 '나쁜 값이 지워지는지'만 보고 '정상 값이 남는지'는 안 봄, 판정 사례 조건은 납입 30회 이하뿐
- 변경: 칸별 최댓값 P_MAX(acctCount 1200), 나머지 개수 칸은 그대로 30. 새 검사 tools/qa/profile_keep.cjs — 판정 사례 조건 292개 + 현실적인 큰 값(납입 0·1·30·31·170·240·600·1200회, 자산 수십억, 1950년생 등) 저장·새로고침 뒤 칸마다 같은지 + 질문 칸(fieldHtml)에 170 입력 → 새로고침 → 170.
  collect·verify Actions, verify-status qa.profile_keep_fails. 스킬 함정 추가
- 파일: docs/index.html, tools/qa/profile_keep.cjs, evidence/qa/profile-keep.json, .github/workflows/{collect,verify}.yml, tools/verify_status.py, docs/changelog.json, VERSIONS.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: profile_keep 고치기 전 화면 6칸 지워짐(31·170·240·600·1200회, 입력 화면 170) → 고친 뒤 0, 판정 사례 349/349, engine_lock 그대로, 판정 일치 7,680 다름 0, pytest
- 기능: 없음(수정)
- 버전: v1.42.5
- 백업: backup/20261002-1845-acct

## 2026-10-02 18:34 · 공고문 받기 실패 때 저장해 둔 원문 사본으로 읽기 (정답 불일치 해결)
- 요청: 올린 뒤 확인 (CLAUDE.md 4항 3) — v1.42.3 수집에서 [검증·정답 불일치] 힐스테이트 고덕엘리스트 A65BL 84A·84B residence_duty 수집값 None ≠ 공고문 3
- 원인: 이번 수집에서 2026000438 공고문 PDF 받기 실패(청약홈 'The requested URL was not found') → 예전 읽기 규칙(PARSER_VERSION 15)으로 보관한 값을 그대로 씀 → 거주의무 모름이 남음. 정답 데이터가 잡아 verify-status ok=false
- 변경: app/pipeline.apply_notice — 받기 실패·시간 초과면 evidence/notices 또는 evidence/qa/notices 의 원문 사본(같은 공고문을 앞서 받아 옮긴 글)이 있을 때 그것을 새 규칙으로 읽음, run-log 에 '저장해 둔 원문 사본(…)으로 읽음'
- 파일: app/pipeline.py, tests/test_notice_and_notify.py(사본으로 읽는 테스트 추가, 기존 '지난 실행 값 유지' 테스트는 사본 없는 공고 번호로)
- 확인: pytest 164. 실제 결과는 이 커밋으로 도는 수집에서 [검증·정답 불일치] 0 인지 확인
- 기능: 없음(수정)
- 백업: backup/20261002-1834-arch

## 2026-10-02 18:15 · v1.42.4 교차 규칙(Cross-Rule) 모순 검사
- 요청: 사용자 추가 MASTER QA 'CROSS-RULE CONSISTENCY' — 값마다가 아니라 값·규칙·계산·화면 문구가 함께 모순되지 않는지 검사 체계
- 변경: tools/qa/cross_rule.cjs — 지금 공고 + 판정 사례 고정 공고 201주택형 × 판정 사례 조건 40 + 유주택 2, 규칙 20개(LEASE·DUTY·FUND·ELIG·UI·STATUS), 위반마다 rule_id·심각도·조건·실제·기대·충돌 필드·근거.
  공고 상태 NORMAL/WARNING/CONFLICT/UNKNOWN. evidence/qa/CROSS_RULES.md — 기존 QA 가 못 잡은 이유(A~G)·구조 원인 4가지·두 계층·규칙 표·전세 의존 요소(근거)·의존 그래프·모순 행렬·회귀 ID REG-CROSS-001~010·출시 차단·새 기능 완료 조건·못 하는 것.
  collect·verify Actions 에 넣고 verify-status qa.cross_rule_fails(CRITICAL·HIGH)로 차단. ship.sh 가 pytest 뒤 docs/chat-notice 를 되돌림(pull 멈춤). HANDOFF·스킬 갱신
- 파일: tools/qa/cross_rule.cjs, evidence/qa/{CROSS_RULES.md,cross-rule.json}, .github/workflows/{collect,verify}.yml, tools/verify_status.py, tools/qa/ship.sh, docs/changelog.json, VERSIONS.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: v1.42.2 화면으로 돌리면 1,048건(LEASE-001 76 · STATUS-001 972) 잡음, v1.42.3 화면 0건(검사 60,888회, UNKNOWN 38 = 거주의무 아직 모름 — 수집이 새 규칙으로 다시 읽으면 줄어듦), verify_status 통과
- 기능: 없음(수정)
- 버전: v1.42.4
- 백업: backup/20261002-1759-duty

## 2026-10-02 17:59 · v1.42.3 실거주 의무 '모름'을 '없음'으로 보이던 것·마감 공고 상세 (사용자 제보)
- 요청: 과천 푸르지오 벨라르테 99B 자금 플랜 — 칩 '분양가상한제'·'실거주 의무 없음' + 주의 '실거주 의무가 있을 수 있어요' + '전세 조건부'. 서로 모순 (사용자 추가 MASTER QA 'Cross-Rule Consistency' 첨부)
- 원문: 2026930037 1쪽 단지 주요정보 표 '전매제한 거주의무기간 분양가상한제 택지유형 / … 현재 전매제한 도과 · 없음 · 적용 · 공공택지' → 거주의무기간 없음(최초 공고 2020.07).
- 원인: (1) 데이터 — 수집이 이 표를 못 읽어 residence_duty = null(모름). 지금 공고 32주택형이 같은 상태. (2) 화면 — 칩이 null 을 거짓으로 보고 '실거주 의무 없음', 주의 문구는 null 이라 '있을 수 있어요', 전세는 '조건부' → 모르는 값 하나가 세 곳에서 서로 다른 사실로 바뀜.
  (3) 같은 구조의 다른 문제: 마감 공고 상세 맨 위가 '신청 가능'만 보임(교차 규칙 검사에서 162주택형), 카드 '자금 가능'이 전세·대출 전제를 말하지 않음
- 변경: notice_pdf._summary_table(단지 주요정보 표의 거주의무기간·분양가상한제) + LH 표 '거주의무 거주의무 개시일 3년 「주택법」제57조의2'·'거주의무 - 없음' 문장. PARSER_VERSION 16. 원문 101건 중 바뀐 것은 모름 → 값 15건뿐(확정값이 바뀐 것 0).
  화면 jeonseCheck: 상태에 check(확인 필요) 추가 — 거주의무 모름이면 '전세 확인 필요', 칩 '실거주 의무 확인 필요', 전세 시나리오 '확인 필요', 자금 계획 기본값 잔금대출. 상한제인데 거주의무 없음이면 왜인지 안내. app/engine.py 도 같게.
  상세 맨 위: 마감 공고는 '접수 마감' + '내 조건으로 보면 … — 참고용'(판정 색은 카드와 같게). 카드: '자금 가능(잔금대출 포함|전세 활용|전세 조건부)'
- 파일: app/notice_pdf.py, app/pipeline.py, app/engine.py, docs/index.html, tests/golden/notices.json(2026930037 새로 · 930036·437·438·414·820008·820010 거주의무 — 원문 확인), tests/test_residence.py, tests/test_engine.py, tests/qa/snapshots.json, evidence/qa/snapshot.json, docs/changelog.json, VERSIONS.md
- 확인: pytest 163, 판정 사례 349/349, engine_lock 그대로, 판정 일치 7,680 다름 0, 특공 문구 0, 공급유형 0, 필터 0, regress 0, 스냅샷 31곳(마감 상세 '접수 마감'·거주의무 모름 공고 자금 '(대출)' — 의도, 기준 갱신),
  새 교차 규칙 검사(다음 커밋)로 고치기 전 1,048건(LEASE-001 76 · STATUS-001 972) → 0건, 390px 라이트·다크(벨라르테 — 거주의무 없음: '실거주 의무 없음' + 상한제인데 없음인 이유, 모름: '전세 확인 필요', 3년: '실거주 의무 3년')
- 기능: 없음(수정)
- 버전: v1.42.3
- 백업: backup/20261002-1759-duty

## 2026-10-02 17:55 · 시세 원자료 대조 첫 결과 기록
- 요청: 올린 뒤 확인 (CLAUDE.md 3항)
- 확인: 수집 실행(de1c959) run-log '[QA 시세 원자료] 공고 8개 · 근거 거래 46건을 국토부 원자료와 대조 · 다름 0건', verify-status ok true(판정 349/349, 특공 문구 0, 판정 일치 0, 공고문 대조 불일치 0)
- 변경: HANDOFF 남은 일 갱신
- 파일: HANDOFF.md
- 기능: 없음(수정)
- 백업: backup/20261002-1730-mkcheck

## 2026-10-02 17:40 · HANDOFF·작업 스킬 정리 (MASTER QA 마무리)
- 요청: 작업 마무리 기록 (CLAUDE.md 8항)
- 변경: HANDOFF '진행 중인 일' 맨 위에 MASTER QA 끝난 것·검사 도구·남은 일(시세 원자료 첫 결과, 청년 특별공급 미지원, E2E·스냅샷 CI 여부, 새 공공임대 공고 확인). 스킬에 함정 5가지(특공 문구 여러 곳, ship 파이프 뒤 release, 매일 바뀌는 근거 파일, 공공임대 금액표, 원자료는 Actions 에서만)
- 파일: HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 기록만 바뀜 (pytest)
- 기능: 없음(수정)
- 백업: backup/20261002-1730-mkcheck

## 2026-10-02 17:30 · 시세 원자료 대조 검사 (MASTER QA 남은 일)
- 요청: MASTER QA 남은 일 '시세 원자료 대조' — 화면 시세·근거 거래가 국토부 실거래가 원자료와 같은지
- 변경: tools/qa/market_check.py — 수집 코드(app/market.py·rtms.py)를 쓰지 않고 국토부 매매·분양권 전매 XML 을 따로 받아 따로 계산(해제·직거래 제외, 같은 단지 ±3㎡ → 없으면 같은 구 준공 10년 이내 3건 이상, 중앙값·하위 25%)해
  mkt_basis·mkt_base·mkt_low·mkt_count 와 근거 거래 한 건씩(단지·날짜·면적·층·금액)이 원자료에 있는지 비교. 수집 뒤 공고 8개씩 날마다 돌아가며(요청 수 제한), 인증키 없으면 건너뜀(로컬은 원자료 접근 불가).
  결과 evidence/qa/market-check.json · run-log '[QA 시세 원자료]' · verify-status qa.market_fails(다르면 실패). 첫 실행 전 자리 파일을 둠(git add 가 없는 파일에서 멈추지 않게)
- 파일: tools/qa/market_check.py, tests/test_market_check.py, evidence/qa/market-check.json, .github/workflows/collect.yml, tools/verify_status.py
- 확인: tests/test_market_check.py — 원자료 XML 모양 거래 8건(같은 단지·다른 신축·옛 단지·해제·직거래)으로 따로 만든 계산이 app/market.estimate_market 과 4가지 경우 모두 같음, 시세 0.1억 바꾸면·해제 거래를 근거로 넣으면 잡음. pytest. 실제 원자료 대조는 이 커밋으로 도는 수집 실행에서 확인
- 기능: 없음(수정)
- 백업: backup/20261002-1730-mkcheck

## 2026-10-02 17:26 · v1.42.2 특별공급 뽑는 방식·단계 세대수 표시 고침 (자체 점검에서 발견)
- 요청: (자체 피드백) 공공임대 특공 화면 확인 중, 같은 판정 결과를 화면마다 다르게 말하는 곳 발견 — 사용자 지적(과천 84D)과 같은 종류라 전수 검사 도구를 만들고 고침
- 원인: (1) 공공 신혼부부 2단계(일반공급)는 2026000409 「선정순위에 따라 공급 … 동일 순위 내 경쟁이 있는 경우 추첨」인데 spPosition·spMinePlain 은 '순위·추첨', 한 줄 요약(spHeadPlain·spHeadline)·설명(spHowPlain)은 '점수 순'.
  (2) '약 N세대'를 이름표 SP_SHARE('우선공급' 70%)로 단계마다 반올림 — 공공 노부모부양 우선공급은 90%(2026000409 '우선공급(90%)'), 공공은 '소수점 이하는 올림'·앞 단계부터 배정(wsPlan 은 이미 그렇게 계산)이라 물량 3세대 70%를 2세대로 보임
- 변경: spStageUnits(wsPlan 과 같은 배분)·spShare, 한 줄 요약·설명의 공공 신혼 2단계 문구 '순위 → 추첨'. 판정(spJudge)은 그대로(engine_lock 변화 없음).
  검사 도구 tools/qa/sp_text.cjs — 판정 사례 조건 × 유형 물량 1~12세대, 판정 '가능' 칸 768개의 방식 문구·세대수를 공고문 비율 표(도구 안에 따로 적음)와 비교. 고치기 전 코드로 돌리면 1,158건 걸림, 고친 뒤 0건. collect·verify Actions 와 verify-status(qa.sp_text_fails) 에 넣음
- 함께 고침: tests/test_lh_public.py 가 Actions 가 매일 바꾸는 evidence/pages/lh-list-1027.html 을 읽어, 오늘 목록에서 계양 A6 정정공고가 밀려나 실패 → 통과하던 마지막 목록(5f40691)을 tests/qa/pages/lh-list-1027-20261002.html 로 고정
- 파일: docs/index.html, tests/test_lh_public.py, tests/qa/pages/lh-list-1027-20261002.html, tools/qa/sp_text.cjs, evidence/qa/sp-text.json, tools/verify_status.py, .github/workflows/{collect,verify}.yml, docs/changelog.json, VERSIONS.md
- 확인: 특공 문구 768칸 다름 0, 판정 사례 349/349, 판정 일치 7,680 다름 0, 공급유형 0, 스냅샷 바뀐 곳 0, regress 0, pytest, 390px 라이트·다크(2026000414 59A 인천 신혼 3인 월 833만원 → '소득 2구간(일반공급)에서 순위 → 추첨 (자녀가 있어 1순위)')
- 기능: 없음(수정)
- 버전: v1.42.2 (v1.42.1 은 건너뜀: 첫 올리기에서 pytest 가 tests/test_lh_public.py 로 실패했는데 release.sh 가 이어 실행돼 release/v1.42.1 이 이전 상태 904cef9 로 만들어짐. 원격 브랜치 삭제가 막혀 있어 번호를 건너뜀)
- 백업: backup/20261002-1726-sptext

## 2026-10-02 17:20 · v1.42.0 공공임대 특별공급 판정
- 요청: MASTER QA 남은 일 — 공공임대 특별공급 규칙 (사용자 결정 '임대 규칙 따로 만들기'의 남은 부분)
- 원문: 2026000307 군포대야미 A-1 6년 분양전환공공임대 <표4> (표4-2) 2인·(표4-3) 3~8인 유형별 소득표 — 신혼부부·생애최초 우선 70% 100%(맞벌이 120%)·일반 20% 130%(140%)·추첨 10% 130%(200%), 신생아 일반·추첨 140%, 노부모·다자녀 우선 90% 120%(130%)·추첨 10% 120%(200%), 2인은 퍼센트가 다름(신혼 110/130·140/150·140/200).
  '3. 총자산보유기준 적용대상: 청년·다자녀·신혼부부·생애최초·노부모부양·신생아 특별공급' <표2> 362,000천원, <표3> 출산 397,000·431,000천원. 신청자격·선정순위(1단계 순위·가점, 2단계 순위·추첨, 3단계 추첨)는 공공분양과 같음
- 변경: notice_pdf._rental_sp_table — 유형별 단계·비율·퍼센트·가구원수별 금액을 그대로 읽어 pub_limits.sp (비율 합 100 아님·2인/3인 단계 다름·금액 칸 수 틀림이면 그 유형은 읽지 않음), PARSER_VERSION 15.
  화면 spJudge: 공공임대이고 표가 있는 유형은 이 금액으로 단계 판정·총자산(townAssetItem) 판정, 마지막 단계도 넘으면 출산가구 완화 가능성이 있으면 확인 필요(금액 계산으로 '가능' 단정 안 함). 소득 사다리·'왜 이렇게 판정했나'도 공고문 금액으로. 표가 없는 유형·스위치 끄면 예전처럼 '확인 필요'. 스위치 rental_special
- 파일: app/notice_pdf.py, app/pipeline.py, docs/index.html, docs/config.json, tests/golden/notices.json(2026000307 pub_limits.sp — 표4 퍼센트를 손으로 옮기고 금액은 원문 <표5> 표에서 따로 계산해 표4 금액과 같음 확인), tests/test_rental.py, tests/judge/{cases,listings}.json, tools/make_judge_cases.py(rental_sp_expect — 원문 표 따로 옮긴 oracle), tools/engine_lock.json, tests/qa/snapshots.json, evidence/qa/snapshot.json, docs/changelog.json, VERSIONS.md
- 확인: 판정 사례 349/349(공공임대 특공 49건: 신혼 3·2인 외벌이·맞벌이, 신생아, 생애최초, 노부모, 다자녀 단계 경계 이하·초과 + 총자산 362,000·397,000·431,000천원 경계; 스위치 끄면 불일치 남), pytest 159, 판정 일치 7,680 다름 0, 공급유형·불변식·필터 0, regress 0, E2E 32/32, 스냅샷 바뀐 곳 2(공공임대 카드 '특별공급 확인' → 판정, 의도한 변경이라 기준 갱신), 390px 라이트·다크(군포 신혼 3인 월 1,000만원 → 신혼부부 '소득 2구간(일반공급)' 월 1,062만원 이하, 총자산 충족)
- 기능: rental_special
- 버전: v1.42.0
- 백업: backup/20261002-1720-rentsp

## 2026-10-02 16:30 · v1.41.1 저장된 조건 값 정리 + E2E·퍼징·화면 스냅샷
- 요청: MASTER QA 남은 일 — 사용자 흐름 E2E, 입력 퍼징, 화면 회귀
- 감사: tools/qa/e2e.cjs — 공고 6종 × 조건 5가지 = 30 흐름(카드→상세 결론이 eligBucket 과 같은지, 자금 계획→뒤로→새로고침→뒤로, #/detail/id 바로가기) + 검색·지난 공고 흐름 + 저장 조건 퍼징 39칸 × 이상값 10 = 390.
  퍼징에서 실제 오류 발견: 저장된 acctSince 가 숫자(-1)면 'a.split is not a function' 으로 화면 멈춤, 금액 칸 'abc' 면 NaN 표시
- 변경: cleanProfile — 설정을 읽은 뒤 저장된 조건을 정리(날짜는 YYYY-MM-DD 아니면 빈칸, 인원 0~30 정수, 금액 0~1억 유한수 아니면 기본값, 너무 긴 글자 초기화, 참/거짓 칸은 그대로). 스위치 profile_clean.
  tools/qa/snapshot.cjs — 고정 공고·고정 날짜(2026-10-02)·조건 3가지로 카드·상세 결론·일반·특공 칸 글자를 tests/qa/snapshots.json 과 비교 (화면 사진은 evidence/qa/shots)
- 파일: docs/index.html, docs/config.json, tools/qa/e2e.cjs, tools/qa/snapshot.cjs, tests/qa/snapshots.json, evidence/qa/{e2e.json,snapshot.json,shots/}, docs/changelog.json, VERSIONS.md
- 확인: E2E 32/32(스위치 끄면 퍼징 실패 → 막는 것 확인), 스냅샷 다름 0·화면 오류 0, 판정 사례 303/303(사례 조건 303개는 정리 전후 같음), 판정 일치 다름 0, regress 0, engine_lock 그대로, pytest
- 기능: profile_clean
- 버전: v1.41.1
- 백업: backup/20261002-1630-clean

## 2026-10-02 16:17 · v1.41.0 재공급 특별공급 판정 + 변경분 블라인드 감사
- 요청: MASTER QA 남은 일 — 변경분(일반 0세대 공통 조건·공공임대) 블라인드 판정 감사
- 감사: tools/qa/audit/audit_verdict.cjs — 공고 6개(414 59G·84B, 930036 84D, 930035 84A, 930031 59A, 307 55A) × 설계한 조건 6개 = 36건. 앱을 보지 않은 검토자 2명이 원문만으로 '어떤 공급으로든 신청 가능한가' 판정 (evidence/audit/2026-10-02-verdict).
  결과: 가짜 '가능' 0, 가짜 '불가' 0, 검토자는 결론을 냈는데 앱은 '확인 필요' 12건 — 전부 불법행위 재공급 0세대 주택형. 청약홈이 재공급 주택형의 특별공급 세대수를 안 줘서 특공 유형을 몰랐음
- 변경: notice_pdf.parse_sp_table — 공고문 공급대상 표에서 주택형별 특별공급 유형·세대수(합이 안 맞으면 읽지 않음), 재공급 주택형에만 special_units 로 씀(PARSER_VERSION 14).
  화면: 재공급도 공고문에서 읽은 유형은 특별공급 판정(spTypesFor), 재공급 특공은 청약통장을 보지 않음('청약통장 가입여부와 관계없이'), 일반 0세대 주택형의 특공 칸 안내 문구. 스위치 resupply_special
- 파일: app/notice_pdf.py, app/pipeline.py, docs/index.html, docs/config.json, tests/test_resupply_special.py, tests/golden/notices.json(930036·035·031 공급표 — 원문·검토자 값), tests/judge/{cases,listings}.json, tools/make_judge_cases.py(audit-083 기대값: 자료 생김 → 신혼부부 oracle), tools/qa/audit/audit_verdict.cjs, evidence/audit/2026-10-02-verdict/*, tools/engine_lock.json, docs/changelog.json, VERSIONS.md
- 확인: 감사 36건 다시 비교 36/36 일치(evidence/audit/2026-10-02-verdict/metrics.json), 판정 사례 303/303, 판정 일치 7,680 다름 0, regress 0, 공급유형 0, pytest, 390px 라이트·다크(과천 84D 과천 거주 신혼 — 카드·상세 '특별공급 신청 가능', 특공 칸 신혼부부 가능·노부모 불가)
- 기능: resupply_special
- 버전: v1.41.0
- 백업: backup/20261002-1617-resupply

## 2026-10-02 16:15 · MASTER QA 남은 일 1·2: 제주형 거주 기준일, LH 공고문 받기
- 요청: 남은 일 진행
- 원인·변경: (1) 거주 요건 기준일 괄호 안에 설명이 있으면('(공고일로부터 1년 전, 2025.02.12. 이전부터 계속 거주)', 2026000018 제주) 기준일을 못 읽어 '1년 이상'만 남던 것 — 정규식이 설명을 건너뛰게. 원문 60+41건 재파싱 결과 바뀐 것은 이 1건뿐. PARSER_VERSION 13.
  (2) fetch_notices.py 가 청약홈에 PDF 가 없는 LH 공고(국민)는 LH청약플러스(app/lh.py)에서 받게 — 2026000313·320·193·820007
- 파일: app/notice_pdf.py, app/pipeline.py, tests/golden/notices.json(2026000018 거주 요건 — 원문·블라인드 검토 값), tests/test_residence.py(지난 공고 원문도 형식 검사, 괄호 설명 사례), tools/qa/fetch_notices.py
- 확인: pytest 157
- 기능: 없음(수정)
- 백업: backup/20261002-1611-jeju

## 2026-10-02 15:52 · v1.40.1 판정 표시 불일치 (과천 84D, 사용자 제보)
- 요청: 과천 푸르지오 라비엔오 84D — 카드 '특별공급 확인 필요' · 상세 '신청 불가' · 칸 '재공급 전체 0세대'·거주지 불가. 잘못된 정보인지, 왜 놓쳤는지, 검증 강화
- 원문: 2026930036 '본 입주자모집공고의 특별공급은 해당 주택건설지역 거주자 중 …', '경기도 과천시 거주자' → 서울 거주자는 특별공급도 불가. 상세 '신청 불가'가 맞고 카드가 틀림
- 원인: gen_none(v1.38.2)이 카드·필터용 genNoneBucket 을 새로 만들면서 특별공급 판정만 보고 공통 조건(거주지)을 안 봄. 상세 맨 위는 기존 eligibility 를 써서 화면마다 결론이 달랐음.
  같은 결론인지 확인하는 검사가 없었음: 판정 사례는 함수 하나씩, 과천 84D 사례는 '과천 거주자'만, 10-01 블라인드 감사는 gen_none 이전, MASTER QA 원문 대조는 데이터 값만 비교
- 전수 확인: 새 검사 tools/qa/consistency.cjs (지금 공고 192 × 조건 40 = 7,680조합) — 고치기 전 119건 다름(카드 확인 필요/상세 불가 102 등 6종), 고친 뒤 0
- 변경: genNoneBucket 이 거주지·재당첨 '불가'면 불가, 공통 조건 '확인 필요'면 '가능' 대신 확인 필요. 상세 맨 위·카드 문구를 같은 판정으로. 일반 0세대 칸 머리 '전체 0세대' → '일반 몫 0세대', 공통 조건 불가면 첫 안내부터 '특별공급도 신청할 수 없어요'.
  스위치 verdict_one. 판정 사례 common-00~04(과천 84D 서울 거주 → 불가 등), 코드 변이 1개 추가, consistency 를 qa_gate·Actions 에 연결, 운영 스킬에 함정 기록
- 파일: docs/index.html, docs/config.json, tools/qa/consistency.cjs, tools/qa/code_mutation.cjs, tools/make_judge_cases.py, tests/judge/cases.json, tools/verify_status.py, .github/workflows/{collect,verify}.yml, tools/engine_lock.json, .claude/skills/cheongyakpass-ops/SKILL.md, evidence/qa/consistency.json, docs/changelog.json, VERSIONS.md
- 확인: 판정 사례 303/303(새 사례는 고치기 전 코드에서 실패 확인), 판정 일치 7,680 다름 0, 코드 변이 16개 중 15 잡음 + 동등 1, regress 0, pytest, 390px 라이트·다크(카드 '내 자격 불가 · 거주지 신청 불가' · 상세 '신청 불가' · 칸 안내)
- 기능: verdict_one
- 버전: v1.40.1
- 백업: backup/20261002-1552-verdict

## 2026-10-02 15:55 · MASTER QA: 검색·필터 일치 검사 + 게이트 연결
- 요청: MASTER QA 23항 — 검색·필터 결과가 실제 데이터와 맞는지
- 변경: tools/qa/filter_check.cjs — 원자료(listings.json) 필드로 따로 계산한 기대 집합과 화면 matches() 결과를 단일 필터 32개 + 무작위 조합 200개(시드 고정)로 비교, 검색어 '서울'(다른 시·도 섞임)·'무순위'(다른 유형)·'재공급/불법행위'(누락) 확인.
  collect·verify Actions 의 MASTER QA 단계에 추가, verify_status 게이트(qa_gate)에 포함. supply_type.cjs 는 한 줄 요약만 실행 기록에 남김
- 파일: tools/qa/filter_check.cjs, tools/qa/supply_type.cjs, tools/verify_status.py, .github/workflows/collect.yml, .github/workflows/verify.yml, evidence/qa/filter-check.json
- 확인: 필터 232개 조합 다름 0, 검색 이상 없음, 변화 방향 검사(mutation.cjs 프로필 300개 4,261변경) 위반 0, verify_status 통과
- 기능: qa_gate
- 백업: backup/20261002-1526-needhead (서비스 코드 변경 없음)

## 2026-10-02 15:40 · MASTER QA: 사람 원문 대조 30건 (블라인드)
- 요청: MASTER QA 37항 — 공고 30건 이상을 원문과 직접 비교
- 방법: 앱 데이터를 보지 않은 검토자 3명(별도 에이전트)이 원문(evidence/qa/notices)만 읽고 값을 적음 → evidence/qa/spotcheck-blind.json. tools/qa/spotcheck_compare.py 로 보관함(청약홈 값)·판정 자료(공고문에서 읽은 값)와 대조 → evidence/qa/spotcheck-result.json
- 결과: 공급 구분 30/30, 주택형 128/128, 일반 세대수 128/128, 특공 세대수 96/96(+무순위 32 해당 없음), 최고 분양가 128/128, 접수 시작·끝·발표 30/30 ×3, 1순위 세대주 5/5, 재당첨 8/8, 1순위 가입기간 5/5 (6/15 전 공고 22건은 판정 자료가 없어 NOT_TESTABLE). FAIL 0
- 검토 중 확인한 것: 2026000241·453·399·103 원문 요약표 1순위 세대주 '필요' ↔ 앱 need_head false. 처음엔 오류로 보고 요약표를 먼저 읽게 고쳤으나 판정 사례 3건(rank2-00·01·audit-051)이 실패 —
  need_head 는 '공급 전체 대상이 세대주'이고 투기과열 1순위 세대주는 규제지역 규칙으로 판정(세대원도 2순위 가능)하는 구조라 앱이 맞았음. 고친 것을 되돌리고, 뜻을 정답 데이터 notes 와 tests/test_need_head.py 로 고정
- 파일: tools/qa/spotcheck_compare.py, evidence/qa/spotcheck-blind.json, evidence/qa/spotcheck-result.json, tests/test_need_head.py, tests/golden/notices.json(need_head 4건 + 설명)
- 확인: pytest, 판정 사례 298/298
- 기능: 없음(검증)
- 백업: backup/20261002-1526-needhead (서비스 코드 변경 없음)

## 2026-10-02 15:35 · MASTER QA: 출시 게이트에 공급유형 표시·데이터 불변식 연결 (QA-08)
- 요청: MASTER QA 31·32항 — 매 수집·화면 변경마다 자동 검사, 실패하면 막기
- 변경: tools/qa/invariants.py (지금 공고·보관함: ID 중복, 공급유형↔구분 상호배타, 무순위인데 국민/민영, 금액·면적·세대수 범위, 특공 합계, 날짜 순서, 시·도, 공공임대 조건, 보관 기간 지난 공고가 목록에 남음 — 신혼희망타운 특공 합계만은 예상된 차이),
  collect.yml·verify.yml 에 supply_type.cjs + invariants 단계(실패해도 다음 단계 진행, 결과 evidence/qa/*.json 저장), verify_status 가 둘을 읽어 하나라도 위반이면 ok=false → 기존처럼 Actions 실패·이슈. 스위치 qa_gate(끄면 결과만 남김)
- 파일: tools/qa/invariants.py, tests/test_qa_invariants.py, tools/verify_status.py, .github/workflows/collect.yml, .github/workflows/verify.yml, docs/config.json, FEATURES.md
- 확인: 일부러 망가뜨린 데이터 13종을 모두 잡는 테스트, 지금 데이터 위반 0, verify_status 통과, pytest
- 기능: qa_gate
- 백업: backup/20261002-1451-rental (서비스 화면·판정 변경 없음)

## 2026-10-02 15:20 · MASTER QA: 판정 사례 경계값 보강 (QA-04·05)
- 요청: MASTER QA — 코드 변이 검사에서 못 잡던 규칙을 테스트로 지키기
- 변경: make_judge_cases.py 12) 경계값 16건 (60.00/60.01㎡ 공공 소득·자산, 85.00/85.01㎡ 예치금, 규제지역 통장 24개월 ±1일, 거주 기준일 당일/다음 날, 신혼희망타운 혼인 7년 ±1일·한부모 자녀 만 6세 ±1일, 소득 미입력이면 '확인 필요'),
  경계 시험용 고정 공고 4개(tests/judge/listings.json, 원 공고 변형 — _basis 에 적음). judge_check·code_mutation 의 거주지 비교를 includes → startsWith 로 ('기타지역 (해당지역 다음)'이 '해당지역'을 포함해 틀려도 통과하던 약점)
  code_mutation.cjs: '소득 <= → <' 는 동등 변이로 분류(만 원/년 입력으로는 월평균이 원 단위 기준액과 같아질 수 없음 — 표 전체 확인)
- 파일: tools/make_judge_cases.py, tests/judge/cases.json, tests/judge/listings.json, tools/judge_check.cjs, tools/qa/code_mutation.cjs, evidence/qa/code-mutation.json, docs/changelog.json
- 확인: 판정 사례 298/298, 코드 변이 15개 중 14개 잡음 + 동등 1 (점수 0.467 → 1.0), pytest
- 기능: 없음(검증)
- 백업: backup/20261002-1451-rental (서비스 코드 변경 없음)

## 2026-10-02 14:52 · v1.40.0 공공임대 규칙 (MASTER QA QA-02·03)
- 요청: MASTER QA 결정 1 — 임대 공고는 '임대 규칙 따로 만들기'
- 원인(분석): 청약홈 RENT_SECD_NM(분양/임대)을 저장만 하고 안 써서 2025000645 공공건설임대 임차인모집이 '일반분양'으로, 2026000307 6년 분양전환공공임대가 공공분양 규칙으로 판정됨. 청약홈 공급금액은 임대보증금(원문 임대조건 표 55A 85,614,000원).
  원문 대조 중 추가 발견: 이 임대 공고의 소득표는 1인 4,576,036(120%)·2인 6,452,897(110%)·3인 8,168,429(100%)로, 공공분양 '3인 이하 7,533,763'과 기준액이 다름 → 금액을 공고문 표 그대로 씀
- 변경: 수집 is_rental(RENT_SECD_NM, 없으면 이름; 토지임대부·분양전환 후 잔여세대는 분양) → rental, 시세 조회 건너뜀, 종류 '공공임대'. notice_pdf._parse_rental_limits(kind total: 자격·우선공급 %·<표4> 금액·총자산·출산 완화), PARSER_VERSION 12.
  화면: '공공임대' 배지·'임대보증금'·임대 조건 카드(마진·자금 플랜 대신), totalGeneralItems(가구원수별 금액·총자산), 특별공급은 확인 필요, 지난 공고 카드. validate: 임대인데 기준 못 읽으면 [검증]. 지난 공고 보관함에 rent_secd 칸(잠긴 공고는 개요 값으로 칸만 채움)
  원문 대조용 지난 공고문은 evidence/qa/notices/ 로 옮김(evidence/notices 전체를 도는 테스트가 지금 공고 기준이라 섞이면 깨짐)
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, docs/index.html, docs/config.json, tools/history/build.py, tools/qa/fetch_notices.py, tools/make_judge_cases.py, tests/judge/{cases,listings}.json, tests/golden/notices.json(2026000307), tests/test_rental.py, tests/test_residence.py, evidence/qa/notices/*, tools/engine_lock.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 정답 데이터 2026000307(원문 직접 읽음) 일치, 다른 공고문 60건 파싱 결과 변화 없음, 판정 사례 282/282(공공임대 21건 추가 — 1·2·3·4인 외벌이/맞벌이 경계 ±1만원, 총자산 ±1만원, 특별공급 확인 필요), pytest, regress 0, 공급유형 표시 검사 0, 390px 라이트·다크(카드·상세·자금 플랜)
- 기능: rental_rules
- 버전: v1.40.0
- 백업: backup/20261002-1451-rental

## 2026-10-02 14:55 · MASTER QA 1차 분석 (STEP 1~5) + 코드 변이 검사 도구
- 요청: 출시 전 MASTER QA 요구서 — 분석부터, 코드는 고치지 않고 (치명 오류만 먼저)
- 결과: 보고서 Claude 문서 '청약패스 MASTER QA — 1차 분석 보고서 (STEP 1~5)'. 치명 1건(QA-01 재공급 배지)은 v1.39.2 로 고침.
  남은 High: QA-02 분양/임대 구분(RENT_SECD_NM) 미사용 → 2025000645 공공건설임대 임차인모집이 '일반분양'으로, QA-03 2026000307 분양전환공공임대를 공공분양 규칙으로 판정,
  QA-04 '확인 필요 → 가능' 변이를 어떤 테스트도 못 잡음, QA-05 경계값 7종 무방비
- 변경: tools/qa/code_mutation.cjs — 판정·표시 코드에 오류 15개를 하나씩 넣고(파일은 그대로, 브라우저로 보낼 때만) 판정 사례·표시 검사가 잡는지 셈. 결과 잡음 7 · 못 잡음 8 (점수 0.467, 기존 판정 사례만으로는 4)
- 파일: tools/qa/code_mutation.cjs, evidence/qa/code-mutation.json
- 확인: 기준선(변이 없음) 판정 사례 261/261 일치 확인 후 변이별 실행
- 기능: 없음(검사 도구)
- 백업: backup/20261002-1421-badge (서비스 코드 변경 없음)

## 2026-10-02 14:30 · MASTER QA: 원문 대조용 공고문 받기 도구
- 요청: 출시 전 MASTER QA 요구서 (5·37항 공식 공고문 기준·사람 원문 대조 30건)
- 변경: tools/qa/fetch_notices.py — evidence/qa/notice-ids.txt 의 공고(위험군 14 + 원문 대조 30)를 evidence/notices/ 로 받음. 근거 자료 모으기(probe.yml)에 단계 추가(실패해도 계속). 작업 환경에서는 청약홈 접속이 막혀 Actions 에서 받음
- 파일: tools/qa/fetch_notices.py, evidence/qa/notice-ids.txt, .github/workflows/probe.yml
- 확인: 실행 뒤 evidence/qa/fetch-notices.log
- 기능: 없음(검사 도구)
- 백업: backup/20261002-1421-badge (직전 백업, 서비스 코드 변경 없음)

## 2026-10-02 14:21 · v1.39.2 불법행위 재공급 카드 배지 '무순위' 오표시 (MASTER QA 중 발견)
- 요청: 출시 전 MASTER QA 요구서 — '불법행위 재공급 → 무순위' 같은 공급유형 오분류를 전체에서 찾고 재발 방지
- 원인: v1.38.3 에서 상세 '일반공급 칸 이름'(genLabel)만 '재공급'으로 고치고, 목록 카드 배지(cardBadges)는 category === 'remainder' 면 무조건 '무순위'로 남아 있었음 (표시 단계, 데이터·판정은 맞음)
- 전수 검사: tools/qa/supply_type.cjs 새로 만듦 — 원천 유형(청약홈 category·HOUSE_SECD_NM) → 목록 카드·일반공급 칸 이름·지난 공고 카드 글자를 공고 전부 대조, 기대값은 원천 유형 표(EXPECT)로 정함.
  고치기 전: 목록 카드 불법행위 재공급 8건 중 8건 FAIL, 나머지(지금 192주택형 × 2곳, 지난 공고 536공고) PASS. 상세 화면 본문에 '무순위' 없음(8건 확인)
- 변경: cardBadges 가 재공급이면 '재공급' 배지 (스위치 general_units 를 따름)
- 파일: docs/index.html, tools/qa/supply_type.cjs, evidence/qa/supply-type.json, docs/changelog.json, VERSIONS.md
- 확인: supply_type.cjs 위반 0, 판정 사례 261/261, regress 0, 엔진 잠금 그대로, pytest
- 기능: 없음(수정)
- 버전: v1.39.2
- 백업: backup/20261002-1421-badge

## 2026-10-02 14:04 · v1.39.1 지난 공고 1년치로 운영
- 요청: 마감된 것은 과거 공고로 넘기고 26년부터 쌓다가 1년 넘은 공고는 차례로 삭제 — 과거 공고는 1년치만
- 변경: tools/history/window.py(마감일 기준 365일, 시작 2026-01-01). build.py 는 기간 밖 주택형 삭제·새로 받을 때도 거름(meta.pruned), enrich.py 는 기간 밖 공고 제외·공고문 기록(cache)도 삭제(meta.cache_pruned).
  보관 파일 이름을 연도 없는 이름으로: archive/2026.json → past.json, 2026-judge.json → past-judge.json, 2026-notice-cache.json → past-notice-cache.json.
  화면: 마감된 공고만(오늘 날짜로 다시 계산, 보관함은 주 1회라), 마감 1년 지난 공고 제외, 제목 '지난 공고 · 최근 1년 마감 공고', 버튼 '지난 1년 공고 보기', 아래 건수는 화면에 보이는 마감 공고 수
- 파일: tools/history/{window,build,enrich,validate_sample}.py, tests/test_history_window.py, tools/qa/pastjudge.cjs, docs/index.html, docs/archive/*, docs/changelog.json, VERSIONS.md, FEATURES.md, HANDOFF.md
- 확인: pytest(경계 — 마감일 = 기준일 남김·하루 전 삭제), 실제 보관함으로 오늘 2092/2092 · 2027-03-01 가정 1832 · 2027-09-01 가정 270 남음. 390px 라이트·다크: 예정 공고 빠지고 536건(마감만), 판정 그대로, 오류 0. 판정 사례 261/261, regress 0, 엔진 잠금 그대로
- 기능: historical_search, historical_judge
- 버전: v1.39.1
- 백업: backup/20261002-1404-pastwindow

## 2026-10-02 13:53 · v1.39.0 2026년 지난 공고 + '그때 넣었다면' 켬
- 요청: 과거 청약은 이 정도면 충분, 참고용으로 쓸 만하니 추가 (사용자 결정 — 실험 유지, 폐기 안 함)
- 변경: 스위치 historical_search·historical_judge 켬, 지난 공고 머리말 '실험 중' → '참고용', FEATURES 에 historical_judge 줄, changelog·VERSIONS v1.39.0
- 파일: docs/config.json, docs/index.html, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 미리보기 표시 없이 390px 라이트·다크 — 목록 아래 '지난 공고 전체 보기' → 지난 공고 화면 → '그때 넣었다면' 판정, 스크립트 오류 0. 판정 사례 261/261, regress 0건, 엔진 잠금 그대로, pytest
- 기능: historical_search, historical_judge
- 버전: v1.39.0
- 백업: backup/20261002-1353-pastlaunch

## 2026-10-02 13:31 · 과거 공고 판정: 다시 읽기 결과 + 막 마감된 공고도 판정
- 요청: '그때 넣었다면'이 거의 확인 필요 — 한 달 전 공고문을 왜 못 읽나 (이어서)
- 확인 결과: 시간 제한 1500초로 다시 실행(Actions 36963905425, 공고문 읽기 353초) → 154건 중 154건 읽음.
  대표 조건(서울 무주택 세대주·통장 10년) 571주택형: 가능 274 · 불가 204 · 확인 필요 93. 확인 필요 중 공고문 쪽 원인은 거주 요건 못 읽음 15·공공 소득자산 기준 못 읽음 10, 나머지는 내 조건(전입일) 입력 부족
- 변경: 막 마감돼 아직 listings.json 에 남은 공고(enrich 가 건너뜀, 50건)는 '판정 자료가 아직 없어요' 대신 그 목록의 공고 조건으로 판정
- 파일: docs/index.html, tools/qa/pastjudge.cjs(판정 분포 확인 도구)
- 확인: JS 문법, 판정 사례 261/261, regress 0건, 엔진 잠금 그대로, 390px 라이트·다크(아크로 리버스카이 2차 140P '신청 가능했어요', 과천 84D·99B)
- 기능: historical_judge (꺼져 있음, 미리보기만 — 버전 안 올림)
- 백업: backup/20261002-1331-pjlive

## 2026-10-02 13:17 · 과거 공고 판정: 공고문 대부분 못 읽던 문제 (시간 제한)
- 요청: '그때 넣었다면'이 거의 확인 필요 — 한 달 전 공고문을 왜 못 읽나
- 원인: 공고문을 못 받는 게 아니라, apply_notice 의 공고문 읽기 시간 제한(NOTICE_BUDGET_SEC 300초, 매일 수집용)에 걸려 154건 중 29건만 읽고 나머지는 취소됨(실행 386초).
  같은 날 랜덤 검증은 제한 없이 120건 중 114건을 받았음 → 받을 수 있는 공고문
- 변경: enrich 에서만 제한을 1500초로(매일 수집은 그대로 300초). 읽은 값은 2026-notice-cache.json 에 보관돼 다음 실행은 새 공고만. history.yml 제한 60분
- 파일: tools/history/enrich.py, .github/workflows/history.yml
- 확인: 다시 실행 후 evidence/history/enrich.json 의 notice_read
- 기능: historical_judge
- 백업: backup/20261002-1256-pastjudge

## 2026-10-02 13:00 · 과거 공고 6단계: '그때 넣었다면' 화면 (꺼 둠·미리보기)
- 요청: 과거 공고도 판정 (6/15 이후), 켜고 끄기 가능하게
- 변경: 지난 공고 카드에 '그때 넣었다면? · 내 조건으로 보기' — 누르면 docs/archive/2026-judge.json 을 불러와 주택형별 eligBucket·특공 spJudge 를 화면 엔진 그대로 실행,
  과거형 문구(신청 가능했어요/2순위만 가능했어요/신청할 수 없었어요/확인 필요). 6/15 전 공고는 '규칙 개정 전이라 판정하지 않음'. 스위치 historical_judge=false(?past=1 미리보기만)
- 파일: docs/index.html, docs/config.json
- 확인: JS 문법, pytest, 화면 회귀 판정·목록 판정 차이 0. 판정 자료(Actions enrich) 생성 뒤 브라우저로 다시 확인 예정
- 기능: historical_judge
- 백업: backup/20261002-1256-pastjudge

## 2026-10-02 12:56 · 과거 공고 5단계: '그때 넣었다면' 판정용 데이터 (6/15 이후 마감 공고)
- 요청: 과거 공고도 판정 — 규칙 개정(2026-06-15) 이후 공고만, 백업·켜고 끄기 가능하게
- 변경: tools/history/enrich.py — 6/15 이후 공고 중 마감(지금 목록에 없는 것)만 매일 수집과 같은 코드(build_listing·apply_notice, 공고일 기준)로 공고 조건을 만들어 docs/archive/2026-judge.json.
  시세·경쟁률·위치·청약봇 조각은 쓰지 않음. 공고문 읽은 값은 docs/archive/2026-notice-cache.json 에 보관해 다음 주간 실행에서 이어 읽음. history.yml 에 단계 추가(실패해도 계속, 제한 45분)
- 파일: tools/history/enrich.py, .github/workflows/history.yml
- 확인: build_listing(시세 없이) 로컬 실행, Actions 결과 evidence/history/enrich.json
- 기능: historical_judge (화면 연결은 다음 커밋)
- 백업: backup/20261002-1256-pastjudge

## 2026-10-02 12:50 · 과거 공고(2026) 실험 4단계: 랜덤 검증 120공고 (seed 저장)
- 요청: 2026 공고를 검증 모집단으로, 랜덤 100개 이상, seed·샘플 ID 저장, PASS/FAIL/UNCERTAIN·오류 분류, 실제 결과만
- 변경: tools/history/validate_sample.py — 보관함 공고를 유형(일반/무순위)×권역(수도권/지방) 층화 랜덤(seed 기본 = 날짜, --fresh 새 seed). 검사 D1 일정 순서·D2 세대수 합(본청약은 사전청약 몫 → EXPECTED_DIFFERENCE)·
  D3 지역·N1 공고문 받기·N2 분양가 원문 대조·N3 공급규모·N4 정답 데이터. 결과 evidence/history/validation-<날짜>.json. history.yml 에 단계 추가(실패해도 서비스 영향 없음)
- 파일: tools/history/validate_sample.py, .github/workflows/history.yml
- 확인: 로컬 — 같은 seed 두 번 같은 120공고(일반 55·무순위 65, 수도권 72·지방 48), D1 120 PASS, D2 51 PASS·65 N/A·4 → 본청약 사전청약 몫(EXPECTED_DIFFERENCE), D3 120 PASS. 공고문 검사(N1~N4)는 Actions 실행 결과로
- 기능: historical (실험)
- 백업: backup/20261002-1233-pastui

## 2026-10-02 12:33 · 과거 공고(2026) 실험 3단계: '2026년 지난 공고' 화면 (미리보기만)
- 요청: 과거 공고 실험 진행 — 활용도·속도를 보고 폐기 여부 결정
- 변경: 새 화면 past(vPast) — docs/archive/2026.json 을 이 화면을 열 때만 불러옴(첫 화면 영향 없음). 공고 단위 카드(이름·지역·유형·공고일·주택형·분양가 범위·일반/특공 세대·청약홈 링크),
  상태 '과거 공고 · YYYY.MM 마감'/접수 중/예정, 검색(단지명·지역)·유형·시도 칩·30건씩 더 보기, 바닥에 기준일·건수·불러오기 ms. 목록 아래 '2026년 지난 공고 전체 보기' 버튼.
  스위치 historical_search=false — 운영자만 ?past=1 로 봄(?past=off 끄기). history.yml 매주 월 06:40 보관함 갱신(마감분 잠금·덮어쓰지 않음)
- 파일: docs/index.html, docs/config.json, .github/workflows/history.yml
- 확인: 390px 라이트·다크, 송파 검색 1건(송파 시그니처 롯데캐슬 · 과거 공고 · 2026.08 마감), 유형·시도 칩, 로컬 불러오기 69ms, 화면 오류 0, 화면 회귀 판정·목록 판정 차이 0, 판정 261/261, pytest
- 기능: historical_search (꺼 둠, 미리보기)
- 백업: backup/20261002-1233-pastui (실험 시작점 backup/20261002-1208-pre-historical)

## 2026-10-02 12:12 · 과거 공고(2026) 실험 2단계: 보관함 데이터 만들기 (화면 미연결)
- 요청: 과거 데이터까지 넣어 보기 (1단계 측정: 2026 공고 544건 — 일반분양 249·무순위 295, 주택형 약 1,400개 추정, 개요 호출 26회 10초)
- 변경: tools/history/build.py — 2026-01-01 이후 공고 개요+주택형을 docs/archive/2026.json 에 주택형 단위로(청약홈 값만: 공고명·주소·시도/시군구·유형·면적·분양가·세대수·특공·일정·상태·링크). 마감된 주택형은 locked_at 을 찍고 다음 실행에서 다시 받지 않음(덮어쓰지 않음).
  매일 수집(app/pipeline)·listings.json·화면은 그대로 — 아직 아무 화면도 이 파일을 읽지 않음. history.yml 에 build 단계 추가
- 파일: tools/history/build.py, .github/workflows/history.yml
- 확인: Actions 실행 후 evidence/history/build.json(건수·호출 수·시간·파일 크기)
- 기능: historical (실험)
- 백업: backup/20261002-1208-pre-historical

## 2026-10-02 12:08 · 과거 공고(2026) 실험 1단계: 규모 측정
- 요청: 현재 상태를 백업하고 2026 과거 공고까지 넣어 보되, 활용도가 없거나 느리거나 못 쓸 정도면 폐기하고 백업으로 되돌린다
- 변경: 실험 시작점 백업 backup/20261002-1208-pre-historical. tools/history/probe.py + .github/workflows/history.yml — 청약홈 API 로 2026-01-01 이후 공고 개요 건수·월별·유형·이름 표시(정정·취소 등)·필드·주택형 평균 수·예상 호출 수를 evidence/history/probe.json 에 기록. 서비스 데이터(docs/)·매일 수집은 그대로
- 파일: tools/history/__init__.py, tools/history/probe.py, .github/workflows/history.yml
- 확인: 문법, Actions 실행 결과(evidence/history/probe.json)
- 기능: historical (실험, 아직 스위치 없음 — 화면·수집 변화 없음)
- 백업: backup/20261002-1208-pre-historical

## 2026-10-02 11:42 · 단지 규모 정답 비교 고침 (거짓 '정답 불일치')
- 요청: (STEP 0-2 올린 뒤 수집 확인) — 수집 실행이 실패로 끝남
- 원인: 정답 데이터 complex 는 {총세대, 동 수}인데 수집값에는 상태·출처·원문이 더 붙어 dict 전체 비교에서 값이 같아도 [검증·정답 불일치] 12줄 → verify-status ok false → 수집 실패
- 변경: validate.golden_mismatches 가 complex 는 정답에 있는 키(총세대·동 수)만 비교
- 파일: app/validate.py, tests/test_complex.py
- 확인: 지금 listings.json 전체로 정답 불일치 0, pytest 144(새 1: 같으면 일치·다르면 불일치), 다시 수집 실행 결과 확인
- 수집 결과(첫 실행): 192개 주택형 중 complex 확인 173·확인 불가 19(공고 9건: 흐트러진 PDF 7, 공급규모 문장 없는 조각 2), 나홀로 no 169·maybe 4(미아 3차 1개동 118세대, 신림스카이 1개동 43세대)·unknown 19
- 기능: 없음(수정)
- 백업: backup/20261002-1142-cxgold

## 2026-10-02 11:17 · 청약봇 V2 STEP 0-2 단지 총세대·동 수·나홀로 3상태 (모집공고문 '공급규모')
- 요청: STEP 0 데이터 보강 — 단지 총세대수·동 수·나홀로 여부 (동 수=1 만으로 단정하지 말고 3상태)
- 변경: notice_pdf.parse_complex — '공급(\s)규모' 뒤 260자에서 '총 N세대'/'블록 N세대'/공공 'N개동 … N세대' 와 'N개동'. 글자 순서가 흐트러진 PDF('지하 층 지상 층 개동 총 세대')는 읽지 않음(확인 불가).
  single_status: no(동 2개 이상)·maybe(동 1개, 또는 동 모름·100세대 미만)·unknown. Listing.complex = {households, buildings, single, status 확인/확인 불가, src, quote}.
  새로 받은 공고문은 원문에서, 보관 기록으로 읽은 공고는 청약봇 공고문 조각(notice_chunks.text_of)에서 읽음. PARSER_VERSION 은 그대로(다시 받지 않음)
- 정답 데이터: tests/golden/notices.json 에 11건 complex 추가 — 공고문 원문 '공급규모' 문장을 직접 읽고 넣음(103·314·409·414·448·820011·910227·910244·910250·930031, 930036 은 흐트러진 숫자 → 확인 불가)
- 파일: app/notice_pdf.py, app/notice_chunks.py, app/models.py, app/pipeline.py, docs/config.json, tests/test_complex.py, tests/golden/notices.json
- 확인: evidence 원문 60건 추출 결과 전부 문장과 대조(읽음 52·확인 불가 8), pytest 143(새 4: 정답 11건·흐트러진 숫자·공공/신희타 문장·3상태 경계), 올린 뒤 수집 실행에서 listings.json complex 확인
- 기능: complex_size
- 백업: backup/20261002-1117-complex

## 2026-10-02 11:17 · 청약봇 V2 STEP 0-1 데이터 사전
- 요청: 청약봇 V2 STEP 0부터 진행 — 확보/추가 데이터와 상태(확인·외부·추정·확인 불가) 확정
- 변경: chat/DATA.md — 청약봇이 쓰는 필드별 값·상태 규칙·출처·비고, 나홀로·방/욕실 3상태 규칙, 판정은 화면 엔진만 쓴다는 원칙
- 파일: chat/DATA.md, WORK.md
- 확인: 문서만 (코드 변경 없음)
- 기능: 없음(문서)
- 백업: backup/20261002-1117-complex

## 2026-10-02 10:45 · 청약봇 끔 (다시 설계)
- 요청: 챗봇 답이 법령만 길게 설명하고 청약패스 판정 엔진 결과가 안 나옴 → 챗봇 기능 끄고 설계부터 다시
- 변경: config `chat_off: true` — chatOn() 이 운영자 미리보기까지 모두 false (둥근 버튼·이 공고 물어보기 안 보임). 서버(Worker)·공고문 조각 수집(chatbot_notice)은 그대로 둠(다시 개발에 씀)
- 되돌리기: config `chat_off` 를 false 로
- 파일: docs/index.html, docs/config.json, HANDOFF.md
- 확인: 미리보기 코드 기기로 열어도 목록·상세에 버튼 없음(chatOn false), JS 문법, pytest
- 기능: 없음(설정)
- 백업: backup/20261002-1045-chatoff

## 2026-10-02 10:40 · 청약봇 운영자는 질문 횟수 제한 없음
- 요청: 챗봇 운영자만 질문 제한 풀어 달라 — 질문 입력이 안 됨(하루 2건 소진)
- 변경: 서버가 미리보기 코드가 맞는 운영자 질문은 하루 제한(사람 2·IP 3·전체 100)을 세지 않음(AI 모드 포함, 비용은 월 한도로만 막음). 운영자 대화창 아래 '운영자 · 질문 제한 없음'
- 파일: chat/worker/src/index.js, chat/test/chat.test.mjs, docs/index.html
- 확인: node --test chat 38개(운영자 5번 연속 200, 일반 이용자는 그대로 2번), chatflow 실패 0, JS 문법, pytest, 청약봇 서버 배포
- 기능: 없음(운영 도구)
- 백업: backup/20261002-1040-oplimit

## 2026-10-02 10:29 · 특별공급 칸에도 '전체 N세대', 재공급 칸 이름
- 요청: 특별공급 옆에도 일반공급처럼 전체 몇 세대 표기, 다른 조건(신혼희망타운 등)도 확인
- 변경: 특별공급 카드 제목 옆 '전체 N세대'(청약홈 특별공급 합계). 유형 줄(신생아·신혼·생애최초·다자녀·노부모) 합계보다 크면 '기관추천·이전기관 등 N세대(판정하지 않음)' 한 줄.
  불법행위 재공급의 일반 칸 이름 '무순위' → '재공급', 일반 물량 0이면 '일반 물량 없음'
- 확인(전 주택형 상세 카드 머리 점검): 일반공급·특별공급·신혼희망타운·무순위·재공급 모든 카드 머리에 '전체 N세대' 표시 (특공 0 인 주택형은 특공 카드 자체가 없음, 재공급은 청약홈이 특공 세대수를 안 줘 특공 카드 없음).
  고덕(공공) 84A 특공 558 = 유형 394 + 기관추천 등 164, 광명 59A 11 = 9 + 2. 390px 라이트·다크, 판정 261/261, 화면 회귀 판정·목록 판정 차이 0, pytest
- 파일: docs/index.html
- 기능: general_units
- 버전: v1.38.3
- 백업: backup/20261002-1029-spunits

## 2026-10-02 10:12 · 일반공급 물량 0 주택형 판정 고침 (일반공급 없음 → 특별공급 기준)
- 요청: '일반물량이 0세대면 일반공급이 아닌 거 아니야?' — 추천 방식(공급 0은 목록에서 빼고, 특공만 있는 주택형은 일반공급 '해당 없음'·목록은 특공 기준)대로
- 원인: 목록 판정(eligBucket)·목록 문구(meLine)·상세 일반공급 칸이 청약홈 일반공급 세대수를 보지 않고 일반공급 자격(eligibility)만으로 '신청 가능'을 냄
- 변경: (화면) genNone(L) = 일반공급 세대수 0(신혼희망타운 제외)이면 eligBucket 은 특별공급 판정 최선(가능>확인 필요>불가), 특공 유형별 세대수를 모르면(무순위·재공급) 확인 필요,
  특공도 0 이면 불가. 상세 일반공급 칸 pill '일반공급 없음' + 안내(아래 조건은 특공 공통 조건), '뽑는 방식' 칸 숨김. eligibility 자체는 그대로(판정 사례 256건 영향 없음).
  (수집) no_supply: 일반 0·특별 0 이면 목록에서 빼고 run-log [제외] 로 남김. (검증) regress 에 목록 판정 변화 표시 추가
- 근거 대조: 2026000414 공급표(59C 15세대 전부 사전청약 당첨자 몫, 59G 특공만), 2026930036 '특별공급 2세대(신혼 1·노부모 1)', 2026930035 '특별공급 2세대(다자녀 1·신혼 1)',
  2026930031 '불법행위재공급 2세대[생애최초 특별공급 1세대, 일반공급 1세대]'
- 파일: docs/index.html, docs/config.json, app/pipeline.py, tests/test_gen_none.py, tools/make_judge_cases.py, tests/judge/cases.json, tests/judge/listings.json, tools/engine_lock.json, tools/qa/regress.cjs
- 확인: 판정 사례 261/261(새 5건, 스위치 끄면 3건 불일치 = 고치기 전 오류 재현), pytest 139(새 5), 화면 회귀 970조합 eligibility·점수·마진 차이 0,
  목록 판정 변화는 위 7개 주택형만(59G·84B ok→no 등 프로필별), 390px 라이트·다크
- 기능: gen_none
- 버전: v1.38.2
- 백업: backup/20261002-1012-gennone

## 2026-10-02 09:55 · 일반공급 세대수 표기를 특별공급 모양으로 + 신혼희망타운·0세대 경우 처리
- 요청: 일반/특공 세대 표기 양식을 특공 기준으로 맞추고, 신혼희망타운은 왜 세대가 안 나오는지, 모든 경우에 세대가 나오는지 확인
- 원인: 신혼희망타운은 청약홈이 전 물량을 특별공급 칸(special_units.total)에 주고 일반공급 세대수는 0 → 일반 세대수만 보던 v1.38.0 은 표시 안 함
- 변경: 제목 옆 '전체 N세대'(특별공급 줄과 같은 small muted), 아래 줄에 가점제 g세대 · 추첨제 l세대(추정 근거) / 모두 추첨 / 모두 추첨제.
  신혼희망타운 = 특별공급 합계. 일반 0세대: 특공 있으면 '모두 특별공급(특별공급 N세대)', 무순위·재공급은 '청약홈에 일반 물량 없음 · 특공 세대수는 공고문',
  그 밖은 '이번 공고에서 새로 공급하는 세대 없음'(예: 인천계양 A6 59C·77C — 공고문 공급표상 전량 사전청약 당첨자 몫, 과천 라비엔오 84D — 공고문상 특별공급 2세대뿐)
- 파일: docs/index.html
- 확인: 194개 주택형 전부 경우별 표기 확인(14가지 경우, 표시 안 되는 경우 0), 390px 라이트·다크(광명 59A·신혼희망타운 55A·과천 84D·계양 59G), 화면 회귀 차이 0, 판정 256/256, pytest
- 기능: general_units
- 버전: v1.38.1
- 백업: backup/20261002-0955-genunits2

## 2026-10-02 09:40 · 일반공급·무순위 세대수와 가점제·추첨제 몫 표시
- 요청: 특별공급은 'N세대'가 나오는데 일반공급·무순위는 몇 세대인지 안 나옴 → 추첨/가점 각각 적어 달라
- 변경: 상세 일반공급 카드 제목 아래 '전체 N세대 · 가점제 g · 추첨제 l'. N = 청약홈 일반공급 세대수(households), g = ceil(N × 공고문 가점제 비율(score_ratio, 면적 구간)),
  l = N − g (주택공급에 관한 규칙 제28조 ②·④ '소수점 이하는 올림'). '1순위 기준 추정' 표시. 무순위·불법행위 재공급 = 모두 추첨, 공공(국민) = 세대수만,
  비율표 없음 = '몫은 공고문 확인', 신혼희망타운·세대수 0 = 표시 안 함. 판정은 바꾸지 않음
- 파일: docs/index.html, docs/config.json
- 확인: 화면 회귀 970조합 판정·점수·마진 차이 0(엔진 지문은 fromApi 가 households 를 넘기게 돼 갱신, 판정 함수는 그대로), 전 공고 상세 렌더 오류 0, 표기 표본(광명 59A 10세대→가점제 4·추첨제 6 / 84A 36세대 70%→26·10, 오남역 무순위 12세대 모두 추첨, 고덕 공공 97세대),
  390px 라이트·다크 화면, JS 문법, pytest, 판정 사례 256/256
- 기능: general_units
- 버전: v1.38.0
- 백업: backup/20261002-0940-genunits

## 2026-10-02 09:12 · 청약봇 AI 답이 안 나가던 진짜 원인 확인 (키 설정)
- 요청: AI 모드로 물어도 법령 원문만 나옴
- 원인: chat-probe 실제 시험 결과 Claude 호출이 매번 400 — "This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header".
  등록된 ANTHROPIC_API_KEY 가 워크스페이스에 속하지 않은 키라 호출이 거절됨 → 모든 답이 기본 답(법령 원문)으로 대체. 지금까지 AI 토큰 사용 0
- 변경: llm.js 가 실패 시 Anthropic 오류 종류·문구를 진단에 남김(키 없음). 조치는 사용자: Console 워크스페이스 안에서 새 API 키 → GitHub Secret ANTHROPIC_API_KEY 교체 → 재배포
- 파일: chat/worker/src/llm.js, chat/probe_questions.json, evidence/chat-probe/latest.json(Actions)
- 확인: node --test chat 37개, chat-probe 결과
- 기능: 없음(수정·운영 도구)
- 백업: backup/20261002-0859-chatdiag

## 2026-10-02 09:05 · 청약봇 !AI 직후에도 무료로 답하던 문제 고침
- 요청: 무료 모드·AI 모드로 같은 질문을 했는데 답이 똑같다
- 원인: 운영자 무료 모드를 서버 KV(opfree)에 저장했는데, Cloudflare KV 는 지운 값을 최대 60초 동안 다시 읽을 수 있음 → !AI 바로 뒤 질문도 무료(AI 안 부름)로 처리.
  Actions 실제 시험(evidence/chat-probe/latest.json)에서 diag.opFree=true·AI 시도 0 으로 확인
- 변경: 무료 모드는 운영자 기기(localStorage cy-chat-free)가 기억하고 질문마다 free:true 로 보냄. 서버는 미리보기 코드가 맞을 때만 따름(코드 없이 free 를 보내면 무시). KV opfree 안 씀
- 파일: chat/worker/src/index.js, chat/test/chat.test.mjs, docs/index.html, .github/workflows/chat-probe.yml
- 확인: node --test chat 37개(코드 없는 free 무시 포함), JS 문법, chatflow 실패 0, pytest, 배포 뒤 chat-probe 로 실제 AI 답 확인
- 기능: 없음(수정·운영 도구)
- 백업: backup/20261002-0859-chatdiag

## 2026-10-02 08:59 · 청약봇 운영자 진단 표시 + 실제 답 시험 워크플로
- 요청: 무료 모드·AI 모드로 같은 질문('신혼부부, 자금 5억, 신청 가능한 공고')을 했는데 두 답이 똑같이 법령 원문 붙여넣기 — 왜 이런지
- 원인(1차): AI 모드 답에도 'AI 요약 없이 원문 일부' 문구 → AI 답이 나가지 못하고 기본 답으로 대체됨. 서버가 거절 이유를 밖으로 안 내서 원인 확인 불가
- 변경: 미리보기 코드가 맞는 운영자 답에만 diag(시도별 통과/막힘·검사기 이유·호출 실패 코드·토큰, 근거 조각 수)를 붙이고 대화창에 '운영자 진단' 한 줄로 표시.
  .github/workflows/chat-probe.yml + chat/probe_questions.json: Actions 에서 운영자 코드로 실제 질문을 보내 결과를 evidence/chat-probe/latest.json 에 남김
- 파일: chat/worker/src/index.js, docs/index.html, .github/workflows/chat-probe.yml, chat/probe_questions.json
- 확인: node --test chat 37개, JS 문법, chatflow 통과, pytest
- 기능: 없음(운영 도구) — 운영자에게만 보임, 버전 그대로
- 백업: backup/20261002-0859-chatdiag

## 2026-10-02 08:44 · 청약봇 운영자 무료 시험 모드 (!무료 / !AI)
- 요청: 확인용으로 무료로 답하게 설정하고, 무료로 쓸 땐 하루 2회 제한도 풀어 달라. 몇 가지 확인 뒤 실제 AI 로 질문해 볼 것
- 변경: 운영 명령 `!무료`(KV opfree=1) — 미리보기 코드가 맞는 운영자 질문만 AI 를 부르지 않고(토큰 0) 기본 답, 하루 횟수 제한 건너뜀.
  `!AI`(또는 !유료) — 해제, 운영자도 실제 AI·하루 2건. `!상태` 에 지금 모드 표시. 다른 이용자 동작은 그대로
- 파일: chat/worker/src/index.js, chat/test/chat.test.mjs, chat/README.md, HANDOFF.md
- 확인: node --test chat 37개 통과(무료 모드 6번 연속 200·AI 호출 0, 다른 이용자는 AI 호출, !AI 뒤 운영자 AI 호출), pytest, 청약봇 서버 배포 Actions 성공
- 기능: 없음(운영 도구) — 이용자 화면 변화 없음, 버전 그대로
- 백업: backup/20261002-0844-opfree

## 2026-10-02 08:31 · 네이버 서치어드바이저 소유 확인 메타 태그 추가
- 요청: 네이버 서치어드바이저 등록 — 사용자가 확인 태그를 줌
- 변경: 모든 화면 <head> 에 `naver-site-verification` 메타(공개 값) 추가 (index.html, build_static 머리말 → 정적 페이지 재생성)
- 파일: docs/index.html, tools/build_static.py, docs/*/index.html, docs/notice/*
- 확인: pytest, 모든 index.html 에 메타 1줄만 추가된 것 확인, Pages 배포 성공 확인
- 기능: 없음(설정) — 화면 변화 없음, 버전 그대로
- 백업: backup/20261002-0831-naver

## 2026-10-02 08:21 · 구글 서치 콘솔 소유 확인 메타 태그 추가
- 요청: 애드센스 승인에 도움되게 서치 콘솔 등록 — 사용자가 확인 태그를 줌
- 변경: 모든 화면 <head> 에 `google-site-verification` 메타(공개 값) 추가 (index.html, build_static 머리말 → 정적 페이지 재생성)
- 파일: docs/index.html, tools/build_static.py, docs/*/index.html, docs/notice/*
- 확인: pytest, 모든 index.html 에 메타 1줄만 추가된 것 확인, Pages 배포 성공 확인
- 기능: 없음(설정) — 화면 변화 없음, 버전 그대로
- 백업: backup/20261002-0821-gsc

## 2026-10-02 08:04 · 애드센스 사이트 확인용 메타 태그·ads.txt 추가 (광고는 꺼 둔 채)
- 요청: 애드센스에 cheongyakpass.kr 을 추가하려는데 사이트 확인 화면에서 무엇을 눌러야 하는지
- 변경: 모든 화면(index.html·정적 페이지 머리말 build_static) <head> 에 `google-adsense-account` 메타(게시자 ID ca-pub-8680972365235939, 공개 값),
  docs/ads.txt 추가(google.com, pub-8680972365235939, DIRECT, f08c47fec0942fa0). 광고 스위치 ads=false·adsense_client 는 그대로 — 승인 전에는 광고가 뜨지 않음
- 파일: docs/index.html, tools/build_static.py, docs/ads.txt, 정적 페이지 재생성(docs/*/index.html, docs/notice/*), tools/static_fragments.json
- 확인: pytest, 모든 정적 페이지에 메타 1줄만 추가된 것 확인, 배포 후 https://cheongyakpass.kr/ads.txt·메타 확인
- 기능: 없음(설정) — 화면 변화 없음, 버전 그대로
- 백업: backup/20261002-0804-adsense

## 2026-10-02 06:45 · 청약봇을 '청약 도우미'로: 오른쪽 아래 둥근 버튼 + 청약 전반 질문 + 공고문에서 서류 찾아 답하기
- 요청: 써 보니 '이 공고 물어보기'보다 청약 전반에 답하는 용도로, 화면 오른쪽 아래 동그란 버튼 → 팝업 창, '필요한 서류' 질문에 '공고문 참고'라고만 하지 말고 공고문을 확인해 서류를 알려줄 것
- 원인: 서버 근거가 공고문 발췌(rules-evidence, 자격 키워드 주변만)라 서류 문단이 없었고, 서류 질문은 고정 문구('공고문의 제출 서류 항목에서 확인하세요')로 답했음
- 변경:
  · 근거 새로 만듦: docs/chat-law.json(주택공급에 관한 규칙 조문·별표 1·2, 165조각, chat/tools/build_law.py), docs/chat-notice/<공고번호>.json(모집공고문 전체를 약 800자 조각으로, app/notice_chunks.py —
    매일 수집 때 공고문을 읽으면 저장, 조각이 없는 공고는 한 번 다시 읽음, 기능 chatbot_notice). 지금 있는 50건은 evidence/notices 원문으로 미리 만듦
  · 서버(chat/worker): 판정(engine) 없이도 질문을 받음(청약 전반), 근거 찾기 retrieve.js(질문 낱말+청약 용어 넓히기, 순위·가점·특공·재당첨 등 핵심 조문 우선, '특별공급 종류'는 조문 목록),
    프롬프트 v2(공고 질문은 공고문 조각에서 서류 이름 등을 직접 정리, '공고문 확인하세요'로만 끝내지 않기, 판정 없으면 verdict null), 검사기는 판정 없는 답이 판정을 지어내면 막음,
    AI 없이 답할 때는 찾은 공고문·법령 조각을 그대로 보여줌(고정 문구 대신). 답 길이 900→1400 토큰
  · 화면: 기능 chat_fab — 모든 화면 오른쪽 아래 둥근 버튼(상세에서는 아래 고정 버튼 위) → '청약 도우미' 창. 공고 화면에서 열면 '이 공고 기준: 이름' 표시(누르면 끄고 켬, 대화 새로),
    내 조건이 있으면 판정도 함께, 목록에서 열면 청약 전반 빠른 질문(1순위 조건·가점 계산·특별공급 종류·재당첨). 공고 상세의 '이 공고 물어보기' 버튼은 숨김. 판정 상자는 판정이 있을 때만
  · 예전 공고별 근거 docs/chat-evidence·split_evidence 삭제(쓰지 않음)
- 파일: chat/worker/src/{index,retrieve,prompt,validate,fallback,llm}.js, chat/test/chat.test.mjs, chat/tools/build_law.py, app/notice_chunks.py, app/pipeline.py, docs/chat-law.json, docs/chat-notice/*, docs/index.html, docs/config.json, tools/qa/chatflow.cjs, tests/test_notice_and_notify.py, .github/workflows/probe.yml
- 확인: 청약봇 서버 시험 36/36(일반 질문·서류 질문·판정 지어내기 차단 새 시험), 골든셋 270/270(두 방식), pytest 134, 판정 사례 256/256, 회귀 판정 차이 0·오류 0, 엔진 잠금 그대로,
  화면 검사 chatflow 300/300(둥근 버튼: 목록 청약 전반 답·판정 상자 없음·법령 출처 / 상세 '이 공고 기준'·서류 질문에 공고문 서류 내용), 390px 화면 확인
- 기능: chat_fab, chatbot_notice
- 버전: v1.37.0 (내부 — 미리보기)
- 백업: backup/20261002-0645-chatgeneral

## 2026-10-02 06:30 · 청약봇 미리보기 연결 + 운영 명령(!점검·!오픈) + 월 사용액 안전장치
- 요청: 미리보기 연결, ① 인당 하루 2회(꼼수 방지) ② 월 한도 $20 확인 ③ '!점검' → 청약봇 끄고 점검 모드 ④ '!오픈' → 켜고 정상 동작
- 변경(기능 chatbot, 스위치는 꺼진 채):
  · docs/config.json chat_api = 배포된 청약봇 서버 주소(chat/deployed.json, AI 키 있음) → ?chat=preview + 미리보기 코드 기기에서 바로 사용
  · ① 기기 번호(지우면 새로 생김)와 별도로 같은 인터넷 주소 하루 3번(6→3, 공유 와이파이 여유 1), 기기당 2번, 사이트 하루 100번, 되물음 공짜는 질문당 2번까지
  · ② 콘솔 월 한도($20, 사용자가 설정)는 Anthropic 쪽이라 여기서 읽을 수 없음 — 서버에 이중 안전장치: 이번 달 추정 사용액(토큰×Haiku 단가)이 $18(CHAT_MONTH_USD)에 닿으면 AI 를 부르지 않고 판정 결과로 만든 기본 답만
  · ③④ 미리보기 코드가 맞는 기기에서 대화창에 '!점검'/'!오픈'/'!상태' → 서버 KV mode 저장(횟수에 안 셈, 응답에 이번 달 추정 사용액). 점검 중이면 운영자 포함 모두 '점검 중' 안내·이용자 화면은 버튼 숨김.
    '!오픈' 은 서버를 열고, 화면은 /health 로 상태를 읽어 방침 시행일(chat_legal_date) 이후면 스위치 없이도 모두에게 버튼을 보임 — 시행 전에는 미리보기 기기만
- 파일: chat/worker/src/index.js, chat/worker/src/limits.js, chat/test/chat.test.mjs, docs/index.html, docs/config.json, tools/qa/chatflow.cjs
- 확인: 청약봇 서버 시험 33/33(명령·점검·IP 3번·월 한도 새 시험), 골든셋 270/270, pytest 133, 판정 사례 256/256, 회귀 판정 차이 0·오류 0, 화면 검사 chatflow 102/102(운영 명령 5개 포함), 엔진 잠금 그대로
- 기능: chatbot
- 버전: v1.36.2 (내부)
- 백업: backup/20261002-0630-chatops

## 2026-10-02 06:06 · 공고문을 못 읽은 공고는 운영자 알림(이슈)으로
- 요청: 여의재 1단지처럼 공고문을 놓치지 않도록 앞으로도 반영
- 변경: ① (앞 커밋) 첨부가 PDF 가 아니면 공고 페이지를 Referer 로 다시 받기 — 코드에 계속 남아 매 수집에 적용
  ② app/pipeline.py — 이번에 못 읽었고 보관 기록·지난 값도 없는(한 번도 못 읽은) 공고는 run-log 에 '[경고] 공고문을 읽지 못한 공고: 이름 (번호) — 이유' → collect.yml 이 이슈로 알림(시간 제한으로 못 읽은 건 다음 실행에 다시 읽으므로 제외)
  ③ 운영 스킬에 함정 기록
- 파일: app/pipeline.py, tests/test_notice_and_notify.py, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: pytest(새 시험: 못 읽은 공고 → [경고] 줄) 통과, 수집 실행 run-log 확인
- 기능: 없음(수정)
- 백업: backup/20261002-0606-pdfwarn

## 2026-10-02 06:00 · 청약봇 서버 첫 배포
- 요청: Anthropic API 키 등 청약봇 연결 준비를 마쳤으니 후속 작업 진행
- 변경: chat/worker/wrangler.toml 에 주석 한 줄 — chat-worker.yml 이 chat/worker/** 변경에 돌아 배포(비밀값 확인 → KV cheongyakpass-chat → wrangler deploy → 비밀값 넣기 → 확인 → chat/deployed.json). 이어서 config.json chat_api 에 주소를 넣음(스위치 chatbot 은 꺼진 채, 미리보기만)
- 파일: chat/worker/wrangler.toml
- 확인: 청약봇 시험(Actions 단계) · 배포 확인 단계(/health, 토큰 없는 /stats 401, 다른 사이트 403)
- 기능: chatbot
- 백업: backup/20261002-0600-chatdeploy

## 2026-10-02 05:59 · 공고문 첨부를 Referer 와 함께 다시 받기
- 요청: 오남역 서희스타힐스 여의재 1단지 공고문 수집 실패 원인
- 원인(앞 커밋의 기록으로 확인): 첨부 주소가 PDF 대신 59바이트 HTML(text/html)을 돌려줌 — 바로 받기를 막는 응답으로 보임
- 변경: 첫 응답이 PDF 가 아니면 공고 페이지 주소를 Referer 로 붙여 한 번 더 받음. 그래도 HTML 이면 그 내용 앞부분을 run-log 에 남김(다음 대응 근거). 판정 로직 변경 없음
- 파일: app/notice_pdf.py, tests/test_notice_and_notify.py
- 확인: pytest(새 시험: Referer 없이 HTML·있으면 PDF → 읽음) 통과, 수집 실행 run-log [공고문] 줄 확인 예정
- 기능: 없음(수정)
- 백업: backup/20261002-0559-pdfref

## 2026-10-02 05:55 · 공고문 PDF 를 못 읽었을 때 원인을 기록에 남기기
- 요청: 오남역 서희스타힐스 여의재 1단지(2026910253) — 모집공고문에 거주 요건이 있는데 왜 수집 못 했나
- 원인 조사: run-log '[공고문] … PDF 받기 실패(형식 아님)'. 청약홈이 준 첨부(atchmnflSn=3)는 응답 200 이지만 ① PDF 가 아니거나(HWP 등) ② 글자를 못 뽑는 PDF(스캔 이미지, 글자 500자 이하)였는데 둘 다 '형식 아님'으로만 남아 구분 불가. 작업 환경에서는 청약홈에 접속이 막혀 직접 확인 못 함
- 변경: app/notice_pdf.py — 실패 이유를 '글자를 못 읽는 PDF(스캔 이미지 추정, 글자 n자)' 또는 'PDF가 아닌 파일(HWP·ZIP/HWPX·HTML, 형식, 크기)'로 기록. 판정·추출 결과는 그대로. 다음 수집 run-log 로 원인 확정 후 대응(HWP 읽기 또는 스캔 OCR)
- 파일: app/notice_pdf.py, tests/test_notice_and_notify.py
- 확인: pytest(새 시험: HWP 첨부면 'HWP' 기록) 통과
- 기능: 없음(수정)
- 백업: backup/20261002-0555-pdfdiag

## 2026-10-02 01:01 · 무순위 공고에 가점 안내가 나오던 것 수정
- 요청: 무순위처럼 가점이 필요 없는 공고에 '내 가점 입력 필요', 가점제 순서·당첨선 설명이 나와 무순위 설명과 안 맞음 — 다른 곳도 무순위는 가점 없이 추첨
- 원인: 판정 칸의 '내 가점' 칸과 일반공급 칸의 '뽑는 방식' 줄이 청약통장이 필요 없는 공고(무순위·잔여세대, needAccount=false)를 가리지 않고 민영 1순위 가점제 기준으로 그림 (판정 값은 원래 맞음)
- 변경(표시만, 판정 변경 없음): 무순위 공고는 ① 판정 칸에 '뽑는 방식: 추첨 (가점 없음)'(내 가점 칸 없음) ② 일반공급(무순위) 칸 '참고 · 뽑는 방식과 내 위치'를 '청약통장·가점 없이 추첨으로 뽑아요 —
  무순위(사후접수·잔여세대)는 통장·가점과 상관없이 공고문 신청 자격(거주지·무주택 등)을 갖춘 사람 중 추첨'으로(지역 순서 없으면 그 문장도) ③ 가점 컷 탭 관심 공고 카드 문구 '청약통장·가점 없이 추첨으로 뽑는 공고예요'
  ④ 구역 탭 이름을 공고 종류대로('무순위'), 특별공급이 없는 공고는 '특별공급' 탭 없앰. 참고 칸 제목을 공급 이름과 상관없이 '참고 · 뽑는 방식과 내 위치'로
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow 통과, 청약봇 화면 검사 통과, 충정로역자이르네 84A 상세·가점 컷·목록에서 '가점' 문구는 '가점 없음/없이 추첨'만, 390px 밝은·어두운 넘침·오류 0
- 기능: 없음(수정) — detail_tidy·supply_split 표시 수정
- 버전: v1.36.1
- 백업: backup/20261002-0101-mu

## 2026-10-02 00:55 · 내 청약 가점·근처 경쟁률을 일반공급 칸 안으로
- 요청: 일반공급 칸에 가점 정보가 있으면 좋은데 '내 청약 가점'이 따로 떨어져 있음 — 하나로 합치기
- 변경: 기능 score_in_general (supply_split 이 켜졌을 때). 일반공급 칸 안 '참고 · 뽑는 방식과 내 위치' 아래에 접는 칸 2개: '내 가점 33점 / 84 · 최근 해당지역 당첨선 49점'(펼친 채 — 눈금·당첨선 비교·항목별 점수·계산 방법, 예전 내 청약 가점 칸 그대로),
  '근처 최근 경쟁률 · n곳'(접힘 — 예전 근처 경쟁률 칸 그대로). 따로 있던 두 칸과 구역 탭 '가점·경쟁률' 없앰(탭: 요약·일반공급·특별공급·위치·제약), 판정 칸의 '내 가점'을 누르면 일반공급 칸으로. 계산 변경 없음. 끄면 예전 구성
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182, 청약봇 화면 검사 121/121, 390px 밝은·어두운(가점 있음·계산 전) 넘침·오류 0
- 기능: score_in_general
- 버전: v1.36.0
- 백업: backup/20261002-0055-scorein

## 2026-10-02 00:40 · 자격을 '일반공급'·'특별공급' 카드로 나누기
- 요청: 자격 체크리스트(사실상 일반공급)와 공급 유형별 내 자격과 위치(대부분 특별공급)를 일반공급/특별공급으로 나눠 보기. 일반공급에도 신청 가능·확인 필요·불가 표시, 지금 설명(지역 순서·가점제→추첨제)은 참고로 유지
- 변경: 기능 supply_split. ① '자격 체크리스트' → '일반공급' 카드: 제목 옆에 판정(신청 가능·확인 필요·2순위만 가능·신청 불가·판정 전), 조건 수, 판정 문장,
  '참고 · 뽑는 방식과 내 위치'(예전 공급 유형별 칸의 일반공급 줄 그대로 — 내 순서·①가점제→②추첨제·내 가점 위치·근거), 조건 목록·바로 답하기 그대로. 중복이던 '일반공급 조건'·'일반공급 ·' 앞말 뺌.
  ② '공급 유형별 내 자격과 위치' → '특별공급' 카드: 특별공급 유형만 + '특별공급 1개와 일반공급 1개는 함께 신청 가능 · 공통 조건은 위 일반공급 카드' 한 줄.
  ③ 구역 탭 '자격' → '일반공급'·'특별공급', 판정 칸의 특별공급 칸을 누르면 특별공급 카드로. 판정·계산 변경 없음. 끄면 예전 구성
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182, 청약봇 화면 검사 121/121,
  390px 밝은·어두운(가점 있음 '확인 필요', 통장 없음 '2순위만 가능') 넘침·오류 0
- 기능: supply_split
- 버전: v1.35.0
- 백업: backup/20261002-0040-split

## 2026-10-02 00:32 · 자금 플랜 버튼을 아래 고정 버튼 줄로
- 요청: '자금 플랜 보기'도 청약홈 배너(아래 고정 버튼) 옆에
- 변경: 기능 detail_cta 개선. 아래 고정 버튼 줄을 '모집공고문 · 자금 플랜 · 청약홈 공고 ↗' 3개로(자금 플랜은 이 공고 자금 계획 화면). 상세 맨 아래의 '자금 플랜 보기' 버튼은 숨김(같은 버튼). 버튼 글자를 줄여 한 줄에. 끄면 예전과 같음
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 스크립트 문법, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 390px 밝은·어두운 상세 넘침·오류 0
- 기능: detail_cta
- 버전: v1.34.1
- 백업: backup/20261002-0032-cta2

## 2026-10-02 00:07 · 공고 상세 겹치는 내용 정리
- 요청: 아래 고정 버튼에 공고문·청약홈이 있으니 위 버튼 3개 삭제, '마진 계산 자세히'를 누르면 실제 계산이 보이게 하고 따로 있는 마진 계산 칸은 삭제, 가운데 타일 3개는 위 '확인 필요' 큰 칸과 통합,
  기능을 빠르게 붙이며 생긴 중복·반복 내용을 모두 찾아 통합해서 줄이기
- 변경: 기능 detail_tidy (공고 상세 화면 구성만, 판정·계산 변경 없음).
  ① 제목 아래 '모집공고문 PDF·청약홈 공고·네이버 지도' 버튼 숨김(아래 고정 버튼과 같음, 지도는 '위치와 주변 입지'에 있음), 맨 아래 '모집공고 (청약홈)' 버튼도 숨김
  ② 맨 위 '내 판정' 칸에 작은 칸 3개(내 가점·자금·특별공급, 누르면 그 구역으로) — 가운데 타일 3개(자격·마진·자금)와 판정 칸 안의 마진·자금 문장을 대신함
  ③ 마진 계산 칸을 가격 비교 카드 안 '마진 계산 자세히'(펼치면 분양가→실매입가→시세 계산·근거 거래)로 옮기고 따로 있던 마진 칸·구역 탭 '마진' 삭제
  ④ '이 공고 주택형 중 위치' 카드를 가격 비교 카드 안 한 줄('주택형 7개 중 마진 2위 · 신청 가능 n개') + '주택형별 마진 보기'로 합침
  ⑤ 자격 체크리스트 위 요약(일반공급·특별공급·지역 순서)은 맨 위 판정·공급 유형별 칸과 같아 숨김, '특별공급 세대수' 칸은 공급 유형별 칸에 유형마다 세대수가 있어 숨김,
     공급 유형별 칸의 일반 설명 문단 숨김, '내 청약 가점'의 ①가점제→②추첨제 설명은 공급 유형별 칸에만 두고 가점 칸은 당첨선 비교 한 줄로
  화면 높이(광명 59A): 체크리스트 1,346→1,016px, 가점 1,213→774px, 마진 칸 895px·주택형 카드 408px·타일 95px·특공 세대수 189px 없어짐. 끄면 예전 구성
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182(바로 답하기 그대로), 청약봇 화면 검사 121/121, 390px 밝은·어두운 상세(판정 칸·가격 비교·펼친 자세히) 넘침·오류 0
- 기능: detail_tidy
- 버전: v1.34.0
- 백업: backup/20261002-0007-dedupe

## 2026-10-01 23:50 · 목록의 베타·개정 안내를 ✕ 로 닫기
- 요청: 베타며 알림(개정 안내)은 ✕ 를 눌러 지울 수 있게
- 변경: 기능 dismiss_notes. 공고 목록의 베타 안내 줄과 '10월 9일부터 개인정보처리방침·이용약관이 바뀌어요' 줄 오른쪽에 ✕. 누르면 이 기기에서 목록에서만 숨김.
  공고 상세의 '참고용' 안내와 방침·약관 화면의 개정 예고는 그대로 보임(고지 의무). 자동 검증에 문제가 생기면 베타 경고는 다시 보임. 개정 안내는 새 개정 예고가 오면 다시 보임. 끄면 예전과 같음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 브라우저: ✕ 두 번 → 두 줄 사라짐·상세 안내는 남음, 390px 밝은·어두운 넘침·오류 0
- 기능: dismiss_notes
- 버전: v1.33.0
- 백업: backup/20261001-2350-compact

## 2026-10-01 23:50 · 맨 위 필터·내 조건·요약을 작게 (카드가 첫 화면에)
- 요청: 필터에서 모집 상태·새 공고 빼고 초기화를 기호로 옆에, 필터 크기를 줄이고(너무 커서 아래 카드가 안 보임), 내 조건 칸 크기 최적화
- 변경: 기능 top_compact. 맨 위 필터 줄을 지역·분양가·면적·상세로 줄이고(모집 상태는 '상세' 칸으로, 새 공고는 요약 숫자 '새 공고 7일'로), 줄 오른쪽에 ↻ 초기화 아이콘(조건이 없으면 흐리게).
  필터·등급 칩 높이 36~40 → 32px, 내 조건 칸 여백·글자 줄임, 처음 쓰는 분 안내를 한 줄로('이 기기에만 저장' 문구 합침), 요약 숫자 칸 높이 줄임. 첫 공고 카드 위치 약 690px → 약 480px(390×844 화면). 끄면 예전 크기
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 청약봇 화면 검사 통과, 브라우저: 지역 경기 → ↻ → 초기화·아이콘 흐려짐, 390px 밝은·어두운(조건 있음·없음) 넘침·오류 0
- 기능: top_compact
- 버전: v1.32.0
- 백업: backup/20261001-2350-compact

## 2026-10-01 23:23 · 목록 카드 등급을 원형 배지로
- 요청: 다른 앱의 원형 등급 배지(SS)처럼 (사용자 4번 선택)
- 변경: 기능 grade_medal. 공고 목록 카드 왼쪽의 등급(로또·고려·마진없음·비추천·시세 부족)을 지름 54px 원형 배지로, 아래에 마진율. 색은 등급 색 그대로. CSS 만(화면 구조·계산 변경 없음). 끄면 예전 네모 배지
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·청약봇 화면 검사 통과, 390px 밝은·어두운 목록 넘침·오류 0
- 기능: grade_medal
- 버전: v1.31.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:23 · '이 공고 주택형 중 위치' 카드
- 요청: 다른 앱의 '이 평형 내 순위 1/8'처럼 (사용자 3번 선택)
- 변경: 기능 type_rank. 공고 상세 가격 비교 아래에 같은 공고 주택형을 보수 마진 순으로 줄 세운 카드: 큰 순위 'N / 전체'(가장 큼·가장 작음 안내), '내가 신청 가능한 주택형 n개',
  위 3개 + 지금 주택형(분양가·마진·내 판정 점), 나머지는 '주택형 N개 모두 보기'로 펼침. 줄을 누르면 그 주택형 상세로 바뀜(type_group 과 같은 방식). 주택형이 하나면 없음.
  계산은 grade()·eligBucket() 그대로. 끄면 없음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 광명 84D(7/7)·59A(2/7) 390px 밝은·어두운 넘침·오류 0
- 기능: type_rank
- 버전: v1.30.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:23 · 공고 상세 '가격 비교' 카드
- 요청: 다른 앱의 '적정가 vs 호가' 카드처럼 (사용자 2번 선택)
- 변경: 기능 price_compare. 공고 상세 요약의 '마진 등급' 카드 자리에 '가격 비교' 카드: 시세(보수~기준)와 실매입가(분양가+확장+취득세 등)를 위아래 큰 숫자로,
  원형 등급 배지 + '시세 − 실매입가 · 시세보다 싸요' + 차이(+1.63억 ~ +2.43억)·보수 시세 기준 %, '왜 이 시세'(시세 기준 설명·근거 거래 수·최근 거래일·중앙값/하위 25%), 출처(청약홈 공고·국토부 실거래가), '마진 계산 자세히' 이동.
  숫자는 grade()·수집 시세 그대로(계산 변경 없음). 끄면 예전 마진 등급 카드
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0(모든 공고 상세를 그림), 광명 59A 390px 밝은·어두운 넘침·오류 0
- 기능: price_compare
- 버전: v1.29.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:23 · 공고 상세 아래 고정 버튼 (청약홈 공고·모집공고문)
- 요청: 다른 앱의 '네이버 매물 보러가기'처럼 상세 아래에 늘 보이는 버튼 (사용자 1번 선택)
- 변경: 기능 detail_cta. 공고 상세 화면 아래(하단 메뉴 바로 위)에 고정: '모집공고문'(PDF가 있을 때)과 '청약홈 공고 보기 ↗'(청약홈 공고 화면), 위에 '신청은 청약홈에서 해요 · 신청 전 모집공고문을 꼭 확인하세요'.
  내용이 가리지 않게 상세 화면 아래 여백을 늘리고, 청약봇 대화창이 열리면 숨김. 샘플 공고는 없음. 끄면 예전과 같음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 청약봇 화면 검사·fixfocus 통과, 390px 밝은·어두운 상세 화면 넘침·오류 0
- 기능: detail_cta
- 버전: v1.28.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:23 · 필터를 맨 위(검색 아래)에 펼쳐 두기
- 요청: 다른 앱처럼 알림 자리에 돋보기, 그 아래에 필터 — 필터를 다시 펼쳐 두기 (접힌 '필터 · 판정 등급' 버튼 대신)
- 변경: 기능 top_filters. 공고 목록 제목 아래(검색창을 열면 그 아래)에 지역·분양가·면적·모집 상태·새 공고·상세 칩 한 줄(가로로 밀기, 고른 값이 칩에 보임)과 판정 등급 칩(전체·관심·로또·고려·마진없음·비추천).
  '상세'를 누르면 바로 아래에 시·군·구·공급 구분·날짜 범위 칸. 목록 중간의 접힌 '필터 · 판정 등급' 버튼은 숨김. 필터 동작·결과는 그대로. 끄면 예전 위치·접힘
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 청약봇 화면 검사 통과, 브라우저: 지역 경기 → 1곳, 로또 → 0곳, 상세 → 칸이 필터 바로 아래 1개, 390px 밝은·어두운 넘침·오류 0
- 기능: top_filters
- 버전: v1.27.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:23 · 알림을 아래 탭으로 (맨 위 알림 버튼 자리는 검색)
- 요청: 다른 앱(급매캐치)처럼 알림을 아래 하나의 탭으로 빼고, 알림 자리에 돋보기
- 변경: 기능 alerts_tab. 하단 메뉴에 '알림' 탭(공고·가점 컷·등급 기준·알림·내 조건·이용 안내). 알림 기능이 켜졌을 때(web_push 또는 미리보기)만 보임 — 지금은 운영자 미리보기 기기에서만.
  맨 위 알림 버튼은 숨기고(돋보기만), 알림 화면의 '‹ 공고' 뒤로 버튼도 탭이라 숨김. 탭이 6개면 글자를 조금 줄여 한 줄로. 끄면 예전 맨 위 알림 버튼
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 미리보기 기기에서 탭 6개 한 줄·알림 탭 눌러 알림 화면·현재 탭 표시, 390px 밝은·어두운 넘침·오류 0
- 기능: alerts_tab
- 버전: v1.26.0
- 백업: backup/20261001-2323-ui6

## 2026-10-01 23:14 · 검색을 맨 위 돋보기 버튼으로
- 요청: 다른 앱(급매캐치)처럼 검색 기능을 돋보기로 보여주기
- 변경: 기능 search_icon. 공고 목록 맨 위 오른쪽(알림 버튼 옆)에 돋보기 버튼. 누르면 제목 바로 아래에 검색창이 열리고 입력칸에 바로 커서. 다시 누르면 검색어를 지우고 닫음.
  검색어가 있으면 계속 열려 있음. 목록 중간에 늘 보이던 검색창은 이 기능이 켜지면 숨김. 끄면 예전 위치의 검색창
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 브라우저: 돋보기 → 검색창·포커스 → '광명' 1곳 → 다시 누르면 닫히고 5곳, 390px 밝은·어두운 넘침·오류 0
- 기능: search_icon
- 버전: v1.25.0
- 백업: backup/20261001-2314-search

## 2026-10-01 23:07 · 일반공급 표시를 '신청 가능 → ① 가점제 먼저 → 떨어지면 ② 추첨제' 순서로
- 요청: '가점 부족'·'가점 무관' 표기가 둘 중 하나를 골라 쓰는 것처럼, 가점이 부족하니 쓰지 말라는 것처럼 읽힘 — 쓸 수 있으면 쓸 수 있다고 하고, 물량과 내 가점(평균보다 낮아 추첨으로 갈 가능성)을 '가점 뽑은 뒤 추첨' 방식 근거와 함께
- 변경: 기능 score_lottery_split 표시 개선. 일반공급 줄 표시를 내 판정(신청 가능·확인 필요)으로, 그 아래 '신청할 수 있어요. 한 번 신청하면 가점제로 먼저 뽑고, 떨어지면 따로 신청하지 않아도 추첨제에서 한 번 더 뽑아요' →
  ① 가점제 N%(가점 높은 순 · 내 가점, 최근 당첨선·평균) ↓ 떨어지면 자동으로 ② 추첨제 M%(떨어진 사람까지 함께 가점 없이 추첨 · 무주택 우선 75%) → '내 가점이 당첨선보다 N점 낮아서 ② 추첨제에서 당첨을 노리게 돼요'(높으면 ①에서 먼저, 떨어져도 ②) →
  근거: 모집공고문 가점제·추첨제 적용비율 + HUG 주택청약도우미('가점제 낙첨자는 별도 신청절차 없이 추첨제에 의한 당첨자 선정대상자에 포함하여 추첨', 2026-10-01 화면에서 문장 확인).
  '가점 부족'·'가점 무관'·'추첨제 가능' 꼬리표 없앰. 2순위만인 경우·추첨 0% 주택형은 예전 표시. 공고 상세·가점 컷 관심 공고 카드·내 청약 가점 같은 모양
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow 통과, 광명 59A·기타지역 33점 프로필 390px 밝은·어두운 화면 넘침·오류 0
- 기능: score_lottery_split
- 버전: v1.24.1
- 백업: backup/20261001-2307-split2

## 2026-10-01 22:25 · 같은 공고의 주택형을 카드 하나로 (주택형 칩)
- 요청: 같은 공고인데 평형 타입만 다른 것이 각각 카드로 나와 너무 많음 — 카드 위쪽에서 타입을 골라 카드 하나의 정보가 타입별로 바뀌게. 공고 상세에서도 타입별로 구분하되 복잡하지 않게
- 변경: 기능 type_group. 공고 목록에서 같은 공고(주택관리번호)의 주택형을 카드 하나로 묶고, 카드 위에 주택형 칩(59A·59B·84A…, 면적 순)을 둠. 칩을 누르면 카드의 등급·마진·분양가·내 판정이 그 주택형으로 바뀜.
  칩의 점 색은 그 주택형의 내 판정(초록 가능·노랑 확인 필요/2순위만·빨강 불가). 필터에 맞는 주택형만 칩으로(하나뿐이면 예전 카드). 결과 수는 '결과 5곳 · 주택형 26'.
  공고 상세 제목 아래에 '주택형 N개 · 눌러서 바꿔 보기' 칩 — 누르면 같은 화면에서 그 주택형 상세로 바뀜(뒤로 가기 기록을 쌓지 않고 주소만 바꿈). 판정·등급 계산은 그대로(엔진 잠금 그대로). 끄면 예전처럼 주택형마다 카드
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182, 청약봇 화면 검사 121/121, 변이 300 위반 0,
  브라우저: 목록 26개 주택형 → 5곳, 칩 누르면 카드가 59B 로 바뀜, 상세 칩 7개·84A 로 바꾸면 주소 #/detail/…84A, 뒤로 가기 → 목록, 390px 밝은·어두운 넘침·오류 0
- 기능: type_group
- 버전: v1.24.0
- 백업: backup/20261001-2225-ux5

## 2026-10-01 22:25 · 일반공급을 가점제·추첨제 물량별로 나눠 보여주기
- 요청: 일반공급이 '당첨선 미만'으로만 보여 지원하면 안 되는 것처럼 읽힘 — 추첨 물량 60%도 있으니 가점제·추첨제 물량별로 설명. 가점 컷 탭(관심 공고 카드)은 추첨 물량 언급이 아예 없어 가점제로만 판단하는 느낌
- 변경: 기능 score_lottery_split. 공고 상세 '공급 유형별 내 자격과 위치'의 일반공급 줄, 상세 '내 청약 가점' 비교, 가점 컷 탭 관심 공고 카드에서 일반공급을
  '1순위 가점제 N%'(내 가점 vs 당첨선, '가점 부족'/'당첨선 이상')와 '1순위 추첨제 M%'(가점 무관, 무주택 우선 75% 해당 여부, 공고문 비율 출처) 두 줄로.
  가점이 당첨선보다 낮고 추첨 물량이 있으면 일반공급 표시를 '당첨선 미만' 대신 '추첨제 가능'. 기타지역·경기 몫이면 '가점제·추첨제 모두 해당지역 신청자를 먼저 뽑아요' 한 줄.
  추첨제 무주택 우선(75%)은 규제지역·수도권·광역시만 씀 — evidence/notices 25건 대조(충남·전북·경남 비규제 공고문에는 없음). 비율을 못 읽은 주택형은 '공고문 표 확인'.
  가점제 100%(추첨 0%)·모두 추첨 주택형은 예전 표시 그대로. 판정 값은 바꾸지 않음(엔진 잠금 그대로). 끄면 예전과 같음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 광명 시티프라디움 에듀하임 59A·기타지역 33점 프로필로 상세·가점 카드·가점 컷 탭 390px 밝은·어두운 화면 넘침·오류 0
- 기능: score_lottery_split
- 버전: v1.23.0
- 백업: backup/20261001-2225-ux5

## 2026-10-01 22:25 · 날짜 입력을 년·월·일 드롭다운으로
- 요청: 인터뷰 달력 날짜 설정을 년·월·일 각각 드롭다운으로 (달력이 불편함)
- 변경: 기능 date_select. 인터뷰·바로 답하기의 날짜 칸(생년월일·전입일·세대주가 된 날·혼인신고일·통장 가입일·자녀 생년월일·처분일 등)을 년·월·일 선택 3개로.
  셋 다 고르면 YYYY-MM-DD 로 저장하고 아래에 '1990년 2월 28일', 하나라도 비우면 '입력 안 함'(고르는 중이면 '모두 고르면 저장돼요'). 없는 날(2월 31일)은 그달 마지막 날로.
  연도 범위: 생년월일 최근 90년, 자녀 생년월일 30년~내년, 그 밖 60년. 바로 답하기에서 다시 그려도 고르던 값 유지(DATE_PART), 빨간 칸 포커스는 첫 선택칸. 끄면 예전 달력 입력. (공고 필터의 날짜 범위는 그대로)
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182, 브라우저에서 1990·2·31 선택 → 1990-02-28 저장, 390px 밝은·어두운 화면 넘침·오류 0
- 기능: date_select
- 버전: v1.22.0
- 백업: backup/20261001-2225-ux5

## 2026-10-01 22:25 · 금액 입력칸 아래 '= 2억 1,550만원' 표시
- 요청: 금액을 입력하는 모든 칸 아래에 1억원처럼 바꿔 보여 주기 (바로 답하기 자산 칸에 5000 을 넣어도 얼마인지 안 보임)
- 변경: 기능 money_echo. 만원 단위 입력칸(인터뷰·바로 답하기의 금액 칸, '입력 안 함'이 되는 선택 금액 칸, 자금 계획의 가족 지원·전세 보증금) 아래에 입력하는 대로 '= 2억 1,550만원', '= 5천만원'.
  예전에는 일부 칸만 '= 2.16억'으로 보였고 선택 금액 칸(자산·자동차 등)·자금 계획 칸에는 없었음. 끄면 예전과 같음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow·fixfocus 1182/1182, 390px 밝은·어두운 화면(21550 → '= 2억 1,550만원') 넘침·오류 0
- 기능: money_echo
- 버전: v1.21.0
- 백업: backup/20261001-2225-ux5

## 2026-10-01 20:57 · 청약봇 '이 공고 물어보기' (꺼진 채로, 운영자 미리보기)
- 요청: 청약봇 계획 승인(추천대로: 캐시 없이 시작·7일 예고+첫 사용 동의·하루 2건/사이트 100건/AI 호출 200·콘솔 한도 $30·미리보기 코드) + 사용자가 준 시제품(chatbot-proto.zip, 설계 Phase 1)을 바탕으로 진행. zip 에 HANDOFF-PROMPT.md 는 없어 README 와 승인한 계획대로 함
- 변경: 기능 chatbot (스위치 false, chat_api 비어 있음).
  · chat/ — 시제품 서버(검사기·근거 지도·프롬프트 v1·고정 문구 답·제한·가리기·분류)를 그대로 가져오고 더함: 공개 전 미리보기 코드 잠금(CHAT_OPEN), 하루 합계 stats.js(개인 식별 없음)·/feedback(평가 이유 7가지)·/stats(토큰)·/health,
    IP·기기 번호 해시에 비밀 소금+날짜, 되물음 공짜는 질문 1건당 2번까지(시제품은 답이 계속 되물으면 무제한이던 구멍), 근거는 공고별 작은 파일 docs/chat-evidence/<번호>.json 만 받음(2.4MB 전체는 Worker CPU 10ms 한도 초과).
  · 화면 docs/index.html — 공고 상세 '내 판정' 아래 '이 공고 물어보기' 버튼 → 아래에서 올라오는 대화창. 첫 사용 동의(국외 이전·가림·저장 안 함·참고용), 빠른 질문 4개,
    답 형식 결론→내 조건 기준→이유→공식 기준→주의할 점→출처(근거 번호·원문 보기)→되물음→고정 안내, 👍👎+이유 7가지, '정보가 틀렸어요'는 지금 조건으로 판정을 다시 돌려 비교,
    보내기 전 개인정보 가림, 서버 답의 판정이 화면 판정과 다르면 보여주지 않음, 대화는 메모리에만(닫거나 다른 화면이면 사라짐). ?chat=preview + 코드로 운영자만.
  · 판정 엔진은 읽기만: tools/engine_lock.py + tests/test_engine_lock.py 가 판정 함수 28개 지문을 비교(작업 전 백업과 같음 확인).
  · 배포 .github/workflows/chat-worker.yml (알림 서버와 별도 Worker·KV cheongyakpass-chat, 비밀값 없으면 배포 안 함), probe.yml 이 근거를 공고별로 나눔, collect.yml 이 [청약봇] 하루 합계를 run-log 에.
  · 시제품 README 의 '/home/claude/cheongyak/…' 기본 경로를 저장소 기준으로 고침
- 파일: chat/**, docs/chat-evidence/*, docs/index.html, docs/config.json, docs/about·privacy·story·terms/index.html, tools/static_fragments.json, tools/engine_lock.py, tools/engine_lock.json, tests/test_engine_lock.py, tools/qa/chatflow.cjs, .github/workflows/chat-worker.yml·probe.yml·collect.yml, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 130(엔진 잠금 2 포함), 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 변이 400 위반 0, 바로 답하기 fixflow·fixfocus 1182/1182, 알림 서버 시험 통과,
  청약봇 서버 시험 30/30, 골든셋 270/270(AI 없이·미리 쓴 답), 화면 검사 chatflow 529/529(공고 40×프로필 3 답 판정=화면 판정 126/126, 390px 밝은·어두운 넘침 0, 스위치 끄면 버튼·방침 문구 없음, 미리보기 코드, 하루 2건, 되물음, 평가, 변조 판정 차단, KV 에 질문·전화·IP 없음)
- 아직: 실제 Claude 답 품질(키 받은 뒤 골든셋 실제 실행), 배포(사용자 비밀값 3개), 공개(10-09 시행 후 CHAT_OPEN·스위치)
- 기능: chatbot
- 버전: v1.20.0 (내부 — 공개 전이라 업데이트 소식에 안 보임)
- 백업: backup/20261001-2057-chatbot

## 2026-10-01 20:57 · 개인정보처리방침·이용약관 개정 예고 (새 공고 알림·AI 질문 답변, 10월 9일 시행)
- 요청: 청약봇 계획 승인 — 방침 개정은 '7일 예고 + 첫 사용 동의'로, 이미 잘 오는 새 공고 알림의 방침 개정도 같이 진행
- 변경: 기능 legal_notice. config.json legal_notice(시행 2026-10-09, 게시 2026-10-01, 바뀌는 점 목록)로 방침·약관 맨 위에 '개정 예고' 카드(바뀌는 점 + '바뀐 뒤 전문 보기'),
  공고 목록 베타 안내 아래 한 줄, 이용 안내 문서 줄에 '개정 예정'. 전문은 LEGAL_AS 로 알림·청약봇이 켜진 상태의 실제 개정안을 그림. 시행일이 지나면 예고는 저절로 사라짐.
  청약봇(chatOn = chat_api + 스위치 chatbot) 방침 문구 추가: 처리 항목(가린 질문·공고 번호·판정 요약·앞선 대화, IP 해시), 목적, 보유(운영자 보관 안 함, Anthropic 30일 내 삭제·학습 안 함, IP 해시 다음 날 삭제, 합계 1년),
  4-3 처리 위탁·국외 이전(Anthropic PBC·Cloudflare, 미국), 외부 서비스 표, 권리, 안전성. 약관 제4조 AI 답변 성격·이용 제한, 제6조 개인정보 적지 않기·반복 호출 금지.
  개정 이력은 같은 날 개정을 한 줄로 묶음(legalRevs). 청약봇 기능 자체는 아직 없음(chat_api 비어 있음) — 방침 문구는 기능이 켜질 때만 보임
- 근거: Anthropic API 입출력 30일 내 삭제 privacy.claude.com/en/articles/7996866, 학습 금지 anthropic.com/legal/commercial-terms ('Anthropic may not train models on Customer Content from Services'), 문의 privacy@anthropic.com (anthropic.com/legal/privacy)
- 파일: docs/index.html, docs/config.json, docs/privacy/index.html, docs/terms/index.html, docs/about/index.html, docs/story/index.html, tools/static_fragments.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 128, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 390px 밝은·어두운 화면(목록 한 줄·방침·약관 예고 카드·전문 펼침) 넘침·오류 0
- 기능: legal_notice (예고는 켜야 의미가 있어 처음부터 켬 — 사용자 승인)
- 버전: v1.19.0
- 백업: backup/20261001-2057-chatbot

## 2026-10-01 20:05 · 기록 정리 (v1.18.0)
- 요청: CLAUDE.md 6·8항 — FEATURES 커밋 번호, HANDOFF 진행 중인 일
- 변경: FEATURES.md fix_focus 커밋 번호, HANDOFF 에 v1.18.0 과 새 문구 연결 규칙
- 파일: FEATURES.md, HANDOFF.md
- 확인: 커밋 번호 대조
- 기능: 없음(수정)
- 백업: backup/20261001-2004-fixfocus

## 2026-10-01 20:05 · 바로 답하기: 필요한 칸 표시·커서 이동·저장 후 접기
- 요청: 바로 답하기를 누르면 해당 질문이 빨갛게 표시되고 커서가 그 칸으로, 닫기 말고 저장 버튼을 누르면 다시 접히게 (화면: 신혼희망타운 '부동산에 부모님 집 넣기 필요'를 눌렀는데 부동산 칸은 '이미 넣은 값'에 접혀 있었음)
- 변경: 기능 fix_focus. '확인 필요' 문구 → 질문 연결표(FIX_TARGETS)로 지금 판정에 필요한 칸을 찾아(값이 이미 있어도) 맨 위에 빨간 테두리 + '이 칸을 넣으면 판정돼요'로 표시, 아직 비어 있는 칸도 같은 표시. 열면 그 칸으로 스크롤하고 입력칸에 포커스(0 같은 기존 값은 선택). '닫기' → '저장' 버튼: 누르는 순간(pointerdown) 처리해 입력칸 포커스 이탈로 화면이 다시 그려져 클릭이 사라지는 문제를 피함, 접고 그 항목으로 돌아가 1.6초 강조. 검사 도구 tools/qa/fixfocus.cjs
- 파일: docs/index.html, docs/config.json, tools/qa/fixfocus.cjs, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 사용자 화면과 같은 경우(성남복정2 신혼희망타운, 60세 부모 집, 부동산 0)에서 부동산 칸이 빨갛게 맨 위·포커스·0 선택 → 20000 입력 → 저장 → 접힘·총자산 '충족'. 버튼 1,182개 전부 빨간 칸 표시·저장 후 접힘, 바로 답하기 흐름 2,918개 전부 판정, 판정 사례 256/256, 회귀 판정 차이 0·화면 1,287개 오류 0, 스크립트 문법, pytest 128
- 기능: fix_focus
- 버전: v1.18.0
- 백업: backup/20261001-2004-fixfocus

## 2026-10-01 19:53 · 기록 정리 (v1.17.0)
- 요청: CLAUDE.md 6·8항 — FEATURES 커밋 번호, HANDOFF 진행 중인 일
- 변경: FEATURES.md optional_inputs 커밋 번호, HANDOFF 에 사용자 방침(드문 질문은 비우면 해당 없음)과 새 질문 만들 때 규칙
- 파일: FEATURES.md, HANDOFF.md
- 확인: 커밋 번호 대조
- 기능: 없음(수정)
- 백업: backup/20261001-1953-optin

## 2026-10-01 19:53 · 해당하는 분만 답하는 질문 (비우면 해당 없음)
- 요청: 드물게 해당하는 질문은 안 적으면 '해당 없음'으로 넘어가고 해당하는 사람만 기입하게. 모든 질문을 필수/선택으로 구별해 목록화
- 변경: 기능 optional_inputs. ① 판정 직전 기본값 optDefaults: 임신·만 65세 부모 부양·3세대·예비신혼/한부모·주택 소유 예외는 비우면 해당 없음, 당첨 이력은 비우면 없음(예전 '5년 내 당첨' 답 우선), 집이 없으면 부동산 0, 신혼희망타운 부채 0, 보험·기타 자산은 비우면 0이되 총자산이 기준의 90% 를 넘으면 다시 물음 ② 질문에 '해당하는 분만 · 안 고르면 ○○' 표시, 내 조건 '비어 있음' 개수에서 뺌 ③ 새 질문: 주택 소유 예외(규칙 제53조 1·5·9호 — 9호는 2026.6.15 원문상 빌라 등 85㎡·수도권 5억 이하도 포함, 특별공급·공공분양에도 적용), 배우자 주택 처분일(별표1 3), 특별공급 당첨 여부(제55조)·2년 내 가점제 당첨(제28조⑥) ④ 집 질문 문구에 공유지분·상속 지분, 소득 질문에 '지금 월급이 크게 다르면 지금 기준' 안내(감사 O1~O4). 자녀가 있으면 가장 어린 자녀 생일은 필수로(자녀 수 0이면 안 보임). 판정 사례 3건은 사용자 방침에 따라 기대값을 바꿈(당첨 이력·예비신혼·임신 여부를 비우면 해당 없음), 새 사례 20건
- 파일: docs/index.html, docs/config.json, tools/make_judge_cases.py, tests/judge/cases.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 판정 사례 256/256, 변이 검사 11,295건 위반 0, 회귀 1,030조합 판정 변경 18건(신혼희망타운: 자산 칸 비움 → 가능 9, 미혼·유형 미선택 → 불가 9, 의도한 변화)·화면 1,287개 오류 0, 바로 답하기 2,918개 전부 판정, 질문 화면(390px 밝은·어두운, 넘침 0), 스크립트 문법, pytest 128
- 기능: optional_inputs
- 버전: v1.17.0
- 백업: backup/20261001-1953-optin

## 2026-10-01 19:08 · 판정엔진 감사보고서·근거·감사 도구 저장
- 요청: 판정엔진 감사보고서 작성 (v1.16.1 수정의 근거 기록)
- 변경: evidence/audit/2026-10-01-engine/ — REPORT.md(①~⑮), 법령·공고문 대조 보고서 3편, 블라인드 160건(사례·검토자 판정 4·감사 전후 앱 판정·지표). 감사 도구 tools/qa/audit/audit_gen2.cjs(층별·일관된 프로필), brief2.md, rejudge.cjs. HANDOFF 진행 중인 일·운영 스킬 함정 추가
- 파일: evidence/audit/2026-10-01-engine/, tools/qa/audit/audit_gen2.cjs, tools/qa/audit/brief2.md, tools/qa/audit/rejudge.cjs, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 보고서 수치를 지표 파일(blind160/metrics.json)·판정 사례 수·정답 데이터 수와 대조
- 기능: 없음(수정)
- 백업: backup/20261001-1908-audit

## 2026-10-01 19:08 · 판정엔진 감사 — 법령·공고문과 어긋난 규칙 29건 수정
- 요청: 판정 알고리즘을 해부해 공식 기준(법령·공고문)과 대조하고, 경계값·변이·실제 공고 정답 테스트로 정확도를 측정해 고치고 감사보고서 작성
- 변경: 법령·공고문 대조 검토자 3명 + 블라인드 검토자 4명(실제 공고 40건 × 프로필 160건)으로 찾은 오류 수정. CRITICAL 2(예비신혼부부 예비 배우자 미확인 → 확인 필요, 특공 재당첨 제한 무시), HIGH 8(가점 세대원 주택·미성년 가입기간 제10조⑥, 공공 생애최초·노부모 1순위, 신혼희망타운 자격 소득 200%·세대주·순위, 부모님 소득 누락, 규제지역 세대주 추정은 1순위 요건, 특공 1회), MEDIUM·LOW 19(비규제 민영 재당첨, 2026000436 세대주 오인식, 청약저축 2순위, 미입력값을 '없음'으로 본 것, 공공 신혼 6세 이하·예비·한부모, 생애최초 1인 가구, 자동차 완화 표 값, 공공 청약저축, 60세 부모 집 자산 포함 등). 수집: 세대주 문장에서 노부모 칸 제외, 신혼희망타운 자격 소득 상한(eligible) 읽기, 신혼희망타운 세대주 추정 안 함(PARSER_VERSION 11). 공고문 대조에 공공 출산가구 완화 표(RELAX_TABLE) 추가. 판정 검증 사례 175 → 236건(새 사례 기대값은 공고문·법령 표로 계산, 테스트용 규제지역 변형 공고 2건), 판정 사례 실행기에 항목 판정(item) 추가, 변이 검사 도구 tools/qa/mutation.cjs
- 파일: docs/index.html, app/notice_pdf.py, app/pipeline.py, app/crosscheck.py, tests/golden/notices.json, tests/judge/cases.json, tests/judge/listings.json, tests/test_special_rules.py, tools/make_judge_cases.py, tools/judge_check.cjs, tools/qa/mutation.cjs, docs/changelog.json, VERSIONS.md
- 확인: 판정 사례 236/236, 블라인드 160건 일반공급 FP 0·FN 0(감사 전 FN 1·잘못 단정 2), 가점 76/76(감사 전 62/76), 변이 검사 16,914건 위반 0, 회귀 1,030조합 판정 변경 4건(성남복정2 신혼희망타운 불가→확인 필요)·화면 1,287개 오류 0, 바로 답하기 2,995개 중 2,973 판정, 스크립트 문법, pytest 128, 정답 데이터(2026000436 세대주·신혼희망타운 4건 자격 소득) 추가. 보고서 evidence/audit/2026-10-01-engine/REPORT.md
- 기능: 없음(수정)
- 버전: v1.16.1
- 백업: backup/20261001-1908-audit

## 2026-10-01 18:43 · 기록 정리 (v1.15.0·v1.16.0)
- 요청: CLAUDE.md 6·8항 — FEATURES 커밋 번호, HANDOFF 진행 중인 일, 운영 스킬 요령
- 변경: FEATURES.md tap_affordance 커밋 번호, HANDOFF '진행 중인 일'에 v1.15.0·v1.16.0, 스킬에 '공고문 새 항목 읽기 순서'·'가점 비교는 지역 순서 먼저'
- 파일: FEATURES.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 수집 실행(f2e91e0) 성공 — 민영 일반공급 122건 중 117건 비율 읽음, 5건(더샵 시에르네 2026000436 표 글자 뒤섞임) [검증] 에 남음, 정답 불일치 0, 공고문 불일치 0, verify-status ok true
- 기능: 없음(수정)
- 백업: backup/20261001-1843-b

## 2026-10-01 18:43 · 접힌 칸을 버튼처럼 보이게
- 요청: 바꾼 화면에서 '충족한 조건 5개'·'근거와 출처' 같은 접힌 줄이 그냥 글자처럼 보여 눌러야 하는지 헷갈림 → 누를 수 있는 것에 시각적 표시
- 변경: 기능 tap_affordance. 공고 상세·관심·내 조건의 펼치기 줄(충족한 조건·근거와 출처·판정 기준과 출처·계산 방법과 출처·시세 근거 거래·이미 넣은 값 등)을 테두리 있는 44px 버튼 모양(파란 글자) + 오른쪽 화살표(펼치면 위로)로. 항목별 점수 줄에도 화살표, 공급 유형 줄 화살표를 파란색으로. 끄면 예전 모양
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 390px 밝은·어두운 화면에서 접힌·펼친 상태 확인(무순위 강변역·광명 84A), 보이는 펼치기 줄 6개 모두 높이 44px 이상, 넘침 0, 오류 0. 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0
- 기능: tap_affordance
- 버전: v1.16.0
- 백업: backup/20261001-1843-b

## 2026-10-01 18:35 · 일반공급 가점을 지역 순서와 함께 표시
- 요청: 일반공급 줄에 '가점 31점 · 비교 단지 당첨 최저 49점보다 18점 낮아요'만 있어 가점이 우선인지 거주지역이 우선인지 헷갈림 → 지역 순서 먼저 표시, 비교 기준 명확히, 추첨 물량 안내, 기타지역 경고(1~4)
- 변경: 기능 region_first_score. ① 일반공급 줄·관심 카드·내 청약 가점 카드에 '해당지역(먼저) → 그 안에서 가점 31점'처럼 지역 순서 다음 가점을 씀(공고문 '당첨자 선정 순서: ①지역 → ②가점 → ③통장 가입기간 → ④추첨') ② '당첨 최저'를 비교 점수의 지역에 맞춰 '해당지역 당첨선'/'기타지역 당첨선'으로, 기타지역 사용자는 이 공고의 기타지역 결과가 있으면 그것과 비교 ③ 공고문 '전용면적별 1순위 가점제/추첨제 적용비율' 표를 새로 읽어(app/notice_pdf.parse_score_ratio, PARSER_VERSION 10) '가점제 70% · 추첨제 30%'와 '추첨제 물량은 가점과 상관없이 뽑아요'를 보여 주고, 85㎡ 초과처럼 추첨제 100%면 '이 주택형은 가점이 쓰이지 않아요' ④ 기타지역·경기 몫이면 '해당지역 신청자로 가점제 물량이 다 차면 기타지역 차례는 오지 않아요' 경고(지역별 배정 비율이 있는 공고는 '다음 몫에서 함께 겨뤄요'). 지역 순서 줄에 '가점·추첨은 같은 지역 순서 안에서 비교해요' 추가. 판정은 바꾸지 않음. 비율 표를 못 읽은 민영 공고는 자동 검증에 남김
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, tests/golden/notices.json, tests/test_notice_and_notify.py, docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 정답 데이터 4건(2026000453·103·403·454 원문 표를 직접 읽음)과 추출 결과 일치 테스트, 저장된 공고문 57건에 돌려 민영 25건 읽음·1건(2026000436 표 글자 뒤섞임) unknown·공공 null. 화면(390px): 해당지역·기타지역(서울)·사는 곳 미입력·59㎡(40/60)·84㎡(70/30)·115㎡(추첨 100%)·비율 없음 각각 문구 확인, 넘침 0, 오류 0. 스크립트 문법, pytest 128, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0
- 기능: region_first_score
- 버전: v1.15.0
- 백업: backup/20261001-1835-a

## 2026-10-01 18:20 · 베타 안내를 확인 뒤 한 줄로 (UX 5)
- 요청: UX 점검 5번 — 노란 베타 안내가 화면마다 가장 눈에 띄는 자리를 차지해 결과가 묻힘(Von Restorff 역효과)
- 변경: 기능 beta_compact. 큰 베타 안내에 '확인했어요' 버튼 — 누르면 이 기기에 기억하고(localStorage cy-beta-ok, 이 기기 편의 설정) 이후 모든 화면에서 작은 '베타' 표시 + 한 줄('판정은 내 입력으로 계산한 참고용이에요. 신청 전 모집공고문으로 확인하세요. 자세히')로. 자동 검증에서 공고문과 다른 값이 발견되면(verify_badge) 다시 크게. '자세히'는 이용 안내 메뉴화(about_menu)에 맞춰 '만든 이유와 데이터'로 연결. 정적 문서의 베타 안내는 그대로
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 처음 큰 안내 → '확인했어요' → 한 줄, 새로고침해도 유지, 첫 공고 카드 위치 641px → 578px(390×844), 상세도 한 줄. 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 밝은·어두운 화면 넘침 0
- 기능: beta_compact
- 버전: v1.14.0
- 백업: backup/20261001-1820-betacompact

## 2026-10-01 18:15 · 공고 상세 구역 탭과 묶음 순서 (UX 4)
- 요청: UX 점검 4번 — 상세 화면이 휴대폰 7화면 분량으로 길고 비슷한 카드가 이어져 어디가 무엇인지 구분이 어려움(Proximity·Jakob)
- 변경: 기능 detail_nav. 상단에 붙는 구역 탭(요약·자격·가점·경쟁률·마진·위치·제약, 390px 에 한 줄로 들어가게) — 누르면 그 구역으로 이동, 스크롤하면 지금 구역이 칠해짐. 순서를 내 판정 → 자격(자격 체크리스트·특별공급·특별공급 세대수) → 가점·경쟁률 → 마진 → 위치·제약으로 묶음(예전: 경쟁률 → 가점 → 자격). 끄면 예전 순서·탭 없음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 탭 4개를 차례로 눌러 각 구역 제목이 탭 바로 아래(64px)에 오고 지금 구역 표시가 맞는지(밝은·어두운 화면), 탭 줄 너비 374/374(넘침 없음), 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 바로 답하기 흐름 2,358개 중 2,326개 판정(남은 것은 서로 어긋난 답)
- 기능: detail_nav
- 버전: v1.13.0
- 백업: backup/20261001-1815-detailnav

## 2026-10-01 18:12 · 작은 링크의 누르는 영역 넓히기 (UX 3)
- 요청: UX 점검 3번 — 상세 화면에 누르기 어려운 작은 링크가 많음(Fitts)
- 변경: 기능 tap_targets. ① 공고 이름 아래 출처 글자 링크 3개(청약홈 공고·모집공고문 PDF·네이버 지도)를 한 줄짜리 44px 버튼으로 ② 출처 링크·작은 글자 버튼·베타 안내 '자세히'는 보이는 크기 그대로 두고 손가락이 닿는 영역만 위아래 44px로(투명한 ::after) ③ ☆ 관심 버튼 44px, '바로 답하기' 44px, 접힌 '계산 방법과 출처' 같은 단순 펼치기 줄 44px, 목록/지도 칩 40px, 경쟁률 표 단지명 링크 위아래 여백, 확인 필요 항목의 출처 줄을 바로 답하기 버튼과 12px 띄움. 출처 표시는 그대로(CLAUDE.md 5항)
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 실제 누르는 위치를 찍어 보는 검사(가운데 ±18px 를 눌러 그 요소가 눌리는지): 광명 상세 화면 누를 수 있는 것 80개 중 36px 이상 눌리는 것 15개 → 49개. 남은 것은 접힌 칸 안에 촘촘히 붙은 출처 링크. 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 상세 밝은·어두운 화면(넘침 0)
- 기능: tap_targets
- 버전: v1.12.0
- 백업: backup/20261001-1812-taptargets

## 2026-10-01 18:09 · 공고 상세 맨 위에 '내 판정'을 가장 크게 (UX 2)
- 요청: UX 점검 2번 — 상세에서 가장 크게 보이던 것이 마진 등급(파란 카드)이고, 사용자가 먼저 궁금한 '내가 넣을 수 있나'는 그 아래 작은 상자였음
- 변경: 기능 detail_result_first. 맨 위에 '내 판정 · 내가 넣은 정보 기준' 카드: 신청 가능(초록)·확인 필요(노랑, 확인할 항목 이름과 '아래 자격 체크리스트에서 바로 답하면 판정돼요')·2순위만 가능/2순위 확인 필요(노랑)·신청 불가(빨강)·판정 전(조건 미입력)을 크게, 그 아래에 예전 안내 문장(이유·자금·다음에 할 일)을 같은 카드 안에. 마진 등급 카드는 '마진 등급'으로 이름을 바꾸고 작게 그 아래로. 판정 로직은 그대로
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 다섯 상태(신청 가능·확인 필요·2순위만·불가·판정 전) × 밝은·어두운 화면 스크린샷 확인(넘침 0·오류 0)
- 기능: detail_result_first
- 버전: v1.11.0
- 백업: backup/20261001-1809-resultfirst

## 2026-10-01 18:06 · 공고 목록 첫 화면에 공고가 보이게 (UX 1)
- 요청: UI/UX 법칙(Hick·Fitts·Jakob·Proximity·Von Restorff)으로 화면을 점검해 개선 — 1번: 공고 목록 첫 화면에 공고가 안 보임
- 변경: 기능 feed_compact. 조건을 넣은 사람의 '내 조건' 카드를 한 줄(사는 곳·집·세대·현금 + 수정)과 판정 숫자 줄로 접고, '필터'·'판정 등급' 두 줄을 '필터 · 판정 등급' 버튼 하나로 접음(누르면 펼침, 적용 중이면 'N개 적용' 표시). 처음 온 사람의 '먼저 내 조건을 넣어 주세요' 카드는 그대로. 끄면 예전 화면
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 390×844 화면에서 첫 공고 카드가 보임(예전: 안 보임), 필터 펼침·적용·접힘 동작, 밝은·어두운 화면 넘침 0
- 기능: feed_compact
- 버전: v1.10.0
- 백업: backup/20261001-1806-feedcompact

## 2026-10-01 17:56 · 이용 안내를 메뉴로 정리, 업데이트 소식·청약 기준 가이드 내림
- 요청: (참고 앱 화면) 이용 안내에는 오픈카톡방·앱으로 받기·알림 설정·데이터와 만든 사람·이용약관·개인정보처리방침 정도만. 업데이트 이력·청약 기준 가이드는 빼고 자체 기록으로 관리
- 변경: 기능 about_menu — 이용 안내를 카드형 메뉴 목록으로(오픈카톡방[open_chat_url 있을 때]·앱으로 받기[누르면 홈 화면 추가 방법]·알림 설정[알림 기능이 보일 때]·만든 이유와 데이터·이용약관·개인정보처리방침·이 기기에 저장된 내 정보 모두 지우기[개인정보처리방침이 가리키는 버튼이라 유지]·문의) + '판정은 참고용' 한 줄. 예전 이용 안내의 '판정은 참고용'·'데이터와 검증 방식'은 '만든 이유와 데이터' 끝으로 옮김. 업데이트 소식은 정적 페이지(/updates/)를 만들지 않고 메뉴·정적 내비에서 뺌(기록 docs/changelog.json·VERSIONS.md·WORK.md 는 계속). guide_pages 끔(/guide/ 내림). 끄면 예전 이용 안내
- 파일: docs/index.html, docs/config.json, tools/build_static.py, 정적 문서(about·story·terms·privacy 다시 만듦, guide·updates 삭제), docs/sitemap.xml, tools/static_fragments.json, docs/changelog.json, VERSIONS.md, FEATURES.md, HANDOFF.md
- 확인: 스크립트 문법, pytest 126, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 이용 안내·만든 이유와 데이터 390px 밝은·어두운 화면 확인(넘침 0), 정적 /about/ 메뉴 링크(/story/·/terms/·/privacy/·mailto) 확인, 정적 문서 4쪽·sitemap 60
- 기능: about_menu
- 버전: v1.9.0
- 백업: backup/20261001-1756-aboutmenu

## 2026-10-01 17:48 · 신청 전 부적격 방지 체크 끄기
- 요청: (휴대폰 화면) 무슨 내용인지 이해가 안 됨 — 공지인지 판정인지 모호(세대 주택 1채로 넣었는데 청약은 가능?). 부적격은 실제 정보와 다르게 신청하면 안 된다는 것이라 본인이 검토할 일이고, 서비스는 입력 정보 기준으로 신청 가능·불가만 보면 됨 → 빼기
- 변경: docs/config.json 스위치 inelig_check 를 false (코드는 남김, 다시 켜면 보임). FEATURES.md 에 꺼 둔 이유, HANDOFF 에 사용자 방침(입력 정보 기준 판정만, 부적격 공지 카드 만들지 않음) 기록
- 파일: docs/config.json, FEATURES.md, HANDOFF.md, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 판정 사례 175/175, 회귀 판정 차이 0·화면 오류 0, 상세 화면에 카드가 나오지 않음(1,236회 그려 0회)
- 기능: inelig_check (끔)
- 버전: v1.8.2
- 백업: backup/20261001-1748-ineligoff

## 2026-10-01 17:43 · 관심 공고가 없을 때 안내를 눈에 띄게
- 요청: '공고에서 ☆ 관심을 누르면 … 비교해 드려요' 안내가 잘 안 보임 — 눈에 띄게
- 변경: 기능 ws_empty_v2. 가점 컷 탭 '관심 공고 · 내 점수'에 관심 공고가 없으면 파란 테두리·옅은 파란 바탕 카드로 ☆ 아이콘, '관심 공고를 담아 보세요', 한 줄 설명, 3단계(공고 탭에서 공고 열기 → 오른쪽 위 ☆ 관심 → 여기서 내 점수·유리한 공급 보기), '공고 보러 가기' 버튼. 끄면 예전 한 줄 안내. 같은 화면 '내 가점' 칸의 '입력하기'가 두 줄로 접히던 것도 한 줄로
- 파일: docs/index.html, docs/config.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 390px 밝은·어두운 화면 확인(넘침 0·오류 0)
- 기능: ws_empty_v2
- 버전: v1.8.1
- 백업: backup/20261001-1743-wsempty

## 2026-10-01 17:10 · 바로 답하기: '확인 필요'를 공고 화면에서 바로 답하고 바로 판정
- 요청: '확인 필요'에서 버튼을 누르면 필요한 정보 칸으로 딱 가고, 그것만 넣으면 바로 판정 결과가 나오게 (지금은 인터뷰 단계로 이동해 입력해도 계속 확인 필요라 불편)
- 변경: 기능 inline_fix. 공고 상세의 '확인 필요' 항목·'답하면 판정되는 질문'·'청약통장 1순위 요건'·특별공급 유형별·'비어 있는 정보' 버튼을 '바로 답하기'로 바꾸고, 누르면 그 자리(자격 체크리스트 또는 특별공급 칸)에 그 항목을 판정하는 데 필요한 질문만 펼침. 아직 안 넣은 질문이 위, 이미 넣은 값은 '이미 넣은 값 N개 · 고치기'로 접음. 답할 때마다(선택은 바로, 날짜·금액은 입력을 마치면) 다시 판정해 패널 위에 '판정됐어요 · 충족/불가' 또는 '아직 확인 필요 · 이유'를 보여줌. 답하다가 새로 필요한 질문(예: 가구원수 → 세대 소득)이 생기면 이어서 보여줌. 질문은 인터뷰와 같은 정의(fieldHtml 로 분리)를 쓰고 값은 내 조건에 저장. 끄면 예전 버튼(인터뷰 단계로 이동)
- 판정: 바꾸지 않음
- 검사 도구: tools/qa/fixflow.cjs — 무작위·빈 프로필로 상세의 모든 '바로 답하기'를 눌러 나온 질문에 답한 뒤 판정되는지 셈
- 파일: docs/index.html, docs/config.json, tools/qa/fixflow.cjs, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest 126, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, fixflow 두 번(버튼 2,922개·3,905개): 답한 뒤 판정됨 2,890·3,851 — 남은 것은 모두 '노부모 부양함 + 같은 등본 부모님 0명'처럼 서로 어긋난 답(패널에 두 질문이 함께 보여 그 자리에서 고칠 수 있음). 사용자 상황(세대 주택 1채·본인 무주택) 재현: 버튼 → '그 집은 누구 명의인가요?'만 보임 → 답하면 '판정됐어요 · 충족'. 390px 밝은·어두운 화면 넘침 0·오류 0
- 기능: inline_fix
- 버전: v1.8.0
- 백업: backup/20261001-1710-inlinefix

## 2026-10-01 16:58 · 세대 주택 명의 질문 추가, 특별공급이 '세대 주택 확인 필요'를 무주택으로 보던 오류 수정
- 요청: (휴대폰 화면) 본인 집 '없어요'로 넣었는데 '무주택 세대 · 세대 주택 확인 필요'가 계속 뜸
- 원인: ① '세대 전체 주택 1채'(세대 주택·당첨 이력 단계)는 남아 있고 본인·배우자 명의는 아니라서 누구 명의인지 몰라 확인 필요인데, 그걸 답할 질문이 없었고 버튼('집 보유 여부 넣기')은 본인 집 질문으로 감 ② 특별공급 판정(spJudge)이 이 '확인 필요'를 무주택 충족으로 봐서 같은 화면에 '신생아·생애최초 가능'이 함께 나옴(가능 쪽으로 틀림)
- 변경: 세대 주택 단계에 '그 집은 누구 명의인가요? (만 60세 이상 부모님(배우자 부모님 포함) / 그 밖의 세대원)' 질문 hhOwner 추가(세대 주택 1채 이상 · 본인·배우자·부모님 명의 아님일 때만). 60세 이상 부모님 → 무주택(제53조제6호), 그 밖의 세대원 → 유주택. 확인 필요 항목 버튼을 '집 명의 답하기'(세대 주택 단계)로. 특별공급은 명의 모름이면 '세대 주택 명의 확인 필요'. 노부모부양은 60세 이상 부모님 명의 예외를 적용하지 않음(제53조 단서: 제46조·공공주택 특별법 시행규칙 별표6 2라) — 예전에는 민영만 적용, 공공도 적용. 세대 주택 단계 설명 문구도 공공·특공 무주택 요건에 쓰인다고 고침
- 판정 검증 사례: home 2건(부모 60세 이상 명의 가능·그 밖의 세대원 불가), sphome 5건(특공 생애최초 명의 모름 확인 필요·60세 이상 부모 가능·그 밖 불가, 노부모부양 60세 이상 부모 명의 불가). 예전 코드로는 5건 불일치, 새 코드 175/175
- 파일: docs/index.html, tools/make_judge_cases.py, tests/judge/cases.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 스크립트 문법, pytest, 판정 사례 175/175, 회귀 판정 차이 0·화면 1,287개 오류 0, 사용자 상황 재현(세대 주택 1채·본인 무주택 → 상세 '집 명의 답하기' → 새 질문 → '만 60세 이상 부모님' → 무주택 충족, 특공 신생아·생애최초 가능, 노부모 불가)
- 기능: 없음(수정)
- 버전: v1.7.5
- 백업: backup/20261001-1658-hhowner

## 2026-10-01 16:49 · 청약통장을 안 넣었으면 '2순위만'으로 단정하지 않기
- 요청: 다음 할 일 1번 — 청약통장 미입력인데 1순위 요건만 못 채운 경우 '2순위만'으로 보이는 문제 (블라인드 감사 A30·A35에서 남긴 한계)
- 원인: 2순위도 청약통장 가입이 필요한데(2026000453 '2순위 : 예치금액과 관계없이 청약예금·청약부금·주택청약종합저축에 가입한 분'), 1순위 요건(세대주 등)만 못 채우면 통장 정보가 없어도 '2순위만'으로 판정
- 변경: eligibility() 에 rank2Need(1순위만 막힘 + 통장이 필요한 공고 + 통장 종류 미입력). 이때 목록 분류·자격 칸·관심 공고·비교표는 '확인 필요', 상세 안내는 '1순위로는 신청할 수 없어요 · 2순위는 청약통장 확인 필요'와 '2순위는 청약통장(…)에 가입돼 있으면 신청할 수 있어요. 청약통장 정보를 넣으면 판정해요', 사유 문장의 '2순위로는 신청할 수 있어요'는 뺌. 통장 없음(none)은 예전처럼 불가. 상세 '마진 (보수적 추정)' 칸 이름이 두 줄로 접혀 '마진 (보수적)'으로
- 판정 검증 사례: fn 'bucket' 3건(광명 2026000453 세대원: 통장 가입 → 2순위만, 미입력 → 확인 필요, 없음 → 불가), judge_check.cjs 에 'bucket'. 예전 코드로는 미입력 사례 불일치, 새 코드 168/168
- 파일: docs/index.html, tools/make_judge_cases.py, tools/judge_check.cjs, tests/judge/cases.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 스크립트 문법, pytest, 판정 사례 168/168, 회귀 판정 차이 0·화면 1,287개 오류 0, 세대원·통장 미입력 프로필로 광명 상세 화면 확인
- 기능: 없음(수정)
- 버전: v1.7.4
- 백업: backup/20261001-1649-rank2acct

## 2026-10-01 16:38 · 검사 도구: 블라인드 판정 감사·화면 문구 훑기 (저장소에 보관)
- 요청: 판정 정확도 검증과 문구 점검을 다음 세션에서도 같은 방법으로 할 수 있게 (CLAUDE.md 8항: 검사 도구는 저장소에)
- 변경: tools/qa/audit/(사례 생성기 2개·검토자 지시서·README), tools/qa/textsweep.cjs, 이번 감사 결과 evidence/audit/2026-10-01/(무작위 40건·특별공급 16건의 사례·앱 판정·검토자 판정, 합성 프로필이라 개인 정보 없음), HANDOFF 진행 상황·저장소 스킬 함정 추가
- 파일: tools/qa/audit/*, tools/qa/textsweep.cjs, evidence/audit/2026-10-01/*, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md
- 확인: 도구 실행 결과(감사 비교·문장 1,561개 수집 오류 0), pytest
- 기능: 없음(도구)
- 버전: 올리지 않음
- 백업: backup/20261001-1638-qatools

## 2026-10-01 16:27 · 화면 문구 점검·수정 (무작위 프로필로 전 화면 훑기)
- 요청: 최종 QA 뒤 무작위 샘플 데이터로 최종 확인하면서 설명 문구 이상·어색한 어감 전부 찾아 고치기
- 방법: tools/qa/textsweep.cjs 로 무작위 프로필 14개(빈 프로필·일부만 채운 프로필 포함) × 목록·상세·자금·인터뷰·가점 컷·등급·내 조건·안내·업데이트·비교 화면 + 정적 문서를 그려 문장 1,822개(숫자 묶음 기준)를 모으고, 검토자 4명(별도 에이전트)이 맞춤법·어색함·오해 소지를 표시 → 162건 중 원문을 보고 판단해 고침(표 행 쪼개짐 등 화면 추출 착시·법률 문서 문체·전문 용어는 그대로)
- 변경(주요): 당첨이 정해진 것처럼 읽히던 '…에서 뽑혀요' → '… 대상이에요' / 추정 출처 '규제지역 기준 추정 · 공고문 확인' → '이 서비스 추정(규제지역 기준) · 공고문에서 확인하세요' / 신혼희망타운 '…이 1단계 → … 3단계 추첨으로 신청해요' → '…을 … 순서로 뽑아요' / 약관·방침 운영자 이름 뒤 조사(이/가·은/는)를 받침에 맞게 / 해당지역 '해당지역 X · 기타지역 Y 거주자만' → '해당지역(X)과 기타지역(Y) 거주자만', '해당지역은 X 거주자예요' → 'X 거주자가 해당지역이에요' / 통장 값 'A / B 필요' → '내 A · B 필요' / '세요'(세다)를 '봐요·포함해요·계산해요'로 / '나나 세대원' → '나 또는 세대원' / 자금 '[일자]' 자리표시자 → '날짜 미정' / 비교표 단지명 잘림에 '…' / 마진·차이 범위를 작은 값→큰 값 순서로 / 가점 범례 '점' 단위, '최대까지 N점' → '만점까지 N점' / 부적격 체크 '?점' → '미입력' / '가장 작은 값'(둘 중) → '더 작은 값' / 가이드 '(최대 32·35·17점)', 마침표 두 번, 도·시 연장 기간 문장 / 업데이트 소식 문장 5곳 / 그 밖의 어색한 표현 다수
- 판정: 바꾸지 않음 (회귀 1,030조합 판정 차이 0, 항목 상태·이름 변화 0, 값 문구만 624곳 바뀜)
- 파일: docs/index.html, tools/build_static.py, docs/changelog.json, 정적 문서(docs/guide·about·privacy·terms·story·updates), tools/static_fragments.json, VERSIONS.md
- 확인: 스크립트 문법, pytest 126, 판정 사례 165/165, 회귀 화면 1,287개 오류 0, 다시 훑기(문장 1,561개)에서 지적 문구 사라짐 확인, 상세·부적격 체크 390px 밝은·어두운 화면 확인
- 기능: 없음(수정)
- 버전: v1.7.3
- 백업: backup/20261001-1627-wording

## 2026-10-01 16:19 · 노부모부양: '부양함'과 '같은 등본 부모님 0명'이 함께면 확인 필요
- 요청: 판정 정확도 검증 (특별공급 블라인드 감사 S08·S09에서 발견)
- 원인: 노부모부양 특별공급은 공고문 '만65세 이상의 직계존속(배우자의 직계존속 포함)을 3년 이상 계속하여 부양(같은 세대별 주민등록표등본에 등재되어 있는 경우에 한함)'(2026000453·426, 공공 414도 같은 뜻). 앱은 '3년 이상 같은 등본에서 모시나요 = 예'만 보고 '같은 등본 부모님 수 = 0명' 답과 어긋나도 '가능'으로 판정
- 변경: 두 답이 어긋나면 '같은 등본 부모님을 0명으로 입력했어요…' 확인 필요. 판정 사례 3건 추가(같은 등본 1명 가능·0명 확인 필요·부양 아님 불가), 기존 노부모 소득 사례의 기본 프로필에서 어긋난 값(같은 등본 0명)을 모름으로 바꿈(소득 단계만 보는 사례). 예전 코드로는 새 사례 1건 불일치, 새 코드 165/165
- 파일: docs/index.html, tools/make_judge_cases.py, tests/judge/cases.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 공고문 원문 3건 문구 확인, 스크립트 문법, pytest, 판정 사례 165/165, 회귀 판정 차이 0·화면 1,287개 오류 0
- 기능: 없음(수정)
- 버전: v1.7.2
- 백업: backup/20261001-1619-elderdeed

## 2026-10-01 16:10 · 세대 주택이 있는데 명의를 모르면 '무주택 세대 충족'으로 보지 않기
- 요청: 판정 정확도 검증 (블라인드 감사에서 발견)
- 원인: '무주택 세대' 판정이 본인·배우자·부모님(세대원일 때) 명의만 보고, '세대 전체가 가진 주택 수'(hhHomes)를 1채 이상이라고 답해도 그 밖의 세대원 명의면 '충족'으로 봄. 공공분양 일반공급·특별공급은 무주택세대구성원(제2조제4호: 세대원 전원 무주택)이 요건이라, 만 60세 이상 직계존속 명의(제53조제6호 예외)가 아니면 신청할 수 없는데 '가능'으로 나올 수 있었음 (감사 사례 A40 양주회천 A-26 74A)
- 변경: 세대 주택 1채 이상인데 본인·배우자·(60세 미만) 부모님 명의가 아니고 60세 이상 부모님 예외도 확인되지 않으면 — 민영 일반공급은 '세대 주택 있음 · 1순위 신청 가능'(유주택도 1순위 가능, 가점제·특공은 명의에 따라 다르다는 설명), 그 밖(공공·특공 요건)은 '세대 주택 확인 필요'
- 판정 검증 사례: fn 'home' 8건 추가(공공 6: 없음 가능·1채/2채 이상 확인 필요·60세 이상 부모 명의 가능·60세 미만 부모 명의 불가·본인 명의 불가, 민영 2: 가능). judge_check.cjs 에 'home' 추가. 예전 코드로는 2건 불일치, 새 코드 162/162
- 블라인드 감사 결과(별도 검토자 3명, 앱 코드·결과를 보지 않고 공고문·법령 원문만으로 판정): 무작위 40건 일반공급 34/40 일치 — 불일치 6건 중 1건이 이 오류, 5건은 감사용 프로필의 '청약통장 미입력'을 검토자가 '통장 없음'으로 읽은 차이. 가점 23건 중 16건 일치 — 7건은 검토자가 세대원 주택으로 무주택기간을 0으로 본 것이며 법령 별표 1 3)('무주택기간은 신청자와 그 배우자를 기준') 대로 앱이 맞음. 특별공급 32/32. 특별공급 중심 16건: 일반 16/16, 가점 12/12, 특별공급 14/16(나머지 2건은 다음 커밋 노부모부양)
- 파일: docs/index.html, tools/make_judge_cases.py, tools/judge_check.cjs, tests/judge/cases.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 스크립트 문법, pytest, 판정 사례 162/162, 회귀 판정 차이 0·화면 1,287개 오류 0
- 기능: 없음(수정)
- 버전: v1.7.1
- 백업: backup/20261001-1610-hhhomes

## 2026-10-01 16:01 · 가점이 쓰이지 않는 공고에서 '당첨 최저 비교' 대신 안내
- 요청: 2순위만 가능한 공고에서도 가점 칸이 당첨 최저와 비교해 헷갈림 — '2순위는 추첨' 안내
- 변경: 기능 score_scope. 내 청약 가점 카드에서 ① 2순위만 가능하면 '이 공고는 2순위로만 신청할 수 있어요. 2순위는 가점 없이 추첨으로 뽑아서(제28조⑨) 아래 가점은 이번 공고에 쓰이지 않아요' ② 규제지역 유주택이면 '추첨 물량으로만 뽑혀요' 안내를 당첨 최저 비교 자리에 보여줌. 점수·판정은 그대로
- 파일: docs/index.html, docs/config.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md
- 확인: 제28조⑨ '제2순위에서 경쟁이 있는 경우에는 추첨의 방법으로 입주자를 선정' 원문 확인(evidence/law/rule.xml), 스크립트 문법, pytest, 판정 사례 154/154, 회귀 판정 차이 0·화면 오류 0, 세대원 프로필 × 광명 시티프라디움 에듀하임 상세 화면 확인
- 기능: score_scope
- 버전: v1.7.0
- 백업: backup/20261001-1601-rank2score

## 2026-10-01 16:01 · 가점 부양가족 설명을 법령대로 (배우자·만 30세 이상 자녀)
- 요청: (2순위 가점 칸 작업 중 발견) 내 청약 가점 카드·가점 질문 설명 문구 점검
- 원인: '부양가족은 같은 등본의 배우자·미혼 자녀…'라고 적혀 있었으나 법령 별표 1 나목 1)은 '같은 세대별 주민등록표에 등재되어 있지 않은 배우자를 포함', 만 30세 이상 미혼 자녀는 '최근 1년 이상 계속하여 같은 등본'. 출처 표기 '별표1의2'도 법령 별표 번호와 다름(가점제 적용기준은 별표 1)
- 변경: 가점 카드(새·예전)와 가점 질문 설명을 '배우자(등본이 달라도 포함), 같은 등본의 미혼 자녀(만 30세 이상은 1년 이상 같은 등본)…'로, 출처를 '별표 1'로. 계산은 바꾸지 않음(입력한 부양가족 수 그대로)
- 파일: docs/index.html, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: evidence/law/byeolpyo_1.txt 나목 원문 대조, 스크립트 문법, pytest, 판정 사례 154/154
- 기능: 없음(수정)
- 버전: v1.6.3
- 백업: backup/20261001-1601-rank2score

## 2026-10-01 15:58 · 출산가구 완화: +10%p 확인된 가구의 +10~+20%p 구간을 '불가' → '확인 필요'
- 요청: 출산가구 완화 판정 정확도 개선 ('확인 필요' 중 '불가'로 확정할 수 있는 것)
- 원인: 공고문 원문(2026000409 13쪽·2026000438·2026820010) 「’23.3.28. 이후 출생한 자녀(태아 포함)가 1명만 있는 경우 10%p, 2명 이상(’23.3.28. 이후 출생한 자녀가 1명이고, ’23.3.27. 전 출생한 자녀가 있는 경우 포함)인 경우 20%p」. 이전에 생각한 '불가 확정'은 틀림 — 그 전에 태어난 만 19세 이상 자녀가 있으면 +20%p 인데 이 서비스는 미성년 자녀(kidsMinor)만 물음. 오히려 특별공급(spJudge)이 신생아 1명 가구를 +10%p 로 확정해 +10~+20%p 구간을 '불가'로 판정하던 오류(가능할 수 있는 사람에게 불가)를 찾음. 공공 일반공급·신혼희망타운 소득은 미성년 자녀 2명 이상(신생아 포함)으로 +20%p 가 확인돼도 '확인 필요'였음
- 변경: relaxRange(p) = [확실한 최소, 가능한 최대] 완화폭(+10%p 확인 → [10, 20]). 특별공급 소득·부동산·자동차, 공공 일반공급 소득·자산, 신혼희망타운 소득에 적용: 최소 완화로 충족 → 가능, 최대 완화로도 초과 → 불가, 그 사이 → 확인 필요(설명: '그 전에 태어난 자녀(만 19세 이상 포함)가 더 있으면 +20%p'). 신혼희망타운 총자산은 그대로(이미 넘으면 확인 필요)
- 판정 검증 사례: tools/make_judge_cases.py 에 relax_range(공고문 문장으로 따로 계산) 추가, 경계 사례 10건 추가(154건). 예전 화면 코드로 돌리면 10건 불일치(9건 불가→확인 필요, 1건 확인 필요→가능), 새 코드는 154/154
- 파일: docs/index.html, tools/make_judge_cases.py, tests/judge/cases.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 스크립트 문법, pytest, 판정 사례 154/154, 회귀(프로필 5개) 판정 차이 0·화면 1,287개 오류 0
- 기능: 없음(수정)
- 버전: v1.6.2
- 백업: backup/20261001-1558-birthrelax

## 2026-10-01 15:48 · '확인 필요를 줄이려면' 칸 끄기
- 요청: '확인 필요를 줄이려면'은 필요 없을 것 같으니 기능 꺼 줘 (내 청약 현황도 필요 없음)
- 변경: unsure_actions 안의 내 조건 카드 요약 칸만 새 스위치 unsure_summary 로 나누고 false. 공고 상세 '확인 필요' 항목별 버튼(unsure_actions)은 그대로 켜 둠. HANDOFF 다음 후보에서 '내 청약 현황' 뺌
- 파일: docs/index.html, docs/config.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md, HANDOFF.md
- 확인: 스크립트 문법, pytest, 판정 사례 144/144, 회귀 판정 차이 0·화면 오류 0, 브라우저로 내 조건 카드에 칸이 없고 공고 상세 버튼은 남는 것 확인
- 기능: unsure_summary (끔)
- 버전: v1.6.1
- 백업: backup/20261001-1548-unsuresum

## 2026-10-01 15:37 · 신청 전 부적격 방지 체크
- 요청: 보고서 순서대로 다음 후보 진행 — 부적격 방지 체크
- 변경: 기능 inelig_check. 공고 상세(신청 가능·2순위만일 때)에 '신청 전 부적격 방지 체크' 카드: 부적격 취소 시 당첨 제한 기간(제58조③: 수도권 1년·수도권 외 6개월(투기과열·청약과열 1년)·위축지역 3개월), 자주 걸리는 지점을 '이 공고 조건'과 '내 입력'으로 나눠 표시 — ① 청약 가점 입력(민영 가점제, 내 가점 항목별 점수, 부양가족·무주택기간 세는 법, 재산정 점수가 당첨선 이상이면 유지 제58조④) ② 세대 전원 주택·분양권(제2조 세대 범위, 제53조 분양권·공유지분, 60세 이상 직계존속 예외와 노부모 특공 제외) ③ 규제지역 세대주·세대 5년 내 당첨(제28조①1다) ④ 특별공급 한 차례(제55조, 판정하지 않음) ⑤ 거주기간(제4조⑦ 국외 90일·183일). 청약홈 '청약자격확인' 메뉴 이름만 안내(링크 없음). 판정은 바꾸지 않음
- 파일: docs/index.html, docs/config.json, tests/test_law.py, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md
- 확인: 근거 문구를 evidence/law/rule.xml(2026.6.15 시행) 원문에서 직접 확인. tests/test_law.py 에 제58조③ 기간 = 앱 INELIG_BAN, 제4·28·53·55조 문구 존재 테스트 추가(값을 바꾸면 실패 확인). pytest, 판정 사례 144/144, 회귀 판정 차이 0·화면 1,287개 오류 0, 프로필 6개 × 공고 206건 상세 1,236회 그려 오류 0(카드 678회 표시), 390px 밝은·어두운 화면 넘침 0
- 기능: inelig_check
- 버전: v1.6.0
- 백업: backup/20261001-1537-inelig

## 2026-10-01 15:32 · '확인 필요' 원인별 다음 행동 버튼
- 요청: 보고서 순서대로 다음 후보 진행 — '확인 필요'를 다음 행동 버튼으로 바꾸기
- 변경: 기능 unsure_actions. '확인 필요' 항목마다 원인(itemCause: A 내 정보 부족 / B~E 공고·기준 쪽)을 보고, A 면 그 항목을 판정하는 질문 단계로 가는 버튼(예: 청약통장 정보 넣기·가구원수 넣기·자산 넣기·집 보유 여부 넣기·사는 곳 넣기), 그 밖이면 '모집공고문 PDF에서 확인' 링크. 내 조건 카드에는 '확인 필요를 줄이려면' — 확인 필요 공고들의 원인을 행동별로 묶어 필요한 공고 수가 많은 순으로 3개까지 버튼. 자격 체크리스트의 '청약통장 1순위 요건 · 입력 필요'에도 버튼. 판정은 바꾸지 않음. 끄면 예전과 같음
- 파일: docs/index.html, docs/config.json, docs/changelog.json, docs/updates/index.html, VERSIONS.md, FEATURES.md
- 확인: 스크립트 문법, pytest, 판정 사례 144/144, 회귀(스위치 켬) 판정 1,030조합 차이 0·화면 1,287개 오류 0, 프로필 6개 × 공고 206건의 확인 필요 원인별 행동 대응표 확인(전부 버튼 또는 공고문 링크), 버튼 3개 눌러 해당 질문(청약통장·자녀와 가구·소득과 자산)이 열리는지, 390px 밝은·어두운 화면 가로 넘침 0·오류 0
- 기능: unsure_actions
- 버전: v1.5.0
- 백업: backup/20261001-1532-unsureact

## 2026-10-01 15:27 · 답하면 판정되는 항목을 '판정하지 않는 항목'과 나눠 표시
- 요청: (휴대폰 화면) 가구원수 질문에 답하면 판정되는데 왜 '이 서비스가 판정하지 않는 항목'으로 뜨는지
- 원인: pendingChecks() 가 '아직 판정 못 한 것'을 한 목록으로 돌려줘서, 질문에 답하면 판정되는 항목(특별공급 가구원수 산정)도 '직접 확인할 것 · 이 서비스가 판정하지 않는 항목'·'공고문에서 1가지를 더 확인하세요'로 표시됨. 판정은 맞음(표기 문제)
- 변경: 질문 단계가 화면에 있는 항목(pendAsk)은 '답하면 판정해요 n개 · 질문에 답하면 바로 판정' 묶음(열림)으로 따로 보여 주고 표시를 '특별공급 · 답하면 판정'으로. 체크리스트 판정 문구 '아래 질문 n개에 답하면 특별공급까지 판정해요', 상세 판정 안내도 같은 뜻으로. 판정하지 않는 항목만 '직접 확인할 것'에 남김
- 파일: docs/index.html, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: 스크립트 문법, pytest, 판정 사례 144/144, 회귀 판정 1,030조합 차이 0·화면 1,287개 오류 0, 브라우저로 세대주 프로필 × 광명 시티프라디움 에듀하임(2026000453) 체크리스트 확인
- 기능: 없음(수정)
- 버전: v1.4.2
- 백업: backup/20261001-1527-pendask

## 2026-10-01 15:17 · 버전 브랜치 도구: 올리기 전 실행 막기
- 요청: (작업 중 발견) v1.4.1 올리기가 pull 실패로 멈춘 상태에서 release.sh 가 원격 main(변경 전)을 release/v1.4.1 로 남김
- 변경: release.sh 가 지금 커밋이 원격 main 에 없으면 멈춤. release/v1.4.1 은 실제 v1.4.1 커밋(b776f8a)으로 앞으로 당김(빨리 감기, 강제 아님). 저장소 스킬 함정·HANDOFF 갱신
- 파일: tools/qa/release.sh, .claude/skills/cheongyakpass-ops/SKILL.md, HANDOFF.md
- 확인: bash -n, git ls-remote 로 release/v1.4.1 = b776f8a 확인
- 기능: 없음(도구)
- 버전: 올리지 않음
- 백업: backup/20261001-1517-release

## 2026-10-01 15:14 · '2순위만 가능' 표시 정리
- 요청: (휴대폰 화면) '2순위는 가능'이라는데 상세 화면이 다 빨개서 자격이 되는지 안 되는지 헷갈림
- 원인: 판정(rank2 = 1순위 요건만 미충족)은 맞는데, 상세 화면의 판정 안내(빨간 note)·자격 칸('불가')·체크리스트('문제가 있는 조건' 빨강)·목록 한 줄(빨강)이 완전 불가와 같은 표기였음. 관심 공고·비교 화면은 이미 노란 '2순위만'
- 변경: rank2 일 때 상세 안내를 노란색 '2순위로만 신청할 수 있어요', 자격 칸 '2순위만'(노랑), 체크리스트 '1순위만 막는 조건 (2순위는 신청 가능)'·'1순위 요건 미충족'(노랑), 목록 '2순위만 가능'(노랑). 2순위는 1순위 신청자가 공급 물량보다 적을 때만 접수한다는 안내 추가. 판정 로직은 바꾸지 않음
- 파일: docs/index.html, docs/changelog.json, docs/updates/index.html, VERSIONS.md
- 확인: pytest, 판정 사례 144/144, 회귀 판정 1,030조합 차이 0·화면 1,287개 오류 0, 스크립트 문법, 브라우저로 세대원 프로필 × 광명 시티프라디움 에듀하임(2026000453) 상세 확인
- 기능: 없음(수정)
- 버전: v1.4.1
- 백업: backup/20261001-1514-rank2

## 2026-10-01 15:03 · 청약 기준 가이드 다시 열기 (법령 원문 기준)
- 요청: 청약 기준 가이드가 특정 공고문을 출처로 삼는 문제 — 공통 기준은 공식 지침(법령)을 출처로 (사용자가 방안2 법제처 OPEN API 선택, LAW_OC 등록)
- 변경: tools/build_static.py — evidence/law/rule.xml(법제처 API 로 받은 주택공급에 관한 규칙 원문)의 별표 1(가점제 적용기준)·별표 2(예치기준금액)를 읽어 /guide/score/·/guide/deposit/ 를 만들고 출처를 법령(시행일·개정일·조항)으로 표시, 공고문 링크 제거. 가점제에서 빠지는 경우(별표 1 비고 1), 부양가족 인정 기준을 법령대로 고침(배우자 등본 무관, 직계존속 세대주·3년, 30세 이상 자녀 1년), 배우자 통장(비고 2) 추가. 소득 기준표 페이지는 공고마다 달라 뺌. 법령 원문이 없으면 가이드를 만들지 않음. guide_pages 다시 켬. tools/law_probe.py — 같은 번호의 서식(신청서)이 별표를 덮어쓰던 문제를 별표구분으로 거름. tests/test_law.py — 법령 별표 2 예치금 = 화면 ACCOUNT_DEPOSIT, 법령 별표 1 가점표 40칸 = 판정 사례 생성기 계산, 가이드에 공고문 출처가 없는지
- 파일: tools/build_static.py, tools/law_probe.py, tests/test_law.py, tests/test_pipeline.py, docs/config.json, docs/index.html, docs/guide/, docs/sitemap.xml, docs/about·privacy·story·terms·updates/index.html, tools/static_fragments.json, docs/changelog.json, VERSIONS.md
- 확인: pytest 124 통과(값을 바꾸면 test_law 실패하는 것 확인), 판정 사례 144/144, 회귀 판정 1,030조합 차이 0·화면 1,287개 오류 0, 스크립트 문법 검사, 브라우저로 /guide/ 3쪽 밝은·어두운 화면 확인(넘침·오류 없음). 법령 값: 예치금 300/600/1000/1500·250/400/700/1000·200/300/400/500 이 앱과 같음
- 기능: guide_pages
- 버전: v1.4.0
- 백업: backup/20261001-1503-lawguide

## 2026-10-01 14:59 · 법령 원문 받기: Referer·인증키 형태 점검
- 요청: (두 번째 실행 결과) 네 가지 주소 모두 '필수입력요소 검증에 실패' — 원인 찾기
- 변경: Referer(등록 도메인 cheongyakpass.kr) 있음·없음, display 있음·없음을 https/http 로 시도해 기록, 인증키의 길이·앞뒤 공백·문자 종류만 기록(값은 남기지 않음)
- 파일: tools/law_probe.py
- 확인: 문법 검사, Actions 실행 결과로 확인
- 기능: 없음(도구)
- 버전: 올리지 않음
- 백업: backup/20261001-1459-lawprobe3

## 2026-10-01 14:57 · 법령 원문 받기: 주소 형태 바꿔 시도
- 요청: (첫 실행 결과) 법제처 API 검색이 '필수 입력값이 존재하지 않습니다'로 거절됨
- 변경: http/https 주소와 법령명 띄어쓰기 있음·없음을 차례로 시도하고, 리다이렉트 경로·응답 앞부분을 모두 기록(인증키 가림). 성공한 주소로 본문을 받음
- 파일: tools/law_probe.py
- 확인: 문법 검사, Actions 실행 결과로 확인
- 기능: 없음(도구)
- 버전: 올리지 않음
- 백업: backup/20261001-1457-lawprobe2

## 2026-10-01 14:55 · 법령 원문 받기 (법제처 OPEN API)
- 요청: 청약 기준 가이드의 출처를 특정 공고문이 아닌 공식 법령으로 — 법령 원문을 읽을 방법 (사용자가 open.law.go.kr 에서 API 인증키를 받아 GitHub Secrets LAW_OC 에 넣음)
- 변경: tools/law_probe.py — 법제처 국가법령정보 공동활용 API 로 '주택공급에 관한 규칙'을 찾아(법령일련번호·시행일·공포일) 본문 XML 을 받고, 별표 목록과 별표 1·2 의 본문 글자·PDF 를 evidence/law/ 에 저장(인증키는 저장 파일에서 *** 로 지움). 워크플로 law-probe.yml(손으로 실행·도구 변경 시·매주 월요일 06:10)
- 파일: tools/law_probe.py, .github/workflows/law-probe.yml
- 확인: 문법·YAML 검사. 작업 환경은 law.go.kr 접속이 막혀 있어 Actions 실행 결과(evidence/law/README.txt)로 확인 — 서버 IP 미등록으로 거절되면 그 응답이 기록에 남음
- 기능: 없음(도구)
- 버전: 올리지 않음
- 백업: backup/20261001-1455-lawprobe

## 2026-10-01 14:19 · 인수인계: v1.3.3 까지
- 요청: 사용자 지적 4건 처리 기록
- 변경: HANDOFF.md 진행 현황 갱신 (v1.3.1~1.3.3, 운영자용 정보 위치, 가이드 재개 조건)
- 파일: HANDOFF.md
- 확인: 문서만 바뀜. pytest 통과
- 기능: 없음(수정)
- 버전: 올리지 않음
- 백업: backup/20261001-1419-handoff5

## 2026-10-01 14:15 · 청약 기준 가이드 내림 (v1.3.3)
- 요청: 청약 기준 가이드 출처가 특정 공고의 모집공고문인데, 공고마다 기준이 다를 수 있어 그걸 기준으로 삼는 게 맞는지. 공통 기준이면 공식 지침을 출처로, 고정해서 표기하기 어렵다면 삭제
- 판단: 소득 기준표는 해마다 바뀌고 공고마다 적용 비율·단계가 달라(공공·민영·신혼희망타운, 출산가구 완화) 하나의 고정 표로 안내하면 오해를 줄 수 있음. 가점표·예치금은 법령(주택공급에 관한 규칙 별표1·2) 공통이지만, 지금 작업 환경에서 법령 원문 화면을 열어 숫자를 확인할 수 없어(출처 원칙 CLAUDE.md 5항) 세 페이지 모두 내림. 앱 판정은 원래대로 공고별 공고문 기준
- 변경: 스위치 guide_pages(꺼짐) — 꺼져 있으면 /guide/ 페이지를 만들지 않고 지움, 정적 페이지 메뉴·바닥·앱 이용 안내 문서 목록에서 가이드 링크 숨김, 사이트맵 65 → 61. 가이드 코드(tools/build_static.py)와 숫자 테스트는 보존(법령 출처로 다시 만들 때 사용). 업데이트 소식 1.0.0 항목에서 가이드 언급 정리, 1.3.3 항목 추가. 정적 이용 안내 설명에서 '데이터 검증 현황' 문구 제거. collect.yml·verify.yml 의 git add 를 없는 폴더에도 실패하지 않게 바꿈
- 파일: tools/build_static.py, docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, .github/workflows/collect.yml, .github/workflows/verify.yml, docs/guide/(삭제), docs/sitemap.xml, 정적 페이지들, tools/static_fragments.json
- 확인: build_static → 5쪽·사이트맵 61, docs/guide 없음, 정적 페이지·공고 페이지에 /guide/ 링크 0, 워크플로 git add 조건(있는 폴더·추적 중인 폴더만) 로컬 확인. 회귀: 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, pytest 통과
- 기능: guide_pages
- 버전: v1.3.3
- 백업: backup/20261001-1415-guide

## 2026-10-01 14:05 · 이용 안내 정리: 업데이트 소식 (v1.3.2)
- 요청: 이용 안내의 데이터 검증 현황·업데이트 내역은 운영자만 알면 됨 — 물어볼 때 알려주거나, 업데이트는 간단한 소식만 (예: bonuschip.app 업데이트 소식)
- 변경: 스위치 about_simple — ① 이용 안내에서 '데이터 검증 현황' 카드 숨김, '검증' 설명은 한 줄(공고문 숫자와 앱 수치 자동 대조, 다르면 '데이터 확인 필요')로 ② '업데이트 내역 (베타)' → '업데이트 소식': 날짜·제목·한 줄, 여러 개면 '더 보기'. changelog 항목에 internal(버전 표시 1.0.1·사용 측정 1.1.0 숨김), news_title·news(사용자용 요약) 필드, '검증' 종류 항목은 빼고 보여줌 ③ 정적 /updates/ 제목·메뉴 '업데이트 소식'. 상세 기록은 그대로: changelog.json·VERSIONS.md·WORK.md·docs/verify-status.json (운영자가 물으면 이걸로 답함). 베타 상자의 '검증에서 다른 값 발견' 경고는 그대로 둠
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, tools/build_static.py, docs/updates/, docs/about/, 정적 페이지 메뉴, tools/static_fragments.json
- 확인: 브라우저(밝은·어두운): 이용 안내에 검증 현황 없음·'업데이트 소식', 소식에 사용 측정·버전 표시·검증 항목 없음, 오류 0. 회귀: 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, pytest 통과
- 기능: about_simple
- 버전: v1.3.2
- 백업: backup/20261001-1405-aboutsimple

## 2026-10-01 14:02 · 관심 공고 유주택 표기·시도 검색 수정 (v1.3.1)
- 요청: ① 공고 화면은 '신청 가능 · 추첨제만'인데 가점 컷 탭(관심 공고)은 일반공급 '가능'과 가점 27/84 만 보여 헷갈림 ② 검색에 '서울'만 넣었는데 서울로 걸러지지 않음
- 변경: ① 관심 공고 카드(wsCard)가 공고 상세와 같은 판정 항목(무주택 세대 owns)을 읽어, 규제지역이면 배지 '추첨제만'·숫자 대신 '추첨'·설명 '집이 있어 1순위 가점제로는 신청할 수 없고 추첨 물량으로만 뽑혀요'·요약 문장도 가점 비교 대신 추첨 안내, 비규제면 배지 '가능 · 무주택기간 0점'(가점 그대로). 판정 로직은 그대로 ② 원인: 검색이 주소 글자까지 보는데 인천계양 공고 주소 문자열에 '서울'이 들어 있어 섞임. 검색어가 시·도 이름(서울·서울시·서울특별시·경기도·전라북도 …)이면 그 시·도 공고만, '광주'는 광주광역시와 경기 광주시 둘 다. 그 밖의 검색어는 그대로
- 파일: docs/index.html, docs/changelog.json, VERSIONS.md, docs/updates/, tools/static_fragments.json
- 확인: 브라우저(밝은·어두운): 유주택 프로필로 광명(규제) 관심 카드 '추첨제만·추첨', 숭의역(비규제) '가능 · 무주택기간 0점·27/84', 상세 체크리스트와 일치. 검색: 서울 8=서울 공고 8, 서울시·서울특별시 8, 경기도 92, 인천 20, 전라북도=전북 3, 광진구·강변·계양 그대로, 서울+계양 0, 화면 목록에 인천 없음. 회귀: 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, 판정 검증 144/144, pytest 통과
- 기능: 없음(수정)
- 버전: v1.3.1
- 백업: backup/20261001-1402-wsowner

## 2026-10-01 13:47 · 인수인계: v1.3.0 까지 진행 현황
- 요청: 전략 실행 1·4·5·6번 진행 기록
- 변경: HANDOFF.md 진행 중인 일 맨 위에 버전·끝난 일·다음 후보·측정 확인 방법
- 파일: HANDOFF.md
- 확인: 문서만 바뀜. pytest 통과
- 기능: 없음(수정)
- 버전: 올리지 않음
- 백업: backup/20261001-1347-handoff4

## 2026-10-01 13:36 · 커밋 도우미: 받기 실패 시 멈춤, 수집 실행으로 공고 페이지 단계 확인
- 요청: (작업 중 발견) tools/qa/ship.sh 가 git pull 이 실패해도 멈추지 않고 다음 단계로 넘어감 (v1.3.0 올릴 때 로컬에서 다시 만든 공고 페이지 때문에 pull 실패 → 수동으로 정리 후 올림, 서비스 영향 없음)
- 변경: ship.sh — pull·push 실패 시 이유를 보여주고 멈춤. 스킬 노트: 로컬 정적 페이지 재생성으로 생긴 docs/notice 시각 diff 는 버림. collect.yml 단계 이름에 v1.2.0 표시(수집을 한 번 돌려 공고 페이지 갱신 단계를 확인하려는 변경, a089ef5 수집 실행이 대기 중 취소돼 아직 확인 못 함)
- 파일: tools/qa/ship.sh, .claude/skills/cheongyakpass-ops/SKILL.md, .github/workflows/collect.yml
- 확인: pytest 통과, 올린 뒤 수집 실행에서 '공고별 페이지 다시 만들기' 단계 결과 확인
- 기능: 없음(수정)
- 버전: 올리지 않음
- 백업: backup/20261001-1336-shipfix

## 2026-10-01 13:33 · 빠른 시작 (v1.3.0)
- 요청: 전략 보고서 6번 — 첫 판정까지 질문 줄이기 (지금은 24~33개 답해야 첫 판정)
- 변경: 처음 온 사람 카드에 '빠르게 시작하기' / '전부 입력하기'. 빠른 시작은 기존 인터뷰 단계 중 판정에 꼭 필요한 것만 보여줌(사는 곳 · 세대 구성 · 세대주가 된 날(세대주만) · 집과 혼인 · 청약통장 · 세대 주택·당첨 이력 = 5~6단계, 질문 문구·판정 로직은 그대로). 첫 단계 '이전'은 공고 화면으로, 마치면 공고 화면의 내 조건 카드에 판정 수와 '빠른 시작을 마쳤어요 … 채우면 특별공급·가점·현금까지' 안내, '빈 항목 채우기'는 전체 단계로. 측정 이벤트 quick/start·quick/done
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, docs/updates/, tools/static_fragments.json
- 확인: 측정(주택형 206개): 빠른 시작 답만으로 신청 가능 92·확인 필요 20·불가 94 (입력 전 확인 필요 206). 브라우저(밝은·어두운): 카드 두 버튼, 단계 순서, 끝난 뒤 카드 안내, 빈 항목 채우기 = 전체 단계, 첫 단계 이전 → 공고, 스위치 끄면 예전 카드, 오류 0. 회귀: 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, 판정 검증 144/144, pytest 통과
- 기능: quick_start
- 버전: v1.3.0
- 백업: backup/20261001-1333-quick

## 2026-10-01 13:31 · 공고별 검색 유입 페이지 (v1.2.0)
- 요청: 전략 보고서 5번 — "단지명 청약" 검색으로 들어오는 공고별 페이지
- 변경: tools/notice_pages.py — 수집한 공고마다 /notice/<공고번호>/ 일반 HTML: 청약 일정, 주택형별 전용면적·일반공급 세대·분양가·추정 시세 범위·1순위 해당지역 경쟁률(있을 때), 특별공급 유형별 물량 합계, 공고문에서 읽은 조건(재당첨·실거주·해당 지역·기타 지역·규제지역·분양가상한제), 출처(청약홈 공고·공고문 PDF·청약홈 경쟁률·특공 접수 현황, 시세는 국토부 실거래 추정), '내 조건으로 보기' → 앱 상세. 등급('로또'·'비추천')·개인 판정은 넣지 않음. /notice/ 목록(접수일 최신순), 사이트맵 10 → 65개 주소. 스위치 끄면 /notice/ 폴더를 지우고 사이트맵에서도 뺌. tools/build_static 이 부르고, collect.yml 에 수집 뒤 다시 만드는 단계 추가(목록에서 빠진 공고 페이지는 지움)
- 파일: tools/notice_pages.py, tools/build_static.py, .github/workflows/collect.yml, docs/notice/, docs/sitemap.xml, docs/config.json, docs/changelog.json, VERSIONS.md, docs/updates/, tools/static_fragments.json, tests/test_webpush.py
- 확인: 54개 공고 페이지 + 목록을 밝은·어두운 390px 로 열어 제목·가로 넘침·오류 0 (표는 가로 스크롤 안에서), 스위치 끄기 → 폴더 삭제·사이트맵 10개, 다시 켜기 → 55쪽. 테스트: 일정·분양가·시세 범위·특공 합계·링크·등급 단어 없음. pytest 통과
- 기능: notice_pages
- 버전: v1.2.0
- 백업: backup/20261001-1331-noticepages

## 2026-10-01 13:25 · 안 쓰는 코드 정리 (ntfy 삭제, api.py 표시)
- 요청: 전략 보고서 4번 — 유지보수만 늘리는 코드 정리 (화면 변화 없이)
- 변경: ① ntfy 알림 삭제(꺼져 있었고 웹 푸시로 대체): 화면 알림 안내·주제 복사·설정값(ntfy_server/topic, 스위치 ntfy_alerts)·방침 표의 ntfy 줄(이미 숨김 상태)·수집 뒤 ntfy 발송과 메시지 만들기(app/notify.py 는 설정·지난 결과 읽기만 남김) ② 테스트 이전: ntfy 메시지 테스트 3개 → 웹 푸시 이벤트 테스트로(새 공고·첫 실행·내일 시작·마감·접수 끝난 공고 제외), 'ntfy 가 남아 있지 않음' 테스트 추가 ③ README: app/api.py 는 사이트가 쓰지 않고 테스트용으로만 남김을 표시, webpush.py 추가 ④ FEATURES.md ntfy_alerts 줄에 삭제 표시
- 파일: docs/index.html, docs/config.json, app/notify.py, app/pipeline.py, tests/test_notice_and_notify.py, tests/test_cmpet.py, tests/test_pipeline.py, README.md, FEATURES.md, 정적 페이지(사용 안 하는 CSS 한 줄만 빠짐)
- 확인: pytest 120 통과(ntfy 테스트 대체), 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, 알림 미리보기·켜짐 표시 브라우저 검사 통과, 정적 방침·약관 문구 변화 없음
- 기능: 없음(수정)
- 버전: 올리지 않음 (화면 변화 없음)
- 백업: backup/20261001-1325-cleanup

## 2026-10-01 13:23 · 사용 측정 (v1.1.0)
- 요청: 전략 보고서 1번 — 무엇이 쓰이는지 재기 (프로필 완료율, 첫 판정, 확인 필요 원인, 재방문)
- 변경: metric() — 기존 방문 통계(GoatCounter) 이벤트 'm/…' 로 횟수만 보냄, 같은 기기·같은 이름은 하루 한 번(once 는 처음 한 번). 이벤트: visit/new·return-7d·return-later, profile/0·1-4·5-14·15-24·25+(입력 항목 수 구간), onboard/<단계 이름>·onboard/done, verdict/ok·unsure·rank2·no·first-clear, unsure/<규칙 이름>. 입력값은 보내지 않음. 개인정보처리방침 1항 방문 통계에 '기능을 쓴 횟수' 문장(스위치가 켜졌을 때만). 확인: GoatCounter 대시보드의 이벤트(m/…)
- 파일: docs/index.html, docs/config.json, docs/changelog.json, VERSIONS.md, docs/privacy/, docs/updates/, tools/static_fragments.json
- 확인: 브라우저: 첫 방문 이벤트, 상세 판정·확인 필요 규칙 이벤트, 하루 한 번만, 인터뷰 단계 이벤트에 입력값(소득·날짜) 없음, 7일 내 재방문, 스위치 끄면 이벤트 0·방침 그대로, 오류 0. 회귀: 판정 1,030개 조합 차이 0·화면 1,287개 오류 0, 판정 검증 144/144, pytest 통과
- 기능: usage_metrics
- 버전: v1.1.0
- 백업: backup/20261001-1323-metrics

## 2026-10-01 13:20 · 버전 관리 체계 (v1.0.0 기준점, v1.0.1)
- 요청: 완성도가 높으니 항상 백업하고, 새 기능은 언제든 원복 가능하게, 기능 업데이트는 버전별로 관리해 무엇이 바뀌었는지 기록
- 변경: ① 지금 main(d948d4d)을 release/v1.0.0 브랜치로 고정 ② VERSIONS.md — 버전 목록·되돌리는 방법(스위치 끄기 / 커밋 revert / release 브랜치로 화면 되돌리기)·버전 규칙 ③ tools/qa/release.sh — 기록 확인 후 release/vX.Y.Z 브랜치 생성(덮어쓰지 않음) ④ CLAUDE.md 9항, HANDOFF·스킬에 절차 ⑤ docs/changelog.json 항목에 version(0.9.0·1.0.0·1.0.1) ⑥ 업데이트 내역 화면에 버전 표시·'지금 버전' (스위치 version_label, 끄면 이전처럼 날짜만)
- 파일: VERSIONS.md, tools/qa/release.sh, CLAUDE.md, HANDOFF.md, .claude/skills/cheongyakpass-ops/SKILL.md, docs/changelog.json, docs/config.json, docs/index.html, docs/updates/, tools/static_fragments.json
- 확인: 브라우저(밝은·어두운): 업데이트 내역에 '지금 버전 v1.0.1'·버전 3개 표시, 스위치 끄면 버전 표시 없음, 오류 0. 판정 검증 144/144, pytest 통과
- 기능: version_label
- 버전: v1.0.1
- 백업: backup/20261001-1320-version

## 2026-10-01 13:09 · 인수인계: 제품 전략 보고서 요약
- 요청: 청약패스 제품 전략 보고서 (시장·경쟁·차별화·청약봇·수익·로드맵)
- 변경: 보고서는 사용자 문서(Claude Docs)로 작성. HANDOFF.md 진행 중인 일에 결론·3개월 순서·정리 후보·측정치 요약 추가 (코드 변경 없음)
- 파일: HANDOFF.md
- 확인: 문서만 바뀜. pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1309-handoff3

## 2026-10-01 12:46 · 커밋 도우미가 테스트 실패를 놓치던 문제
- 요청: (작업 중 발견) tools/qa/ship.sh 가 pytest 가 없거나 실패해도 그대로 커밋·올리기를 진행함 (직전 HANDOFF 커밋에서 'No module named pytest' 후에도 올라감, 문서만 바뀐 커밋이라 영향 없음)
- 변경: pytest 결과 코드를 확인해 실패·미설치면 멈추고 마지막 20줄과 설치 방법을 보여줌. python 이 없으면 python3 사용
- 파일: tools/qa/ship.sh
- 확인: pytest 없는 환경에서 실행 → '올리지 않음'으로 멈추고 아무것도 커밋되지 않음, pytest 있는 환경에서 123 통과 후 올라감(이 커밋)
- 기능: 없음(수정)
- 백업: backup/20261001-1246-ship

## 2026-10-01 12:46 · 인수인계: 알림 휴대폰 확인 완료
- 요청: 휴대폰에 알림이 잘 온다고 확인, 애드센스 신청 진행
- 변경: HANDOFF.md 진행 중인 일 갱신 (안드로이드 확인 완료·아이폰 미확인, 애드센스 신청 진행 중)
- 파일: HANDOFF.md
- 확인: 문서만 바뀜. pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1246-handoff2

## 2026-10-01 12:30 · 작업 방식 스킬을 저장소에
- 요청: 이 프로젝트에서 새 세션을 열어도 지금과 같은 노하우·업무 진행 방식으로 일하게
- 변경: .claude/skills/cheongyakpass-ops/SKILL.md — 세션 시작(저장소 준비·읽는 순서·환경), 사용자와 대화하는 방식, 작업 순서(백업→스위치→검증 5종→기록→ship→Actions 확인→HANDOFF 갱신), 알아 둔 함정, 자주 하는 답. CLAUDE.md 8항·HANDOFF.md 에서 스킬을 가리킴
- 파일: .claude/skills/cheongyakpass-ops/SKILL.md, CLAUDE.md, HANDOFF.md
- 확인: 문서만 바뀜. pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1230-skill

## 2026-10-01 12:26 · 세션 인수인계 문서와 검사 도구를 저장소로
- 요청: 이 세션이 지워져도 새 세션에서 지금까지 작업을 같은 방식으로 이어갈 수 있게
- 변경: ① HANDOFF.md — 사용자와 일하는 방식, 새 세션 환경 준비, 도구·Actions 목록, Secrets 이름, 진행 중인 일(웹 푸시 미리보기·공개 순서, 광고 신청 뒤 받을 값·시행일 예고), 최근 끝난 일 ② 세션 임시 폴더에만 있던 도구를 저장소로: tools/qa/ship.sh(테스트→WORK/FEATURES 기록→커밋→올리기), tools/qa/regress.cjs·regress.sh(origin/main 과 판정 1,030개 조합 비교 + 화면 1,287개 오류, 로컬 서버 없이 폴더를 바로 엶) ③ CLAUDE.md 8항: 새 세션 읽는 순서, 도구는 저장소에, 작업 끝날 때 HANDOFF '진행 중인 일' 갱신
- 파일: HANDOFF.md, CLAUDE.md, tools/qa/ship.sh, tools/qa/regress.cjs, tools/qa/regress.sh
- 확인: bash tools/qa/regress.sh → 판정 차이 0 (1,030개 조합)·화면 1,287개 오류 0, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1226-handoff

## 2026-10-01 12:21 · 알림 켜짐 표시
- 요청: 알림을 켜면 알림 버튼에 켜져 있다는 표시가 보이면 좋겠음
- 변경: 알림을 켠 기기는 위쪽 알림 버튼이 '알림 켜짐'(채운 종 아이콘·초록 배경)으로 바뀜. 이 기기에 표시값(cy-push-on)을 두고 화면을 열 때 등록된 서비스 워커의 실제 구독을 읽어 맞춤(이 표시 전에 켠 기기는 켜짐으로, 브라우저에서 알림을 막았거나 구독이 사라졌으면 해제). 알림 화면을 바로 열면 확인하는 동안 '확인 중…'으로 보여 꺼진 것처럼 깜빡이지 않게 함
- 파일: docs/index.html
- 확인: 브라우저(밝은·어두운): 켜기 전 '알림' → 켠 뒤 '알림 켜짐', 다시 열어도 유지, 표시값 없는 기존 구독 기기도 켜짐으로, 알림 화면 바로 열기 켜짐 상태, 구독이 사라지면 해제, 끄기 → 해제, 오류 0. 미리보기 아닌 방문자는 버튼 숨김 그대로, 화면 1,287개 오류 0, 판정 검증 144/144, pytest 통과
- 기능: web_push
- 백업: backup/20261001-1221-bell

## 2026-10-01 12:16 · 알림 서버 연결과 운영자 미리보기
- 요청: 알림 서버 배포 완료 (사용자가 Cloudflare 가입·Secrets 등록·'알림 서버 배포' 실행 #2 성공, 주소 https://cheongyakpass-push.ckwlsgur.workers.dev, 배포 확인 단계에서 health·VAPID·무토큰 401 통과)
- 변경: ① config push_api 연결, push_preview true — 스위치 web_push 는 그대로 끔. ?push=preview 로 연 기기에서만 알림 화면·버튼·방침 문구가 보이고(그 기기에 기억, ?push=off 로 해제) 다른 방문자는 그대로 ② 미리보기 중에도 수집 뒤 발송(구독자는 미리보기로 켠 기기뿐) ③ 알림 서버: 운영자 테스트 이벤트(all) — 설정과 상관없이 모든 구독자에게 ④ 워크플로 '알림 테스트 발송'(workflow_dispatch, 내용 입력)
- 파일: docs/config.json, docs/index.html, push/worker.js, push/test.mjs, app/pipeline.py, .github/workflows/push-test.yml
- 확인: push/test.mjs 전체 통과(테스트 이벤트 항목 추가), 브라우저: 일반 방문 버튼 숨김·방침 그대로, ?push=preview 버튼·미리보기 표시·켜기, 기억, ?push=off 해제, 다른 기기 #/alerts 직접 열기도 공개 전 안내, 오류 0. 판정 검증 144/144, 정적 페이지 변화 없음, pytest 통과
- 기능: web_push
- 백업: backup/20261001-1216-pushpv

## 2026-10-01 11:46 · 이용약관 제5조 오래된 문구 수정
- 요청: (출시 전 점검 중 발견) 이용약관 '아직 판정하지 않는 요건'에 이미 판정하는 출산가구 소득기준 완화가 남아 있음
- 변경: sp_birth_relax 가 켜져 있으면 예시에서 출산가구 소득기준 완화를 뺌. 정적 /terms/ 다시 만듦. 업데이트 내역에 한 줄
- 파일: docs/index.html, docs/changelog.json, docs/terms/, docs/updates/, tools/static_fragments.json
- 확인: 문법 검사, 정적 /terms/ 에 해당 문구 0건·'기관추천 특별공급 등)' 확인, 화면 문서 그리기 오류 0, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1146-terms

## 2026-10-01 11:30 · 웹 푸시 새 공고 알림 (Cloudflare Workers, 꺼 둠)
- 요청: 앱처럼 공고 알림을 웹에서도 받게 (B안: Cloudflare Workers 직접 운영)
- 변경: ① 알림 서버 push/worker.js — 구독 보관(KV 메타데이터: 푸시 주소·키·지역·종류·날짜만), VAPID 키를 서버에서 만들어 KV 에만 보관, RFC 8291 암호화·RFC 8292 서명을 WebCrypto 로 직접 구현, 구독자별로 지역·등급·전날 알림 설정에 맞는 이벤트만 골라 하루 한 통으로 묶어 발송, 404/410 만료 구독 즉시 삭제, 푸시 서비스 주소만 허용·청약패스 출처만 CORS·발송은 토큰 필요, 무료 한도(호출당 외부 요청 50·CPU 10ms)에 맞춰 10명씩 이어 받기 ② app/webpush.py — 수집 뒤 이벤트(새 공고: 공고 단위로 지난 결과와 비교·접수 끝난 공고 제외·30건 넘으면 비정상으로 보고 중단 / 내일 접수 시작: 특별공급 있으면 특별공급 시작일 / 내일 마감) 만들어 발송, 코드 변경 실행에서는 전날 알림 생략, 결과를 run-log [알림·웹푸시] 로 ③ 화면: 알림 화면(지역 17개·로또·고려만·전날 알림, 켜기·설정 저장·끄기), 아이폰 홈 화면 추가·앱 안 브라우저·차단 안내, docs/sw.js(알림 표시·누르면 그 공고 상세, 캐시 없음, 켤 때만 등록) ④ 개인정보처리방침: 수집 항목·목적·보유/파기·4-2 처리 위탁과 국외 이전(Cloudflare)·외부 서비스 표·권리·안전성, 시행일·개정 이력(push_legal_date), 이용약관 제4조 알림 지연 안내, 이용 안내 문구 — 모두 스위치가 켜지고 push_api 가 있을 때만 ⑤ 배포 워크플로 push-worker.yml(Cloudflare API 로 workers.dev 주소·KV 준비 → wrangler 배포 → 발송 토큰 등록 → health·VAPID·무토큰 401 확인 → push/deployed.json 기록), collect.yml 에 PUSH_SEND_TOKEN
- 파일: push/worker.js, push/test.mjs, push/wrangler.toml, push/package.json, app/webpush.py, app/pipeline.py, tests/test_webpush.py, docs/index.html, docs/sw.js, docs/config.json(web_push false, push_api, push_legal_date), .github/workflows/push-worker.yml, .github/workflows/collect.yml, requirements.txt(cryptography, 테스트용), .gitignore, 정적 페이지 재생성(CSS 만 바뀜)
- 확인: push/test.mjs 22개 항목 통과(구독·출처·주소 검증·410 미저장·설정 덮어쓰기·고르기/묶기·토큰·이어 받기 16명 2번·만료 삭제·해지·CORS). 워커가 보낸 실제 암호문 3통을 제3자 라이브러리(web-push-libs http_ece)와 워커와 따로 짠 파이썬 RFC 8291 복호화로 풀고 VAPID 서명 검증(tests/test_webpush.py), 암호화 정보 문자열·서명 입력을 바꾸면 테스트 실패 확인. 브라우저(크로미움, 로컬 워커): 켜기→서버 저장 항목·확인 알림 1통·VAPID 키 일치, 서비스 워커 등록, CDP 푸시 전달→알림 표시, 알림 누름→상세 이동, 상세 주소 새로 열기, 설정 저장·끄기→서버 삭제, 방침·약관 문구, 아이폰/카카오톡/차단 안내, 밝은·어두운 화면 가로 넘침 없음, 오류 0. 스위치 꺼진 상태: 직전 배포와 1,030개 조합 차이 0, 1,287개 화면 오류 0, 판정 검증 144/144, 정적 방침 페이지 문구 변화 없음. pytest 123 통과
- 기능: web_push
- 백업: backup/20261001-1130-push

## 2026-10-01 11:14 · 개인정보 보호책임자 이름 기입
- 요청: 개인정보 보호책임자 실명을 차진혁으로
- 변경: config.json privacy_officer = 차진혁 → 개인정보처리방침 서두·책임자 항목, 이용약관·이용 안내의 운영자 표기가 '서비스 운영자' 대신 실명으로 나옴. 정적 페이지(/privacy/ /terms/ /about/ /updates/) 다시 만듦. 업데이트 내역에 한 줄
- 파일: docs/config.json, docs/changelog.json, tools/static_fragments.json, docs/privacy/, docs/terms/, docs/about/, docs/updates/
- 확인: snapshot_docs 화면 오류 0, 정적 /privacy/·/about/ 에 '서비스 운영자' 0건·'차진혁' 표기 확인, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-1113-officer

## 2026-10-01 10:57 · 검색엔진·광고 심사용 정적 페이지와 청약 기준 가이드
- 요청: 애드센스 승인 위험(한 페이지 앱이라 콘텐츠 부족 판정) 줄이기
- 변경: ① 앱 문서 화면(만든 이유·이용 안내·이용약관·개인정보처리방침·업데이트 내역)을 /story/ /about/ /terms/ /privacy/ /updates/ 별도 주소의 일반 HTML 로(tools/snapshot_docs.cjs 가 앱 화면을 그대로 그림) ② 청약 기준 가이드 /guide/ — 2026년 소득 기준표(공고문 2026000414·2026820010 원문 표 13개 비율 × 3~8인), 공공·민영 특별공급 단계별 기준·출산가구 완화, 가점 계산표(2026000103 가점표·부양가족 인정 기준·배우자 통장, 판정 검증과 같은 계산의 예시 3개), 예치금 표(2026000453 원문)·1순위 조건 — 모든 숫자는 원문 표에서 바로 읽어 씀 ③ 페이지마다 제목·설명·canonical·OG, 베타·참고용 안내, 공통 메뉴·바닥 링크 ④ sitemap.xml 에 10개 주소 ⑤ 앱 이용 안내 문서 목록에 '청약 기준 가이드' 링크(기능 static_pages) ⑥ verify.yml 이 화면·업데이트 내역이 바뀔 때마다 정적 페이지를 다시 만들어 올림. 업데이트 내역에 한 줄 추가
- 파일: tools/snapshot_docs.cjs, tools/build_static.py, tools/static_fragments.json, docs/story/, docs/about/, docs/terms/, docs/privacy/, docs/updates/, docs/guide/, docs/sitemap.xml, docs/index.html, docs/config.json, docs/changelog.json, .github/workflows/verify.yml, tests/test_pipeline.py
- 확인: 가이드 숫자가 원문 표 숫자 그대로인지 테스트(9,793,892·24,342,602, 예치금 1,500/1,000/500, 가점 32·17). pytest 115 통과. 브라우저(밝은·어두운, 휴대폰 폭): 9쪽 모두 열림·제목·가로 넘침 없음·오류 0. 앱 전체 화면 1,287개 오류 0, 직전 배포와 1,030개 조합 차이 0
- 기능: static_pages
- 백업: backup/20261001-1057-static

## 2026-10-01 10:50 · 광고 준비: 광고 자리·개인정보처리방침·이용약관 광고 조항 (스위치 꺼 둠)
- 요청: 애드센스·애드핏 등록 전에 개인정보처리방침 개정 문안을 만들어 두기
- 변경: 기능 ads (기본 꺼짐). config.json 에 adsense_client(ca-pub-…)·adsense_slot_feed/detail 또는 adfit_units 를 넣고 스위치를 켜야만 동작. 켜지면 ① 개인정보처리방침: 1항 '광고' 처리 내용(행태정보, 운영자는 받지 않음, 인터뷰 입력값은 보내지 않음), 2항 목적, 5항 외부 서비스 표에 Google AdSense·카카오 애드핏, 7항 '쿠키와 맞춤형 광고(행태정보)'(Google·서드 파티 공급업체 쿠키 사용, 행태정보 항목·목적·보유, Google 광고 설정·aboutads.info·브라우저·휴대폰 광고 식별자 거부 방법, 사업자 정책 링크), 시행일은 ads_legal_date ② 이용약관 제4조 광고 게재 조항 ③ 이용 안내 개인정보 안내에 광고 문장 ④ 광고 자리: 공고 목록 5번째 카드 뒤, 공고 상세 맨 아래(판정·추천 영역과 떨어진 곳)에 '광고' 표시, 광고 스크립트는 켜졌을 때만 불러옴. 그 밖에 알림 기능이 꺼져 있으면 방침 5항 표의 ntfy 줄 숨김
- 파일: docs/index.html, docs/config.json
- 확인: 근거 — AdSense 필수 공개사항(support.google.com/adsense/answer/1348695: Google·서드 파티 쿠키 사용 고지, 맞춤 광고 사용 중지 www.google.com/settings/ads, aboutads.info). pytest 통과, 문법 검사. 꺼진 상태: 직전 배포와 1,030개 조합 차이 0, 전체 화면 1,287개 오류 0. 시험 값으로 켠 상태: 목록·상세 광고 자리 각 1, 광고 스크립트 로드, 방침 1·2·5·7항·시행일·약관 조항 표시, 오류 0
- 기능: ads
- 백업: backup/20261001-1050-ads

## 2026-10-01 10:42 · 검증 절차·업데이트 내역 관리 규칙화 (CLAUDE.md 4·7항)
- 요청: 데이터 수집되면 공고문·앱 수치를 무조건 검증하는 프로세스, 베타 기간 업데이트 내역 관리
- 변경: CLAUDE.md 4항에 6) 공고문 원문 ↔ 앱 수치 대조(매 수집 필수, 불일치는 사고로 처리·원인 쪽을 고치고 테스트 추가, 새 고정 수치는 대조 추가) 7) 판정 검증 사례(100건+, 기대값은 화면 코드와 따로 공고문·법령 표로, 규칙 변경 시 경계값 사례 추가, 올리기 전 로컬 전부 일치) 8) 검증 현황 공개(verify-status.json ok 확인 후 작업 종료, 이슈 우선 처리) 추가. 7항 '베타 업데이트 내역' 신설(사용자에게 보이는 변경은 changelog.json 에 같은 커밋으로). 이용 안내 '데이터와 검증 방식'의 검증 설명을 새 절차로 갱신(verify_badge 켜져 있을 때)
- 파일: CLAUDE.md, docs/index.html
- 확인: pytest 통과, 문법 검사, 판정 사례 144/144, 이용 안내 문구 브라우저 확인, 전체 화면 1,287개 오류 0
- 기능: 없음(수정)
- 백업: backup/20261001-1042-rules

## 2026-10-01 10:37 · 베타 업데이트 내역 화면·데이터 검증 현황 표시
- 요청: 베타 기간 동안 업데이트 내역(무엇이 바뀌고 개선됐는지) 관리, 검증 결과를 신뢰할 수 있게
- 변경: ① 업데이트 내역(기능: changelog) — docs/changelog.json 에 날짜별 변경(새 기능·개선·수정·검증)을 사용자 말로 적고, 이용 안내 > 문서 > '업데이트 내역 (베타)' 화면에서 보여줌. 2026-09-30·10-01 변경 정리 ② 데이터 검증 현황(기능: verify_badge) — 이용 안내에 docs/verify-status.json(마지막 검증 시각, 판정 검증 사례 n/144, 공고문 원문 대조 요약, 정답 데이터) 카드. 검증에서 차이가 나면 '베타 · 참고용' 상자가 붉게 바뀌고 '최근 자동 검증에서 공고문과 다른 값이 발견돼 확인 중' 표시. 두 기능은 같은 화면 코드라 한 커밋에 넣고 스위치는 따로 둠
- 파일: docs/index.html, docs/config.json, docs/changelog.json
- 확인: pytest 통과, 문법 검사. 브라우저: 이용 안내 검증 카드(144/144, 공고문 53건·기준표 258줄·분양가 204/204), 업데이트 내역 화면·뒤로가기, 검증 실패 상태를 넣으면 베타 상자 붉게 바뀜. 전체 화면 1,287개 오류 0, 직전 배포와 1,030개 조합 차이 0, 공고 × 프로필 2,678장 오류 0
- 기능: changelog, verify_badge
- 백업: backup/20261001-1037-updates

## 2026-10-01 10:29 · 판정 검증 사례 144건 + 수집·코드 변경마다 자동 실행
- 요청: 검증용 샘플 100개 이상으로 돌려서 이상 없는지 확인, 데이터 수집 뒤 공고문·법령과 앱 수치를 무조건 검증하는 프로세스
- 변경: ① tools/make_judge_cases.py — 화면 판정 엔진과 따로, 공고문·법령 표를 옮긴 계산(oracle)으로 기대값을 정한 사례 144건 생성(tests/judge/cases.json): 가점 41(무주택기간·부양가족·통장·배우자 통장, 경계일), 공공 특별공급 46(5개 유형 소득 단계 경계 ±1만원, 출산가구 완화, 자산·자동차 경계, 맞벌이), 민영 특별공급 17(130·160%, 신혼 맞벌이 1인 기준, 추첨 부동산 3억3,100만), 청약통장 1순위 12(24개월·예치금 지역별), 공공 일반공급 60㎡ 이하 8, 신혼희망타운 소득·총자산 10, 거주지 10. 기준 공고는 tests/judge/listings.json 에 고정(2026000414·453·103·409·443·820010) ② tools/judge_check.cjs — 브라우저에서 화면 판정 함수로 사례를 돌려 기대값과 비교, docs/judge-status.json ③ tools/verify_status.py — 판정 사례 + 수집 기록의 [검증·공고문]·[검증·정답]을 모아 docs/verify-status.json, 하나라도 다르면 실패 ④ collect.yml: 수집 뒤 판정 사례·검증 요약을 반드시 실행하고 실패하면 Actions 실패 + 이슈 알림(공고문 불일치·판정 불일치 줄 포함) ⑤ verify.yml: docs/index.html·사례가 바뀌면 바로 판정 사례 실행
- 파일: tools/make_judge_cases.py, tools/judge_check.cjs, tools/verify_status.py, tests/judge/cases.json, tests/judge/listings.json, tests/test_pipeline.py, .github/workflows/collect.yml, .github/workflows/verify.yml, docs/judge-status.json, docs/verify-status.json
- 확인: 처음 실행 142/144 → 불일치 2건은 사례 쪽 실수(신생아 자녀 생일이 기본값에 덮임)라 사례를 고침 → 144/144 일치. 판정 코드에 일부러 버그 3개(통장 점수 +1, 서울 예치금 250, 신생아 2단계 145%)를 넣으면 31건이 불일치로 잡히는 것 확인 후 원복. 오라클 금액이 공고문 표(130% 3인 9,793,892원 등)와 같은지 테스트. 생성기와 저장본이 같은지 테스트. pytest 114 통과. 직전 수집(dd6839c) 공고문 대조: 공고문 53건·기준표 258줄·분양가 204/204 일치, 불일치 0
- 기능: 없음(수정)
- 백업: backup/20261001-1029-verify

## 2026-10-01 10:29 · 수집마다 공고문 원문 ↔ 앱 수치 자동 대조 추가
- 요청: 데이터가 수집되면 공고문과 앱에 적용된 수치가 맞는지 무조건 검증하는 프로세스
- 변경: ① 공고문을 읽을 때 대조용 원문 숫자(facts)를 함께 뽑아 보관 — 소득 기준표('도시근로자 … N%' 3인 이하~8인, 공공·민영·신혼희망타운 표기 모두), 민영 예치금 표(표 머리글의 지역 순서를 읽음), 공공 부동산·자동차 기준(천원), 민영 부동산 기준(만원), 주택형별 청약홈 분양가가 원문 공급금액에 나오는지 ② app/crosscheck.py 가 화면 고정 수치(docs/index.html 의 SP_INCOME_2025·SP_ASSET·ACCOUNT_DEPOSIT·출산가구 완화 자산값)를 코드에서 직접 읽어 원문과 비교 ③ 다르면 해당 공고 주택형에 '공고문 대조: …' 확인 필요를 붙이고(화면 '데이터 확인 필요') 실행 기록에 [검증·공고문 불일치], 요약은 [검증·공고문] ④ PARSER_VERSION 9 (모든 공고문 다시 읽기, 시간 제한으로 두 번에 걸쳐 완료)
- 파일: app/notice_pdf.py, app/crosscheck.py, app/pipeline.py, docs/config.json, tests/test_pipeline.py
- 확인: 보관된 공고문 57건 전체 대조 — 소득 기준표·예치금 표 287줄, 공공 자산 기준 5건, 민영 부동산 기준 24건 모두 화면 수치와 일치 (처음 대조 때 나온 차이 2종은 대조 도구 쪽 문제였음: 0.5원 반올림 방식, 예치금 표 지역 순서가 공고마다 다름 → 고침). 현재 공고 206개 주택형 분양가 206/206 원문에서 확인. 일부러 틀린 값(소득 1원, 예치금, 분양가)을 넣으면 잡아내는 테스트 추가. pytest 112 통과. 올린 뒤 수집 실행의 [검증·공고문] 줄 확인 예정
- 기능: notice_crosscheck
- 백업: backup/20261001-1029-verify

## 2026-10-01 09:52 · 관심 공고 카드에 '왜 이렇게 판정했나' 접기 추가
- 요청: 관심 공고 카드의 '소득 1구간(우선공급)에서 뽑혀요' 같은 판정이 어떤 로직으로 나왔는지, 공고 상세처럼 정리된 설명을 달아 달라
- 변경: 가점 컷 탭 관심 공고 카드의 줄마다 '왜 이렇게 판정했나' 접기 추가. 특별공급 줄: ① 소득 구간 — 내 월평균 소득·가구원수 기준 %와 가구원 내역, 외벌이/맞벌이 기준, 구간별 물량·소득 기준(%·월 금액, 출산가구 완화 반영, 민영 추첨 몫은 부동산 기준) 표에 내 구간 표시 ② 조건별 판정(✗·!·✓ 목록) ③ 뽑는 방식 ④ 근거 공고문·이 공고 모집공고문 링크. 일반공급 줄: 자격 체크리스트 항목(불가·확인 필요·충족 순, 항목 설명 포함). 모두 공고 상세와 같은 판정 결과(spJudge·eligibility)를 정리만 하고 새 판정은 만들지 않음
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 문법 검사. 브라우저(밝은·어두운): 광명 시티프라디움 59A — 일반공급 8개 항목, 신생아 '월평균 4,166,667원 · 3인 55% → 소득 1구간(130% 이하, 월 9,793,892원)', 신혼부부 100%·140% 표, 인천계양 A6 공공 기준표, 가로 넘침 없음. 공고 × 프로필 2,678장 오류 0, 직전 배포와 1,030개 조합 차이 0, 전체 화면 1,287개 오류 0, 스위치 끄면 접기 없음
- 기능: ws_why
- 백업: backup/20261001-0952-why

## 2026-10-01 09:46 · 신혼희망타운 공고의 '특별공급 없음'과 '특별공급 세대수 56' 표기 충돌 수정
- 요청: 인천계양 A17 신혼희망타운 55B에서 자격 체크리스트는 '이 주택형은 특별공급 없음', 아래 카드는 '특별공급 세대수 합계 56세대'로 나와 헷갈림
- 원인(표기): 데이터는 맞음 — 청약홈은 신혼희망타운 주택형 공급 전체(55B 본청약 56세대, 모집공고문 공급표 '055.8800B … 56'과 같음)를 특별공급으로 집계하고 일반공급 0으로 줌. 그런데 화면은 신혼희망타운을 일반공급처럼 다뤄 체크리스트는 '일반공급 / 특별공급 없음'(유형별 특별공급 판정 대상이 아니라서), 세대수 카드는 '특별공급 56 · 유형별 세대수 없음'으로 서로 다르게 보였음
- 변경: 신혼희망타운 공고는 ① 체크리스트 첫 줄 이름을 '일반공급' → '신혼희망타운'('신혼부부·예비신혼부부·한부모가족만 신청하는 공급'), 특별공급 줄은 '따로 없음 — 이 주택형 56세대는 모두 신혼희망타운 공급이에요 (청약홈에는 특별공급으로 집계)' ② 세대수 카드를 '공급 세대수 (이 주택형) 56세대 — 모두 신혼희망타운 공급, 1단계 우선공급(30%) → 2단계 일반공급(60%) → 3단계 추첨, 누구나 넣는 일반공급과 따로 고르는 특별공급 유형은 없음 · 청약홈에는 특별공급 56·일반공급 0으로 집계'로 ③ '일반공급 조건'·'일반공급 · 기본 요건 충족'·관심 공고 카드 줄 이름도 '신혼희망타운'으로, 지역 순서 설명은 '1~3단계 공통'. 판정은 그대로
- 파일: docs/index.html, tests/test_residence.py
- 확인: 모집공고문 2026820008·009·010·011 '1단계 우선공급·2단계 일반공급·3단계 추첨공급', '주택형(타입)별 공급량의 30%·60%'를 테스트로 고정(test_town_supply_stages_in_originals). pytest 109 통과, 문법 검사. 브라우저: A17 55B 상세 체크리스트·세대수 카드 문구 확인, 직전 배포와 1,030개 조합 판정 차이 0, 전체 화면 1,287개 오류 0, 신혼희망타운 판정 점검(qa11~13) 정상
- 기능: 없음(수정)
- 백업: backup/20261001-0946-townlabel

## 2026-10-01 09:29 · 관심 공고 '어느 쪽이 유리할까'를 결론 위주로 정리
- 요청: 추천 상자의 문구가 번잡해 요점 위주로, 세부 내용은 정리된 형식으로
- 변경: 상자를 ① 결론 한 줄(예: '점수에 자신 있으면 신생아, 아니면 추첨인 생애최초' / '모두 추첨이라 점수와 상관없어요 · 경쟁률이 가장 낮았던 신생아 (9.0:1)') ② 핵심 2~3개 글머리(지역 몫, 2순위, 경쟁률 근거·없음) ③ '자세히 보기' 접기 — 유형별 비교표(뽑는 방식·노릴 몫·내 점수·경쟁률), '단계별 물량' 목록(한 번 신청·자동 단계 포함), '알아둘 것' 목록(특별공급 한 가지만, 특별공급 1개+일반공급 1개, 일반공급 가점 비교), 출처로 나눔. 아래 유형별 줄에서 표와 겹치는 '노릴 수 있는 몫'은 뺌. 판정·점수·숫자는 그대로. 끄면 이전 상자
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 문법 검사. 브라우저(밝은·어두운, 360~390px): 인천계양 A6(LH) · 광명(이 공고 경쟁률) 카드, 자세히 펼침, 가로 넘침 없음. 공고 × 프로필 2,678장 오류 0, 직전 배포와 1,030개 조합 차이 0, 전체 화면 1,287개 오류 0, 스위치 끄면 이전 문구
- 기능: ws_compact
- 백업: backup/20261001-0929-wscompact

## 2026-10-01 09:25 · 공공분양 특별공급에 출산가구 소득·자산 완화 반영
- 요청: 점검 중 발견한 문제 수정 — 특별공급 판정에 출산가구 완화가 없어, 2023.3.28 이후 출생 자녀가 있는 가구에 '소득 기준 초과 불가'가 잘못 나올 수 있음
- 변경: 공공분양(국민) 특별공급(신생아·신혼부부·생애최초·다자녀·노부모부양) 소득 단계 기준에 2023.3.28 이후 출생 자녀(태아 포함) 1명 +10%p, 2명 이상(그 뒤 출생 1명 + 그 전 출생 자녀 포함) +20%p 가산. 부동산·자동차 기준도 <표3> 완화값(부동산 2억 3,705만·2억 5,860만, 자동차 4,996만·5,451만) 적용. 완화로 들어간 경우 '출산가구 완화 +N%p 적용 (출생·임신 증빙 필요)' 표시. 자녀 정보가 없어 완화 여부를 모르면 +20%p 안쪽은 '불가' 대신 '출산가구 완화 확인 필요'(가능으로 단정하지 않음). 자녀가 없거나 모두 2023.3.28 전 출생이면 이전과 같음. 민영 특별공급은 공고문(2026000103·443)에 출산가구 완화가 없어 그대로. 공공 신혼·신생아 점수의 소득 80% 항목은 그대로
- 파일: docs/index.html, docs/config.json, tests/test_residence.py
- 확인: 공고문 2026000409·414 「(출산가구 소득기준 완화) … 1명만 있는 경우 10%p, 2명 이상 … 20%p 가산」, 「적용대상: 다자녀·노부모부양·생애최초·신혼부부·신생아 특별공급 및 전용면적 60㎡ 이하 일반공급」, <표3> 237,050·258,600천원 / 49,960·54,510천원을 테스트로 고정(test_public_special_birth_relax_in_originals). pytest 통과, 문법 검사. 경계값(A6 59A, 3인): 신생아 141%·150% +10 → 일반공급 가능, 151% +10 → 불가, 160% 자녀 2명 +20 → 가능, 자녀 정보 없음 141% → 확인 필요·161% → 불가, 109% +10 → 우선공급, 부동산 23,705만 충족·23,706만 초과·25,860만(+20) 충족·정보 없음 24,000만 확인 필요, 자동차 4,996만 충족·4,997만 초과, 2019년생만 있는 가구는 변화 없음, 민영 공고 변화 없음. 공공 공고 전체 41,800개 조합 비교: 불가→가능 4,879건(모두 2023.3.28 이후 출생 자녀 있음), 불가→확인 필요 3,582건(자녀 정보 없음), 자녀 없음·옛 출생 자녀 조합 변화 0. 전체 화면 1,287개 오류 0, 특별공급 카드 228개 이상 없음
- 기능: sp_birth_relax
- 백업: backup/20261001-0925-birth

## 2026-10-01 09:16 · 이용 안내 문구 점검·갱신
- 요청: 이용 안내 쪽 문구 중 바꿔야 할 것 점검
- 변경: ① '아직 판정하지 않는 것'이 옛 목록(해당지역 거주기간·가구원수 산정 등 — 지금은 판정함)이라 지금 실제로 판정하지 않는 것으로 고침: 기관추천·이전기관·청년 특별공급, 특별공급의 예비신혼부부·한부모 가족과 출산가구 소득 완화(신혼희망타운은 판정), 소형·저가주택 등 무주택 예외, 과거 특별공급 당첨 여부, 해외 체류 기간(계속 90일·연 183일) ② 베타 안내 문단 추가(beta_notice 켜져 있을 때) ③ 갱신 시각을 '매일 새벽 5시 30분쯤'으로(수집 일정 cron 30 20 * * * UTC) ④ 알림 기능이 꺼져 있으면 '알림을 구독하면 …' 문장 숨김 ⑤ 데이터 안내: 모집공고문에서 읽는 항목(거주 요건·소득·자산 기준·특별공급 선정 방식·접수 일정), 경쟁률에 특별공급 유형별 접수 현황(LH 청약플러스 접수 공고는 없음) 추가. 이용약관·개인정보처리방침 본문은 시행일이 있는 문서라 바꾸지 않음. 직전 beta_notice 기록의 화면 수를 1,287개로 바로잡음
- 파일: docs/index.html, docs/config.json, WORK.md
- 확인: 근거 — spJudge 에 출산가구 완화·예비신혼부부 판정 없음(공고문 확인 안내), SP_NAME 에 기관추천·청년 없음, 무주택 예외·특별공급 당첨 이력·해외 체류는 입력·판정 없음, collect.yml cron. pytest 통과, 문법 검사, 브라우저에서 이용 안내 문구 확인, 전체 화면 1,287개 오류 0
- 기능: about_v2
- 백업: backup/20261001-0916-about

## 2026-10-01 09:13 · 베타 표시와 '참고용' 공지를 눈에 띄게
- 요청: 베타 버전임을 표시하고, 참고용이라는 공지를 더 눈에 띄게
- 변경: 공고 목록 머리의 '청약패스' 옆에 '베타' 표시. 공고 목록·공고 상세·가점 컷 탭 맨 위에 주의 색 상자 '베타 · 참고용 — 모든 판정은 참고용 추정이에요. 신청 전 모집공고문과 청약홈 청약자격 확인으로 꼭 확인하세요 (자세히 → 이용 안내)' (상세는 '이 화면의 자격·점수·마진은 공개 자료와 내 입력으로 계산한 참고용 추정'). 겹치던 작은 회색 '참고용 추정' 문구는 이 기능이 켜져 있으면 숨김. 밝은·어두운 화면 색 토큰 사용
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 문법 검사, 밝은·어두운 화면 캡처(목록·상세), 직전 배포와 1,030개 조합 차이 0, 전체 화면 1,287개 오류 0, 데이터 실패 화면 정상
- 기능: beta_notice
- 백업: backup/20261001-0913-beta

## 2026-10-01 09:02 · 내 조건 인터뷰 다듬기 (중복 질문 정리·단계 합치기·문구 정리)
- 요청: 내 정보 입력 인터뷰 질문을 최적화하고 이해하기 쉽게 다듬기, 중복으로 묻는 정보 정리
- 변경: ① '집을 가져본 적이 없나요(생애최초)'(firstTime)는 판정 어디에도 쓰이지 않고 '세대원 모두 집을 가진 적 없나요'와 겹쳐 뺌(내 정보 요약은 세대 주택 이력으로 표시) ② 본인·배우자·같은 세대 부모님 명의 집이 지금 있다고 답했으면 '세대원 주택 이력'은 묻지 않고 '있음'으로 둠(답을 바꾸면 자동 값 되돌림) ③ 당첨 이력: 청약통장 단계의 '재당첨 제한 기간인가요?'와 '최근 5년 안 당첨'을 '나나 세대원이 당첨된 적 있나요?' 하나로 먼저 묻고, '있어요'일 때만 5년 내 여부·재당첨 제한을 물음('없어요'면 둘 다 없음, 예전 답에서 이어받기, '있어요'인데 재당첨 제한 미입력이면 '확인 필요') ④ '혼인신고일·배우자 통장' 단계를 '배우자 정보'에 합침(17→16단계, 기혼·수도권·다자녀 예시 15→14) ⑤ 본인 연소득을 맨 끝 '소득과 대출'에서 '세대 소득·자산'(세대 소득을 비우면 본인+배우자로 추정한다는 질문) 앞으로, 배우자 대출 월 상환액은 '소득과 대출'로 옮김 ⑥ 수도권 '거주 시작일'(다자녀 배점용)이 비어 있으면 앞의 시·도 전입일로 채우고 바꿀 수 있게 안내(같거나 더 늦은 날이라 점수를 부풀리지 않음), 단계 이름을 '수도권 거주 시작일'로 ⑦ 문구: 통장 '예치금'과 '납입 인정 금액'을 '통장 잔액(민영주택 기준)'과 '납입 인정 금액(공공분양 기준, 회차당 최대 25만원)'으로 구분, 같은 등본 자녀 수는 '태어난 자녀만'(태아는 따로 셈), 세대 구성 '기타'에 예시, 배우자 주택에 분양권 포함, 배우자 단계에 각 값의 쓰임 안내. 스위치를 끄면 이전 인터뷰 그대로
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 스크립트 문법 검사. 브라우저: 단계 목록 비교(이전 17개 구성 → 새 구성), 본인 집 있음 → 세대 주택 이력 자동 '있음'·질문 숨김, 집 없음으로 바꾸면 되돌림, 당첨 '없어요' → 5년 내·재당첨 제한 모두 없음, '있어요' → 두 질문 표시·재당첨 제한 미입력이면 '확인 필요', 예전 '5년 내 당첨 있음' 답 → '있어요'로 이어받음, 서울 전입일 → 수도권 거주 시작일 자동 채움. 직전 배포와 1,030개 조합 판정·점수·마진 차이 0, 전체 화면 1,287개 오류 0(합친 단계 1개 감소), 인터뷰·내 조건 단계별 수정·뒤로가기·데이터 실패 흐름 정상, 공고 × 프로필 2,678장 오류 0, 스위치 끄면 이전 단계 구성 그대로
- 기능: onboard_v2
- 백업: backup/20261001-0902-onb

## 2026-10-01 08:41 · 특별공급 경쟁률 출처를 청약홈 '특별공급 청약접수 현황' 화면으로, 출처 링크 규칙 추가
- 요청: 출처를 API 링크로 달지 말고 실제 데이터가 보이는 화면으로 — 이를 규칙으로 추가
- 변경: 관심 공고 특별공급 경쟁률의 출처를 공공데이터포털 API 안내 페이지 대신 청약홈 '특별공급 청약접수 현황' 화면(selectSpsplyReqstStusPopup.do?houseManageNo=…)으로 바꿈. 이 공고 결과는 이 공고 화면, 근처 지난 공고는 공고 이름마다 그 공고 화면 링크. CLAUDE.md 5장에 '출처 링크는 API·명세 페이지가 아니라 숫자가 보이는 화면으로, 새 주소는 열어서 수집 값과 대조 후 사용, 확인 못 하면 이름만' 규칙 추가
- 파일: docs/index.html, CLAUDE.md
- 확인: 근거 자료 모으기(c890585) evidence/pages/applyhome-special.txt — 2026000453 화면에 059.9742A 배정세대수 신혼부부 3·생애최초 1·신생아 2, 접수건수 해당지역 7·13·5 + 기타지역 38·92·13 → 합 45·105·18 로 수집 값(API)과 일치. 후보 주소 selectAPTSpsplyReqstStusPopup·selectSpsplyCompetitionPopup 은 404. pytest 통과, 문법 검사, 브라우저에서 광명(이 공고 화면 링크)·숭의역(근처 공고 이름별 화면 링크) 확인, 공고 × 프로필 2,678장 오류 0
- 기능: 없음(수정)
- 백업: backup/20261001-0841-srcrule

## 2026-10-01 08:41 · 청약홈 특별공급 신청현황 화면 주소 확인용 점검
- 요청: 출처는 API 링크가 아니라 실제 데이터가 보이는 화면으로 달아 달라
- 변경: 근거 자료 모으기에 probe_applyhome_result_pages 추가 — 청약홈 결과 화면 후보 주소(selectAPTCompetitionPopup 등)를 열어 특별공급 유형별 숫자가 보이는지 evidence/pages/applyhome-special.txt 에 기록. 서비스 수집·화면은 바꾸지 않음
- 파일: tools/rules_probe.py
- 확인: 문법 검사, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-0841-srcrule

## 2026-10-01 08:37 · 특별공급 경쟁률에 출처 링크 표시, 관심 공고 머리말 문구 갱신
- 요청: 이 공고 경쟁률은 어디서 확인한 것인지(출처) 질문
- 변경: 관심 공고 '어느 쪽이 유리할까'의 경쟁률 안내 끝에 출처 링크 추가 — '청약홈 특별공급 신청현황 (한국부동산원·공공데이터포털)'(data.go.kr 15098905)과 '청약홈 이 공고'(공고 상세). '유형별 경쟁률은 반영하지 않았어요'로 남아 있던 탭 머리말을 ws_reco_v2 가 켜져 있으면 '공고문 선정 방식·배정 비율과 청약홈 특별공급 신청현황(있을 때)으로 만든 추정'으로 고침
- 파일: docs/index.html
- 확인: pytest 통과, 문법 검사, 브라우저에서 출처 링크 표시·공고 × 프로필 2,678장 오류 0·전체 화면 1,288개 오류 0
- 기능: 없음(수정)
- 백업: backup/20261001-0837-spsrc

## 2026-10-01 08:15 · 관심 공고 특별공급 점수 내역·올리는 방법 표시
- 요청: 점수가 어떻게 산정됐는지, 점수를 올리려면 무엇을 개선해야 하는지 알려주기
- 변경: 가점 컷 탭 관심 공고 카드의 점수 순 특별공급 행(공공 신혼부부·신생아, 다자녀)에 '점수는 어떻게 나왔나 · 올리려면' 접기 추가 — 항목별 내 점수/만점과 기준(공고문 점수표), 다음 공고를 위한 안내(납입 횟수: 다음 구간까지 남은 개월, 거주기간: 공고 지역에 살아야 점수·계속 살면 다음 구간 날짜, 혼인기간: 점수가 줄어드는 날짜(경고색), 다자녀 무주택·거주·통장 가입기간: 다음 구간 날짜). '점수는 공고일 기준이라 이 공고에서는 바뀌지 않아요' 명시, 빠진 입력은 입력하기 버튼. 판정·점수 계산식은 그대로(pubPoints 가 항목 목록을 함께 돌려줌, mcScore 항목에 시작일·구간 추가)
- 파일: docs/index.html, docs/config.json, tests/test_residence.py
- 확인: 공고문 2026000409·414 점수표 문장을 테스트로 고정(test_public_points_table_in_originals). pytest 통과, 문법 검사. 브라우저: A6 59A 서울 거주(거주 0점·납입 15회 → 9개월 뒤 +1), 인천 1년 미만(계속 살면 2026.10.01 이후 +1), 혼인 2023.05 → 2028.05.01 이후 1점으로 줄어요, 다자녀 통장 2030.01.01 이후 +5. 공고 × 프로필 2,678장 오류 0, 직전 배포와 1,030개 조합 판정·점수 차이 0, 전체 화면 1,288개 오류 0, 특별공급 카드 228개 이상 없음, 스위치 끄면 접기 없음
- 기능: score_tips
- 백업: backup/20261001-0815-tips

## 2026-10-01 08:15 · 관심 공고 추천에 '특별공급은 한 번 신청, 단계는 자동' 안내 추가
- 요청: 1단계→2단계→3단계가 특별공급을 여러 번 넣는 것인지, 한 번 신청으로 이어지는 것인지 헷갈림
- 변경: '어느 쪽이 유리할까'에 '특별공급은 한 번만 신청해요. 소득 기준에 맞는 첫 단계부터 경쟁하고, 떨어지면 다음 단계로 자동으로 넘어가 다시 경쟁해요 (따로 신청하지 않아요)' 한 줄 추가 (단계가 2개 이상일 때만)
- 파일: docs/index.html
- 확인: 근거 — 공공 2026000409·414·416 「1단계 우선공급 낙첨자 전원을 대상으로」(테스트 test_public_special_selection_method_in_originals 로 고정), 민영 2026000103·443 「각 단계별 낙첨자는 다음 단계 공급대상에 포함」. pytest 통과, 문법 검사, 브라우저에서 문구 표시·공고 × 프로필 2,678장 오류 0
- 기능: 없음(수정)
- 백업: backup/20261001-0815-tips

## 2026-10-01 07:41 · 특별공급 경쟁률 표시 보완 (공공분양은 근처 민영 결과 제외, 미달 표기)
- 요청: sp_competition 배포 후 실제 수집 결과 확인 중 보완
- 변경: 첫 수집 결과(이 공고 결과 22개 공고·98개 주택형, 근처 지난 공고 30개 주택형) 확인. 공공분양(국민) 공고에는 선정 방식이 다른 근처 민영 공고 경쟁률을 빌려 쓰지 않고 이 공고 결과만 사용. 신청이 공급보다 적으면 '0.0:1' 대신 '미달'. 이 공고 결과만 있을 때 안내를 '특별공급 접수가 끝나 실제 결과'로, 신청 건수에 부적격이 섞일 수 있음을 표시
- 파일: docs/index.html
- 확인: 실제 수집 데이터로 광명 시티프라디움 59A 카드 — 신생아 9.0:1(18/2)·신혼부부 15:1(45/3)·생애최초 105:1(105/1), 이전 화면의 유형별 세대수(3·2·1)와 공급 세대수 일치. 수집 로그 [특별공급 신청] 25건 중 22건, [지난 경쟁률] 신청현황 60건 조회·46건 결과, [검증] 50건(직전과 같음), [검증·정답] 모두 일치, 실거래 648/648. 공고 × 프로필 2,678장 오류 0, 1,030개 조합 차이 0, 전체 화면 1,288개 오류 0
- 기능: 없음(수정)
- 백업: backup/20261001-0741-spreq

## 2026-10-01 07:41 · 특별공급 유형별 경쟁률(청약홈 신청현황)을 관심 공고 추천에 반영
- 요청: 민영 공고 추천에 근처 과거 공고의 특별공급 유형별 신청자 수 반영 (추천 개선 4번)
- 변경: 수집 — 청약홈 getAPTSpsplyReqstStus(특별공급 신청현황)를 받아 주택형별·유형별 공급 세대수와 신청 건수(해당지역·해당 시·도·기타지역)를 정리(parse_special). ① 이 공고의 특별공급 접수가 끝났으면 그 결과를 sp_competition 에, ② 지난 경쟁률 기록(docs/cmpet-history.json)의 일반 공고에 sp 를 채우고(한 번 60건씩, 받은 건 다시 안 받음, 빈 결과는 30일 뒤 재확인) 같은 시·군·구 12개월·면적 ±15㎡ 주택형을 area_sp 로 최신 3건. 화면 — 관심 공고 '어느 쪽이 유리할까'에 유형별 '근처 지난 공고 경쟁률 약 N:1 (신청 / 세대 · 건수)'와 가장 낮은 유형 안내, 참고한 공고 이름 표시. 자료가 없는 LH 공공분양은 '유형별 신청 건수가 청약홈에 공개되지 않아 당첨 확률은 비교하지 않았어요'. 끄면 수집·화면 모두 이전과 같음
- 파일: app/sources/cmpet.py, app/models.py, app/pipeline.py, docs/index.html, docs/config.json, tests/test_cmpet.py
- 확인: 필드 뜻을 실제 응답과 모집공고문 대조로 확인 — 2026000103 066.0000A 공급세대수 표(기관추천 6·다자녀 -·신혼부부 8·노부모 1·생애최초 4·신생아 5·합계 24)와 INSTT_RECOMEND/MNYCH/NWWDS_NMTW/OLD_PARNTS_SUPORT/LFE_FRST/NWBB_NWBBSHR/SPSPLY_HSHLDCO 일치, 074.0000A(1·1·1·0·1·1·5)도 일치. 이 행을 정답 테스트(test_golden_special_request_fields_match_notice_table)로 고정. LH 2026000409·414 는 0건. pytest 106 통과, 스크립트 문법 검사. 브라우저: 자료를 넣은 민영 공고 카드 표시·가장 낮은 유형 문구, LH 공고 안내 문구, 스위치 끄면 이전 문구. 공고 × 프로필 2,678장 오류 0, 직전 배포와 1,030개 조합 차이 0, 전체 화면 1,288개 오류 0, 특별공급 카드 228개 이상 없음. 올린 뒤 수집 실행의 [특별공급 신청]·[지난 경쟁률] 줄 확인 예정
- 기능: sp_competition
- 백업: backup/20261001-0741-spreq

## 2026-10-01 07:41 · 특별공급 신청현황 점검: 응답 필드 전체 기록
- 요청: 민영 공고 추천에 근처 과거 공고의 특별공급 유형별 신청자 수 반영 — 먼저 필드 뜻 확인
- 변경: 점검이 getAPTSpsplyReqstStus 응답을 자르지 않고 전체 기록 (민영 2026000103·443, 2025000488, LH 2026000409). 서비스 수집·화면은 바꾸지 않음
- 파일: tools/rules_probe.py
- 확인: 문법 검사, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20261001-0741-spreq

## 2026-10-01 07:20 · 특별공급 신청현황 API 점검 결과 기록
- 요청: 추천 개선 4번(과거 경쟁률 활용) — API 확인 결과 기록
- 변경: 코드 변경 없음. evidence/cmpet/special.txt 결과: 청약홈 경쟁률 서비스에 getAPTSpsplyReqstStus(특별공급 신청현황, 전체 12,408건)가 있고 유형별·지역별 신청 건수 필드가 옴(CRSPAREA_/CTPRVN_/ETC_AREA_ × LFE_FRST·MNYCH·NWBB_NWBBSHR·NWWDS_NMTW·OPS·YGMN). 민영 2026000103 은 13건 조회되지만 LH 공공분양 2026000409·414 는 0건 — LH 청약플러스 접수분은 없는 것으로 보임. 필드 뜻(특히 NWBB_NWBBSHR·YGMN)과 주택형·공급 세대수 필드는 응답 전체를 다시 확인한 뒤에만 쓴다. 화면 반영은 사용자 확인 후 별도 기능으로
- 파일: WORK.md
- 확인: 근거 자료 모으기 실행(743248d) 결과 파일 확인
- 기능: 없음(수정)
- 백업: backup/20261001-0720-ws

## 2026-10-01 07:20 · 공공 신혼부부 특별공급 상세 설명 수정 (2단계는 점수가 아니라 순위·추첨, 선정순위 표시)
- 요청: 추천 로직 점검 중 발견 — 공고문 선정 방식과 다른 설명 수정
- 변경: 공공분양 신혼부부 특별공급 상세 카드가 소득 2구간(2단계 일반공급)에서도 '점수 ○점 · 높을수록 먼저'로 안내하던 것을 '선정순위(혼인 중 자녀가 있으면 1순위) 안에서 추첨'으로 고침. 1단계는 '선정순위가 먼저이고 같은 순위 안에서 점수 순'을 덧붙이고, 1순위/2순위(자녀 없음)를 표시. 신청 가능 여부 판정은 바꾸지 않음
- 파일: docs/index.html, tests/test_residence.py
- 확인: 공고문 2026000409·414·416 신혼부부 '당첨자 선정방법' 원문 문장을 테스트로 고정(test_public_special_selection_method_in_originals). pytest 통과, 스크립트 문법 검사. 브라우저: A6 59A 1구간·자녀 → '1순위 · 점수 10/13', 2구간 → '1순위 · 순위 → 지역 → 추첨 (가점 무관)', 무자녀 → '2순위'. 직전 배포와 1,030개 조합 판정 차이 0, 전체 화면 1,288개 오류 0, 특별공급 카드 228개 이상 없음
- 기능: 없음(수정)
- 백업: backup/20261001-0720-ws

## 2026-10-01 07:20 · 특별공급 신청현황 API 점검: 기능 이름 후보로 직접 확인
- 요청: 추천 개선 중 특별공급 경쟁률 데이터 활용 가능성 확인
- 변경: 첫 점검에서 기능 목록(OAS) 주소가 404 — 목록을 못 받으면 알려진 이름 후보(getAPTSpsplyReqstStus 등)로 직접 호출해 응답 코드·필드를 evidence/cmpet/special.txt 에 기록. 서비스 수집·화면은 바꾸지 않음
- 파일: tools/rules_probe.py
- 확인: 문법 검사, pytest 통과. 근거 자료 모으기 실행 결과로 확인 예정
- 기능: 없음(수정)
- 백업: backup/20261001-0720-ws

## 2026-10-01 07:20 · 관심 공고 '어느 쪽이 유리할까' 추천을 선정 방식·지역 몫·단계별 재도전 기준으로 개선
- 요청: 추천 로직이 실효성 있는지 확인하고 개선 (세대수만으로 '가장 유리'를 고르는 문제)
- 변경: 기존 추천은 '우선공급 여부 → 내 몫 세대수'로 한 유형을 '가장 유리'로 골랐는데, (1) 공공 생애최초는 모든 단계가 추첨인데 점수 순 유형과 같은 줄에서 비교했고 (2) 지역 배분(예: 인천 50%·수도권 50%)을 무시해 기타지역 거주자 몫이 2배로 나왔고 (3) 1단계 낙첨자가 2·3단계에서 다시 경쟁하는 것을 반영하지 않았고 (4) 경쟁률이 없는데 '가장 유리'로 단정했다. 새 방식: 공고문 '당첨자 선정방법'대로 유형·단계별 선정 방식(공공 신생아 1·2단계 점수 순, 공공 신혼부부 1단계 순위·가점 순·2단계 순위·추첨, 공공 생애최초 전 단계 추첨, 3단계 추첨, 민영은 소득구분·지역 뒤 추첨·신혼은 순위·추첨)을 보여주고, 단계별 물량(공공은 소수점 올림, 추첨은 잔여)을 내 단계부터 이어서 표시, 지역 몫은 해당지역 거주자 전체·기타지역 거주자 기타지역 비율만(L.residence.quota, 다자녀는 별도 배정 표라 제외). 추천 문구는 점수 순 유형과 추첨 유형이 함께 있으면 '점수에 자신이 있으면 A(점수 순), 애매하면 점수와 상관없는 B(추첨)'로, 한 방식뿐이면 물량 비교만. 공공 신혼부부도 자녀가 없으면 2순위 표시. '경쟁률 자료가 없어 당첨 확률은 비교하지 않았어요' 명시. 공공 신혼부부 2단계 행은 점수 대신 '순위·추첨' 표시. 끄면 이전 추천 그대로
- 파일: docs/index.html, docs/config.json
- 확인: 공고문 원문 대조 2026000414(인천계양 A6)·409·416 선정방법, 2026000103·443 「각 단계별 낙첨자는 다음 단계 공급대상에 포함」. pytest 통과, 스크립트 문법 검사. 브라우저: A6 59A 인천 거주 → 신생아 1단계 점수 순 15 → 2단계 5 → 3단계 추첨 1(21세대), 서울 거주 → 8→3→1(12세대/전체 21)·'기타지역 몫(50%)만', 무자녀 → 신혼부부 2순위 표시·추천에서 점수 후보 제외. 공고 204개 × 프로필 13개(2,678장) 카드에 undefined/NaN/오류 0. 직전 배포와 1,030개 조합 비교 판정·특별공급·가점·마진·상태 차이 0, 전체 화면 1,288개 오류 0, 특별공급 카드 228개 이상 없음. 스위치 끄면 이전 문구('가장 유리해 보여요') 그대로 확인
- 기능: ws_reco_v2
- 백업: backup/20261001-0720-ws

## 2026-10-01 07:20 · 특별공급 신청현황 API 확인용 점검 추가 (근거 자료 모으기)
- 요청: 추천 로직 개선 중 '과거 경쟁률' 활용 가능성 — 특별공급 신청현황을 공식 API에서 받을 수 있는지 먼저 확인
- 변경: tools/rules_probe.py 에 probe_cmpet_special 추가 — 청약홈 경쟁률 서비스(15098905) 기능 목록(OAS)과 각 기능의 응답 표본(조건 없음·2026000409·414·103)을 evidence/cmpet/special.txt 에 기록 (인증키가 든 주소는 기록하지 않음). 서비스 수집·화면은 바꾸지 않음
- 파일: tools/rules_probe.py
- 확인: 문법 검사, pytest 통과. 올린 뒤 근거 자료 모으기 실행 결과로 기능 목록·필드 확인 예정
- 기능: 없음(수정)
- 백업: backup/20261001-0720-ws

## 2026-10-01 06:43 · 신혼희망타운 총자산 자동 판정 (부채·해약환급금 입력 추가)
- 요청: 신혼희망타운 총자산을 사용자 입력으로 자동 판정 — 공식 기준 재확인, 중복 입력 없이 필요한 항목만 추가, 충족/초과/확인 필요 구분, 예비신혼부부·한부모 입력, 수익공유형 모기지와 자격 분리
- 변경: 공고문(2026820010 등) <표3> 총자산보유기준 원문 재확인 — 총자산 = ①부동산(건물+토지 공시가격) + ②금융자산(예금·적금·주식·펀드·채권·예수금·연금저축·IRP·보험/연금보험 해약환급금) + ③기타자산(임차보증금·분양권 납부액·조합원입주권·회원권·선박 등) + ④자동차(차량기준가액) − ⑤부채(금융회사·공공기관·공제회·서민금융 대출, 법원 확인 사채, 임대보증금은 해당 부동산 가액까지, 마이너스통장·현금서비스 제외) ≤ 362,000천원, 출산가구 397,000·431,000천원, 무주택세대구성원 전원(예비신혼부부는 혼인으로 구성될 세대). '내 조건'에 '총자산 (신혼희망타운)' 단계 추가(무주택이고 혼인 전·혼인 8년 이내·6세 이하 자녀일 때만 보임): 혼인 전이면 예비신혼부부/한부모가족/해당 없음, 보험·연금보험 해약환급금, 그 밖의 금융자산(연금저축·IRP·앞 단계에 안 넣은 예금 등), 기타 자산, 부채. 부동산·자동차·예금·주식·전세보증금은 기존 입력값 재사용(단계 안에 사용 값 표시). 판정: 값이 모두 있으면 충족/초과(출산가구 완화 반영), 하나라도 비면 확인 필요(빠진 항목 이름·'총자산 정보 넣기' 버튼). 예비신혼부부 → 신청 유형 충족, 한부모가족 → 6세 이하 자녀 있으면 충족·없으면 불가, 해당 없음 → 불가. 음수 금액 입력은 저장하지 않음. 마진 카드의 수익공유형 모기지 안내를 '분양가가 3억 6,200만원을 넘는 주택이라 당첨되면 의무 가입 · 신청 자격(내 세대 총자산)과는 별개'로 분리
- 파일: docs/index.html, docs/config.json, tests/test_residence.py
- 확인: pytest 101 통과(총자산 산정 항목 원문 문장 테스트 추가). 브라우저 경계값: 총자산 1억8천 충족·정확히 3억6,200만 충족·3억6,201만 초과·5억8천 초과, 부채 0·있음·자산보다 큼(음수 총자산) 충족, 해약환급금 0·2억(초과)·미입력(확인 필요), 부동산·자동차·그 밖의 금융자산·부채 미입력 각각 확인 필요, 출산가구 3억9천 충족·4억 확인 필요·4억3,200 초과·자녀 없음 3억9천 초과, 혼인 정확히 7년 충족·7년+1일 불가, 7번째 생일 전날 자녀 충족·7세 불가, 태아 충족, 예비신혼·한부모(자녀 있음) 충족, 한부모(자녀 없음)·해당 없음 불가, 유형 미선택 확인 필요, 소득 초과 불가, 유주택자는 단계 숨김, '-500' 입력 → 저장 안 됨. 모든 정보를 넣은 프로필에서 접수 중 공고의 '확인 필요' 12건 → 0건. 직전 배포와 1,030개 조합 비교: 판정·특별공급·가점·마진·상태 차이 0. 전체 화면 1,288개 오류 0, 360px 가로 넘침 없음, 뒤로가기·새로고침·데이터 실패 흐름 정상
- 기능: town_assets
- 백업: backup/20261001-0643-townasset

## 2026-10-01 02:08 · 최종 배포 검증 수집 결과 (기록만)
- 요청: 최종 배포 검증 — 수정 뒤 수집·데이터 상태 확인
- 변경: 코드 변경 없음. 결과 기록
  - 01:46 실행(a4afd53, 동시 실행 막기 적용): 실거래가 648건 모두 성공 → 01:23 실행 때 비었던 무순위 시세 회복(무순위 50건 중 46건 시세, 4건은 비교 거래 부족)
  - 01:59 실행(63fb234, PARSER 8): 공고문 54건 중 32건 새로 읽고 22건은 5분 제한으로 지난 보관 값 사용, 정답 데이터 일치
  - 02:07 실행(손으로 한 번 더): 나머지 22건 읽음, 실거래가 648건 성공, 정답 데이터(신혼희망타운 4건 포함) 모두 일치, data-updated 02:07
  - 현재: 공고 206건(일반분양 156·무순위 50), 접수 전·중 26건(일반 23·무순위 3), 시세 없음 31건은 모두 '비교할 거래가 부족'(실거래 자료가 실제로 부족한 경우), 알림 꺼져 있어 보내지 않음
- 파일: WORK.md
- 확인: run-log.txt, listings.json 집계, Actions 실행 3건 성공
- 기능: 없음(기록)
- 백업: backup/20261001-0208-final

## 2026-10-01 01:57 · 인천계양 A17 신혼희망타운 정답 데이터·잘못된 응답 테스트 추가
- 요청: 최종 배포 검증 — 새로 받은 공고문(2026820010)으로 신혼희망타운 기준 확인, 잘못된 응답·API 실패 상황 테스트
- 변경: 근거 자료 모으기(워크플로) 실행으로 받은 인천계양 A17 신혼희망타운 공고문 원문을 읽고 정답 데이터(pub_limits: 소득 130/140%, 총자산 362,000천원, 완화 397,000·431,000천원) 추가, 원문 문장 테스트 대상에 포함. 청약홈이 HTML·500 을 주면 실행이 실패하고 지난 결과·마지막 정상 수집 시각을 덮어쓰지 않는다는 테스트 추가(타임아웃도 같은 경로로 실패함을 직접 확인). 코드 변경 없음
- 파일: tests/golden/notices.json, tests/test_residence.py, tests/test_pipeline.py
- 확인: pytest 100 통과
- 기능: 없음(테스트)
- 백업: backup/20261001-0157-a17

## 2026-10-01 01:43 · 신혼희망타운 신청 유형·소득 판정, 확인 필요 원인 구분·판정 근거 추적
- 요청: 최종 배포 검증 — '확인 필요'를 공고문 → 공식 자료 → 법령 순으로 더 판정할 수 있으면 자동 판정, 원인(A~E) 구분, 판정 근거 추적
- 변경: (1) 조사: 모든 질문에 답한 프로필 3개로 접수 중 공고 26건을 돌려 남은 '확인 필요'를 모두 모음 → 신혼희망타운 '소득·총자산 확인 필요'만 남음. 그 밖에 신혼희망타운은 혼인 7년 초과여도 '신혼부부 전용 충족'(잘못된 가능 위험), 혼인 전이면 '불가'(예비신혼부부·한부모 가능인데 불가)로 판정하던 문제 발견. (2) LH 신혼희망타운 공고문(2026820008·009·011) <표1> 신청자격·소득 표·<표3> 총자산보유기준·<표4> 출산가구 완화를 읽는 _parse_town_limits 추가(pub_limits kind=town, PARSER_VERSION 8). 화면(town_rules): 신청 유형 — 혼인 7년 이내 또는 6세 이하(만 7세 미만·태아 포함) 자녀면 충족, 둘 다 아니면 불가, 혼인 전이면 '예비신혼부부/한부모가족이면 가능'(확인 필요), 소득 130%(맞벌이 140%)·출산가구 완화로 판정, 총자산은 부채·보험 해약환급금을 묻지 않아 입력 자산 합계와 기준만 보여주고 확인 필요(원인 A). 공고문 기준을 못 읽은 신혼희망타운은 확인 필요(원인 E). 마진 카드에 공급가격이 총자산 기준을 넘으면 수익공유형 모기지 의무 가입·시세차익 10~50% 기금 정산 안내(공고문 문장). (3) 개발자용 cpExplain(id): 항목별 판정·확인 필요 원인(A 사용자 정보 부족·B 공식 기준 부족·C 적용 불명확·D 자료 충돌·E 수집 실패)·근거(모집공고문/법령/추정/사용자 입력, URL, 적용 이유). 금액 표시 '2억 1,550만원' 형식
- 파일: app/notice_pdf.py, app/pipeline.py, docs/index.html, docs/config.json, tests/test_residence.py, tests/golden/notices.json
- 확인: 공고문 원문 3건으로 정답 데이터·원문 문장 테스트, pytest 99 통과. 브라우저: 혼인 3년·정확히 7년 충족, 7년+1일 자녀 없음 불가, 10년+5세 자녀·태아 충족, 10년+7세 자녀 불가, 미혼 → 예비신혼부부/한부모 확인 필요, 소득 130% 충족·초과 불가, 맞벌이 155% 불가, 총자산 입력·미입력·초과 모두 확인 필요(A), 기준 미확인 공고 확인 필요(E). 직전 배포와 1,030개 조합 비교: 특별공급·가점·마진·상태 차이 0, 판정 변화 5건(미혼 프로필의 신혼희망타운 불가 → 확인 필요, 의도). 특별공급 카드 오류 없음
- 기능: town_rules
- 백업: backup/20261001-0143-town

## 2026-10-01 01:38 · 수집 안정화: 유형별 0건 보호·수집 동시 실행 막기
- 요청: 최종 배포 검증 — 한 유형만 0건일 때 기존 데이터가 사라지는지, 겹친 실행이 결과를 덮어쓰는지 확인하고 필요한 최소 안전장치 구현
- 변경: (1) 재현: 00:59 실행에서 청약홈이 무순위를 0건 줘 접수 중인 무순위(강변역·충정로역자이르네 등)가 목록에서 사라졌음(전체 0건만 막던 구조). restore_missing_category 추가 — 일반분양·무순위 중 한 유형만 0건이고 그 유형의 지난 결과에 아직 접수·발표 뒤 보관 기간(14일) 안인 공고가 있으면 수집 실패로 보고 지난 결과를 유지, 실행 기록에 [경고]. 지난 결과가 모두 기간을 지났으면 0건을 정상으로 봄. (2) 재현: 01:16(새 코드)·01:23(앞 커밋) 두 실행이 겹쳐 뒤 실행이 실거래가 조회 전부 실패한 결과와 옛 시세 기록으로 덮어씀. 워크플로에 concurrency(group: collect, 겹치면 대기) 추가, checkout 을 main 최신으로(기다렸다 시작해도 최신 데이터에서 시작). (3) 테스트가 실제 docs/listings.json 을 지난 결과로 읽지 않게 conftest 에서 격리
- 파일: app/pipeline.py, .github/workflows/collect.yml, tests/test_pipeline.py, tests/conftest.py
- 확인: pytest 98 통과(무순위만 0건 → 유지, 지난 무순위가 모두 기간 지남 → 유지 안 함, 두 유형 다 옴 → 그대로, 전체 0건 기존 테스트 유지). 배포 뒤 Actions 실행 결과 확인 예정
- 기능: 없음(수정)
- 백업: backup/20261001-0138-catguard

## 2026-10-01 01:25 · 출시 전 QA 수정 뒤 수집 결과 확인 (기록만)
- 요청: QA 수정 8건 배포 후 Actions 실행 결과·run-log 확인 (CLAUDE.md 3·4항)
- 변경: 코드 변경 없음. 확인 결과 기록
  - 01:16 실행(새 코드): 공고 206건, 실거래가 648건 성공, 공고문 54건(정답 데이터 모두 일치), data-updated.txt 01:16 기록, 알림은 꺼져 있어 보내지 않음(보낼 알림 2건)
  - 01:23 실행(그 전 커밋으로 동시에 돌던 실행): 실거래가 요청 648건이 모두 실패·시간 초과 → 일반분양 156건은 지난 조회값, 무순위 50건은 '시세 없음'. 동시에 돈 두 실행이 서로 덮어쓴 결과라 무순위 시세가 비었음. 다음 정기 수집(05:30)에서 다시 조회되는지 06:10 에 확인 예정
  - 00:59 실행: 청약홈이 무순위 공고를 0건 줘 일반분양 156건만 저장됨(01:16 실행에서 무순위 50건 회복). 전체 0건만 막고 유형별 0건은 막지 않는 구조라 기록해 둠 — 수정은 하지 않음(요청 범위 밖, 사용자에게 보고)
- 파일: WORK.md
- 확인: git log 의 수집 커밋 2aeb131·3dc8c6e·63f1175 와 각 run-log.txt 확인, pytest 통과
- 기능: 없음(기록)
- 백업: backup/20261001-0125-qalog

## 2026-10-01 01:06 · 갱신 시각은 공고를 실제로 받았을 때만 (QA 🟡)
- 요청: 출시 전 QA — 청약홈 수집이 0건·실패여도 updated.txt 갱신 시각이 바뀌는 문제. 유효한 공고를 받았을 때만 마지막 갱신 시각을 바꾸고, 실패 때 화면에서 마지막 정상 갱신 시점을 볼 수 있게
- 변경: 수집(pipeline)이 공고를 1건 이상 받아 저장했을 때만 docs/data-updated.txt 에 한국 시각을 씀(0건 실행은 이 파일을 건드리지 않음). 화면 머리의 'N.N HH:MM 갱신'과 '공고 정보가 N일 전 기준' 경고는 이 시각(마지막 정상 수집)을 쓰고, 파일이 없으면 예전처럼 updated.txt(실행 시각). updated.txt 는 워크플로가 계속 실행 시각으로 씀. data-updated.txt 첫 값은 공고 156건을 받은 00:59 실행(커밋 2aeb131) 시각으로 넣음. 테스트가 이 파일을 건드리지 않게 conftest 에서 격리
- 파일: app/pipeline.py, docs/index.html, docs/config.json, docs/data-updated.txt, tests/conftest.py, tests/test_pipeline.py
- 확인: pytest 95 통과(0건 실행은 시각 유지, 정상 수집은 시각 기록 테스트 추가). 브라우저: 머리에 00:59(마지막 정상 수집) 표시, 파일 없으면 updated.txt 로 대체, 5일 전 시각이면 오래된 데이터 경고 표시
- 기능: fresh_time
- 백업: backup/20261001-0106-updtime

## 2026-10-01 01:05 · 마진 화면 안내 보완·권유 표현을 사실 표현으로 (QA 🟡)
- 요청: 출시 전 QA — 마진을 확정 수익으로 오해하지 않게 양도소득세·보유 비용·대출이자·전매 제한 미반영을 안내, '넣지 마세요' 같은 권유 표현을 사실 표현으로. 산식·계산 결과는 그대로
- 변경: 마진 계산 카드의 '차이' 바로 아래와 등급 기준 화면에 '세전 추정 차이예요. 양도소득세, 보유 비용(재산세 등), 대출이자, 중개수수료는 빼지 않았고, 전매 제한·실거주 의무 기간에는 팔 수 없어요. 확정 수익이 아니에요.' 추가. 등급 설명을 '현재 추정 시세보다 실매입가가 높아요/낮아요/비슷해요'로, 상세 판정의 '실거주 목적이 아니면 통장을 아끼세요'를 '당첨되면 재당첨 제한이 걸려 한동안 다른 청약에 당첨될 수 없어요'로 바꿈. grade()·마진 산식은 바꾸지 않음
- 파일: docs/index.html, docs/config.json
- 확인: 브라우저에서 등급 기준·광명 59A 마진 카드 문구 확인, 광명 59A 마진 1.5335억~2.3835억 '고려'(변경 전과 같음), pytest 통과
- 기능: margin_caveat
- 백업: backup/20261001-0105-margin

## 2026-10-01 01:04 · 검색·공유 기본 설정 (QA 🟡)
- 요청: 출시 전 QA — meta description, canonical, Open Graph(og:title·og:description·og:image), robots.txt, sitemap.xml, 404.html. 카카오톡·SNS 공유 때 서비스 내용이 보이게
- 변경: index.html head 에 제목('청약패스 · 청약 자격·마진·자금 판정')·설명·canonical·OG·트위터 카드 추가. 공유 이미지 docs/og.png(1200×630, 앱 아이콘·브랜드 색 그대로, '자격 판정·시세 대비 마진·자금 계획', 참고용 추정 문구). robots.txt(전체 허용, 내부 기록 파일 제외, sitemap 위치), sitemap.xml(첫 화면), 한국어 404.html(noindex, 첫 화면 링크, 다크 모드). 화면 동작은 바꾸지 않음
- 파일: docs/index.html, docs/og.png, docs/robots.txt, docs/sitemap.xml, docs/404.html
- 확인: 브라우저로 head 태그 값 확인, 404 페이지 360px 표시(가로 넘침 없음), sitemap XML 파싱, 공고 23건 정상 표시·스크립트 오류 0, pytest 통과. 실제 카카오톡 미리보기는 배포 후 카카오 공유 디버거에서 확인 필요(이 작업 환경에서는 외부 접속 불가)
- 기능: 없음(정적 설정)
- 백업: backup/20261001-0104-seo

## 2026-10-01 01:02 · ntfy 푸시 알림 임시 중지 (QA 🟠 보안)
- 요청: 출시 전 QA — ntfy 공개 주제에 누구나 메시지를 보낼 수 있는 문제. 공개 화면에 쓰기 토큰을 두지 말 것, 안전하게 제한할 수 없으면 알림 기능 임시 비활성화
- 변경: 확인 결과 ntfy.sh 는 주제 이름이 곧 비밀번호이고, 주제 예약·접근 제어(쓰기 제한)는 유료 요금제에서만 가능(ntfy.sh 이용약관). 주제 이름이 공개 화면(config.json)에 있어 지금 구조로는 쓰기를 막을 수 없음 → 스위치 ntfy_alerts=false: 화면의 '알림 받기' 버튼 숨김, 알림 화면은 '알림은 준비 중' 안내, 수집(Actions)도 알림을 보내지 않고 실행 기록에 '[알림] 꺼져 있어 보내지 않음'. 쓰기 토큰은 어디에도 두지 않음
- 파일: docs/index.html, docs/config.json, app/pipeline.py, tests/test_notice_and_notify.py
- 확인: pytest 95 통과(스위치 끄면 보내지 않음·사이트 설정 꺼짐 테스트), 브라우저에서 알림 버튼 숨김, #/alerts 직접 열면 준비 중 안내, 스크립트 오류 0. 다시 켜려면 ntfy 유료 요금제로 주제를 예약하고 쓰기 토큰을 GitHub Secrets 에 둔 뒤 notify.send 에 인증을 붙여야 함
- 기능: ntfy_alerts
- 백업: backup/20261001-0102-ntfy

## 2026-10-01 01:00 · 공고 데이터 불러오기 실패 안내·다시 시도 (QA 🟠)
- 요청: 출시 전 QA — listings.json 을 못 불러오면 코드 안의 예시 공고가 실제 공고처럼 보이는 문제. 실패를 알리고 다시 시도할 수 있게
- 변경: 공고를 읽는 동안 목록 자리에 '공고를 불러오는 중이에요…'를 보여주고(예시 공고를 먼저 그리지 않음), 실패(네트워크 오류·응답 오류·공고 0건)하면 '공고 데이터를 불러오지 못했어요' 안내와 [다시 시도]·[청약홈 열기] 버튼을 보여줌. 실패 때는 코드 안의 예시 공고(강변역·샘플 B~D)를 목록·판정에 쓰지 않음. 정상 로딩은 그대로. 공고 데이터 읽는 부분을 loadListings() 로 묶어 다시 시도에 씀
- 파일: docs/index.html, docs/config.json
- 확인: 브라우저(360px) listings.json 차단 → 실패 안내·예시 공고 0건, 다른 화면(내 조건·등급 기준·가점 컷·이용 안내·알림·비교) 오류 없음, [다시 시도] → 23건 정상 표시, 1.5초 늦게 오면 '불러오는 중' 뒤 정상 표시, 빈 배열 → 실패 안내, 스위치 끄면 예전처럼 예시 공고. 공유 링크·새로고침 상세 유지, 특별공급 카드 240개 오류 없음, pytest 통과
- 기능: data_fail_ui
- 백업: backup/20261001-0100-datafail

## 2026-10-01 00:57 · 뒤로가기로 이전 화면 돌아오기·공고 주소 (QA 🟠)
- 요청: 출시 전 QA — 공고 상세에서 브라우저 뒤로가기를 누르면 사이트 밖으로 나가는 문제. 새로고침 동작 유지, 가능하면 공고 공유 주소
- 변경: 화면을 바꿀 때(go) 브라우저 기록에 남기고 popstate 로 이전 화면을 다시 그림. 주소는 목록 = 사이트 주소, 공고 = #/detail/<주택형 id>, 그 밖 = #/<화면>. 목록으로 돌아오면 스크롤 위치 복원. 새로고침·공유 링크는 공고 데이터를 읽은 뒤 그 공고를 열고, 없는 공고 주소는 목록으로 돌아가며 주소를 정리. 인터뷰 단계 이동은 기록하지 않음(입력값은 기존처럼 바로 저장)
- 파일: docs/index.html, docs/config.json
- 확인: 브라우저(360px) 목록 → 상세 → 뒤로(목록, 스크롤 복원) → 앞으로(상세), 상세에서 새로고침 → 같은 공고, 그 뒤 뒤로 → 목록, 탭 이동 뒤로가기, 공유 링크(새 창) 상세 열림, 없는 공고·잘못된 주소 → 목록, #/me 직접 열기, 스위치 끄면 예전처럼 주소 변화 없음. 스크립트 오류 0, 특별공급 카드 240개 오류 없음, pytest 통과
- 기능: history_nav
- 백업: backup/20261001-0057-history

## 2026-10-01 00:55 · 유주택 세대의 민영주택 일반공급 판정 (QA 🟠)
- 요청: 출시 전 QA — 1주택 세대가 민영 일반공급 전체에서 '불가'로 나오는 문제. 추첨제 신청 가능 여부와 가점제 적용 여부를 구분
- 변경: 민영주택 일반분양(청약통장 필요)에서 세대에 집이 있으면 '무주택 세대'를 불가로 두지 않고 규제지역은 '유주택 · 추첨제만'(1주택 이상 세대 1순위 가점제 불가, 추첨제 75% 무주택 우선 뒤 1주택 세대 포함), 비규제지역은 '유주택 · 가점 0점'(1순위 신청 가능, 가점 무주택기간 0점)으로 표시. 규제지역은 일반공급 줄에 '가점제 불가 · 추첨제로 신청'. 특별공급·공공분양·무순위의 무주택 요건, 규제지역 2주택 이상·세대주·5년 내 당첨 1순위 제한은 그대로
- 파일: docs/index.html, docs/config.json
- 확인: 근거 원문(광명 2026000453·서울 2026000399 '1주택 이상 소유한 세대에 속한 분은 1순위 가점제 청약이 불가', 추첨제 단계표, 천안 2026000426 '1순위 추첨제 : ①지역 → ②추첨'·'유주택자 0'). 브라우저: 규제 무주택 가능·1주택 가능(추첨제만)·2주택 2순위만·세대원 2순위만, 비규제 1주택·2주택 가능(가점 0점), 공공분양·무순위 1주택 불가 유지, 특별공급 유주택 전부 불가 유지, 가점 무주택기간 0점. pytest 통과, 특별공급 카드 240개 오류 없음
- 기능: owner_lottery
- 백업: backup/20261001-0055-onehome

## 2026-10-01 00:51 · 공공분양 일반공급 소득·자산 기준 판정 (QA 🔴)
- 요청: 출시 전 QA — 공공분양 전용 60㎡ 이하 일반공급에서 소득·자산 기준을 넘는 사람에게 '신청 가능'이 나오는 문제 수정
- 변경: LH 공고문의 신청자격 요약표 일반공급 소득 칸('100% 이하 (맞벌이 200%) * 전용면적 60㎡ 이하만 적용'), 2단계 우선공급 문장(100%, 맞벌이 140%), <표2> 부동산 215,500천원·자동차 45,420천원을 읽는 parse_pub_limits 추가(PARSER_VERSION 7). 화면은 공고문에서 읽은 기준으로만 '소득 (공공 일반공급)'·'자산 (공공 일반공급)'을 판정(가구원수·소득 합산은 특별공급과 같은 공고문 표), 넘으면 불가, 우선공급 상한만 넘으면 '추첨공급만', 출산가구 완화(+10/20%p)는 확실하지 않으면 확인 필요. 기준을 못 읽은 60㎡ 이하 공공분양과 신혼희망타운(총자산 기준)은 '확인 필요'로 두고 '충족'으로 단정하지 않음. 소득 미입력·자산 미입력도 확인 필요. 자동 검증에 '기준을 공고문에서 읽지 못함' 추가. 특별공급·민영 판정은 바꾸지 않음
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, docs/index.html, docs/config.json, tests/test_residence.py, tests/golden/notices.json
- 확인: 공고문 원문 3건(409·414·416)으로 정답 데이터·원문 문장 테스트 추가, pytest 93 통과. 브라우저 경계값: 기준 이하 가능, 정확히 100%(월 7,533,763원)·부동산 21,550만·자동차 4,542만 가능, 1원 초과·9,041만원 불가, 소득·부동산·자동차 각각 초과 불가, 모두 초과 불가(QA 사례 연소득 2억·부동산 5억·자동차 9천만 → '신청 불가'), 소득·자산 미입력·기준 미확인·신혼희망타운 → 확인 필요, 맞벌이 166% → 추첨공급만, 210% 불가, 출산가구 완화 110% 가능·116% 확인 필요·122% 불가, 84㎡·고덕(60㎡ 초과)은 항목 없음. 특별공급 카드 240개 오류 없음
- 기능: pub_general_limits
- 백업: backup/20261001-0051-publim

## 2026-10-01 00:23 · 관심 공고 추천 문구 조사 수정
- 요청: (watch_scores 확인 중 발견) '노부모부양는' 처럼 받침에 맞지 않는 조사
- 변경: 확인 필요 유형 목록 뒤 조사를 받침에 맞춰 은/는으로 표시
- 파일: docs/index.html
- 확인: pytest 통과, 스크립트 문법 검사, 브라우저에서 '노부모부양은' 확인
- 기능: 없음(수정)
- 백업: backup/20261001-0022-wsfix

## 2026-10-01 00:19 · 가점 컷 탭에 관심 공고별 내 당첨 점수와 유리한 공급 추천
- 요청: 관심(★) 공고를 가점 컷 탭에서 일반/특별공급 유형별 내 점수로 크게 보고, 어느 공급이 당첨에 유리한지 추천
- 변경: 가점 컷 탭 맨 위에 '관심 공고 · 내 당첨 점수' 추가. 관심 주택형마다 일반공급(가점·최근 당첨 최저점 차이)과 특별공급 유형별 판정·점수(다자녀 배점, 노부모 가점, 공공 신혼·신생아 점수)·내 몫 세대수를 큰 글씨로 표시. 추천은 신청 가능한 특별공급 중 ① 우선공급 몫 → ② 점수·가점 순 → ③ 추첨 몫만 순서, 같으면 내 몫 세대수가 많은 유형(이 서비스의 추정, 유형별 경쟁률 미반영이라고 표시). 특별공급 1개+일반공급 1개 중복 신청 가능 안내(모집공고문 2026000453·2026000414 문장 확인). 판정·점수 계산 로직은 바꾸지 않음
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 스크립트 문법 검사, 브라우저(iPhone 크기)에서 관심 없음 안내·관심 4개(민영·LH·무순위·마감) 카드, 다자녀 가구 프로필로 120개 카드 오류 없음, '공고 보기' 이동, 스위치 끄면 섹션 없음, 특별공급 카드 240개 오류 없음
- 기능: watch_scores
- 백업: backup/20261001-0019-wscore

## 2026-10-01 00:03 · 청약홈 0건 실행에서 시세 기록이 비워지는 문제 수정
- 요청: (notice_schedule 배포 후 확인 중 발견) 00:02 실행에서 청약홈이 공고를 0건 줘 목록은 유지됐지만 docs/market-cache.json 이 비워짐
- 변경: market_fallback 이 공고 0건일 때는 시세 기록을 쓰지 않고 그대로 둠. 비워진 market-cache.json 을 직전 실행(9226157) 값 211건으로 되돌림
- 파일: app/pipeline.py, tests/test_pipeline.py, docs/market-cache.json
- 확인: test_market_cache_kept_when_no_listings 추가, pytest 90 통과. notice_schedule 수집 결과: 인천계양 특별공급 9/30, 의정부우정·양주회천 9/14~15 채워짐, 정답 불일치 0건
- 기능: 없음(수정)
- 백업: backup/20261001-0003-mcache

## 2026-09-30 23:49 · LH 공고의 특별공급 접수일을 공고문에서 읽기
- 요청: 인천계양 A6블록처럼 특별공급 날짜가 비어 접수 기간이 9/17~10/2로 한꺼번에 보이는 문제 수정
- 변경: 청약홈 API 가 LH 공공분양의 특별공급 접수일(SPSPLY_RCEPT_BGNDE)을 비워 둠(2026000409·414·416). 공고문 '신청시간 : (사전청약 당첨자)…(특별공급)…(일반공급)…' 문장을 읽는 parse_schedule 추가, 청약홈 값이 없을 때만 특별공급 날짜를 채움. 화면 상세 머리·비교표에 '특별공급 09.30 · 일반공급 10.01~10.02 (모집공고문)' 표시. 청약홈 날짜와 공고문 날짜가 다르면 [검증]. PARSER_VERSION 6
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, app/validate.py, docs/index.html, docs/config.json, tests/test_residence.py, tests/golden/notices.json
- 확인: 공고문 원문 3건(신청일정 표·신청시간 문장)을 읽고 정답 데이터 추가, test_golden_schedule 등 pytest 89 통과, 신청시간 문장이 없는 공고(민영·고덕·신혼희망타운)는 읽지 않음 확인, 스크립트 문법 검사, 브라우저에서 인천계양 상태 '접수 중'(특별공급 9/30)·상세 머리 표시 확인, 특별공급 카드 240개 오류 없음
- 기능: notice_schedule
- 백업: backup/20260930-2349-sched

## 2026-09-30 23:33 · 내 조건 판정 숫자로 공고 거르기
- 요청: 내 조건 카드의 신청 가능·불가 숫자를 누르면 그 공고만 보이게 (필터 또는 이동)
- 변경: 내 조건 카드의 신청 가능·확인 필요·2순위만·불가 숫자를 버튼으로 바꿈. 누르면 목록이 그 판정의 공고만 보이고 목록 위치로 이동. 결과 줄에 '내 판정: X ✕' 칩, 다시 누르거나 '조건 모두 해제'로 풀림. 판정 기준은 카드 숫자와 같은 eligibility() 그대로(판정 로직 변경 없음)
- 파일: docs/index.html, docs/config.json
- 확인: pytest 통과, 스크립트 문법 검사, 브라우저(iPhone 크기)에서 신청 가능 12건·불가 19건 눌러 결과 수가 카드 숫자와 같고 보이는 공고가 모두 그 판정인지 확인, 다시 누르기·모두 해제로 44건 복귀, 스위치 끄면 숫자만 표시, 특별공급 카드 240개 오류 없음
- 기능: elig_filter
- 백업: backup/20260930-2333-elig

## 2026-09-30 23:04 · 특별공급 '전체 N세대' 표시 · 사이트 전체 문구 점검·수정
- 요청: ① 특별공급 유형 옆 '2세대'가 추첨 물량인지 전체인지 헷갈림 → '전체 N세대'로, 추첨 몫으로만 뽑히면 안내 ② 웹 전체 설명 문구를 확인해 이상한 부분 수정
- 변경(문구만, 판정·계산 그대로): ① 공급 유형 줄 '전체 N세대', 추첨 몫으로만 뽑히는 경우 '내 위치'에 '이 주택형 ○○ 물량은 전체 N세대예요. 소득 구간 몫(50%·20%)이 먼저 배정되고, 남는 추첨 몫에서 뽑혀요'(5세대 이하면 '추첨 몫이 거의 없을 수 있어요 · 정확한 세대수는 공고문 배정표') ② 전체 점검: 모든 화면(공고 목록·요약 시트·상세·자금 계획·등급 기준·가점 컷·내 조건·이용 안내·만든 이유·약관·개인정보처리방침·알림·인터뷰 전 단계)을 조건 3가지(빈 조건·전부 입력·일부 입력)로 공고 211개 모두 띄워 1,317쪽 글을 모으고 자동 검사 + 다른 에이전트가 문장 1,096개를 읽고 검토 → 고친 것: '○○을(를)' → 받침 맞춘 을/를, '0만' → '0원', '직거래은' → '직거래는'(건수 있으면 '건은'), 규제지역 1순위 항목 값 '없음'(이름과 이중 부정) → '충족', '(세대주: 세대원)' → '(세대주가 아니라 세대원이에요)', 시세·전세 근거 문장 끊김('…기준 (최근 6개월)이에요.', '입주장 할인 10%를 뺐어요 (입주장 설명)'), 세대주 변경 안내 중복 문장, 약관 이메일 조사·괄호 띄어쓰기, '공고: 출처:'처럼 겹친 라벨, 생애최초 1인 가구 안내를 할 일 문장으로, 약관의 '아직 판정하지 않는 요건' 예시를 현재 기준으로, 개인정보처리방침 '수집·보관 개인정보 없음'과 오류 신고 보관의 모순 해소, 무순위 거주지 안내 중복, '둘 다 신청할 수 없어요' → '일반공급과 특별공급 모두', 등급 설명 '자격만 되면 넣기. 자금 계획부터 확보' 정리, '근거 … · 추정이에요' → '…을 바탕으로 한 추정', 노부모부양 유주택 예외 설명, 영문 'FOUNDATION' 삭제, 일반공급 세대수 '-' → '세대수 정보 없음', 경쟁률 '미달 (△3)' → '미달 (3세대 남음)', 빈 순위 → '순위 정보 없음', 가점 기록이 모두 '-'면 '발표된 기록 없음', '승계 필수' 풀이, LTV → '집값 기준(LTV)', 잔금대출 근거 '집값의 70%', 알림 화면 로또·고려 뜻, 화면 이름 '내 정보' → '내 조건'(화면을 가리키는 말만), '임신·입양' → '태아·입양', '다자녀가구' → '다자녀', '자녀수' → '자녀 수', '넣어주세요' → '넣어 주세요', 인용 화살표 통일, 기타지역 순서 '서울·경기·인천', 해당지역 전입일 입력 요청 문장
- 파일: docs/index.html, WORK.md
- 확인: 다시 1,317쪽 모아 검사 — '을(를)'·'0만'·undefined/NaN·'X: 출처:'·빈 순위·전부 '-' 가점·화면 오류 0건, 공고 211개 × 조건 2가지 특별공급 카드 240개 오류 없음, 스크립트 문법 검사, pytest 85개 통과
- 기능: 없음(수정) — 여러 화면 문구
- 백업: backup/20260930-2259-units (전체 N세대), backup/20260930-2304-text (문구 점검)

## 2026-09-30 22:47 · 상세 맨 위 결론 문구 '…은(는) 아직 판정하지 않아요' 수정
- 요청: '기본 요건과 자금은 가능해요 · 세부 요건 확인 필요 / 은(는) 아직 판정하지 않아요…' 문장이 이상함
- 원인: 상세 맨 위 결론 칸이 '아직 판정하지 않는 항목' 목록을 그대로 이어 붙여, 목록이 비었을 때(모두 판정됨) 앞말 없이 '은(는)'으로 시작하고, 판정할 게 없는데도 '세부 요건 확인 필요'라고 표시
- 변경(문구만, 판정 그대로): 판정 안 한 항목이 없으면 '자격과 자금 모두 가능해요 — 신청 전에 모집공고문으로 한 번 더 확인하세요'(확인 필요 조건이 있으면 '확인할 것 있음'), 특별공급 항목만 남으면 '일반공급은 자격과 자금 모두 가능해요 — 특별공급을 쓸 때만 N가지(…)를 확인하세요', 일반공급에 영향 있는 항목이 있으면 '기본 요건과 자금은 가능해요 · N가지는 직접 확인 — 이 서비스가 아직 판정하지 않는 항목이 있어요: …'
- 파일: docs/index.html, WORK.md
- 확인: 브라우저로 공고 211개 × 조건 3가지(모두 입력 / 가구원수 질문 미답 / 통장 미입력) 결론 문구 모음 확인 — '은(는)'으로 시작하는 문장 없음. 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — eligibility_caution 문구
- 백업: backup/20260930-2247-cauttext

## 2026-09-30 22:11 · 특별공급 다자녀 지역 배정 · 가구원수를 공고문 기준으로 판정
- 요청: '직접 확인할 것'에 남은 특별공급 항목(가구원수 산정, 다자녀 지역별 배정)도 입력한 정보와 공고문으로 판정
- 원문 확인: 가구원수 — 민영 공고 공통 '(가구원수 산정 기준) 무주택세대구성원 전원으로 산정. 단, 임신 중인 태아는 태아 수만큼 인정하되, 공급신청자의 직계존속(배우자의 직계존속 포함)은 공고일 기준 최근 1년 이상 계속하여 … 같은 세대별 주민등록표에 등재되어 있는 경우에만 포함'(2026000453·0443·0399 등), 공공 2026000409 '신혼부부·다자녀·신생아 … 무주택세대구성원 전원(태아 포함)', '생애최초 … 직계존속은 1년 이상 같은 등본상 등재된 경우에만', '노부모부양 … 전원과 피부양자 및 그 배우자'. 다자녀 배정 — 민영 공급세대수 표 '다자녀가구 특별공급 해당시·도(○○) 거주자(50%) … 기타지역(○○) 거주자(50%)'(0399·0394·0431·0449·0453), LH '다자녀 특별공급 지역 우선공급 기준 ① 경기도 50%(그 안에서 해당 주택건설지역 ○년 이상 우선, 남는 물량은 경기도 ○개월 이상) ② 기타지역 50%'(0409·0416·0437·0438), '다자녀 특별공급 및 일반공급 지역 우선공급 기준 ① 인천광역시 50% ② 기타지역(수도권) 50%'(0414)
- 변경: ① 공고문 읽기(parse_mc_quota): 다자녀 지역별 배정 몫(비율·시·도·그 안의 해당지역 우선·경기도 거주기간)을 읽음, 흔적은 있는데 못 읽으면 unknown. 공고문 읽기 규칙 버전 5 ② 화면: 다자녀 '내 위치'에 '다자녀 지역 배정: 경기도 몫(50%) · 그 안에서도 양주시 1년 이상 거주자라 먼저'처럼 내 몫(표가 없는 공고는 '지역별 배정 비율이 따로 없어요') ③ 가구원수: '자녀와 가구' 질문에 태아 수·같은 등본의 자녀·손자녀 수·부모·조부모 수·그중 1년 넘게 같은 등본인 분을 받아 공고문 기준으로 셈(민영·공공 생애최초는 부모님 1년 이상만, 공공 신혼·다자녀·신생아·노부모는 전원), 특별공급 소득 판정과 공공 점수(소득 항목)에 그 가구원수를 씀. 소득 칸에 '가구원수 7명 = 본인 1 · 배우자 1 · 자녀 3 · 태아 1 · 부모님 1 — 공고문 기준으로 셌어요'. 새 질문에 답하지 않은 사람은 예전처럼 직접 넣은 가구원수를 쓰고 '직접 확인할 것'에 '가구원수 질문 답하기' 버튼 ④ '직접 확인할 것'에서 두 항목은 판정되면 빠짐
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, docs/index.html, docs/config.json, tests/golden/notices.json, tests/test_residence.py, tests/test_notice_and_notify.py, FEATURES.md, WORK.md
- 확인: 정답 데이터 — 다자녀 배정 11건(배정 표 10건 + 표 없는 2026000103)을 원문으로 확인해 넣고 추출 결과와 같음을 테스트로 고정, 가구원수·다자녀 원문 문장 테스트 추가, pytest 85개 통과. 판정 예시(공고문 값을 넣은 화면): 양주 오래 거주 → 양주회천 '경기도 몫 · 그 안에서도 양주시 1년 이상 먼저', 고덕 '경기도 몫 · 평택시 거주자 다음(경기 6개월 이상)', 인천계양 '기타지역(수도권) 몫'; 경기 3개월 → 양주회천 '기타지역(수도권) 몫', 고덕 '기타지역(전국) 몫'; 서울 → 브라운스톤 월곡 '해당 시·도 몫', 광명 '기타지역 몫'. 가구원수(본인·배우자·자녀 3·태아 1·부모님 1명 1년 미만) → 민영 6명(부모님 제외), 공공 신혼·신생아 7명, 공공 생애최초 6명. 브라우저(iPhone 13 흉내) 질문·소득 칸·다자녀 줄·'직접 확인할 것' 없어짐 확인, 공고 211개 × 조건 2가지 카드 240개 오류 없음, 스크립트 문법 검사
- 올린 뒤: 첫 수집에서 공고문 56건을 새 규칙으로 다시 읽다가 시간 제한(300초)으로 21건은 지난 값 사용, 정답 불일치 0. 수집을 한 번 더 실행(손으로) → 남은 21건 20초에 읽음, 공고 56건 모두 새 규칙, 다자녀 배정 표 10건(예상과 같음), '정답 데이터와 모두 일치', 경고 없음
- 기능: mc_quota (끄면 다자녀 배정 안내만), hh_count (끄면 가구원수 직접 입력) — 한 커밋에 함께 (같은 화면 코드를 함께 고쳐 나누기 어려움, 스위치는 따로)
- 백업: backup/20260930-2211-mchh

## 2026-09-30 22:01 · 무순위 공고에서 '통장 판정 못 함'이 잘못 뜨던 문제
- 요청: 청약통장 정보를 다 넣었는데 '직접 확인할 것 · 통장 가입기간·예치금… 판정하지 못했어요'가 뜸
- 원인: 무순위·재공급 공고는 청약통장이 필요 없어(need_account=false) 통장 판정을 건너뛰는데, '아직 판정하지 않는 항목' 목록이 이를 '통장 정보를 넣지 않아 판정 못 함'으로 셈. 같은 화면 요약의 '지역 순서: 신청 가능 · 먼저 뽑힘'도 지역 우선 순서가 없는 무순위에는 맞지 않는 표현
- 변경: 통장 항목은 청약통장이 필요한 공고에서만 '직접 확인할 것'에 넣음. 무순위 공고 요약은 '무순위 · 신청 가능 — 청약통장이 필요 없는 공고예요', '거주지 · 신청 가능 지역 — 지역별 우선 순서와 거주기간 요건이 없어요', 특별공급 줄은 숨김, 결론·목록 머리도 '무순위'로. 판정 결과는 그대로
- 파일: docs/index.html, WORK.md
- 확인: 브라우저(iPhone 13 흉내) 통장 정보를 넣은 조건으로 무순위(충정로역자이르네) — 통장 항목 없음, 위 문구 확인. 일반 공고(광명)는 이전과 같음. 공고 211개 × 조건 2가지 카드 240개 오류 없음. 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — supply_summary·checklist_v2 표시
- 백업: backup/20260930-2201-acctfix

## 2026-09-30 21:54 · 신청할 수 있는 공급 요약 + 특별공급 거주지 판정
- 요청: 자격 충족일 때 일반공급·특별공급 중 어떤 자격인지, 특공 해당지역 우선이 아니면 못 쓰는지 알아야 아래 '공급 유형별 내 자격과 위치'가 의미 있음 → 개선안 검토 후 진행
- 원문 확인: 2026000103 더샵 분당하이스트 — 신혼부부·생애최초·신생아·다자녀가구·노부모부양자 특별공급 '신청자격 ① 최초 입주자모집공고일 현재 경기도 성남시에 거주하거나 수도권(서울시, 경기도, 인천시)에 거주하는 무주택세대구성원', 선정은 '경쟁이 있을 경우 해당 주택건설지역인 경기도 성남시 2년 이상 거주자' 우선. 2026000409 LH 의정부우정 — '신혼부부ㆍ생애최초ㆍ노부모부양ㆍ신생아 특별공급 및 일반공급 지역 우선공급 기준'(같은 표), '다자녀 특별공급 지역 우선공급 기준'(따로). → 거주 지역 요건은 일반·특별 공통, 해당지역 우선은 순서(자격 아님)
- 변경: ① 특별공급 판정(spJudge)에 체크리스트의 거주지 판정 결과를 그대로 넣음: 신청 불가 → 특별공급도 불가('사는 곳이 이 공고의 신청 가능 지역 밖이에요'), 입력 필요 → 확인 필요, 해당지역/기타경기/기타지역 → 충족 근거로 표시하고 '내 위치'에 지역 순서(해당지역이라 먼저 / 해당지역 다음). 다자녀는 지역별 배정 비율이 따로 있을 수 있다고 안내 ② 자격 체크리스트 맨 위 '신청할 수 있는 공급' 요약: 일반공급(신청 가능·2순위만·신청 불가), 특별공급(가능한 유형), 지역 순서(일반·특별 공통, 해당지역 우선이 아니어도 신청 가능) 또는 거주지 불가. 아래 목록과 결론 칸은 '일반공급' 기준임을 표시 ③ '직접 확인할 것'에서 '특별공급 해당지역 우선·가구원수 산정 세부'를 '특별공급 가구원수 산정'(소득 기준 비교용, 공고문 기준 확인)과 '다자녀 특별공급 지역별 배정 비율'(다자녀 있는 공고만)로 나눔 — 공고문에서 거주 요건을 읽은 공고만, 못 읽은 공고는 예전 문구
- 파일: docs/index.html, docs/config.json, tests/test_residence.py, FEATURES.md, WORK.md
- 확인: 원문 문장 테스트(특별공급 5유형 신청자격 ①·해당지역 우선 문장·LH 공통 표/다자녀 별도 표) 추가, pytest 82개 통과. 특별공급 판정 전후 비교(마감 전 공고의 특별공급 133건): 서울 오래 거주·성남 1년 거주 → 가능 111·불가 22 → 가능 67·불가 66 (지방 공고 44건이 거주지 때문에 불가로 — 위 자격 체크리스트는 원래 불가였던 곳), 울산 거주 → 가능 111 → 36, 불가 97 (수도권 공고 75건). 바뀐 판정은 모두 '공고 대상 지역 밖'. 브라우저(iPhone 13 흉내) 광명 공고: 성남 1년 → '일반공급 신청 가능 · 특별공급 신생아·신혼부부·생애최초·다자녀가구 가능 · 지역 순서 기타지역·해당지역 다음 순서', 울산 → '일반공급 신청 불가 · 특별공급 모두 불가 · 거주지 공고 대상 지역 밖 · 둘 다 신청할 수 없어요'. 공고 211개 × 조건 2가지 카드 240개 오류 없음. 스위치 끄면 이전과 같음. 스크립트 문법 검사
- 기능: supply_summary (끄면 이전 판정·화면)
- 백업: backup/20260930-2154-supply

## 2026-09-30 21:35 · 공급 유형별 중복 문구 정리 · '아직 판정하지 않는 것' 뜻 풀기
- 요청: ① 오른쪽 '신청 가능' 배지와 아래 설명에 '신청 가능 ~'이 또 나와 중복이 많음 → 중복 제거 ② 자격 체크리스트 '충족 8 · 아직 판정하지 않는 것 1개'가 판정을 못 한 건지, 안 해도 되는 건지 헷갈림 → 개선
- 변경(표시만, 판정·계산 그대로): ① 공급 유형 한 줄에서 배지와 같은 말('신청 가능 ·', '신청할 수 없어요 ·', '아직 판단할 수 없어요 ·')을 빼고 이유·뽑는 방식만(예 '소득이 구간 기준을 넘어 추첨 몫으로만 뽑혀요', '미성년 자녀가 2명이 안 돼요'). 펼친 칸의 '네, 신청할 수 있어요' 문장을 빼고 '1. 신청 조건' 목록만. 카드 첫머리 안내 한 줄로 줄임 (special_plain) ② 자격 체크리스트: '아직 판정하지 않는 것' → '직접 확인할 것 N개 · 이 서비스가 판정하지 않는 항목'. 항목마다 뜻을 붙임(예: 특별공급 해당지역 우선·가구원수 → '특별공급 때만' 표시와 '일반공급 자격과는 상관없어요…', 통장 정보 없음 → '판정하지 못해 충족인지 모르는 상태' + '청약통장 정보 넣기'). 결론 칸 문구도 구분: 특별공급 항목만 남으면 '일반공급 기본 요건은 모두 판정했고 충족이에요. 특별공급을 쓸 때만 공고문에서 N가지를 더 확인하세요', 일반공급에 영향 있는 항목이 있으면 '판정하지 않는 N가지는 충족인지 모르는 상태'. 그런 항목이 있으면 칸을 펼쳐 둠. '판정하지 않은 항목은 충족으로 세지 않았어요' 안내. 위 '청약통장 1순위 요건 · 입력 필요'와 같은 뜻인 통장 항목은 한 번만 (checklist_v2)
- 파일: docs/index.html, WORK.md
- 확인: 브라우저(iPhone 13 흉내) 광명 시티프라디움 — 조건 다 넣은 경우 유형 한 줄에 배지 말 중복 없음, 체크리스트 '일반공급 기본 요건은 모두 판정했고 충족…', '특별공급 때만' 항목 1개. 통장 정보 뺀 경우 '확인 필요 1'과 직접 확인할 것에 통장 중복 없음. 공고 211개 × 조건 2가지 카드 240개 오류·빈 값 없음. 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — special_plain·checklist_v2 표시 수정
- 백업: backup/20260930-2135-dedup

## 2026-09-30 21:20 · 공급 유형별 자격과 위치: 쉬운 말로 풀어 쓰기
- 요청: '공급 유형별 내 자격과 위치'의 문구를 계산 결과 나열이 아니라 청약을 잘 모르는 사람도 자기 상황을 이해하게 (기능·계산·판정 로직·데이터는 그대로)
- 변경(표시만): 판정은 spJudge() 결과, 단계·물량은 SP_RULES·SP_SHARE, 점수는 pubPoints·mcScore·myScore 를 그대로 쓰고 문장만 새로 씀. ① 카드 첫머리: '지금 조건으로 신청할 수 있는 특별공급은 ○○예요 / ○○는 정보를 더 넣어야 판단' + 특별공급이 무엇인지 한 줄 ② 유형 한 줄: '○○ 특별공급 · 신청 가능/확인 필요/신청 불가' + 결론 문장(예: '신청 가능 · 소득이 구간 기준을 넘어 추첨 몫으로만 뽑혀요', '신청할 수 없어요 · 미성년 자녀가 2명이 안 돼요') ③ 펼치면 1. 신청할 수 있나요?(결론 + ✕/!/✓ 근거를 문장으로: 예 '1순위' → '청약통장 1순위 요건을 채웠어요') 2. 어떻게 뽑나요?(공고문 선정 순서를 풀어 씀: 예 '같은 소득 구간 안에서 ① 자녀가 있는 신혼부부(1순위)가 먼저 ② 공고 지역 거주자 먼저 ③ 미성년 자녀 많은 순 ④ 추첨') 3. 내 조건은 그 안에서 어떤가요?(소득: '우리 집 월평균 소득 1,583만원은 3인 가구 기준 소득(월 753만원)의 210% 수준' + 이 공고 유형의 구간 사다리 — 구간별 월 소득 한도·물량, 내가 든 구간 '← 나', 맨 아래 '우리 집' 줄, 상한을 넘으면 빨간 줄 / 내 위치: 1순위·2순위의 뜻, 점수·배점·가점과 '높을수록 먼저', 물량 중 약 몇 세대) 4. 해야 할 일(입력 필요·확인 필요를 할 일 문장으로 + 입력 버튼) ④ 일반공급 줄: '내 가점 41점 · 비교 단지 당첨 최저 49점보다 8점 낮아요'와 지난 결과라는 주의. 판정 요약 칩·공통 기준과 출처 칸은 그대로
- 파일: docs/index.html, docs/config.json, FEATURES.md, WORK.md
- 확인: 브라우저(iPhone 13 흉내) 민영(광명 시티프라디움)·공공(인천계양 A6) 공고에 맞벌이·자녀 1명·3인 가구 조건으로 전 유형 펼쳐 문구 확인, 스위치 켜고 끌 때 판정 칩 같음(가능 3·불가 2 / 불가 5). 공고 211개 × 조건 2가지(빈 조건·1인 가구)로 카드 240개 오류·빈 값(undefined·NaN) 없음. 스크립트 문법 검사, pytest 통과
- 기능: special_plain (끄면 이전 문구)
- 백업: backup/20260930-2120-plain

## 2026-09-30 21:09 · 메인 상단 정리: '내 조건' 카드 + '공고 찾기' 묶음
- 요청: 메인 상단 메뉴·필터 영역을 UX 관점에서 정리 (기능·데이터·검색/필터 로직은 그대로, UI·정보구조만). 특히 '내 조건 수정'을 쉽게 발견하고 조건을 이해한 뒤 자연스럽게 고치도록
- 변경(화면만): 위에서부터 ① 머리: 서비스 이름·갱신 시각 옆에 '참고용 추정 · 자세히'를 합쳐 안내 줄 한 줄을 없앰 ② '내 조건' 카드(첫 화면의 첫 행동): 조건을 입력하지 않았으면 '먼저 내 조건을 넣어 주세요' + [내 조건 입력하기]. 입력했으면 사는 곳·집·세대·현금 태그(빈 값은 점선 '○○ 입력 필요'), '마감 전 N건 중 신청 가능·확인 필요·(2순위만)·불가' 요약(공고 카드와 같은 eligibility 결과를 세기만 함), [내 조건 수정](내 조건 화면) + [빈 항목 N개 채우기](첫 빈 단계부터 이어서 입력), '비어 있는 항목은 확인 필요로 판정' 안내 ③ '공고 찾기' 묶음: 검색창 → 접수 중·새 공고·이번 주 마감 요약(누르면 목록 시트, 그대로) → '필터' 한 줄(가로로 밀기, 줄바꿈 없음) → '판정 등급' 줄 → 결과 N건·'조건 모두 해제'·목록/지도. 선택한 상세 필터 칩·비교·목록은 그대로 ④ 하단 탭과 내 정보 화면 이름을 '내 조건'으로 맞춤. 검색어를 칠 때 검색창만 두고 나머지를 다시 그리는 방식을 검색창이 묶음 안에 있어도 되게 일반화
- 파일: docs/index.html, docs/config.json, FEATURES.md, WORK.md
- 확인: 브라우저(iPhone 13 흉내, 밝은/어두운 화면) 조건 없음 → 입력 카드, 조건 있음 → 태그·'마감 전 44건 중 신청 가능 3 · 확인 필요 22 · 불가 19'·버튼 두 개, [내 조건 수정] → 내 조건 화면, [빈 항목 15개 채우기] → 청약통장(5/13)부터 입력. 검색 '광명' 입력 중 같은 입력칸 포커스 유지·7건, 지역 경기+고려 2건 → '조건 모두 해제' 44건, 요약 '접수 중' 시트 8건. 스위치 끄면 예전 상단(내 조건 줄·탭 '내 정보'). 스크립트 오류 없음, 문법 검사, pytest 통과
- 기능: home_v2 (끄면 예전 상단)
- 백업: backup/20260930-2109-home

## 2026-09-30 21:01 · 내 정보 [수정] → 그 단계부터 이어서 입력, 단계마다 저장하고 나가기
- 요청: 내 정보에서 수정을 눌러 들어가면 쭉 입력하게 하고, 단계마다 저장하고 나갈 수 있게 (나머지는 유지)
- 변경: 카드의 [수정]이 그 주제 한 단계만 여는 대신 인터뷰의 그 단계로 들어가 '이전·다음'으로 끝까지 이어서 입력(진행 표시 n / 전체). 모든 단계 아래에 '여기까지 저장하고 내 정보로'(내 정보에서 들어온 경우) 또는 '여기까지 저장하고 나가기'(처음 입력) — 첫 단계·마지막 단계 포함. 값은 칠 때 바로 저장되는 것은 그대로. 한 단계만 여는 화면('완료' 버튼)은 없앰. 내 정보 카드 화면·안내 문구 외 나머지는 그대로
- 파일: docs/index.html, WORK.md
- 확인: 브라우저(iPhone 13 흉내) 내 정보 '집과 혼인' [수정] → '3 / 11' 단계로 열림, 다음 → 청약통장(4/11) → 가점 계산(5/11), '여기까지 저장하고 내 정보로' → 내 정보, 고친 값(없어요·안 했어요) 카드와 기기 저장값에 반영. 공고 화면에서 시작한 입력은 1단계부터 '여기까지 저장하고 나가기' → 공고 화면. 스크립트 오류 없음, 문법 검사, pytest 통과
- 기능: profile_sections (끄면 예전 내 정보 화면·끝까지 입력)
- 백업: backup/20260930-2101-flow

## 2026-09-30 21:00 · 등급 이름 '스킵' → '비추천'
- 요청: 스킵을 비추천으로
- 변경: grade_skip 스위치가 켜졌을 때 '패스' 등급(보수 마진 음수)을 부르는 이름을 '스킵'에서 '비추천'으로. 기준·등급 코드·필터 동작은 그대로. 카드 배지에서 '비추천'이 두 줄로 꺾여 배지 글자 크기를 13px·한 줄로(스위치 켜졌을 때만). API 등급 이름도 같게
- 파일: docs/index.html, app/engine.py, tests/test_engine.py, FEATURES.md, WORK.md
- 확인: 브라우저(390px) 필터 칩 '전체 로또 고려 마진없음 비추천', 비추천 필터 33건·카드 배지 한 줄 '비추천', 스위치 끄면 '패스'. 스크립트 오류 없음, 문법 검사, pytest 통과
- 기능: grade_skip (끄면 '패스')
- 백업: backup/20260930-2100-label

## 2026-09-30 20:23 · 거주 지역 판정 (해당지역·기타지역·거주기간)
- 요청: '서울 거주 예/아니요'만으로는 판정이 안 되니 사는 곳·거주기간까지 공고문 기준으로 판정 (1·2·3 한 번에)
- 원인: 인터뷰가 서울 공고만 다루던 때의 '서울 거주' 질문만 판정에 써서, 경기 공고는 경기 사람도 '확인 필요', 인천·지방 공고는 모두 '확인 필요', 서울 공고는 서울 밖이면 기타지역 신청이 가능한데도 '미충족'. 해당지역 거주기간(예: 서울 2년)은 보지 않았음
- 변경: ① 공고문 읽기(app/notice_pdf.parse_residence): 공고문 첫머리 '해당지역·(기타경기)·기타지역' 표, LH '지역우선 공급기준' 표(해당지역·경기·기타지역 비율), 무순위·재공급 '대상자' 문장에서 해당지역(시·도/시·군), 거주기간(개월)과 기준일, 경기도 몫(개월·기준일), 기타지역 시·도(전국 포함), 배정 비율을 읽음. 못 읽으면 넣지 않음(추측 안 함). 공고문 읽기 규칙 버전 4 → 모든 공고문을 다시 읽음 ② 인터뷰 첫 질문을 '어디에 살고 계세요?'(시·도, 도 지역은 시·군, 시·도 전입일, 시·군 전입일)로 합침. 예전 '서울 거주'·'예치금 지역' 답은 여기서 자동으로 맞추고(예전에 서울이라고 답한 사람은 서울로 옮김), 특별공급의 시·도 거주 시작일도 수도권 밖은 같은 날로 채움(수도권 사람만 '수도권 합산 날'을 따로 물음) ③ 판정: 해당지역에 기준일 이전부터 살면 '해당지역', 기간이 모자라거나 경기 다른 시면 '기타경기'(대규모 택지)·'기타지역(해당지역 다음)', 공고가 정한 지역 밖이면 '신청 불가'(사유에 해당지역·기타지역과 지금 사는 곳), 무순위는 지역 안이면 '신청 가능'. 공고문을 못 읽은 공고는 '확인 필요'. '아직 판정하지 않는 항목'에서 '해당지역 거주기간'을 뺌(읽은 공고만) ④ 공공 신혼·신생아 점수의 거주기간이 특별·광역시에서 수도권 합산 날을 쓰던 것을 그 시 전입일로 바로잡음(입력했을 때)
- 파일: app/notice_pdf.py, app/pipeline.py, app/models.py, docs/index.html, docs/config.json, tests/golden/notices.json, tests/test_residence.py, tests/test_notice_and_notify.py, FEATURES.md, WORK.md
- 확인: 정답 데이터 — 모아 둔 공고문 원문(evidence/notices) 18건의 거주 요건을 원문 문장으로 확인해 tests/golden/notices.json 에 넣고(민영 표 8·국민/LH 표 5·무순위 5, 글자 순서가 뒤섞인 2026000436 포함) 추출 결과와 같음을 테스트로 고정, 56건 모두 오류 없이 읽힘(56건 추출). 판정 비교(공고 211개, 원문으로 읽은 값을 넣은 화면): 서울 오래 거주 → 해당지역 4·기타지역 83·신청 가능(무순위) 30·신청 불가 94(지방 등), 이전에는 충족 105·확인 필요 106. 성남 1년 거주 → 성남 공고(2년) 기타지역, 양주·평택 공공 기타경기, 서울 무순위 신청 불가. 울산 9개월 → 울산 1년 공고 기타지역, 거주기간 없는 울산 공고 해당지역. 브라우저(iPhone 13 흉내): 첫 질문·시·군/전입일 칸, 상세 '지금 조건으로는 신청 불가 — 해당지역 광명시 · 기타지역 서울·경기·인천 거주자만…(지금 울산)', 내 정보 '사는 곳' 카드, 예전 '서울 거주 예' 저장값 → 사는 곳 서울. 스위치 끄면 이전 판정과 같음. 스크립트 오류 없음, 문법 검사, pytest 81개 통과
- 올린 뒤: 첫 수집에서 공고문 56건을 새 규칙으로 한꺼번에 다시 읽다가 시간 제한(300초)에 걸려 17건을 못 읽어 [검증·정답 불일치] 6줄(철산자이 브리에르·두산위브더제니스 대연, 수집값 없음). 추출 규칙 문제가 아니라 읽기 시간 문제라 수집을 한 번 더 실행(손으로 실행) → 남은 17건 16초에 읽음, 공고 56건 모두 거주 요건 읽음, '정답 데이터와 모두 일치', 경고 없음
- 기능: residence_v2 (끄면 예전 '서울 거주' 판정)
- 백업: backup/20260930-2022-resid

## 2026-09-30 20:14 · 내 조건을 항목별로 고치기
- 요청: 내 조건 입력을 처음부터 쭉 하지 않고 중간중간 바꿀 수 있게
- 변경: ① '내 정보' 화면을 인터뷰 주제별 카드(서울 거주·세대 구성·집과 혼인·청약통장·가점 계산·자녀와 가구·… ·바로 쓸 수 있는 돈·소득과 대출)로 바꾸고, 카드마다 입력한 값(인터뷰 선택지 문구 그대로)·'입력 필요 N'·[수정] 버튼. 수정을 누르면 그 주제 한 단계만 열리고 [완료]로 내 정보에 돌아옴(값은 칠 때 바로 저장). 조건에 따라 생기는 단계(예: 세대주를 고르면 '세대주가 된 날')는 카드로 새로 나타남 ② 처음 인터뷰 중간(2단계부터 마지막 전까지)에 '여기까지 저장하고 나가기' ③ 맨 아래 '처음부터 다시 입력하기'. 인터뷰 단계에 화면용 짧은 이름(n)만 붙였고 질문·선택지·판정 로직·저장 형식은 그대로
- 파일: docs/index.html, docs/config.json, FEATURES.md, WORK.md
- 확인: 브라우저(iPhone 13 흉내) 빈 조건에서 카드 13개·'아직 21개가 비어 있어요', 세대 구성 [수정] → '내가 세대주예요' → [완료] → '세대주가 된 날' 카드 생김·기기 저장값 household=head, 현금 5,000만 수정 반영, 인터뷰 2단계 '저장하고 나가기' → 공고 화면 '내 조건' 줄에 반영. 스위치 끄면 예전 내 정보 화면('인터뷰 다시 하기'). 스크립트 오류 없음, 문법 검사, pytest 통과
- 기능: profile_sections (끄면 예전 내 정보 화면·끝까지 입력)
- 백업: backup/20260930-2014-profile

## 2026-09-30 20:04 · 공고 검색창
- 요청: 검색 기능 추가 (항상 보이는 검색창으로)
- 변경: 공고 목록의 필터 줄 바로 위에 검색창. 단지명·주소·시도·시군구·공급 유형에서 찾고, 띄어쓰기로 나눈 말이 모두 들어 있어야 맞음(예: '서울 아이파크'). 칠 때마다 바로 걸러지고 지역·등급·새 공고 등 기존 필터와 함께 적용. 결과가 없으면 "'검색어'에 맞는 공고가 없어요" + 마감 공고에만 있으면 '마감된 공고 N건 보기' 안내. × 로 지우기, '초기화'도 검색어를 지움. 칠 때는 검색창을 그대로 두고 나머지만 다시 그려 폰 키보드가 닫히지 않게 함. 방문 통계에는 '검색을 썼다'만 남기고 검색어 내용은 보내지 않음. 시공사는 수집 데이터에 없어 검색 대상에서 뺌. 판정 로직·데이터는 그대로
- 파일: docs/index.html, docs/config.json, FEATURES.md, WORK.md
- 확인: 브라우저(iPhone 13 흉내)에서 '강변' 한 글자씩 입력 → 1건, 입력 중 같은 입력칸에 포커스 유지, '광진구'·'서울 아이파크' 1건, 없는 이름 0건 안내, 마감 공고(시흥하중) 0건 → 마감 보기 2건, 등급 필터와 함께 적용, × 와 초기화 후 44건. 스위치 끄면 검색창 없고 44건(이전과 같음). 스크립트 오류 없음, 문법 검사, pytest 통과
- 기능: search (끄면 검색창 없음)
- 백업: backup/20260930-2004-search

## 2026-09-30 19:43 · 등급 이름 '패스' → '스킵'
- 요청: 서비스 이름이 '청약패스'가 되면서 등급 '패스'(마진이 음수라 넘겨도 되는 공고)가 '통과'로 읽힐 수 있어 '스킵'으로
- 변경: 등급 이름만 바꿈. 기준(보수 마진 음수)·등급 코드(pass)·필터 동작은 그대로. 화면은 등급 이름을 한 곳(GNAME)에서 스위치를 보고 고르게 해 필터 칩·카드·요약 시트·지도 표시·상세·비교·등급 기준 안내가 함께 바뀜. 백엔드 API 등급 이름(engine.grade_name)도 같은 스위치를 따름
- 파일: docs/index.html, docs/config.json, app/engine.py, tests/test_engine.py, FEATURES.md, WORK.md
- 확인: 브라우저(390px) 스위치 켬 → 필터 칩 '전체 로또 고려 마진없음 스킵', 스킵 필터 결과 배지 '스킵'. 끔 → '패스'로 이전과 같음. 스크립트 오류 없음, 문법 검사, pytest 76개 통과(스위치 켜고 끌 때 이름 테스트 추가)
- 기능: grade_skip (끄면 '패스')
- 백업: backup/20260930-1943-skip

## 2026-09-30 19:26 · 서비스 이름 '청약판정' → '청약패스'
- 요청: 도메인(cheongyakpass.kr)에 맞춰 서비스 이름을 청약패스로
- 변경: 화면 제목(<title>)·맨 위 이름·홈 화면 추가 이름(apple-mobile-web-app-title, manifest name/short_name)·이용 안내·만든 이유·이용약관·개인정보처리방침·서비스 정보의 '청약판정'을 '청약패스'로 (조사도 맞춤: 청약패스는/가/를). 백엔드 API 제목·README 도 같이. 판정 로직·데이터는 그대로. 등급 이름 '패스'(목록 필터·카드)는 바꾸지 않음
- 파일: docs/index.html, docs/manifest.webmanifest, app/api.py, README.md, WORK.md
- 확인: 브라우저(390px)에서 탭 제목·맨 위 이름 '청약패스', 이용 안내·만든 이유·약관·방침 화면에 옛 이름 없음, 스크립트 오류 없음. 스크립트 문법 검사, pytest 통과. 이미 홈 화면에 추가한 기기는 아이콘 이름이 다시 추가해야 바뀔 수 있음
- 기능: 없음(수정)
- 백업: backup/20260930-1926-rename

## 2026-09-30 19:08 · 개인 도메인 cheongyakpass.kr 연결
- 요청: 도메인을 사서 웹에 연결 (수익화 준비: 광고 심사·검색 노출을 새 주소에서 쌓기 위해 정식 오픈 전에 전환)
- 변경: 사용자가 가비아에서 cheongyakpass.kr 을 사고 DNS(A 185.199.108~111.153, www CNAME cheongyak.github.io.)를 넣은 뒤 GitHub Pages 에 도메인을 등록 → GitHub 이 docs/CNAME 을 커밋(8bf5ff4 Create CNAME). 이어서 사이트 주소 표기를 새 도메인으로: config.json site_url(알림 클릭 주소), 이용 안내 서비스 정보·이용약관 '서비스' 정의(이전 주소 포함 명시), 수집기 User-Agent, CLAUDE.md 서비스 주소
- 파일: docs/CNAME(GitHub 자동), docs/config.json, docs/index.html, app/geo.py, CLAUDE.md, WORK.md
- 확인: DNS 조회로 cheongyakpass.kr → GitHub 4개 IP, www → cheongyak.github.io 확인. 작업 환경에서는 사이트 접속이 막혀 새 주소 접속·HTTPS·자동 이동은 사용자 확인 필요. 수집 작업(collect.yml)은 git add -A 라 docs/CNAME 을 지우지 않음. 스크립트 문법 검사, pytest 통과
- 남은 일: 네이버 클라우드 Maps 'Web 서비스 URL'에 https://cheongyakpass.kr 추가(안 하면 지도 인증 실패), Cloudflare Web Analytics 새 도메인 집계 확인, Enforce HTTPS 체크. 기기에 저장된 내 조건·관심 공고는 주소별로 저장돼 예전 주소에서 넣은 값은 새 주소에서 보이지 않음(오픈 전이라 영향 적음)
- 기능: 없음(수정)
- 백업: backup/20260930-1908-domain (CNAME 커밋 전 상태: backup/20260930-1858-pre-domain)

## 2026-09-30 17:37 · 인터뷰 기본값 비우기 (운영자 조건 제거)
- 요청: 인터뷰 내용 싹 초기화
- 원인: 인터뷰 기본값(DEFAULT_PROFILE)에 처음 대화 때 받은 운영자 본인 조건(서울 거주·부모님 세대원·부모님 만 60세 이상·주택 있음·현금 3억2,500만·연소득 4,000만·생애최초)이 들어 있어, 기기에서 지워도 그 값으로 돌아오고 처음 온 방문자도 그 조건으로 판정받고 있었음
- 변경: 기본값을 '입력 안 함'으로(사는 곳·세대 구성·주택·혼인·생애최초는 비움, 현금·소득 0). 모르는 값은 '미충족'이 아니라 '입력 필요'로 표시(거주지·무주택·세대주·신혼부부 전용·규제지역 세대주·특공 세대주 — 입력한 값의 판정은 그대로). 입력 전이면 목록 '내 조건' 줄·카드·상세 맨 위·체크리스트가 '내 조건을 넣으면 판정해요 [입력하기]'로 바뀜. 내 정보 화면은 빈 값을 '미입력'으로
- 파일: docs/index.html, WORK.md
- 확인: 새 방문자(저장값 없음)로 목록·카드·상세·체크리스트 문구 확인, 공고 211개 상세·자금 화면 오류 없음. 예전 값이 저장된 사용자는 바꾸기 전 코드와 211개 공고의 자격 판정(항목별 상태 포함)이 완전히 같음. 사용자 기기에 저장된 값은 서버에 없어 원격으로 지울 수 없음 → 이용 안내의 '이 기기에 저장된 내 정보 모두 지우기'로 지우면 빈 인터뷰부터 시작. pytest 통과
- 기능: 없음(수정)
- 백업: backup/20260930-1737-reset

## 2026-09-30 15:35 · 아이폰에서 필터 선택 목록이 다시 뜨는 문제
- 요청: 아이폰에서 필터의 지역을 누르면 나오는 목록이 안 사라지고 계속 뜬다는 제보
- 원인: 필터를 고르면 화면을 다시 그린 뒤 키보드 사용자를 위해 같은 선택창(select)에 focus() 를 다시 줌. 아이폰 Safari 는 선택창에 포커스만 가도 목록(휠)을 다시 열어서, 고를 때마다 목록이 다시 떠 닫히지 않는 것처럼 보였음 (필터 칩·상세 필터·새 공고 선택 모두 해당)
- 변경: 포커스 되돌리기를 refocus() 하나로 모으고, 터치 기기(hover 없음·굵은 포인터 또는 iPhone/iPad)의 선택창에는 포커스를 주지 않음. PC 는 지금처럼 포커스 유지
- 파일: docs/index.html, WORK.md
- 확인: 브라우저에서 iPhone 13 흉내(터치·UA)로 지역·분양가·새 공고 선택 → 포커스가 선택창으로 돌아가지 않음(BODY), 필터 결과는 정상(3·30·3건). PC 는 선택창에 포커스 유지. 실제 아이폰 Safari 확인은 사용자 확인 필요. 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정)
- 백업: backup/20260930-1535-ios

## 2026-09-30 14:40 · 내 청약 가점 화면 정리 (v2)
- 요청: '내 청약 가점'을 내 총점 → 최근 당첨 사례 비교 → 항목별 점수 → 산정 근거 순으로. 계산 로직·결과는 그대로, 정보·출처 유지, 백업 후 원복 가능하게
- 변경(화면만): ① 큰 총점(50점 / 84, 계산 전이면 '계산 전') ② 0~84 눈금 막대에 내 점수(채움)·당첨 최저(주황 눈금)·당첨 평균(파랑 눈금), 범례에 값 ③ 비교 한 칸 '당첨 최저보다 N점 높아요/낮아요' + 최저·평균·비교 단지·가점제 물량 안내·출처(없으면 '비교할 당첨 가점 기록이 없어요') ④ 입력 필요 배너 ⑤ 항목별 점수 — 무주택기간·부양가족·통장 가입기간마다 점수/최대, 작은 막대, '최대까지 N점 · 1년마다 +2점(부양가족 1명마다 +5점, 통장 1년마다 +1점)'. 누르면 기존 계산 근거 문장 ⑥ 계산 방법·부양가족 기준·출처는 '계산 방법과 출처' 접힌 칸. 점수는 myScore()·scoreTarget() 결과 그대로, '1년마다 +2점' 등은 기존 계산 방법 설명과 같은 규칙 문장
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px) 비교 기록 있는 공고(광명: 50점, 최저 49·평균 58.6)·없는 공고·입력 없음 캡처, 표시 숫자가 myScore·scoreTarget 값과 같음, 공고 211개 오류 없음(v2 129개), 스위치 끄면 예전 화면, pytest 통과
- 기능: score_v2 (끄면 이전 화면)
- 백업: backup/20260930-1440-sc

## 2026-09-30 14:26 · 마진 계산 화면 정리 (v2)
- 요청: '마진 계산'을 분양가 → 실제 투입금액 → 현재 시세 → 가격 차이 흐름으로 직관적이게. 계산 로직·데이터는 그대로, 정보는 삭제하지 말고 핵심과 근거 데이터를 구분, 백업 후 원복 가능하게
- 변경(화면만): ① 맨 위 결론 칸 — 등급 배지 + '시세보다 2.89억~3.64억 싸요'(비싸면 '비싸요', 걸치면 '시세와 비슷해요', 시세 없으면 '시세를 확인해야 해요'와 사유) + 보수 기준 마진율·실매입가 ② 계산 흐름 칸 — 분양가 → + 발코니(있을 때) → + 취득세 등 → = 실매입가(굵게) → 시세 보수/기준 → 차이(등급 색). 줄마다 출처 작게 ③ 기존 막대 그래프·범례 유지 ④ 시세 근거 요약 한 줄(같은 단지/같은 구 신축/거래 부족 태그, 근거 거래 N건, 3건 미만이면 신뢰도 낮음) ⑤ '시세 근거 거래 N건 보기'·'시세는 이렇게 계산했어요'(산정 방식·해제/직거래 제외·실매입가 정의·호수 미공개)는 접힌 칸 ⑥ 네이버 부동산·국토부 링크 유지. 숫자는 grade()와 L 값 그대로
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px) 로또·고려·마진없음·패스·시세 부족 5가지 캡처, 분양가·취득세·실매입가·시세 숫자가 기존 계산값과 같은지 확인, 공고 211개 모두 v2·실매입가 누락 0, 스위치 끄면 예전 화면, pytest 통과
- 기능: margin_v2 (끄면 이전 화면)
- 백업: backup/20260930-1426-mg

## 2026-09-30 14:21 · 자격 체크리스트 화면 정리 (v2)
- 요청: '자격 체크리스트'를 전체 자격 상태 → 문제 조건 → 확인이 필요한 조건 → 세부 근거 순으로 이해되게. 판정 로직·데이터는 그대로, 정보와 출처는 유지, 백업 후 원복 가능하게
- 변경(화면만): ① 제목 아래 상태 칩(미충족·확인 필요·충족 개수, 0은 숨김) ② 전체 판정 한 칸(신청 불가 / 1순위 불가·2순위 가능 / 기본 요건 충족·확인할 것 N개 / 기본 요건 충족) + 이유(eligibility().reason) + '다음 공고부터 가능하게 하려면'(fix) ③ '문제가 있는 조건' — 미충족 항목을 빨간 테두리 칸으로(값·설명·출처) ④ '확인이 필요한 조건' — 한 묶음 목록, 입력이 필요하면 묶음 제목 옆에 '내 정보 입력하기' 하나. 통장 입력 전 안내와 예전 '청약통장 확인 필요' 항목은 같은 뜻이라 하나로 ⑤ '충족한 조건 N개'·'아직 판정하지 않는 것 N개'·'근거와 출처'는 접힌 칸(펼치면 항목별 설명·출처 그대로). 판정은 eligibility()·pendingChecks()·itemSrc() 결과를 그대로 씀
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px, 라이트·다크) 규제지역 세대원(2순위 가능)·전부 충족·5년 내 당첨 3가지 캡처, 긴 조건 이름 줄바꿈, 공고 211개 전부 v2 표시·미충족 개수가 판정 결과와 일치(불일치 0), 스위치 끄면 예전 화면, pytest 통과
- 기능: checklist_v2 (끄면 이전 화면)
- 백업: backup/20260930-1420-chk

## 2026-09-30 14:01 · 공급 유형별 카드 화면 정리 (v2)
- 요청: '공급 유형별 내 자격과 위치' 영역을 모바일 UX 관점에서 정리. 계산·데이터는 그대로, 가능/확인 필요/불가와 내 위치를 먼저, 세부는 구분, 불가·확인 필요 이유를 빨리, 공통 기준은 분리. 원복 가능하게 백업 후
- 변경(화면만): ① 제목 아래 요약 칩(가능 N·확인 필요 N·불가 N, 0은 숨김) ② 정보가 비었거나 점수가 범위로 나오면 한 줄 배너 + 입력하기 ③ 유형마다 접힌 한 줄: 유형·세대수·결과 칩 + '내 위치 · 우선공급 · 약 9세대 · 추첨' / '이유 · 세대주가 아님' / '가구원수 입력 필요'(부분 점수는 '· 거주기간 미입력') ④ 눌러 펼치면 내 위치 전체(단계·세대수·점수 내역), 소득(월평균·%), 다자녀 배점 표, 판정 근거 체크리스트(✕ 불가 사유 → ! 확인 필요 → ✓ 충족), 부족한 정보 입력 버튼 ⑤ 가능 → 확인 필요 → 불가 순, 일반공급은 점선 '비교 기준' 줄로 맨 위 ⑥ 설명·공통 기준·출처는 맨 아래 '판정 기준과 출처' 접힌 칸. 판정·점수는 기존 함수(spJudge·spPosition·pubPoints·mcScore·myScore) 결과를 그대로 씀
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px, 라이트·다크) 민영 전부 입력·공공 거주 미입력·규제지역 세대원 3가지 캡처(접힘·펼침), 스위치 끄면 예전 카드(v2 0건)·켜면 120건, 공고 211개 오류 없음, 기존 판정 시나리오 17건·거주 점수 7건 그대로, pytest 통과
- 기능: special_card_v2 (끄면 이전 화면)
- 백업: backup/20260930-1401-spux

## 2026-09-30 13:45 · 공공 특공 점수의 거주기간 반영
- 요청: 신생아 점수가 6~9점처럼 범위로 나오는 이유 → 사는 시·군구와 살기 시작한 날을 물어서 정확히. 안 적었으면 입력하라고 하거나 반영 안 됐다고 알려주기
- 원인: 공공 신혼부부·신생아 점수의 '해당 주택건설지역 연속 거주기간'(0~3점)은 공고 지역 시·군(특별시·광역시·특별자치시·도는 그 전체) 기준인데, 인터뷰에 시·도만 있어 범위로 표시했음
- 변경: 인터뷰 '사는 곳 (특별공급 점수)' 단계 — 시·도, 시·군(도 지역만, '평택'처럼 '시' 없이 적어도 인정), 시·도 거주 시작일(다자녀용), 시·군 거주 시작일. 다자녀 단계의 사는 곳 질문을 이 단계로 옮김. 입력하면 공고 지역과 비교해 3년 이상 3·1년 이상 2·1년 미만 1·미거주 0으로 점수 하나로 표시('거주기간 (평택시 4년 거주) 3'). 미입력이면 '6~9점 · 거주기간 (사는 시·군 미입력) 점수는 반영 안 했어요 [입력하기]'. 인터뷰가 항목별 표시 조건(도 지역일 때만 시·군 칸)과 글자 입력을 지원
- 파일: docs/index.html, tests/test_special_rules.py, WORK.md
- 확인: 거주 지역 단위·점수 원문(2026000409) 테스트 추가(pytest 통과). 브라우저 시나리오 7건(미입력 6~9, 평택 4.7년 9, 2년 8, 6개월 7, 수원 6, 서울 6, 시·군 미입력 6~9) 기대값과 일치, 인터뷰에서 경기 선택 시 시·군 칸 표시·저장, 기존 특공 시나리오 17건·다자녀 5건 그대로, 공고 211개 상세 오류 없음
- 기능: 없음(수정) — special_position 보완
- 백업: backup/20260930-1345-resid

## 2026-09-30 13:26 · 공급 유형별 내 위치 비교
- 요청: 특공을 쓸 때 각 경우 내 가점(위치)이 어떻게 되는지 보여줘야 어떤 조건이 유리한지 알 수 있음
- 변경: 특별공급 칸을 '공급 유형별 내 자격과 위치'로 바꾸고 유형마다 '내 위치' 한 줄 — 일반공급: 내 가점/84와 비교 당첨 컷(차이), 민영 신생아·생애최초: 소득 단계(우선/일반/추첨)와 이 주택형 세대수 중 그 단계 물량(민영 50·20%, 공공 70·20%) + '그 안에서 지역 → 추첨 (가점 무관)', 민영 신혼부부: 단계 + 1순위(자녀)/2순위 + 지역→자녀 수→추첨, 공공 신혼부부·신생아: 점수표(소득·자녀·납입·혼인기간, 거주 0~3은 범위) 최대 13/10점, 다자녀: 배점/100, 민영 노부모: 84점 가점(배우자 통장 제외), 공공 노부모: 저축총액 순·내 인정 금액. 특공·일반 동시 신청 시 특공만 인정 안내
- 파일: docs/index.html, docs/config.json, tests/test_special_rules.py, FEATURES.md
- 확인: 공공 점수표 문구·점수와 단계 비율이 원문(2026000409·443)에 있는지 테스트로 고정(pytest 통과). 브라우저에서 부산(민영)·고덕(공공) 공고로 손 계산과 일치(4인 76% → 우선·18세대 중 약 9, 공공 신생아 6~9/10, 신혼 8~11/13, 다자녀 70·55점), 기존 시나리오 17건 그대로 통과, 공고 211개 상세 오류 없음
- 기능: special_position
- 백업: backup/20260930-1326-sppos

## 2026-09-30 13:06 · 실거래가 조회 실패 대응 (지난 값 유지·재시도·오류 기록)
- 요청: 지금 시세 확인이 안 된다고 나옴
- 원인: 12:56 수집에서 실거래가 요청 684건이 모두 실패(성공 0·실패 467·시간 초과 217) → 211개 주택형 모두 '실거래가 조회에 실패'. 같은 현상이 오늘 07:25·09:40 에도 있었고 3분 뒤 실행은 정상(09:43, 186건) → 국토부 API 쪽 일시 거절로 보이나, 실패 이유를 기록하지 않아 정확한 오류는 모름
- 변경: ① 실패 이유를 [실거래 오류] 줄로 기록(인증키는 serviceKey=*** 로 가림) ② 연결 오류·5xx·429·XML 아닌 응답은 1.5초·3초 쉬고 두 번 더 시도(권한 없음·호출 한도 초과는 바로 포기) ③ 조회에 성공한 주택형의 시세를 docs/market-cache.json 에 두고, 실패하면 마지막 성공 값을 쓰며 '오늘 실거래가 조회가 실패해 ○월 ○일 조회값' 이라고 표시. [경고·시세] 줄로 남겨 수집 알림 이슈에도 잡힘 ④ 캐시는 오늘 09:43 정상 수집값(211건, 시세 있음 186건)으로 채움 ⑤ 테스트가 실제 캐시 파일을 건드리지 않게 tests/conftest.py
- 파일: app/sources/rtms.py, app/pipeline.py, docs/market-cache.json, tests/test_pipeline.py, tests/conftest.py
- 확인: pytest 73 통과(지난 값 사용·인증키 가림·재시도 테스트 추가), 테스트 전후 docs 캐시 파일 해시 동일. 올린 뒤 수집(4cc7b2a): 실거래 요청 684건 모두 성공(43초), 시세 있음 186/211, [실거래 오류]·[경고] 없음, 실행 기록에 인증키 없음
- 기능: 없음(수정)
- 백업: backup/20260930-1306-mkt

## 2026-09-30 12:57 · 특별공급 세대수: 유형 구분 없는 공고 안내
- 요청: (특별공급 작업 후속) 올린 뒤 수집 결과 확인
- 확인 결과: 수집 실행(311c7f0)에서 211개 주택형 중 161개에 유형별 세대수가 들어옴(예: 부산 에코델타시티 59A 신생아 18·신혼 28·생애최초 31·다자녀 18·노부모 5·기관추천 19, 합계 119 — 생애최초가 많은 것은 공고문 '17% 범위' 문구와 같음). 유형 합계와 total 이 다른 건 신혼희망타운 7건뿐(유형별 필드가 모두 0, total 만 있음). [경고]·[검증·정답 불일치] 없음
- 변경: 유형별 세대수가 모두 0인데 합계가 있으면 '청약홈이 유형별 세대수를 나눠 주지 않았어요 (신혼희망타운은 대상 전용 공급)' 안내
- 파일: docs/index.html, WORK.md
- 확인: 브라우저로 신혼희망타운·부산 공고 상세 확인, 공고 211개 상세 오류 없음, 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — special_counts 표시 보완
- 백업: backup/20260930-1257-spfix

## 2026-09-30 12:49 · 다자녀가구 배점 (100점)
- 요청: 특별공급도 판정할 수 있게, 기능별로 나눠서 (3/3: 다자녀 배점)
- 변경: 특별공급 자격 칸의 다자녀가구 줄 아래 '다자녀 배점 N / 100 (추정)' 펼침(항목별 점수·근거). [별표1] 그대로: 미성년 자녀 4명+ 40·3명 35·2명 25 / 만 6세 미만 3명+ 15·2명 10·1명 5 / 3세대(무주택 직계존속 3년 이상 같은 등본) 또는 한부모 5년 5 / 무주택기간(만 19세 또는 처분일부터) 10년+ 20·5년+ 15·1년+ 10 / 해당 시·도 거주(수도권은 서울·경기·인천 하나로, 만 19세 이후) 10년+ 15·5년+ 10·1년+ 5 / 통장 10년+ 5. 동점은 미성년 자녀 수 → 나이 → 추첨 안내. 인터뷰에 '다자녀 배점' 단계(자녀 2명 이상일 때만: 영유아 수·세대구성·사는 시·도·거주 시작일)
- 파일: docs/index.html, docs/config.json, tests/test_special_rules.py, FEATURES.md
- 확인: 배점표 문구·점수가 민영(2026000103)·공공(2026000409) 원문에 있는지와 화면 계산식 구간을 테스트로 고정(pytest 통과). 브라우저 시나리오 5건(80·65·75·100점·미입력) 손 계산과 일치. 스크립트 문법 검사
- 기능: multichild_score
- 백업: backup/20260930-1249-mc

## 2026-09-30 12:47 · 특별공급 유형별 자격 판정
- 요청: 특별공급도 판정할 수 있게, 기능별로 나눠서 (2/3: 유형별 자격)
- 변경: 인터뷰에 특별공급 3단계(자녀·가구원수 / 세대 소득·부동산·자동차 / 주택 소유 이력·소득세 5년·노부모 3년 부양). 공고 상세에 '특별공급 자격 (민영/공공 · 추정)' 칸 — 신생아·신혼부부·생애최초·다자녀·노부모부양을 가능/불가/확인 필요와 이유, 소득 단계(우선·일반·추첨)로 표시. 규칙은 모집공고문 원문에서 확인한 값만: 민영(2026000103·443·453) 신생아 130/160%·신혼 100/140%(맞벌이 120/160%, 1인 소득 100/140% 이하)·생애최초 130/160%·추첨 단계 부동산 3억3,100만원·규제지역은 생애최초·신생아도 세대주·1인 가구 생애최초 추첨·60㎡ 이하, 공공(2026000409) 신생아 140(200)%·신혼·생애최초 130(200)%·다자녀·노부모 120(200)%·부동산 2억1,550만·자동차 4,542만·생애최초 저축 600만원·1인 가구 불가. 소득 표는 2025년 도시근로자 월평균소득(100% 3인 이하 7,533,763원 …). 유형별 세대수가 있으면 세대가 있는 유형만 보여줌. 신혼희망타운·무순위는 제외. 공공 출산가구 완화·해당지역 우선·예비신혼부부·한부모는 공고문 확인으로 안내. '아직 판정하지 않는 것' 문구 갱신
- 파일: docs/index.html, docs/config.json, tests/test_special_rules.py, FEATURES.md
- 확인: tests/test_special_rules.py(기준값·문장이 원문에 있는지, 퍼센트 금액 반올림이 공고문 표와 같은지) 포함 pytest 통과. 브라우저 시나리오 17건(부산·광명·고덕 공고, 소득 88/144/221%, 맞벌이, 혼인 8년, 세대원, 자녀 수, 소득세, 부양, 자동차, 저축액, 가구원수 없음)을 손으로 계산한 기대값과 모두 일치. 공고 211개 상세 오류 없음, 인터뷰 선택 입력(비우면 미입력) 확인
- 기능: special_eligibility
- 백업: backup/20260930-1246-spel

## 2026-09-30 12:43 · 특별공급 유형별 세대수
- 요청: 특별공급도 판정할 수 있게, 기능별로 나눠서 (1/3: 유형별 세대수)
- 변경: 청약홈 주택형(Mdl) 응답의 유형별 세대수(NWBB 신생아·NWWDS 신혼부부·LFE_FRST 생애최초·MNYCH 다자녀·OLD_PARNTS_SUPORT 노부모·INSTT_RECOMEND 기관추천·TRANSR_INSTT_ENFSN 이전기관·YGMN 청년·ETC·SPSPLY 합계)를 모아 listings.json special_units 로 저장. 필드 이름은 실행 기록 [응답 필드] general 주택형 에서 확인한 것만 씀. 무순위 주택형 응답에는 없어 None. 공고 상세에 '특별공급 세대수 (이 주택형)' 칸(0세대 유형은 숨김, 일반공급 세대수와 출처)
- 파일: app/sources/applyhome.py, app/models.py, app/pipeline.py, docs/index.html, docs/config.json, tests/test_pipeline.py, FEATURES.md
- 확인: 테스트 test_special_units_from_model 추가(pytest 65 통과), 브라우저에서 시험 값으로 칸 표시. 올린 뒤 수집 결과에서 실제 값 확인 예정
- 기능: special_counts
- 백업: backup/20260930-1243-spcnt

## 2026-09-30 11:52 · 만든 이유·이용약관·개인정보처리방침
- 요청: 급매캐치의 '데이터 & 만든 사람'·이용약관·개인정보처리방침을 벤치마킹해 새로 구성
- 변경: 이용 안내에 '문서' 칸(만든 이유와 데이터 / 이용약관 / 개인정보처리방침). 구성만 참고하고 내용은 이 서비스 구조에 맞게 새로 씀 — 회원가입·서버 저장 없음, 입력값은 기기(localStorage)에만, 쿠키 없음, 브라우저가 직접 접속하는 외부 서비스(GitHub Pages·Google Fonts·방문 통계·네이버 지도·ntfy·구글폼·오픈채팅) 표, 판정 콘텐츠는 참고용(청약자격 공식 확인·감정평가·투자 권유 아님), 이용자 권리(내 정보 지우기), 보호책임자·권익침해 구제 기관. 만든 이유 화면은 WHY/FOUNDATION(현재 공고 수·시·도 수)/01~04 구성, 개인 경력 같은 사실 확인이 안 된 내용은 넣지 않고 config.json 의 maker·privacy_officer 로 채우게 함(비면 '서비스 운영자'). 시행일 2026-09-30
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 사이트가 접속하는 외부 주소를 코드에서 뽑아 표와 대조(fonts.googleapis·static.cloudflareinsights·oapi.map.naver·ntfy.sh 등). 브라우저(390px, 라이트·다크) 세 화면 표시·가로 넘침 없음·뒤로가기·탭 선택 확인, 스크립트 문법 검사, pytest 통과. 법률 검토는 받지 않음
- 기능: legal_pages
- 백업: backup/20260930-1152-legal

## 2026-09-30 11:37 · 하단 '이용 안내' 탭
- 요청: 요약 목록 창(B안)은 유지. 이용 안내를 하단 탭으로 따로. 목록의 '자세히' 링크도 유지
- 변경: 하단 메뉴 맨 오른쪽에 '이용 안내' 탭(공고·가점 컷·등급 기준·내 정보·이용 안내). 이용 안내 화면에서 이 탭이 선택 표시됨. 목록 '자세히'·하단 링크는 그대로 같은 화면으로 감. about_page 가 꺼지면 탭도 숨김
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px) 탭 5개 표시·글자 겹침 없음, 탭 → 이용 안내·선택 표시, '자세히' → 이용 안내. 스크립트 문법 검사, pytest 통과
- 기능: about_tab
- 백업: backup/20260930-1137-abtab

## 2026-09-30 11:32 · 요약 숫자를 누르면 공고 목록 창
- 요청: 요약 숫자를 누르면 연결되게 — B안(아래에서 올라오는 목록 창). 마음에 안 들면 A안(목록 거르기)으로 바꿀 수 있게 원복 가능하게
- 변경: 요약 세 칸(접수 중·새 공고 7일·이번 주 마감)을 버튼으로(라벨 옆 ›). 누르면 아래에서 창이 올라와 해당 공고를 공고 단위로 보여줌(등급=그 공고 주택형 중 가장 좋은 등급, 시·군·구, 주택형 수, D-day). 접수 중·이번 주 마감은 마감 가까운 순, 새 공고는 공고일 최신순. 누르면 그 주택형 상세로. 닫기: 닫기 버튼·바깥 누르기·Esc. 목록 필터는 건드리지 않음, 창이 열린 동안 뒤 화면 스크롤 막음. 숫자·목록은 요약과 같은 함수(summaryGroups)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저(390px)에서 세 칸 각각 8·5·10건 표시(요약 숫자와 일치), Esc·바깥 누르기로 닫힘, 항목 → 상세 이동 후 창 닫힘·필터 그대로. 스위치 끄면 숫자만 있는 예전 상태. 스크립트 문법 검사, pytest 통과
- 기능: summary_sheet
- 백업: backup/20260930-1132-sheet

## 2026-09-30 11:26 · 요약 줄에서 최대 마진 빼기
- 요청: 맨 위 요약에서 최대 마진은 빼 달라
- 변경: 요약 줄을 세 칸(접수 중 / 새 공고 7일 / 이번 주 마감)으로. 최대 마진 계산 제거
- 파일: docs/index.html, WORK.md
- 확인: 브라우저(390px) 세 칸 표시, 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — summary_bar 변경
- 백업: backup/20260930-1126-sum2

## 2026-09-30 11:19 · 목록 필터 영역 정리
- 요청: 필터 관련 줄이 너무 많음. '필터 ▼'는 필요 없어 보임. 새 공고 '1일 0'이 헷갈림 → 'n일(n건)'처럼
- 변경: (quick_filters 가 켜져 있을 때) '필터 ▼' 버튼과 새 공고 탭 줄을 없애고, 칩 한 묶음(지역·분양가·면적·모집 상태·새 공고·상세)으로 합침. 새 공고는 '최근 1일 (0건)/최근 3일 (2건)/최근 7일 (3건)' 선택 칩(0건은 비활성, 숫자는 '결과 N건'과 같은 주택형 단위). '상세'는 칩 줄에 없는 필터(시·군·구·공급 구분·주택 구분·청약 유형·날짜)만 펼치고 고른 개수 표시. '결과 N건 · 초기화 · 목록/지도'를 한 줄로. 요약 줄 각주는 참고용 안내 한 줄에 합침('판정·마진은 참고용 추정이에요'). 칩 줄은 두 줄로 줄바꿈해 오른쪽에 숨지 않게. quick_filters 를 끄면 예전 배치(새 공고 탭 표기는 새 표기)
- 파일: docs/index.html, WORK.md
- 확인: 브라우저(390px) — 첫 화면에 첫 공고 카드가 보임. 새 공고 7일 선택 → 결과 3건(선택지 '최근 7일 (3건)'과 일치), 상세 → 시·군·구 등만 표시, 서울+강북구 → '상세 1', 초기화 → 44건. 스크립트 문법 검사, pytest 통과
- 기능: 없음(수정) — quick_filters·new_tabs 화면 배치 변경
- 백업: backup/20260930-1119-tidy

## 2026-09-30 11:08 · 지역별 당첨 가점 컷
- 요청: 급매캐치 벤치마킹 — 트렌드 탭(급지)을 청약에 맞게: 지역별 당첨 가점 컷
- 변경: 하단 메뉴에 '가점 컷' 탭. docs/cmpet-history.json(청약홈 경쟁률·당첨 가점 기록)에서 1순위 해당지역 가점제 당첨자의 최저 가점을 시·도별, 시·군·구별로 모아 범위 막대(범위·중간값·내 가점 세로선)와 '내 가점이 컷 이상 n/N' 표시. 0점(가점제 당첨자 없음)·무순위 제외. 내 가점은 기존 계산(score) 사용, 오늘 기준 추정. 당첨 보장이 아니라는 안내와 출처
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 파이썬으로 따로 계산한 값과 일치(서울 90개 중간값 64·29~74, 경기 72개 48.5·19~69, 인천 16개 50·28~68, 가점 49점 기준 5/38/8). 브라우저(390px) 캡처, 스크립트 문법 검사, pytest 통과. 기록은 현재 수도권(2025.10~2026.09 공고)만
- 기능: score_cut
- 백업: backup/20260930-1108-cut

## 2026-09-30 11:07 · 이용 안내에 데이터와 검증 방식
- 요청: 급매캐치 벤치마킹 — '데이터 & 만든 사람'
- 변경: 이용 안내 화면에 '데이터와 검증 방식' 칸(공고·모집공고문·시세·경쟁률·위치 출처와 수집 시각, 정답 데이터 대조·매일 자동 검사). config.json 의 maker 에 소개 문구를 넣으면 '만든 사람' 줄 표시(비어 있으면 숨김)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 문구를 코드와 대조(수집 cron 20:30 UTC = 05:30 KST, 시세 기준 MARKET_MONTHS=6, 공고문 읽는 항목). 브라우저 캡처로 줄바꿈 확인, 스크립트 문법 검사, pytest 통과
- 기능: data_info
- 백업: backup/20260930-1107-data

## 2026-09-30 11:06 · 오픈카톡방 링크 자리
- 요청: 급매캐치 벤치마킹 — 오픈카톡방(고민 나누기·문의·건의)
- 변경: config.json 의 open_chat_url(https://open.kakao.com/ 주소만 허용)이 있으면 내 정보 화면에 '오픈카톡방' 카드, 이용 안내 문의 칸에 링크. 비어 있으면 숨김 → 사용자가 방을 만들면 주소만 넣으면 됨
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 시험 주소로 카드·링크 표시, 빈 값이면 숨김. 스크립트 문법 검사, pytest 통과
- 기능: community_link
- 백업: backup/20260930-1106-chat

## 2026-09-30 11:05 · 홈 화면에 추가 (PWA)
- 요청: 급매캐치 벤치마킹 — 앱으로 받기(홈 화면 추가 안내)
- 변경: manifest.webmanifest·아이콘(192·512·maskable·apple-touch·favicon, 직접 그린 집+체크 모양)·theme-color 추가. 내 정보 화면에 '홈 화면에 추가' 카드: 안드로이드 크롬은 설치 버튼(beforeinstallprompt), 아이폰은 Safari 공유 메뉴 안내(홈 화면 앱은 저장 공간이 따로라 정보 재입력 필요 안내), 카카오톡 인앱은 다른 브라우저로 열기 안내. 이미 홈 화면에서 열었으면 숨김. 서비스 워커는 넣지 않음(오래된 공고가 캐시에 남는 위험)
- 파일: docs/index.html, docs/config.json, docs/manifest.webmanifest, docs/icon-192.png, docs/icon-512.png, docs/icon-maskable-512.png, docs/apple-touch-icon.png, docs/favicon.png, FEATURES.md
- 확인: manifest JSON 검사·200 응답, 크롬/아이폰/카카오톡 UA 로 안내 문구 확인, 아이콘 이미지 확인, 스크립트 문법 검사, pytest 통과. 실제 설치는 휴대폰 확인 필요
- 기능: pwa (스위치는 안내 카드만 끔. manifest·아이콘 링크는 켜진 상태로 남음)
- 백업: backup/20260930-1105-pwa

## 2026-09-30 11:04 · 카드 뱃지·마진율
- 요청: 급매캐치 벤치마킹 — 카드 칩(무순위·특공·제약 등)과 마진을 크게
- 변경: 목록 카드에 뱃지 줄(무순위·특별공급·규제지역·분양가상한제·재당첨 제한 N년·실거주 의무). 모두 수집 데이터(category·special_apply·regulated·price_cap·limits)에 있는 값만 쓰고, 데이터가 없는 추첨 비율·전매제한은 표시하지 않음. 등급 배지 아래 보수 기준 마진율(%)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저 카드 캡처(강변역: 무순위·규제지역·재당첨 제한 10년, +54% / 광명: 특별공급·규제지역·재당첨 제한 10년, +17%)를 listings.json 값과 대조. 스크립트 문법 검사, pytest 통과
- 기능: card_badges
- 백업: backup/20260930-1104-badge

## 2026-09-30 11:03 · 비교함
- 요청: 급매캐치 벤치마킹 — 비교함
- 변경: 목록에서 '★ 관심' 칩을 고르면 '관심 공고 나란히 비교' 버튼. 비교함 화면에 관심 공고 최대 3개를 열로 놓고 등급·마진(추정)·분양가·실매입가·시세(추정)·계약금·잔금(실거주, 내 입력 기준)·내 자격·접수·당첨 발표·경쟁률·당첨 제약을 비교. 4개 이상이면 칩으로 3개 고르기, 이름을 누르면 상세로. 출처 표시
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저에서 관심 4개 → 비교 3개 표시, 칩으로 교체, 이름 → 상세 이동. 값은 상세 화면과 같은 계산 함수(grade·funding·eligibility) 사용. 스크립트 문법 검사, pytest 통과
- 기능: compare
- 백업: backup/20260930-1103-cmp

## 2026-09-30 11:01 · 관심 공고 ★
- 요청: 급매캐치 벤치마킹 — 관심 단지 모음
- 변경: 공고 상세 오른쪽 위 '☆ 관심' 버튼(누르면 ★). 담은 주택형은 이 기기에만 저장(cy-watch, 로그인 없음). 목록 등급 칩에 '★ 관심 N' 칩 → 담은 공고만 보기(D-day 그대로), 카드에 ★ 표시. '내 정보 모두 지우기'에 포함
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저에서 두 공고 담기 → 저장값 2개, 목록 '★ 관심 2' 칩 → 2건, 새로고침 후 유지. 스크립트 문법 검사, pytest 통과
- 기능: watchlist
- 백업: backup/20260930-1101-watch

## 2026-09-30 11:00 · 새 공고 기간 탭
- 요청: 급매캐치 벤치마킹 — 전체/1일/3일/7일 탭
- 변경: 목록/지도 전환 아래 '새 공고 전체·1일·3일·7일' 탭(공고일 기준, 탭에 공고 수). 필터 초기화에 포함. 필터 칩 너비를 내용에 맞춤(지원 브라우저)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저에서 7일 → 공고일 9/23~9/30 공고만(강변역·충정로역·과천 2곳·아크로 리버스카이), listings.json 공고일과 대조. 탭 숫자는 목록과 같은 기준(마감 숨김이면 마감 제외). 스크립트 문법 검사, pytest 통과
- 기능: new_tabs
- 백업: backup/20260930-1100-new

## 2026-09-30 10:59 · 항상 보이는 필터 칩
- 요청: 급매캐치 벤치마킹 — 필터를 칩으로 꺼내 고른 값이 보이게
- 변경: 등급 칩 위에 지역·분양가(5억 미만/5~10/10~15/15~20/20억 이상)·면적(전용 60㎡ 이하/60~85/85 초과)·모집 상태 칩. 고르면 칩에 값이 보이고 테두리가 진해짐. 분양가·면적 필터 새로 추가(선택 칩·초기화와 연동), 해당 공고가 없는 구간은 비활성
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 브라우저에서 5~10억 → 30건, +60~85㎡ → 18건, 초기화 → 44건. listings.json 으로 따로 센 값(30, 18)과 일치. 스크립트 문법 검사, pytest 통과
- 기능: quick_filters
- 백업: backup/20260930-1059-qf

## 2026-09-30 10:58 · 목록 맨 위 요약 줄
- 요청: 급매캐치 벤치마킹 — 상단 요약 줄 (기능별 작업·백업)
- 변경: 목록 맨 위에 네 칸 요약(접수 중 / 새 공고 7일 / 이번 주 마감 / 최대 마진). 공고(주택관리번호) 단위로 세고, 지역 필터를 고르면 그 지역만. 최대 마진은 마감 전 주택형의 보수적 시세 기준 마진 최댓값(추정)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저(390px) 표시, listings.json 으로 따로 센 값과 일치(접수 중 8, 새 공고 5, 이번 주 마감 10), pytest 통과
- 기능: summary_bar
- 백업: backup/20260930-1058-sum

## 2026-09-30 10:49 · Cloudflare Web Analytics 켜기
- 요청: 방문자 집계 Cloudflare 로 (사용자가 사이트 토큰 전달, 공개용 값)
- 변경: config.json cf_beacon 에 cheongyak.github.io 사이트 토큰 입력 → GoatCounter 대신 Cloudflare 비콘을 불러옴
- 파일: docs/config.json
- 확인: 브라우저에서 Cloudflare 스크립트만 요청되고 GoatCounter 는 요청되지 않음, 이용 안내 문구 'Cloudflare Web Analytics'
- 기능: analytics (설정)
- 백업: backup/20260930-1048

## 2026-09-30 10:34 · 방문자 집계를 Cloudflare Web Analytics 로
- 요청: 방문자 집계는 Cloudflare 로
- 변경: config.json 의 cf_beacon(Cloudflare Web Analytics 사이트 토큰)이 있으면 Cloudflare 비콘을 쓰고 GoatCounter 는 불러오지 않음. 없으면 지금처럼 GoatCounter. 하단·이용 안내 문구가 쓰는 도구 이름을 따라감
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저에서 시험 토큰 → Cloudflare 스크립트만 요청·문구 'Cloudflare Web Analytics', 토큰 없음 → GoatCounter 만 요청
- 기능: analytics (변경)
- 백업: backup/20260930-1034-cf

## 2026-09-30 10:33 · 오류 신고 버튼 (구글폼)
- 요청: 오류 신고 창구는 구글폼으로
- 변경: 공고 상세 버튼 '이 공고 정보가 틀렸어요 (오류 신고)', 이용 안내 '문의'에 오류 신고 링크. config.json 의 report_form_url(구글폼 미리 채워진 링크, 공고 칸에 {listing})에 공고명·주택형·주택관리번호를 채워 엶. 주소가 비어 있으면 버튼을 숨김 → 사용자가 폼을 만들면 주소만 넣으면 됨
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저에서 시험 주소로 버튼 링크(공고명 자동 입력)·문의 칸 확인, 주소 비었을 때 숨김
- 기능: report_form
- 백업: backup/20260930-1033-rf

## 2026-09-30 10:32 · 수집 실패·경고를 이슈로 알림
- 요청: 서비스 공개 준비 (P0 6: 수집 실패 시 운영자 알림)
- 변경: 수집 워크플로 마지막에 단계 추가. 실행 실패, 또는 실행 기록에 [경고]·[검증·정답 불일치] 줄이 있으면 GitHub 이슈 '수집 알림 날짜'를 만들고(열린 것이 있으면 댓글), 저장소 주인에게 메일이 감. 코드 push 로 도는 확인 실행은 제외(schedule·수동 실행만). 이슈 실패가 수집을 막지 않게 continue-on-error
- 파일: .github/workflows/collect.yml (permissions 에 issues: write)
- 확인: YAML 문법 검사, 단계 스크립트를 가짜 gh 로 실행(실패+경고 → 새 이슈, 경고만+열린 이슈 → 댓글, 경고 없음 → 아무것도 안 함)
- 기능: 없음(수정)
- 백업: backup/20260930-1032

## 2026-09-30 10:32 · 데이터 오래됨 경고
- 요청: 서비스 공개 준비 (P0 6: 수집이 멈추면 알아차리기)
- 변경: 마지막 갱신(updated.txt, 한국 시각)이 1.5일 넘게 지났으면 목록 맨 위에 'N일 전 기준, 청약홈에서 확인' 경고
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저에서 갱신 시각을 3일 전으로 바꿔 경고 표시·현재 시각에서는 숨김 확인, pytest 64 통과
- 기능: stale_warning
- 백업: backup/20260930-1031 (d99ea54)

## 2026-09-30 10:31 · 목록 상단 참고용 안내 한 줄
- 요청: 서비스 공개 준비 (P0 1: 첫 화면 면책 안내)
- 변경: 목록 맨 위에 '판정은 참고용이에요. 신청 전 공고문을 꼭 확인하세요. 자세히(→ 이용 안내)' 한 줄
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저(390px) 한 줄 표시 확인, pytest 64 통과
- 기능: disclaimer_banner
- 백업: backup/20260930-1031-pre (d639263. backup/20260930-1031 은 같은 분에 다시 올려 이 기능 이후 상태가 됨)

## 2026-09-30 10:30 · 이용 안내·개인정보 페이지
- 요청: 서비스 공개 준비 (P0 1·3: 면책·판정 범위 안내, 개인정보 안내, 연락 이메일 ckwlsgur@naver.com)
- 변경: '이용 안내' 화면 추가(판정은 참고용·부적격 불이익·아직 판정하지 않는 요건·운영 주체, 개인정보: 서버 전송 없음·방문 통계 도구·지도/알림 외부 전달, 내 정보 지우기 버튼, 문의 이메일). 목록·상세·내 정보 하단에 링크. config.json 에 contact_email
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: 스크립트 문법 검사, 브라우저(390px)에서 링크 → 화면 → 지우기 후 인터뷰로 이동·저장값 삭제 확인, pytest 64 통과
- 기능: about_page
- 백업: backup/20260930-1030

## 2026-09-30 09:28 · 지방 시세: 전남광주통합특별시·괄호 주소 처리
- 요청: (지역코드 후속) 사용자가 네이버 클라우드에서 Reverse Geocoding 을 켬
- 확인 결과: 다시 수집하니 14개 시군구 코드 확인(진주 48170, 부산 강서 26440, 인천 검단구 28290 등), 표와 대조 3곳(미추홀·권선·분당) 모두 일치. 다음 수집에서 진주·부산·울산·천안·청주·대전·전주·고성·검단 공고에 시세가 나옴(실거래 요청 666건 모두 성공)
- 남은 문제와 변경: ① 2026-07-01 출범한 '전남광주통합특별시' 주소를 시·도 표가 몰라 키를 못 만듦 → 청약홈 공급지역 이름(SUBSCRPT_AREA_CODE_NM)을 대신 쓰고, 역지오코딩 이름은 글자 그대로 같을 때만 인정 ② '…첨단3지구 A6블록(전남광주통합특별시 북구 월출동)'처럼 행정 주소가 괄호 안에 있으면 위치·시군구를 못 찾음 → 괄호 안 행정 주소를 씀(region.main_address)
- 파일: app/region.py, app/lawd.py, app/geo.py, app/pipeline.py, tests/test_lawd.py
- 확인: pytest 64 통과. 올린 뒤 수집 2회: 첨단3지구 위치 찾음, '광주 북구' 코드 12300(통합특별시 새 코드) 확인 → 실거래 368건으로 시세 조회됨. 시군구 코드 없어 시세 못 낸 공고 0건
- 기능: 없음(수정)
- 백업: backup/20260930-0928

## 2026-09-30 09:01 · 지역코드 확인 기록 정리
- 요청: (앞 항목 후속) 지방 공고 시세 조회
- 변경: 같은 시군구를 여러 번 조회하지 않게 하고, 역지오코딩 권한 없음(403)이면 첫 건에서 멈춤. 첫 실행 기록: 진주·전주·부산·울산·천안·청주·대전·고성·인천 검단구 모두 403 → 네이버 클라우드 설정 대기
- 파일: app/geo.py
- 확인: pytest 62 통과, 직전 수집 기록 [지역코드] 20줄 확인
- 기능: 없음(수정)
- 백업: backup/20260930-0901

## 2026-09-30 08:54 · 지방 공고 시세 조회 (시군구 코드 자동 확인)
- 요청: '지역코드 몰라 시세조회 안 됨' 원인 확인 후 되게 수정
- 원인: 실거래가 조회용 시군구 코드 표가 서울·경기·인천만 있어 그 밖 지역 공고는 모두 시세 없음. 공식 코드 자료(data.go.kr)는 Actions 에서 접속 불가.
- 변경: 지도 좌표로 네이버 역지오코딩(법정동 코드 앞 5자리)을 해 docs/lawd-cache.json 에 '시도 시군구 → 코드'로 쌓고, 다음 수집부터 시세 조회에 씀. 역지오코딩 지역 이름이 공고 주소와 다르면 버림. 표가 있는 지역 3곳은 표와 대조해 [지역코드·대조]로 기록. 안내 문구 변경.
- 파일: app/lawd.py(신규), app/geo.py, app/pipeline.py, docs/lawd-cache.json, tests/test_lawd.py
- 확인: pytest 62 통과. 역지오코딩은 현재 403(네이버 클라우드 앱에서 Reverse Geocoding 미사용) → 사용 설정 후 수집 기록 [지역코드] 확인 필요
- 기능: 없음(수정)
- 백업: backup/20260930-0854

## 2026-09-30 08:53 · 제약이 없으면 '자금 확보 전 신청하지 마세요' 숨김
- 요청: 당첨 시 제약이 모두 '없음'인데도 '계약을 포기해도 당첨자로 관리돼요. 자금 확보 전에는 신청하지 마세요' 문구가 떠서 어색함 → 제약이 있을 때만
- 변경: 재당첨 제한·실거주 의무 등 공고 조건 중 하나라도 '없음'이 아니면(기간이 있거나 '공고문 확인') 문구를 보이고, 모두 없음이면 숨김. 문구를 '당첨자로 관리돼 이 제약이 그대로 걸려요'로 조금 구체화
- 기능: 없음(표기 수정)
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 통과. 브라우저: 삼천 하늘채(모두 없음 → 문구 없음), 강변역(재당첨 10년 → 문구 표시)
- 백업: backup/20260930-0853

## 2026-09-30 08:52 · 네이버 부동산 링크가 다른 단지로 가는 문제
- 요청: '네이버 부동산에서 이 단지 매물'을 누르면 해당 단지가 아닌 곳으로 연결될 때가 있음 → 해당 단지로, 검색이 안 되면 안 되는 화면 그대로
- 원인: 단지 이름만으로 검색해 이름이 비슷한 다른 단지로 연결되고, 공고 이름에 '(조합원 취소분)', '추가입주자모집', '(공공분양)' 같은 말이 붙어 엉뚱한 결과가 나옴
- 변경: 검색어 앞에 법정동 이름을 붙임(공고 단지: 공고 주소의 동, 시세 근거 거래: 실거래 자료의 법정동 umdNm 을 새로 저장, 없으면 시·군·구). 공고 이름에서 모집 관련 말을 뺌. 결과가 없으면 네이버의 '검색 결과 없음' 화면 그대로 보임. 네이버 부동산은 이 작업 환경·Actions 에서 접속이 막혀 실제 연결 결과는 사용자 확인 필요
- 기능: 없음(수정)
- 파일: docs/index.html, app/sources/rtms.py, app/market.py
- 확인: JS 문법 검사, pytest 통과. 검색어 변환 5건 확인(정자동 더샵 분당하이스트, 하중동 시흥하중지구 A-4블록 신혼희망타운, 용곡동 천안 용곡 두산위브, 구의동 강변역 센트럴 아이파크, 정자동 더샵분당파크리버)
- 백업: backup/20260930-0852

## 2026-09-30 08:44 · 지역코드: 네이버 역지오코딩 시험 (준비)
- 요청: (준비) 전국 시군구 코드 확보
- 확인 결과: GitHub Actions(해외 서버)에서 공공데이터포털 파일 화면·법정동코드 API·네이버 부동산 화면이 모두 연결 시간 초과(evidence/codes/probe.txt, evidence/pages/naver-land.txt). 실거래가 API(apis.data.go.kr)와 네이버 클라우드 지도 API 는 동작 중
- 변경: 공고 좌표로 네이버 역지오코딩(법정동 코드)을 불러 시군구 코드를 얻을 수 있는지 시험. 근거 자료 작업에 지도 키를 넘김(Secrets, 기록에는 코드·지역명만 남김)
- 기능: 없음(준비)
- 파일: tools/rules_probe.py, .github/workflows/probe.yml
- 확인: evidence/codes/reverse.txt 확인
- 백업: backup/20260930-0844

## 2026-09-30 08:31 · 전국 지역코드·네이버 부동산 링크 조사 (준비)
- 요청: (1) '네이버 부동산에서 이 단지 매물'이 다른 단지로 연결되는 경우 수정 (2) '지역코드를 몰라 시세 조회 못함'(강원 고성 등) 원인 확인·수정 (3) 제약이 없을 때 '자금 확보 전 신청하지 마세요' 문구 숨김
- 확인 결과(2): 실거래가 조회용 시군구 코드 표가 서울·경기·인천만 있어 그 밖 지역 공고는 시세를 못 구함
- 변경: 근거 자료 모으기에 (a) 공식 법정동코드 자료 받을 수 있는지 (b) 네이버 부동산 검색 주소가 어디로 가는지 확인 단계 추가
- 기능: 없음(준비)
- 파일: tools/rules_probe.py
- 확인: 올린 뒤 evidence/codes, evidence/pages/naver-land.txt 확인
- 백업: backup/20260930-0831

## 2026-09-30 08:05 · 규제지역 1순위 '세대주' 요건 누락 수정
- 요청: (자체 점검) 광명 시티프라디움 에듀하임은 신청 대상이 '무주택세대구성원'이라 세대주 항목이 없었으나, 공고문은 투기과열지구·청약과열지역 1순위에 '세대주일 것'을 요구 → 세대원도 1순위 가능으로 보였음
- 근거: 광명 2026000453 공고문 '투기과열지구 및 청약과열지역에서 공급하는 경우 아래 조건을 만족해야 1순위 신청 가능 - 세대주일 것 …'
- 변경: 규제지역 민영 일반공급 체크리스트에 '세대주 (규제지역 1순위)' 추가(공고일 기준, 이미 세대주 항목이 있는 공고는 생략). 세대원이면 '1순위로는 신청 불가 (2순위는 가능)'
- 기능: regulated_rules (수정)
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 통과. 브라우저: 광명에서 세대원 → 1순위 불가·2순위 가능, 세대주 → 충족
- 백업: backup/20260930-0805

## 2026-09-30 07:50 · 이미 읽은 공고문은 다시 받지 않기 (시간 제한 초과 수정)
- 요청: (배포 후 확인) public_deposit 배포 수집에서 LH 공고문 6건은 모두 읽었고 정답 8건 일치. 그러나 공고문 56건 읽기가 시간 제한(300초)에 걸려 11건이 취소(CancelledError)되고, 1건(더샵 청주그리니티)은 '시간 제한' 처리에서 보관 기록도 쓰지 않아 공고문 값이 빠짐
- 원인: 80쪽까지 읽기 + LH 받기로 느려졌고, 매번 모든 공고문을 다시 받음. 시간 제한으로 못 읽은 공고는 대체값 없이 건너뜀
- 변경: 보관 기록에 읽기 규칙 버전(PARSER_VERSION=3)을 남기고, 같은 규칙으로 읽은 공고문은 다시 받지 않고 보관 값을 씀(규칙을 바꾸면 버전을 올려 전부 다시 읽음). 시간 제한·취소도 '못 읽음'으로 보고 보관 기록 → 지난 실행 값을 씀
- 기능: 없음(수정)
- 파일: app/pipeline.py, tests/test_notice_and_notify.py
- 확인: pytest 59개 통과(이미 읽은 공고문 건너뛰기, 규칙 바뀌면 다시 읽기, 시간 제한 시 보관 값). 올린 뒤 실행 시간·정답 확인
- 백업: backup/20260930-0750

## 2026-09-30 07:40 · 자격 5단계: 국민주택·신혼희망타운 납입 인정 횟수 (공고문 8건 검증)
- 요청: 국민주택 납입 인정 횟수 판정을 시작하고, 검증 데이터를 여러 개 넣어 검증한 뒤 추가
- 근거(공고문 원문 8건, evidence/notices): 공공분양 5건(인천계양 A6·양주회천 A-26·의정부우정 A-2 — LH청약플러스 첨부 PDF, 고덕 A65BL·A12BL — 청약홈 첨부 PDF)의 '일반공급 순위별 자격요건' 표 '1순위: 가입 1년(12개월) 경과 + 월 납입금 12회 이상', 경쟁 시 '3년 이상 무주택세대구성원 중 저축총액(월 최대 25만원 인정) 많은 순'. 신혼희망타운 3건(성남복정2 A1·시흥하중 A-4·남양주진접2 A-4) '가입 6개월 경과 + 6회 이상'. 종전 통장은 공고 전일까지 종합저축으로 전환해야 신청 가능(인천계양 A6)
- 변경:
  - 수집: 청약홈 화면에 공고문 PDF 가 없는 LH 공공분양은 LH청약플러스 분양주택 목록에서 이름이 확실히 같은 공고(정정공고 우선, 임대·행복주택·매각 제외)의 공고문 PDF 를 받아 읽음(app/lh.py). 공고문에서 1순위 가입기간·납입 횟수 기준(deposit_count) 읽기. 공고문은 80쪽까지 읽음(고덕 공고문 자격표가 45쪽 이후)
  - 정답 데이터 8건 추가(가입기간·납입 횟수), 실제 공고문 전문으로 추출 테스트. 민영 공고문 2건에서 납입 기준을 만들지 않는지도 확인
  - 화면: 인터뷰 '납입 인정 회차'·'납입 인정 금액'. 국민주택 체크리스트에 '납입 인정 횟수 (국민 1순위/신혼희망타운)'(공고문 값, 없으면 '추정'), '통장 종류 (공공분양)'(종합저축 외에는 전환 안내), '당첨자 선정'(저축총액 순, 커트라인 공개 데이터 없음 안내)
- 기능: public_deposit
- 파일: app/lh.py(새), app/notice_pdf.py, app/models.py, app/pipeline.py, tests/test_lh_public.py(새), tests/golden/notices.json, docs/index.html, docs/config.json, FEATURES.md
- 확인: pytest 57개 통과(실제 공고문 8건 정답 일치, LH 목록 실제 화면에서 정정공고 선택·다른 블록·임대 제외, 팸플릿 제외, LH 대체 받기). JS 문법 검사. 브라우저: 인천계양 A6(10회 → 1순위 불가·2순위 가능, 30회 → 충족), 시흥하중(신혼희망타운 6회 기준), 청약예금 → 전환 안내, 미입력 → 입력 필요, 인터뷰 회차 입력 저장
- 남은 점: 지방·규제지역 공공분양 공고는 아직 없어 그 기준(추정 24·6회)은 공고문으로 확인하지 못함 → 공고문 값이 없으면 '추정' 표시
- 백업: backup/20260930-0740

## 2026-09-30 07:32 · LH 공고문 받기: 분양주택 메뉴에서 검색
- 요청: (준비) 두 번째 시험도 임대 목록(mi=1026)을 검색해 남양주진접2 '행복주택' 공고문을 잘못 저장함
- 원인: LH 청약플러스는 분양주택 공고가 별도 메뉴(mi=1027, 유형 053954)에 있음 (evidence/pages/lh-list-1027.html 에 '인천계양 A6블록 공공분양주택 입주자모집공고'와 정정공고 확인)
- 변경: 분양주택 메뉴로 검색, 제목에 임대·행복주택·매각이 있으면 제외, 정정공고가 있으면 정정공고 우선. 잘못 저장된 evidence/notices/2026820009.txt 삭제
- 기능: 없음(준비)
- 파일: tools/rules_probe.py, evidence/notices/2026820009.txt(삭제)
- 확인: 올린 뒤 기록 확인
- 백업: backup/20260930-0732

## 2026-09-30 07:25 · LH 공고문 받기: 분양 유형으로 검색, 엄격한 이름 대조
- 요청: (준비) 첫 시험에서 목록·상세·첨부 받기 과정은 동작했으나 검색이 임대 공고만 대상이라 대부분 0건, 양주회천은 '영구임대' 공고를 잘못 골라 저장함
- 변경: 분양주택 유형(05·39)·전체 상태·기간 지정으로 검색, 공고 이름의 지구·블록·유형 단어가 모두 들어 있고 '임대'가 아닌 공고만 선택. 잘못 저장된 evidence/notices/2026000416.txt(영구임대 공고문) 삭제
- 기능: 없음(준비)
- 파일: tools/rules_probe.py, evidence/notices/2026000416.txt(삭제)
- 확인: 올린 뒤 기록 확인
- 백업: backup/20260930-0725

## 2026-09-30 07:20 · LH 공고문 PDF 받기 시험
- 요청: (준비) 국민주택 정답 데이터를 여러 개 만들려면 LH 공고문 원문이 필요
- 근거: LH 목록 화면 구조(evidence/pages/lh-list-1026.html): 공고마다 data-id1~4(panId, 연계코드, 상위유형, 유형), 상세는 selectWrtancInfo.do, 첨부는 fileDownLoad('파일번호') → /lhapply/lhFile.do?fileid=
- 변경: 근거 자료 모으기에서 LH 공공분양 공고를 공고명으로 검색 → 상세 → 공고문 PDF 를 받아 evidence/notices/<공고번호>.txt 로 저장, 과정은 evidence/pages/lh-notices.txt
- 기능: 없음(준비)
- 파일: tools/rules_probe.py
- 확인: 올린 뒤 기록 확인
- 백업: backup/20260930-0720

## 2026-09-30 07:13 · LH 목록 화면 원문 저장
- 요청: (준비) LH청약플러스 목록에서 공고 이름을 못 찾음 → 화면 구조 확인 필요
- 변경: 근거 자료 모으기에서 LH 목록 화면 HTML 을 evidence/pages/lh-list-*.html 로 저장
- 기능: 없음(준비)
- 파일: tools/rules_probe.py
- 확인: 저장된 HTML 로 구조 확인
- 백업: backup/20260930-0713

## 2026-09-30 07:07 · 근거 자료 모으기를 따로 떼어 빠르게
- 요청: (작업 효율) 규정·LH 공고문 점검을 할 때마다 전체 수집(약 15분)을 기다려야 해서 분리
- 변경: app/rules_probe.py → tools/rules_probe.py, 매일 수집 작업에서 빼고 새 작업(.github/workflows/probe.yml '근거 자료 모으기')으로 실행. tools/ 를 고치거나 손으로 실행할 때만 돌고 evidence/·docs/rules-evidence.txt 만 저장
- 기능: 없음(인프라)
- 파일: tools/rules_probe.py(이동), tools/__init__.py, .github/workflows/collect.yml, .github/workflows/probe.yml(새)
- 확인: 올린 뒤 새 작업 실행 결과 확인
- 백업: backup/20260930-0707

## 2026-09-30 07:07 · LH 공고문 받는 방법 점검, 공고문 전문을 끝까지 읽기
- 요청: 국민주택 납입 인정 판정 준비 (정답 데이터 여러 개)
- 확인 결과: 청약홈 화면의 LH 공공분양 공고는 공고문 PDF 없이 LH청약플러스 목록 주소만 연결함(evidence/pages). 수집한 국민주택 공고문(고덕 A65BL)은 40쪽까지만 읽어 일반공급 부분이 빠져 있었음
- 변경: 규정 원문 모으기에서 공고문을 끝까지 읽어 저장, LH청약플러스 공고 목록 화면을 받아 공고별 상세·첨부 링크 형태를 evidence/pages/lh-list.txt 에 기록
- 기능: 없음(준비)
- 파일: app/rules_probe.py
- 확인: 올린 뒤 evidence 확인
- 백업: backup/20260930-0707

## 2026-09-30 06:51 · 국민주택 납입 인정 준비: 공고문 전문 보관, LH 공고 링크 점검
- 요청: 국민주택(공공분양) 납입 인정 횟수 판정 시작, 정답 데이터 여러 개로 검증한 뒤 추가
- 변경: 규정 원문 모으기 단계가 (1) 읽은 공고문 전문을 evidence/notices/<공고번호>.txt 로 저장(사이트에는 올라가지 않는 폴더) (2) 공고문 PDF 를 못 찾는 공고(LH 공공분양 6건)의 청약홈 화면 링크를 evidence/pages/ 에 모음 → LH 공고문을 어디서 받을지 근거 확보
- 기능: 없음(준비)
- 파일: app/rules_probe.py
- 확인: pytest 통과. 올린 뒤 evidence 폴더 확인
- 백업: backup/20260930-0651

## 2026-09-30 06:38 · API 링크 출처를 실제 데이터가 보이는 화면으로
- 요청: 다른 곳에도 API 로 단 출처 링크가 있으면 실제 데이터가 보이는 출처로 수정
- 변경: 화면의 모든 링크를 모아 점검(공고 21곳 상세·자금 플랜·목록·등급·내 정보·알림). 공공데이터포털 API 링크는 '분양가' 한 곳 → 그 공고의 청약홈 공고 페이지(공급금액이 보이는 화면)로. '공고 주소'의 출처를 청약홈 첫 화면 → 그 공고 페이지로. 지도 위치 출처(링크 없던 'Geocoding')를 네이버 지도 주소 검색 화면으로
- 기능: 없음(출처 표기 수정)
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 통과. 브라우저에서 모든 화면 링크 목록을 뽑아 data.go.kr·API 링크가 남지 않은 것 확인
- 백업: backup/20260930-0638

## 2026-09-30 06:35 · 가점 계산 근거를 화면에 보이게
- 요청: 청약가점 계산 방식이 어떻게 되는지, 무주택기간 4년은 어디서 얻은 정보인지
- 원인: 카드에 '4년 (2022.06.09부터)'만 보여 어디서 온 날짜인지 알 수 없었음. 2022.06.09 는 입력한 생년월일(1992.06.09)의 만 30세가 되는 날
- 변경: 항목마다 기산일 종류(만 30세가 된 날 / 만 30세 전 혼인신고일 / 주택 처분일)·기간·점수 규칙을 적고, '계산 방법' 펼침에 세 항목 점수표와 '계산에 쓴 값은 내가 입력한 값' 안내
- 기능: score (표기 수정)
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 통과. 브라우저: 브라운스톤 월곡에서 '만 30세가 된 날 2022.06.09부터 공고일 2026.08.28까지 4년 → 10점', 통장 '가입일 2012.12.01부터 13년 8개월 → 15점', 계산 방법 펼침 확인
- 백업: backup/20260930-0635

## 2026-09-30 06:34 · 경쟁률 출처를 청약홈 결과 화면으로
- 요청: 경쟁률·가점 출처에 API 링크 말고 실제 경쟁률이 보이는 곳(청약홈 경쟁률)을 달아 달라
- 변경: 출처 링크를 청약홈 청약 결과 화면(selectAPTCompetitionPopup.do?houseManageNo=…, 주택형별 공급·접수·경쟁률·당첨가점이 보이는 화면임을 2026-09-30 확인)으로 바꿈. 경쟁률 표, 가점 비교, 근처 최근 경쟁률의 단지 이름 링크 모두. 무순위·잔여세대는 결과 화면 주소를 확인하지 못해 청약홈 공고 페이지로 연결
- 기능: competition, area_competition, score (출처 표기 수정)
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 통과. 브라우저: 브라운스톤 월곡(일반) → 청약홈 결과 화면, 무순위 → 공고 페이지, 시흥하중 근처 단지 → 각 단지 결과 화면 링크 확인
- 백업: backup/20260930-0634

## 2026-09-30 01:23 · 공고문 값 보관 기록 (정답 불일치 수정)
- 요청: (배포 후 확인) 수집 결과에 [검증·정답 불일치] 강변역 잔금일 None≠2026-11-30, 확장비 0≠0.2178
- 원인: 청약홈 API 가 복구되던 중 실행된 몇 번의 수집에서 강변역 공고가 목록에서 빠졌고(161건 실행 3회), 다시 돌아온 실행에서 공고문 PDF 받기도 실패('형식 아님') → '지난 실행 값 유지'가 직전 실행만 봐서 되살릴 값이 없었음
- 변경: 공고문에서 읽은 값을 공고번호별로 docs/notice-cache.json 에 보관(Actions 결과물). PDF 를 못 읽으면 보관 기록 → 지난 실행 순으로 씀. 처음 실행 때 지난 결과의 값을 보관 기록으로 옮기고, 이번에는 청약홈 복구 전 마지막 정상 결과(a62932a, 49건)에서 보관 기록을 만들어 넣음. 목록에서 사라진 공고는 기록에서 정리
- 기능: 없음(수정)
- 파일: app/pipeline.py, tests/test_notice_and_notify.py, docs/notice-cache.json(새)
- 확인: pytest 52개 통과(직전 실행에 없던 공고도 보관 기록으로 복구, 읽은 값 보관). 올린 뒤 정답 불일치가 사라지는지 확인
- 백업: backup/20260930-0123

## 2026-09-30 01:10 · 자격 4단계: 내 청약 가점 계산과 당첨 가점 비교
- 요청: 청약 자격 세부 요건 순차 추가 (가점)
- 근거: 모집공고문 가점 산정기준 표와 비고(「주택공급에 관한 규칙」 별표1의2 나목, 광명 2026000453 등, docs/rules-evidence.txt): 무주택기간 1년 미만 2점~15년 이상 32점(만 30세 미만 미혼·유주택 0점), 부양가족 0명 5점~6명 이상 35점, 통장 가입기간 6개월 미만 1점~15년 이상 17점, 배우자 통장 가입기간 50%로 최대 3점(합계 17점까지). 무주택기간은 만 30세(그 전 혼인 시 혼인신고일)부터, 주택 처분 이력이 있으면 처분일부터
- 변경: 인터뷰 '가점 계산'(생년월일·주택 처분일·부양가족 수), 혼인 시 '혼인신고일과 배우자 통장'. 민영 일반공급 상세에 '내 청약 가점 (추정)' 카드(항목별 점수·근거, 공고일 기준). 이 공고 당첨 가점(해당지역) 또는 근처 최근 단지 당첨 가점 최저와 비교해 '몇 점 높아요/낮아요'. 추첨제 물량은 가점과 무관하다고 안내
- 함께 고침: 화면 데이터에 공급 구분(category)이 빠져 있어 무순위 공고를 구분하지 못하던 점 (규제지역 1순위 요건과 가점 카드가 무순위에 붙지 않게)
- 기능: score
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: JS 문법 검사, pytest 통과. 브라우저에서 계산 5가지 사례를 손 계산과 대조(미혼 34세 28점, 30세 전 혼인 32점, 만 29세 미혼 9점, 처분 후 3년+배우자 통장 45점, 유주택 18점 — 모두 일치). 광명 59A 상세에서 53점, 근처 힐스테이트 광명 11(2025.11) 최저 49점과 비교 표시 확인
- 백업: backup/20260930-0110

## 2026-09-30 01:08 · 자격 3단계: 규제지역 1순위 추가 요건
- 요청: 청약 자격 세부 요건 순차 추가
- 근거: 모집공고문 '투기과열지구 및 청약과열지역에서 공급하는 경우 … 세대주일 것, 2주택 이상을 소유한 세대에 속하지 않을 것, 과거 5년 이내 당첨된 분의 세대에 속하지 않을 것' (광명 2026000453 등, docs/rules-evidence.txt). 세대주 요건은 기존 항목 유지
- 변경: 인터뷰 '세대의 주택과 당첨 이력'(세대 주택 수·세대 5년 내 당첨). 규제지역 민영 일반공급의 체크리스트에 '2주택 이상 세대 아님'·'세대 5년 내 당첨 없음'. 1순위 요건(가입기간·예치금·통장 종류·이 두 항목)만 못 채우면 '신청 불가' 대신 '1순위로는 신청 불가 (2순위는 가능)', 목록 '1순위 불가 · 2순위 가능'
- 기능: regulated_rules (2순위 구분 문구는 account_rules 항목에도 적용)
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: JS 문법 검사, pytest 통과. 브라우저: 광명(규제) 상세에서 입력 전 '입력 필요', 2채 이상 → '1순위로는 신청 불가 (2순위는 가능)', 없음 → 충족. 내 정보 화면 표시 확인
- 남은 점: 기존 '무주택 세대' 항목은 모든 공급에서 무주택을 요구함(민영 추첨제는 1주택 세대도 가능) → 다음 단계에서 공급 유형별로 나눌 때 정리
- 백업: backup/20260930-0108

## 2026-09-30 01:05 · 자격 2단계: 청약통장 1순위 요건 판정
- 요청: 청약 자격이 너무 간단함 → 순서대로 세부 요건 추가 (기능별로 나눠 관리)
- 근거: 모집공고문 원문(docs/rules-evidence.txt). 1순위 가입기간 문장(투기과열·청약과열 24개월: 광명·분당·월곡, 수도권 12개월: 숭의·부천·시흥·여주, 그 밖 6개월: 부산·울산·천안·전주), 예치금 표(서울·부산 300/600/1000/1500만, 그 밖 광역시 250/400/700/1000만, 그 밖 200/300/400/500만 · 전용 85/102/135㎡ 이하/모든 면적, 신청자 거주지 기준), 청약부금 85㎡ 이하, 청약저축은 민영 불가(예금 전환)
- 변경:
  - 수집: 공고문에서 1순위 가입기간(account_months) 읽기(문장 3가지 + 뒤섞인 문장). 지난 실행 값 유지. 정답 데이터 5건 추가(광명 24, 숭의 12, 에코델타 6, 삼천 6, 더샵 시에르네 6 — 공고문 추출 텍스트에서 Claude 가 확인, 사람 재확인 권장)
  - 인터뷰: '청약통장'(종류·가입일·예치금·재당첨) 질문, 서울이 아니면 '사는 지역'(예치금 구분). 예전 '가입 2년 이상이고 예치금도 채웠나요?' 질문은 스위치를 끄면 다시 나옴
  - 체크리스트: 가입기간(공고일 기준 개월 / 필요 개월, 공고문 값 없으면 '추정'), 예치금(민영, 신청자 거주지·전용면적 기준), 통장 종류 제한, 국민주택은 '납입 인정 횟수·금액 확인 필요'(미판정). 1순위 미충족이면 '2순위로는 신청 가능' 안내. '아직 판정하지 않는 것' 목록이 기능에 따라 줄어듦
- 기능: account_rules
- 파일: app/notice_pdf.py, app/models.py, app/pipeline.py, tests/test_notice_and_notify.py, tests/golden/notices.json, docs/index.html, docs/config.json, FEATURES.md
- 확인: pytest 50개 통과(실제 공고문 문장 4종 + 기관추천 문장 오인 없음). JS 문법 검사. 브라우저: 인터뷰 '청약통장' 화면, 서울 거주·종합저축 22개월·200만 프로필로 광명(24개월 필요 → 미충족, 예치금 300만 필요 → 미충족), 숭의(12개월 추정 → 충족), 시흥하중(국민 → 납입 확인 필요) 확인
- 백업: backup/20260930-0105

## 2026-09-30 00:54 · 마감 공고는 기본으로 숨기고 버튼으로 보기
- 요청: (배포 후 확인) 마감 공고를 발표 후 14일까지 남기면서 목록 161건 중 120건이 마감 공고가 됨 → 목록이 지나치게 길어짐
- 변경: 목록 기본은 접수 예정·접수 중 공고만. 맨 아래 '마감된 공고 N건 보기 (경쟁률·당첨 가점 확인)' 버튼으로 펼침. 모집 상태 필터를 '마감'으로 고르면 바로 보임. 지도에도 기본은 마감 공고 제외
- 기능: 없음(마감 공고 유지 변경의 보완)
- 파일: docs/index.html, FEATURES.md
- 확인: JS 문법 검사. 브라우저(실제 수집 데이터 161건): 기본 41건, 버튼 누르면 161건·경쟁 칩 102개. 더샵 분당하이스트 상세 경쟁률 표(66A 공급 28·접수 150·5.4:1 등 13개 주택형), 시흥하중 상세 '신청 전 참고'(시흥 은계 에피트, 시흥거모 엘가 로제비앙) 확인
- 백업: backup/20260930-0054

## 2026-09-30 00:54 · 경쟁률: 주택형 끝 공백 때문에 일부 공고에 안 붙던 문제
- 요청: (배포 후 확인) 청약홈 API 복구 후 첫 수집(공고 161건)에서 경쟁률 필드는 후보와 일치(CMPET_RATE, REQ_CNT, SUPLY_HSHLDCO, SUBSCRPT_RANK_CODE, RESIDE_SENM / LWET_SCORE, TOP_SCORE, AVRG_SCORE)하고 31건 중 23건에 반영됐으나, 숭의역 0/2, 진주 2/5 등 일부 주택형이 빠짐
- 원인: 청약홈 주택형 값 끝에 공백이 붙는 경우('069.7032 ')가 있어 공고 id 에는 공백이 남고, 경쟁률 쪽은 공백을 지워 서로 달라짐
- 변경: 비교할 때 양쪽 모두 공백 제거. 실제 사례로 테스트 추가
- 기능: competition (수정)
- 파일: app/sources/cmpet.py, tests/test_cmpet.py
- 확인: pytest 통과. 올린 뒤 [경쟁률] 줄에서 숭의역·진주 반영 수 확인
- 백업: backup/20260930-0054

## 2026-09-30 00:43 · 자격 규정 원문 모으기 (자격 2단계 준비)
- 요청: 청약 자격 판정을 세부 요건까지 넓히기 전에, 기준 숫자를 기억·블로그가 아닌 원문으로 확인
- 변경: 국가법령정보센터는 이 작업 환경에서 열리지 않아, 수집된 모집공고문 PDF(민영 10건)에서 예치기준금액·가입기간·가점제·특별공급 소득 기준 등의 문단을 뽑아 docs/rules-evidence.txt 로 남기는 일회성 단계를 수집 작업에 추가(실패해도 수집은 계속). 규칙을 만든 뒤 이 단계는 뺄 예정
- 기능: 없음(준비)
- 파일: app/rules_probe.py(새), .github/workflows/collect.yml
- 확인: 올린 뒤 docs/rules-evidence.txt 내용 확인
- 백업: backup/20260930-0043

## 2026-09-30 00:40 · 자격 1단계: 기본 요건만 확인했다고 분명히 표시
- 요청: 청약 자격 체크리스트가 너무 간단함(통장 가입기간·예치금·납입, 일반/특별공급 요건 등). 순서대로 진행하되 1단계로 먼저 단정 표현을 없앰
- 변경: 체크리스트 위에 '기본 요건만 확인했어요'와 아직 판정하지 않는 항목 목록. 통장이 있다고 답해도 '보유 · 세부 확인 필요'(가입기간·예치금/납입은 미판정). '넣어도 돼요' → '기본 요건과 자금은 가능해요 · 세부 요건 확인 필요'(모집공고문 링크), 목록 '내 자격 가능' → '기본 요건 충족'/'자격 확인 필요', 타일 '가능' → '기본 충족', '자격은 되지만' → '기본 요건은 되지만'. 스위치를 끄면 이전 표시로 돌아감
- 기능: eligibility_caution
- 파일: docs/index.html, docs/config.json, FEATURES.md
- 확인: JS 문법 검사, pytest 48개 통과. 브라우저(390px): 세대주·통장 보유 프로필로 목록 문구, 상세 안내·통장 줄·판정 문구 확인. 스위치를 끈 설정에서 안내가 사라지는 것 확인
- 백업: backup/20260930-0040

## 2026-09-30 00:37 · 기능 스위치와 기능 목록 (기능별로 끄고 되돌릴 수 있게)
- 요청: 마음에 안 들면 되돌릴 수 있게 기능별(블록별)로 나눠 관리. 나중에 싹 되돌리거나 몇 개만 삭제할 수 있게
- 변경:
  - docs/config.json 에 features 스위치: analytics, naver_map, nearby, dday_colors, competition, area_competition. false 로 두면 화면(on())과 수집(feature_on())에서 그 기능만 꺼짐
  - FEATURES.md(새): 기능별 스위치·하는 일·커밋·추가 직전 백업, 끄는 법/삭제하는 법/시점 복구법
  - CLAUDE.md 6항 추가: 기능 하나 = 커밋·스위치 하나, FEATURES.md 기록, WORK.md 에 '기능:' 줄
  - 설정을 받은 뒤 목록 외 화면(상세·내 정보 등)도 다시 그려 스위치가 바로 반영되게 함
- 기능: 없음(인프라)
- 파일: docs/config.json, docs/index.html, app/pipeline.py, app/geo.py, FEATURES.md(새), CLAUDE.md, tests/test_pipeline.py
- 확인: pytest 48개 통과(스위치 기본값). JS 문법 검사. 브라우저에서 스위치를 모두 끈 설정과 켠 설정을 비교: 끄면 지도 전환·경쟁 칩·일정 색·위치 카드·경쟁률 카드·집계 스크립트가 모두 사라지고, 켜면 그대로
- 백업: backup/20260930-0037

## 2026-09-30 00:20 · 신청 전 참고: 근처 최근 경쟁률
- 요청: 경쟁률은 접수 뒤에야 나오니, 신청 전에 판단에 도움이 되는 정보로 넣어 달라
- 변경:
  - 지난 결과 기록(docs/cmpet-history.json, Actions 가 만드는 결과물): 지금 공고들의 시·군·구에서 최근 12개월 안에 접수가 끝난 공고의 주택형별 1순위 대표 경쟁률·당첨 가점을 청약홈 경쟁률 API 로 받아 쌓음. 한 번 받은 결과는 다시 받지 않고, 결과가 비어 있던 공고는 30일 뒤 재확인, 12개월 지난 기록은 정리. 한 실행에 최대 180초
  - 자기 결과가 없는 공고(접수 예정·접수 중)에 같은 시·군·구, 전용면적 ±15㎡ 단지의 결과를 최신순 3곳까지 붙임(area_comps)
  - 화면: 상세의 경쟁률 카드가 자기 결과가 없을 때 '신청 전 참고: 근처 최근 경쟁률' 표(단지·접수월·주택형·경쟁률·가점 최저/평균)로 바뀜. 입지·분양가가 달라 그대로 적용되지 않는다는 안내와 출처 표시
- 파일: app/sources/cmpet.py, app/models.py, app/pipeline.py, tests/test_cmpet.py, docs/index.html
- 확인: pytest 47개 통과(같은 구·접수 끝난 공고만 조회, 다시 받지 않음, 면적 다르면 제외). JS 문법 검사. 브라우저(390px, 라이트·다크)에서 가짜 기록으로 표·미달 표기·결과 없음 안내 확인. 실제 값은 청약홈 API 가 복구된 뒤 수집에서 확인
- 백업: backup/20260930-0020

## 2026-09-30 00:14 · 공고 0건일 때 원인 확인 기록 추가
- 요청: (배포 후 확인) 지난 결과 유지는 동작(49건 유지). 두 번째 실행도 청약홈이 0건을 줘서 원인 확인이 필요
- 변경: 0건일 때 일반분양·무순위 개요를 날짜 필터 없이/있이 1건씩 불러 totalCount·matchCount·첫 공고를 [경고·확인] 으로 기록
- 파일: app/pipeline.py
- 확인: pytest 통과. 올린 뒤 [경고·확인] 줄로 원인 판단
- 백업: backup/20260930-0014

## 2026-09-30 00:12 · 청약홈이 빈 목록을 주면 지난 결과 유지 (서비스가 비는 문제)
- 요청: (배포 후 확인) 경쟁률 배포 직후 수집(00:08경 실행)이 '공고 0건'으로 저장돼 사이트가 샘플 화면으로 바뀜
- 원인: 청약홈 분양정보 API 가 일반분양·무순위 개요 모두 빈 목록을 돌려줌(응답 필드 줄도 없음. 같은 키로 부른 다른 엔드포인트는 정상). 이번 코드 변경(마감 공고 유지)은 개요를 받은 뒤의 거르기라 원인이 아님. 한밤 데이터 갱신 시간대의 일시적 현상으로 보임
- 조치: (1) docs/listings.json 을 직전 결과(49건)로 즉시 되돌림(a62932a) (2) 공고를 0건 받고 지난 결과가 있으면 덮어쓰지 않고 지난 결과를 유지, 알림도 보내지 않고 실행 기록에 [경고]
- 파일: app/pipeline.py, tests/test_pipeline.py
- 확인: pytest 46개 통과(빈 응답 → 지난 결과 유지·알림 없음). 올린 뒤 실행 기록 확인
- 백업: backup/20260930-0012

## 2026-09-30 00:08 · 청약 경쟁률·당첨 가점
- 요청: 청약 경쟁률 같은 정보 추가 (배치: 목록은 일정 옆 작은 칩, 상세는 판정 아래 카드). 사용자가 공공데이터포털 활용신청 완료
- 변경:
  - app/sources/cmpet.py(새): 청약홈 경쟁률 API(ApplyhomeInfoCmpetRtSvc getAPTLttotPblancCmpet / getRemndrLttotPblancCmpet / getAptLttotPblancScore)를 접수가 시작된 공고마다 HOUSE_MANAGE_NO 로 한 번 조회해 주택형(HOUSE_TY)에 붙임. 필드 이름은 후보 목록이며 실행 기록 [응답 필드]·[응답 예시] 로 실제 응답을 확인
  - 마감 공고 유지: 당첨자 발표 후 14일까지 목록에 남김(결과를 보여주려고). 목록에서는 마감 공고를 아래로 정렬하고, '새 공고' 알림에서는 뺌
  - 화면: 목록 카드 일정 표시 아래 '경쟁 32:1' 칩. 상세 판정 타일 아래 '경쟁률·당첨 가점' 표(주택형·공급·접수·경쟁률·가점 최저/평균, 1순위 해당지역 기준, 보는 주택형 강조)와 순위·지역별 전체 보기. 결과가 없으면 '아직 결과가 없어요' 안내. 출처 링크 표시
- 파일: app/sources/cmpet.py, app/sources/applyhome.py, app/models.py, app/pipeline.py, app/notify.py, tests/test_cmpet.py(새), docs/index.html
- 확인: pytest 45개 통과(새 5개: 응답 해석·대표 경쟁률 선택·미달 표기, 접수 전 공고는 조회 안 함, 권한 오류 기록, 발표 14일 뒤 제외, 마감 공고 새 알림 제외). JS 문법 검사. 브라우저(390px, 라이트·다크)에서 가짜 경쟁률로 칩·표·전체 보기·결과 없음 안내 확인. 실제 값은 올린 뒤 실행 기록과 청약홈 화면으로 대조 예정
- 백업: backup/20260930-0008

## 2026-09-29 23:59 · 접수 일정 표시(D-n)에 급한 정도별 색
- 요청: 공고 목록의 D-7 같은 일정 표시가 모두 회색이라 눈에 안 띔 → 색을 넣어 달라
- 변경: 접수 중·오늘 마감·D-day는 빨강(채움), 3일 안은 주황, 7일 안은 파랑, 그 뒤는 지금처럼 회색, 마감은 흐린 글씨. 판정 등급 배지와 겹치지 않게 빨강 외에는 연한 배경으로
- 파일: docs/index.html
- 확인: JS 문법 검사, pytest 40개 통과, 브라우저(390px, 라이트·다크)에서 날짜를 바꾼 공고 6건으로 접수 중·D-1·D-2·D-5·D-12·마감 표시 확인
- 백업: backup/20260929-2359

## 2026-09-29 23:03 · 좌표를 먼저 전부 찾고, 주변 입지는 남는 시간에
- 요청: 사용자가 네이버 지도 키를 넣음 → 수동 실행으로 확인
- 확인 결과: 좌표 정상 동작(정확 4 · 동 기준 2). 그런데 주변 입지 조회가 느려 시간 제한(180초)에 걸려 나머지 6건(강변역·충정로 등)은 좌표조차 찾지 못함
- 변경: 좌표(빠름)를 모든 공고에 먼저 찾고, 주변 입지는 그다음 제한 시간(240초) 안에서만. 못 한 입지는 다음 실행에서 다시 시도
- 파일: app/geo.py, tests/test_geo.py
- 확인: pytest 40개 통과(입지 시간이 없어도 좌표는 전부 찾는지). 올린 뒤 [위치] 줄 확인
- 백업: backup/20260929-2303

## 2026-09-29 22:42 · Overpass 질의를 가볍게 (태그 먼저, 역은 점만)
- 요청: (배포 후 확인) [입지·점검] 이 세 서버 모두 504·시간 초과
- 변경: 질의를 태그 조건 먼저 쓰는 형태로 바꾸고, 역은 점(node)만 찾음. 한 번 찾은 입지는 공고별로 저장해 다음 실행에서 재사용하므로, 서버가 바쁜 날 실패해도 다음 날 다시 시도됨
- 파일: app/geo.py
- 확인: pytest 39개 통과. 올린 뒤 [입지·점검] 줄 확인
- 백업: backup/20260929-2242

## 2026-09-29 22:38 · 주변 입지 조회(Overpass) 시간 초과 대응
- 요청: (배포 후 확인) 첫 수집의 [입지·점검] 이 'overpass.kumi.systems ReadTimeout' 으로 실패
- 원인: 공용 Overpass 서버 응답이 20초를 넘김. 첫 서버의 오류는 기록에 남지 않았음
- 변경: 서버별 제한 시간 60초, 서버를 3곳(overpass-api.de, private.coffee, mail.ru)으로 늘리고 서버마다 실패 이유를 모두 기록
- 파일: app/geo.py
- 확인: pytest 39개 통과. 올린 뒤 [입지·점검] 줄 확인
- 백업: backup/20260929-2238

## 2026-09-29 22:28 · 방문자 집계 · 네이버 지도 · 주변 입지
- 요청: 방문자 집계 추가, 네이버 지도 연동으로 위치 표시, 참고 게시물 중 주변 입지 정보 추가 (계획 문서 '방문자 집계 · 네이버 지도 연동 계획' 승인분)
- 변경:
  - 방문자 집계: GoatCounter(쿠키 없음). 화면별 조회(/, /map, /detail/공고번호, /plan/공고번호 …)와 이벤트(네이버 지도·부동산·모집공고·알림 구독 클릭, 필터 사용, 인터뷰 완료, 지도 표시 선택). 소득·자산 등 입력값은 보내지 않음. 사이트 코드는 docs/config.json `goatcounter` (cheongyak). 목록 하단에 안내 문구
  - 네이버 지도 링크: 공고 상세 출처 줄과 '위치와 주변 입지' 카드에 '네이버 지도에서 보기'. 검색어는 주소에서 '일원'·블록명 등을 뺀 값(map_query)
  - 좌표 수집(app/geo.py): 매 실행 NCP Geocoding 으로 공고별 1회 조회 → 지번까지(exact) → 동까지(dong) 순. 시·도가 공고와 다르거나 국내 범위 밖이면 버리고, 못 찾으면 좌표를 만들지 않음. 지난 실행 값 재사용. 키(NCP_MAPS_CLIENT_ID/SECRET)는 Secrets 에만 두고, 없으면 건너뜀
  - 지도 화면: 목록/지도 전환(판정 색 표시, 동 기준은 점선), 상세 작은 지도(단지 + 주변 역·학교). Client ID 는 Actions 가 docs/map.json 으로 내보냄(사이트 주소가 등록된 키라 다른 곳에서 못 씀, Secret 은 내보내지 않음). 키가 없거나 인증 실패면 지도 대신 안내 문구와 링크
  - 주변 입지: OpenStreetMap(Overpass)으로 가까운 역 2곳(2km 안), 초·중·고 각 1곳(1.5km 안)의 직선거리와 도보 시간(직선×1.3÷67m/분, '추정' 표시). 출처 링크 표시
  - 자동 검증: 좌표가 국내 범위 밖이면 '데이터 확인 필요'. 실행 기록에 [위치]·[입지] 줄. 키가 없을 때는 [입지·점검] 으로 역·학교 조회만 점검
  - 웹 코드의 `naver` 검색 링크 함수 이름이 네이버 지도 SDK 전역(window.naver)을 가려서 naverSearch 로 바꿈
- 파일: app/geo.py(새), app/models.py, app/pipeline.py, app/validate.py, tests/test_geo.py(새), docs/index.html, docs/config.json, .github/workflows/collect.yml
- 확인: pytest 39개 통과(새 8개: 실제 공고 주소 12종 검색어 변환, 동 기준 대체·다른 시·도 거부, 역 중복 합치기·학교 최근접, 지난 값 재사용, 국내 범위 검증). JS 문법 검사. 브라우저(390px, 라이트·다크): 지도 SDK·GoatCounter 를 가짜 스크립트로 바꿔 목록/지도 전환, 표시 선택 → 공고 카드, 상세 입지 카드(정확·대략·위치 없음 3경우), 집계 호출 경로 확인, 가로 넘침 없음. 실제 지도·좌표는 사용자가 NCP 키를 넣은 뒤 확인 필요
- 백업: backup/20260929-2228

## 2026-09-29 14:09 · 공고문 PDF 를 일시적으로 못 받으면 지난 값 유지
- 요청: (검증이 잡아낸 문제) 직전 수집에서 [검증·정답 불일치] 강변역 잔금일 None≠2026-11-30, 확장비 0≠0.2178
- 원인: 그 실행에서 강변역 공고문 PDF 다운로드가 일시적으로 실패해 공고문 값 대신 추정값으로 돌아감 (직전 실행들에서는 정상)
- 변경: PDF 받기를 실패하면 2초 뒤 한 번 더 시도. 그래도 못 받으면 지난 실행에서 공고문으로 읽었던 값(세대주 요건·상한제·거주의무·잔금일·확장비·재당첨)을 유지하고 실행 기록에 남김. 실패 메시지에 원인(응답 코드·오류 종류)을 적음
- 파일: app/notice_pdf.py, app/pipeline.py, tests/test_notice_and_notify.py
- 확인: 테스트 추가(다운로드 실패 시 지난 값 유지). 올린 뒤 실제 수집에서 정답 일치 확인
- 백업: backup/20260929-1409

## 2026-09-29 14:07 · 비규제지역 재당첨 제한 기본값
- 요청: (검증 결과 후속) 직전 수집에서 충정로는 재당첨 10년을 읽고 정답과 일치. 남은 검증 21건 중 20건이 '재당첨 추정'(인천계양 13, 진주 5, 시흥 2)
- 변경: 공고문에서 못 읽을 때, 비규제지역이면서 분양가상한제가 아닌 주택은 재당첨 제한 '없음'(주택공급에 관한 규칙 기준)으로 두고 검증 경고에서 뺌. 규제지역·상한제 주택은 계속 경고
- 남은 과제: 인천계양·시흥은 LH 공고라 청약홈 페이지에서 PDF 링크를 못 찾음 (공고문 읽기 경로 추가 필요)
- 파일: app/pipeline.py, app/validate.py
- 확인: 테스트 통과, 올린 뒤 실제 수집 [검증] 확인
- 백업: backup/20260929-1407

## 2026-09-29 14:02 · 뒤섞인 PDF 문장에서도 재당첨 제한 읽기, 충정로 정답 추가
- 요청: (검증 결과 후속) 충정로역자이르네 공고문에서 재당첨 제한을 못 읽음
- 원인: 실행 기록의 원문을 보니 PDF 글자 순서가 뒤섞여 '재당첨제한 년 적용10', '년간 재당첨 10 제한을'로 뽑혔음
- 변경: 이 실제 문장 형태 두 가지를 추출 규칙에 추가(1~10년만 인정). 충정로역자이르네를 정답 데이터에 추가(재당첨 10년, 세대구성원 대상, 공고·접수·발표일)
- 파일: app/notice_pdf.py, tests/golden/notices.json, tests/test_notice_and_notify.py
- 확인: 테스트 31개 통과 (실제 뒤섞인 문장으로 테스트). 올린 뒤 실제 수집에서 충정로 재당첨 10년·정답 일치 확인 예정
- 백업: backup/20260929-1402

## 2026-09-29 14:00 · 공고문에서 못 읽은 항목은 원문 문장을 기록
- 요청: (검증 결과 후속) 직전 수집에서 49건 중 18건이 검증에 걸림. 대부분 '재당첨 제한을 공고문에서 확인하지 못해 추정'이었고, 충정로역자이르네는 공고문을 읽었는데도 재당첨 문구를 못 찾음
- 변경: 공고문을 읽었지만 재당첨 제한·세대주 요건·잔금일을 못 찾으면, 해당 단어가 나오는 원문 문장을 실행 기록에 [공고문·원문] 으로 남김. 다음 수정은 이 원문을 근거로 규칙을 고친다 (추측으로 고치지 않음)
- 참고: 직전 수집 결과 강변역은 재당첨 10년을 공고문에서 읽었고 정답 데이터와 모두 일치. 숭의역 69형은 마진율 -61%로 '이례적' 검증에 걸림(시세 근거 확인 필요). 소요 시간은 공고 22초, 실거래 6초, 공고문 41초
- 파일: app/notice_pdf.py, app/pipeline.py, tests/test_notice_and_notify.py
- 확인: 테스트 30개 통과
- 백업: backup/20260929-1400

## 2026-09-29 13:57 · 수집이 느려도 끝나게 (시간 제한·병렬 조회)
- 요청: (검증 작업 후 확인 중 발견) 13:26에 시작한 수집이 30분 제한에 걸려 중단됨(GitHub 기록: 04:26~04:57 UTC). 기존 데이터는 그대로라 서비스 영향은 없었음
- 원인: 공공데이터포털 응답이 느려져(필드 확인 단계에서 요청당 약 7초) 실거래 요청 200여 건을 순서대로 보내다 시간을 넘김. 13:05에 시작한 실행도 같은 이유로 10분 넘게 걸렸음
- 변경:
  - 실거래가는 필요한 (구·종류·월) 조합을 먼저 모아 8개씩 동시에 받고, 최대 10분이 지나면 남은 조회는 이번 실행에서 생략 (해당 공고는 '시세 부족'으로 남고 다음 실행에서 다시 조회)
  - 공고문 PDF 도 6개씩 동시에, 최대 5분
  - 요청 제한 시간 20초 → 15초(연결 10초)
  - 실행 기록에 [시간] 줄로 단계별 소요 시간·성공·실패·생략 건수를 남김
- 파일: app/sources/rtms.py, app/pipeline.py, app/notice_pdf.py, tests/test_pipeline.py, tests/test_notice_and_notify.py
- 확인: 테스트 29개 통과 (시간 제한을 넘기면 남은 조회를 포기하는지 테스트 추가)
- 백업: backup/20260929-1357

## 2026-09-29 13:25 · 재당첨 제한 표기 오류 수정, 데이터 검증 프로세스 추가
- 요청: 아이파크 공고문은 재당첨 제한 10년인데 화면에 '없음'으로 나온다. 데이터 검증 프로세스를 규칙으로 추가해 달라
- 원인: 수집 데이터는 '재당첨 제한 10년'이 맞았다. 화면의 자격 체크리스트에 있는 '재당첨 제한: 없음' 줄은 공고 조건이 아니라 '내가 지금 재당첨 제한 기간인지'(내 상태)였는데, 이름이 같아 공고 조건처럼 읽혔다. 또 공고 조건의 10년도 공고문에서 읽은 값이 아니라 '규제지역이면 10년'으로 추정한 값이었다
- 변경:
  - 내 상태 줄 이름을 '재당첨 제한 (내 이력)', 값을 '해당 없음'으로 바꾸고 출처를 '내가 입력한 값'으로 표시. 제약 섹션 제목을 '당첨되면 걸리는 제약 (공고 조건)'으로
  - 재당첨 제한 기간을 모집공고문에서 직접 읽어 반영(1~10년, '적용받지 않음'은 없음). 못 읽으면 '규제지역 기준 추정'으로 표시
  - 자동 검증(app/validate.py): 날짜 순서, 금액 범위, 규제·의무 조합, 시세 근거 건수·기간·이례적 마진율, 추정 항목을 매 실행 검사해 화면에 '데이터 확인 필요'와 실행 기록 [검증] 으로 남김
  - 정답 데이터(tests/golden/notices.json): 강변역 공고문 원문으로 확인한 값(분양가·일정·세대주 요건·상한제·거주의무·잔금일·확장비·재당첨 10년) 등록, 매 실행 수집값과 비교
  - CLAUDE.md 에 '4. 데이터 검증 프로세스' 추가
- 파일: app/notice_pdf.py, app/pipeline.py, app/engine.py, app/models.py, app/validate.py, tests/golden/notices.json, tests/test_notice_and_notify.py, docs/index.html, CLAUDE.md
- 확인: 테스트 28개 통과 (재당첨 추출, 정답 대조, 검증 규칙 테스트 추가). 올린 뒤 실제 수집의 [검증] 결과 확인 예정
- 백업: backup/20260929-1325

## 2026-09-29 13:21 · 동 표시·직거래 제외 건수 바로잡기
- 요청: (앞 두 작업의 실제 데이터 확인 후 후속 수정)
- 변경:
  - 실제 수집에서 국토부 매매 자료의 동 항목은 201건 중 15건만 채워져 있었고, 그마저 동 번호가 아니라 단지명이 들어 있었다. 동 번호 형태(101, 101동, A동)일 때만 화면에 보이게 했다
  - 직거래 제외 건수를 구 전체(1,910건)로 세던 것을, 실제 비교 대상이 됐을 거래(같은 단지·같은 평형, 없으면 같은 구 신축·같은 평형)만 세도록 고쳤다
- 파일: app/market.py, docs/index.html, tests/test_pipeline.py
- 확인: 테스트 25개 통과(다른 평형 직거래는 세지 않는지 추가 확인), 동 판별 규칙 8가지 입력으로 확인
- 백업: backup/20260929-1321

## 2026-09-29 13:17 · 시세 계산은 실제 시장 거래만 (직거래 제외)
- 요청: 가짜 매물 말고 실제로 확인된 것만 보여주면 좋겠다
- 변경:
  - 이 서비스가 보여주는 시세 근거는 매물(호가)이 아니라 국토부에 신고된 실거래다. 신고 후 해제된 거래는 이미 빼고 있었고, 이번에 직거래(가족 간 저가 거래 등이 섞임)도 시세 계산과 근거 목록에서 뺐다
  - 판정 화면에 '국토부에 신고된 실제 거래만, 해제 거래와 직거래 N건은 뺐다'고 표시
  - 네이버 매물의 허위 여부는 우리가 가려낼 수 없어, 링크로만 연결 (네이버 '확인매물' 필터는 사용자가 네이버 화면에서 선택)
- 파일: app/market.py, app/models.py, docs/index.html, tests/test_pipeline.py
- 확인: 테스트 25개 통과 (직거래 제외 테스트 추가). 직전 실제 수집에서 근거 거래 201건 중 직거래 5건이 있었음
- 참고: 직전 수집(0613ca0)이 평소 1분에서 10분 넘게 걸리는 중. 공공데이터포털 응답이 느린 것으로 보이며 결과를 이어서 확인
- 백업: backup/20260929-1317

## 2026-09-29 13:04 · 근거 거래에 동·평형 표시, 네이버 부동산 단지 링크
- 요청: 시세의 '네이버에서 보기'에 동·호수·평형이 나오고, 링크가 해당 매물로 가면 좋겠다
- 변경:
  - 국토부 매매 자료의 동(aptDong)을 저장해 근거 거래에 '101동 14층'처럼 표시 (분양권·전월세 자료에는 동이 없음)
  - 평형 표시: 전용 ㎡, 전용 평, 공급 평형(전용×1.33 추정, '약'으로 표시)
  - 링크: 네이버 부동산 모바일 단지 검색(m.land.naver.com/search/result/단지명)으로 연결해 그 단지의 현재 매물을 보게 함 + 평형 넣은 네이버 검색 링크
  - 호수는 국토부가 공개하지 않아 표시할 수 없다고 화면에 안내
  - 과거 실거래는 현재 매물과 1:1로 이어지지 않고, 네이버 매물 번호는 약관상 수집하지 않아 '해당 매물' 직접 링크는 만들지 않음
- 파일: app/sources/rtms.py, app/market.py, docs/index.html, tests/test_pipeline.py
- 확인: 테스트 24개 통과, 브라우저에서 근거 거래 행·링크 확인. 네이버 부동산은 작업 환경에서 접속이 막혀 링크 동작은 사용자 확인 필요
- 백업: backup/20260929-1304

## 2026-09-29 12:56 · 모든 숫자에 출처·링크 표시
- 요청: 주변 시세에 매물·실거래 링크를 주고, 모든 데이터에 출처나 링크를 달아 달라
- 변경:
  - 판정 화면: 청약홈 공고·모집공고문 PDF 링크, 자격 항목별 출처(공고문 / 주택공급에 관한 규칙 / 규제지역 기준 추정), 분양가(청약홈 API)·확장비(공고문)·취득세(지방세법)·시세(국토부 실거래가) 출처, 시세 근거 거래 목록(단지·면적·층·금액·날짜·분양권/입주권/매매·직거래 표시)과 거래별 네이버 검색 링크, 거래 3건 미만이면 신뢰도 낮음 경고, 제약 항목 출처
  - 자금 화면: 내 자금은 '내가 입력한 값', 대출·규제는 10·15 대책(국토부)·6·27 방안(금융위) 링크, 잔금일은 공고문 또는 '추정' 표시, 전세 근거 거래 목록
  - 등급 기준 화면: 등급 기준은 이 서비스가 정한 값임을 명시
  - 분양권전매 API 의 소유 구분 약자('분'/'입')를 '분양권'/'입주권'으로 표시
  - 네이버·호갱노노 매물은 약관상 가져오지 않고 검색 링크로만 연결
- 파일: docs/index.html, app/market.py, tests/test_pipeline.py
- 확인: 테스트 23개 통과, 실제 데이터로 브라우저 확인(강변역 판정 화면 출처 링크 17개·근거 거래 3건, 자금 화면 출처 21개, 시세 부족 공고도 오류 없음, 모바일 폭 가로 스크롤 없음)
- 백업: backup/20260929-1256

## 2026-09-29 12:55 · 작업 규칙(CLAUDE.md)과 작업 기록(WORK.md) 추가
- 요청: 수정 전에 백업하고, 규칙을 파일로 못박고, 수정 내용을 계속 기록해 달라
- 변경: 수정 전 백업 브랜치 생성, WORK.md 기록, 검증 후 반영 규칙을 CLAUDE.md 로 정리. 지금까지의 작업을 이 파일에 정리
- 파일: CLAUDE.md, WORK.md
- 확인: 태그 push 가 막혀 있어 백업을 브랜치 방식으로 정하고 `backup/20260929-1255` 가 원격에 생긴 것 확인
- 백업: backup/20260929-1255

## 2026-09-29 12:54 · 시세·전세 근거 거래와 공고문 PDF 주소 저장 (55caf40)
- 요청: 주변 시세에 근거 거래·출처 링크를 달아 달라
- 변경: 시세·전세 계산에 쓴 국토부 실거래(최근순 8건)와 근거 종류·건수, 읽은 공고문 PDF 주소와 공고문에서 반영한 항목을 공고 데이터에 저장
- 파일: app/market.py, app/models.py, app/notice_pdf.py, app/pipeline.py, app/sources/rtms.py, tests/
- 확인: 테스트 23개 통과

## 2026-09-29 12:40 · 웹 주소를 cheongyak.github.io 로 변경 (e226084)
- 요청: github.io/cheongyak 주소가 이상하다, 2번(조직 + 저장소 이름) 방식으로
- 변경: 알림 클릭 주소(docs/config.json site_url)를 새 주소로. 저장소는 사용자가 cheongyak 조직으로 옮기고 이름을 cheongyak.github.io 로 변경
- 파일: docs/config.json, app/notice_pdf.py
- 확인: 새 저장소에서 Pages 배포 성공, push 권한 확인

## 2026-09-29 12:36 · 공고 필터 (83f7917)
- 요청: 지역(시·도→시·군·구), 유형, 상태, 날짜 필터와 초기화·결과 개수·빈 결과 안내
- 변경: 실제 데이터에 있는 값만 선택지로 쓰는 필터 패널, 선택 필터 칩, 결과 개수, 초기화, 빈 결과 안내. 카드 날짜 표시를 모집 상태와 같은 기준으로. 수집 저장 때 원격이 앞서 있으면 rebase 후 push
- 파일: docs/index.html, .github/workflows/collect.yml
- 확인: 실제 49건으로 브라우저 확인 (인천 15 → 계양구 13 → 국민 13, 공고일 9/20 이후 3건 등 데이터와 일치), 모바일 폭 가로 스크롤 없음

## 2026-09-29 12:33 · 데이터 주소 설정 분리 되돌림 (4e370c9)
- 요청: 주소 설정 분리는 잘못된 요청이었으니 원복
- 변경: app/config.py 삭제, API 주소를 원래대로 소스 파일에. 필터용 데이터 필드는 유지
- 확인: 테스트 23개 통과

## 2026-09-29 12:30 · 필터용 데이터 필드와 응답 필드 기록 (391848a)
- 변경: 공고에 시·도, 시·군·구, 공급 구분, 특별공급 접수일 등 실제 응답 필드 저장. 실행 기록에 엔드포인트별 실제 응답 필드 목록 남김. API 서버 /listings 필터 추가
- 확인: 실제 수집에서 새 필드와 응답 필드 목록 확인

## 2026-09-29 12:18 · 실거주 의무 오탐 수정 외 (a646ca8, 77261e9)
- 변경: 거주의무는 수도권 분양가상한제 주택에만 1~5년 인정(광명 '10년' 오탐 수정), 신혼희망타운 등 대상 전용 판정, 접수 마감 전날 알림, 공급유형 이름 정리. 코드가 바뀌면 수집이 바로 한 번 돌도록 워크플로에 push 트리거 추가
- 확인: 실제 수집 결과에서 광명 실거주 의무 0년 확인

## 2026-09-29 11:25~11:53 · 첫 배포 (사용자 업로드: 6db7711, 993d31b, 2ee045d, f3cd536, 49fb4fe)
- 변경: 수집·판정 백엔드, 매일 새벽 5:30 수집 워크플로, 웹 앱, ntfy 알림, 공고문 PDF 읽기
- 확인: 청약홈·국토부 API 실제 호출 성공, 공고문 10곳 중 9곳 읽기 성공
