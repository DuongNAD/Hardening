#!/usr/bin/env bash
set -uo pipefail
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
# shellcheck disable=SC1091
source .hardening.env
python3 -m pytest -q "$HD_TEST" >/dev/null 2>&1 || { echo "TU CHOI: test do sau khi toi uu"; exit 1; }
OUT=$(python3 -m pytest "$HD_TEST" --benchmark-only --benchmark-compare=base --benchmark-compare-fail=mean:5% 2>&1)
echo "$OUT" | tail -20
if echo "$OUT" | grep -qiE 'FAILED|regress'; then
  echo "TU CHOI: khong dat nguong -> revert"
  git checkout -- "$HD_SRC"; exit 1
fi
echo "QUA CONG"
