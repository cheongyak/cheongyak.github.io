#!/bin/bash
# 버전 브랜치 남기기 (CLAUDE.md 9항): 지금 원격 main 을 release/v<버전> 으로 올린다.
# 사용: bash tools/qa/release.sh 1.1.0
#   - 먼저 그 버전의 변경을 ship.sh 로 올리고(changelog.json·VERSIONS.md 에 버전 기록 포함), 그다음 실행한다.
set -e
cd "$(dirname "$0")/../.."
v=${1:?버전을 적어 주세요 (예: 1.1.0)}
grep -q "| v$v |" VERSIONS.md || { echo "VERSIONS.md 에 v$v 줄이 없어요. 먼저 기록하세요."; exit 1; }
python3 -c "import json,sys; c=json.load(open('docs/changelog.json')); sys.exit(0 if any(e.get('version')=='$v' for e in c) else 1)" || { echo "docs/changelog.json 에 v$v 항목이 없어요."; exit 1; }
git fetch -q origin main
git merge-base --is-ancestor HEAD origin/main || { echo "지금 커밋이 아직 원격 main 에 없어요 (올리기 실패?). 먼저 올린 뒤 실행하세요."; exit 1; }
if git ls-remote --exit-code origin "refs/heads/release/v$v" >/dev/null 2>&1; then echo "release/v$v 가 이미 있어요 (덮어쓰지 않음)"; exit 1; fi
git push -q origin "origin/main:refs/heads/release/v$v"
echo "release/v$v -> $(git rev-parse --short origin/main)"
