# 블라인드 판정 감사 (판정 정확도 검증)

앱 코드·결과를 보지 않은 검토자(별도 에이전트)가 모집공고문 원문(evidence/notices)과 법령 원문(evidence/law)만으로 판정하고, 앱 판정과 비교한다.

1. 사례 만들기 (무작위 프로필 × 실제 공고 주택형, 앱 판정은 따로 저장)
   `NODE_PATH=... node tools/qa/audit/audit_gen.cjs <출력폴더> 40 <시드>` → `<출력폴더>/cases.json`(검토자용), `app.json`(앱 판정, 검토자에게 주지 않음)
   특별공급 경계 위주: `audit_gen_sp.cjs` (특별공급이 있는 공고, 무주택·세대주·소득 경계 프로필)
2. 검토자에게 `brief.md` 와 cases(프로필 필드만 남긴 것)를 주고 결과를 JSON 으로 받는다 (docs/·tools/·tests/ 열람 금지)
3. 비교: general(ok/rank2/no/unsure), score, sp. 불일치는 원문을 직접 읽어 앱·검토자 중 어느 쪽이 맞는지 가리고, 앱이 틀렸으면 판정 사례(tools/make_judge_cases.py)를 추가한 뒤 고친다
4. 결과는 evidence/audit/<날짜>/ 에 남긴다

주의: 무작위 프로필은 서로 어긋난 값(예: 세대 주택 1채 + 세대원 모두 주택 이력 없음, 통장 종류 미입력 + 납입 횟수)이 생길 수 있다. 불일치 원인을 볼 때 먼저 확인한다.
