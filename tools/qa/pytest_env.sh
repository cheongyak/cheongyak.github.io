#!/bin/bash
# PyPI(pip)가 막힌 작업 환경에서 python -m pytest 를 돌릴 준비 (2026-11-05)
# 밤 자동 개선 첫 실행이 'httpx 없음'으로 전체 시험을 못 돌려 PR 을 못 만들었다 — pip 대신 GitHub 에서 받는다.
# 사용: bash tools/qa/pytest_env.sh   → 마지막 줄에 나온 PYTHONPATH 를 pytest 명령 앞에 붙인다
#       예) PYTHONPATH=.:/tmp/cy-pytest-env/site python3 -m pytest -q
# 이미 다 있으면 아무것도 받지 않는다. 저장소 폴더 통째(예: httpx/)를 PYTHONPATH 에 넣으면 그 안의 tests 패키지가
# 우리 tests 를 가리므로(No module named tests.test_…) 패키지 폴더만 site/ 에 링크한다.
set -e
D=${PYTEST_ENV_DIR:-/tmp/cy-pytest-env}
missing=$(python3 - <<'PY'
import importlib
need = ["pytest", "pluggy", "iniconfig", "httpx", "httpcore", "fastapi", "starlette"]
miss = []
for m in need:
    try:
        importlib.import_module(m)
    except Exception:
        miss.append(m)
print(" ".join(miss))
PY
)
if [ -z "$missing" ]; then echo "pytest 준비됨(설치돼 있음)"; echo "PYTHONPATH=."; exit 0; fi
mkdir -p "$D/src" "$D/site"
get() {  # 이름 주소 태그
  [ -d "$D/src/$1" ] || git -c advice.detachedHead=false clone -q --depth 1 --branch "$3" "$2" "$D/src/$1"
}
get pytest    https://github.com/pytest-dev/pytest   8.3.5
get pluggy    https://github.com/pytest-dev/pluggy   1.5.0
get iniconfig https://github.com/pytest-dev/iniconfig v2.0.0
get httpx     https://github.com/encode/httpx        0.28.1
get httpcore  https://github.com/encode/httpcore     1.0.9
get fastapi   https://github.com/fastapi/fastapi     0.115.6
get starlette https://github.com/encode/starlette    0.41.3
# setuptools_scm 이 만드는 버전 파일 (git 에는 없음)
for f in "pytest/src/_pytest/_version.py:8.3.5:8,3,5" "pluggy/src/pluggy/_version.py:1.5.0:1,5,0" "iniconfig/src/iniconfig/_version.py:2.0.0:2,0,0"; do
  p=${f%%:*}; rest=${f#*:}; v=${rest%%:*}; t=${rest#*:}
  [ -e "$D/src/$p" ] || printf "__version__ = version = '%s'\nversion_tuple = (%s)\n" "$v" "$t" > "$D/src/$p"
done
for p in pytest/src/pytest pytest/src/_pytest pytest/src/py.py pluggy/src/pluggy iniconfig/src/iniconfig httpx/httpx httpcore/httpcore fastapi/fastapi starlette/starlette; do
  [ -e "$D/src/$p" ] && ln -sfn "$D/src/$p" "$D/site/"
done
PYTHONPATH=".:$D/site" python3 -c "import pytest, httpx, fastapi; print('pytest', pytest.__version__, '· httpx', httpx.__version__, '· fastapi', fastapi.__version__)"
echo "PYTHONPATH=.:$D/site"
