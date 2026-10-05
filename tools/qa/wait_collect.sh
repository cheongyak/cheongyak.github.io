#!/bin/bash
# 수집(collect.yml)이 돌거나 대기 중이면 끝날 때까지 기다린다 (최대 N분, 기본 45). 2026-10-03:
# 판정 검증·공고문 재시도를 수집과 같은 concurrency 묶음에 두면, 대기 중인 수집이 뒤에 온 실행에 밀려 취소된다
# (GitHub 은 한 묶음에 대기 실행을 하나만 둔다 — 1bf91b2·d6aaa8d 수집 취소). 그래서 묶음을 나누고 이 스크립트로 차례를 지킨다.
# 사용(Actions): GH_TOKEN=${{ github.token }} bash tools/qa/wait_collect.sh [분] [lh]  — 권한 actions: read 필요
#   두 번째 인자 lh: LH 임대 수집(lh-rental.yml)도 기다린다 — 판정 검증만 쓴다(2026-10-05 판정 검증이 LH 수집 전 옛 데이터로 lh_invariants 를 돌려 실패).
#   LH 수집 자신은 이 인자 없이 부른다(자기를 기다리면 끝나지 않음).
max=${1:-45}
repo=${GITHUB_REPOSITORY:-cheongyak/cheongyak.github.io}
wfs="collect.yml"; [ "${2:-}" = "lh" ] && wfs="collect.yml lh-rental.yml"
for i in $(seq 1 "$max"); do
  n=0
  for wf in $wfs; do
    k=$(gh api "repos/$repo/actions/workflows/$wf/runs?per_page=5" --jq '[.workflow_runs[] | select(.status=="in_progress" or .status=="queued" or .status=="pending" or .status=="waiting" or .status=="requested")] | length' 2>/dev/null || echo 0)
    n=$((n + k))
  done
  [ "$n" = "0" ] && { echo "수집 실행 없음 — 시작"; exit 0; }
  echo "수집 실행 중 ($n) — 1분 뒤 다시 확인 ($i/$max)"; sleep 60
done
echo "수집이 ${max}분 넘게 이어져 건너뜀"; exit 1
