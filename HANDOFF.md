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

0. **버전·전략 실행 현황 (2026-10-01 오후)** — 지금 버전 v1.4.0 (VERSIONS.md, release/v1.0.0~v1.4.0 브랜치). v1.3.1~1.3.3 은 사용자 지적 수정: 관심 공고 유주택 '추첨제만', 시·도 검색, 이용 안내 '업데이트 소식'(검증 현황·상세 내역은 운영자용 — 사용자가 물으면 verify-status.json·changelog.json·VERSIONS.md 로 답함).
   v1.4.0: 청약 기준 가이드를 법령 원문(주택공급에 관한 규칙 별표 1·2, evidence/law/rule.xml)으로 다시 엶. 소득 기준표는 공고마다 달라 만들지 않음. 법령이 개정돼 값이 앱 수치(ACCOUNT_DEPOSIT·가점표)와 달라지면 tests/test_law.py 가 실패 → 원문 확인 후 앱·판정 사례를 고친다.
   - 끝남: 버전 관리(v1.0.1), 사용 측정 usage_metrics(v1.1.0, GoatCounter 이벤트 m/…), 안 쓰는 코드 정리(ntfy 삭제), 공고별 페이지 notice_pages(v1.2.0, /notice/), 빠른 시작 quick_start(v1.3.0)
   - 다음 후보(보고서 순서): '확인 필요' 원인별 행동 버튼 → 부적격 방지 체크 → '내 청약 현황' 한 화면 → 가점 오르는 날 → (사용자 결정) '비추천' 등급명 → _v2 이전 분기 정리 → 엔진 분리·청약봇(오픈카톡 질문 로그 필요)
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
