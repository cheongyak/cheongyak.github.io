#!/bin/bash
# 커밋 도우미 (CLAUDE.md 1~3·6항): 테스트 → WORK.md 맨 위에 기록 추가 → (새 기능이면) FEATURES.md 줄 추가 → 커밋 → 올리기 → FEATURES 커밋 번호 채우기
# 사용: bash tools/qa/ship.sh <스위치|-> '<FEATURES 줄 또는 빈칸>' <WORK 항목 파일> "<커밋 메시지>" <파일...>
#   - 백업 브랜치는 먼저 만든다: git fetch origin main && git push origin "origin/main:refs/heads/backup/$(TZ=Asia/Seoul date +%Y%m%d-%H%M)-이름"
#   - FEATURES 줄의 커밋 칸은 '(커밋 후 기입)' 으로 두면 올린 뒤 채운다 (그 변경은 따로 커밋해 올린다)
#   - 커밋 메시지 끝에 붙일 줄은 COMMIT_TRAILER 환경 변수로 줄 수 있다
set -e
cd "$(dirname "$0")/../.."
feat=$1; row=$2; wf=$3; msg=$4; shift 4
PY=$(command -v python || command -v python3)
LOG=$(mktemp)
if ! "$PY" -m pytest -q >"$LOG" 2>&1; then tail -20 "$LOG"; echo "테스트 실패 또는 pytest 없음 — 올리지 않음 (pip install -r requirements.txt)"; exit 1; fi
tail -1 "$LOG"
git checkout -q -- docs/chat-notice 2>/dev/null || true   # pytest 가 청약봇 공고 조각 파일을 다시 써서 pull 이 멈추던 것 (2026-10-02)
python3 - "$feat" "$row" "$wf" <<'PY'
import sys
feat, row, wf = sys.argv[1:4]
w = open('WORK.md', encoding='utf-8').read(); i = w.index('\n## ') + 1
open('WORK.md', 'w', encoding='utf-8').write(w[:i] + open(wf, encoding='utf-8').read().rstrip() + '\n\n' + w[i:])
if feat != '-' and row:
    lines = open('FEATURES.md', encoding='utf-8').read().split('\n')
    last = max(k for k, l in enumerate(lines) if l.startswith('| `'))
    lines.insert(last + 1, row); open('FEATURES.md', 'w', encoding='utf-8').write('\n'.join(lines))
PY
git add "$@" WORK.md FEATURES.md
git commit -qm "$msg${COMMIT_TRAILER:+

$COMMIT_TRAILER}"
if ! git pull -q --rebase origin main; then echo "받기(pull) 실패 — 커밋 안 한 변경을 정리한 뒤 git pull --rebase origin main && git push 로 올리세요 (FEATURES 번호도 그다음에)"; exit 1; fi
git push -q origin HEAD:main || { echo "올리기(push) 실패"; exit 1; }
c=$(git rev-parse --short HEAD)
python3 - "$feat" "$c" <<'PY'
import sys
feat, c = sys.argv[1:]
f = open('FEATURES.md', encoding='utf-8').read().split('\n')
for i, l in enumerate(f):
    if l.startswith(f'| `{feat}` |') and '(커밋 후 기입)' in l: f[i] = l.replace('(커밋 후 기입)', c)
open('FEATURES.md', 'w', encoding='utf-8').write('\n'.join(f))
PY
echo "$c $msg"
