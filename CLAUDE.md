# 작업 규칙 (Claude 가 이 저장소를 수정할 때 반드시 지킨다)

이 저장소는 실제 서비스(https://cheongyak.github.io)이고, 매일 새벽 GitHub Actions 가 공고를 수집한다.
잘못된 수정이 곧바로 서비스에 나가므로 아래 규칙을 예외 없이 따른다.

## 1. 수정 전에 반드시 백업한다

코드·설정·화면을 한 줄이라도 바꾸기 전에, 지금 원격 main 상태를 백업 브랜치로 원격에 올린다.
(이 작업 환경에서는 태그 push 가 막혀 있어 브랜치를 쓴다.)

```bash
git fetch origin main
B=backup/$(TZ=Asia/Seoul date +%Y%m%d-%H%M)
git push origin "origin/main:refs/heads/$B"
```

- 백업 브랜치를 올리지 못했으면 수정을 시작하지 않는다.
- 되돌리는 방법: `git checkout origin/<백업브랜치> -- <파일>` 로 파일만 복구하거나, `git revert <커밋>` 으로 커밋을 되돌린다.
  GitHub 화면에서는 브랜치 목록에서 `backup/...` 을 골라 그때 파일을 볼 수 있다.
  `git push --force` 나 `git reset --hard` 로 원격 기록을 지우지 않는다.
- `docs/listings.json`, `docs/updated.txt`, `docs/run-log.txt` 는 Actions 가 매일 만드는 결과물이라 백업·기록 대상이 아니다.

## 2. 모든 수정은 WORK.md 에 기록한다

커밋할 때마다 `WORK.md` 맨 위(최신이 위)에 한 항목을 추가하고, 같은 커밋에 포함한다.

```
## YYYY-MM-DD HH:MM · 제목
- 요청: 사용자가 요청한 내용 (한 줄)
- 변경: 무엇을 바꿨는지
- 파일: 바꾼 파일
- 확인: 어떻게 검증했는지 (테스트 결과, 실제 수집 결과, 브라우저 확인)
- 백업: backup/YYYYMMDD-HHMM (수정 직전 상태 브랜치)
```

## 3. 검증 없이 올리지 않는다

- 올리기 전에 `python -m pytest -q` 를 통과시킨다. 웹 화면(docs/index.html)을 바꿨으면 스크립트 문법 검사와 브라우저 확인을 한다.
- 올린 뒤에는 Actions 실행 결과와 `docs/run-log.txt` 를 확인하고, 문제가 있으면 WORK.md 에 적고 고친다.

## 4. 그 밖의 원칙

- 요청받지 않은 구조 변경을 하지 않는다. 사용자가 되돌리라고 한 것은 되돌리고 기록한다.
- 실제 API 응답·데이터에 없는 필드나 값을 추측해서 만들지 않는다. 확인이 필요하면 실행 기록(`[응답 필드]`)으로 근거를 남긴다.
- 화면에 보이는 숫자에는 출처(청약홈 공고, 모집공고문, 국토부 실거래가, 법령·정책 자료, 이 서비스의 추정)를 함께 표시한다.
- 인증키는 GitHub Secrets(`DATA_GO_KR_KEY`)에만 둔다. 코드·기록·대화에 적지 않는다.
