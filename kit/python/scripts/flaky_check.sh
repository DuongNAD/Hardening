#!/usr/bin/env bash
# Cổng ra Phase 0. Chạy với pytest-randomly để bắt cả phụ thuộc thứ tự test.
set -uo pipefail
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
# shellcheck disable=SC1091
source .hardening.env
N="${1:-20}"; mkdir -p logs
# pytest-randomly la thu tot nhung khong bat buoc. Thieu no ma van ep `-p randomly`
# thi cong se tu choi ca test hop le — false negative chan sach cong viec.
RAND=""
python3 -c "import pytest_randomly" 2>/dev/null && RAND="-p randomly"

fail=0
for i in $(seq 1 "$N"); do
  if python3 -m pytest -q $RAND "$HD_TEST" >"logs/flaky-$i.log" 2>&1; then
    printf '  %2d/%s ok\n' "$i" "$N"
  else
    fail=$((fail+1)); printf '  %2d/%s FLAKY -> logs/flaky-%d.log\n' "$i" "$N" "$i"
    grep -E '^(FAILED|E  )' "logs/flaky-$i.log" | sort -u | head -5 | sed 's/^/      /'
  fi
done
echo "ket qua: $((N-fail))/$N pass"
[ "$fail" -eq 0 ] || exit 1
