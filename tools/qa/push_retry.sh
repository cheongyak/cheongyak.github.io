#!/usr/bin/env bash
# 커밋을 올린다. 그 사이 main 이 앞서 나가 거절되면 최신을 받아 다시 올린다 (최대 4번).
#
# 왜 (2026-10-22 LH 임대 수집 멈춤): 저장 단계가 `git push || (git pull --rebase … && git push)` 였는데,
# 검사 도구·지문 찍기(tools/qa/stamp.py)가 커밋하지 않는 파일까지 고쳐 두면 `git pull --rebase` 가
# '스테이징하지 않은 변경이 있어 받을 수 없음'(종료 코드 128)으로 멈췄다. LH 수집은 40분 가까이 걸려
# 그사이 main 이 거의 항상 앞서 나가므로 10-21·10-22 저장이 모두 실패했다 — 수집은 됐는데 올라가지 않음.
# 그래서 받기 전에 커밋하지 않은 변경을 치우고(stash, 다시 꺼내지 않음 — 이 실행에서 올릴 것은 이미 커밋됨),
# 받기가 실패하면 rebase 를 거두고 병합으로 받는다. 끝내 못 올리면 실패로 보이게 종료 코드 1.
# 쓰는 법: git diff --cached --quiet || { git commit -m "…" && bash tools/qa/push_retry.sh; }
set -u
for n in 1 2 3 4; do
  git push && exit 0
  git stash push -q --include-untracked -- docs evidence tools tests >/dev/null 2>&1 || true
  git checkout -q -- . 2>/dev/null || true
  git pull --rebase -X theirs origin main || { git rebase --abort 2>/dev/null; git pull --no-rebase -X theirs --no-edit origin main; }
  sleep $((n * 7))
done
echo "::error::저장소에 올리지 못했어요 (push 4번 실패) — 수집 결과가 반영되지 않았어요"
exit 1
