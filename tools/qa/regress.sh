#!/bin/bash
# 작업 중 docs 를 origin/main 과 비교하는 화면 회귀 검사 (tools/qa/regress.cjs). 공고 데이터는 같은 것(작업 중 docs/listings.json)으로 맞춘다.
# 사용: bash tools/qa/regress.sh
set -e
cd "$(dirname "$0")/../.."
git fetch -q origin main
OLD=$(mktemp -d)
git archive origin/main docs | tar -x -C "$OLD" --strip-components=1
cp docs/listings.json "$OLD/"
node tools/qa/regress.cjs "$OLD" docs
rm -rf "$OLD"
