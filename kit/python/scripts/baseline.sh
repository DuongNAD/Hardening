#!/usr/bin/env bash
set -uo pipefail
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
# shellcheck disable=SC1091
source .hardening.env
n() { awk -F: '{s+=$2} END{print s+0}'; }

echo "# baseline $(date -u +%FT%TZ)  commit=$(git rev-parse --short HEAD)  modules=$HD_MODULES"
echo -n "src_loc: ";       find "$HD_SRC" -name '*.py' | xargs cat 2>/dev/null | wc -l | tr -d ' '
echo -n "test_loc: ";      find "$HD_TEST" -name '*.py' 2>/dev/null | xargs cat 2>/dev/null | wc -l | tr -d ' '
echo -n "test_count: ";    grep -rhoE '^\s*def test_' "$HD_TEST" 2>/dev/null | wc -l | tr -d ' '
echo -n "skipped_tests: "; grep -rhoE '@pytest\.mark\.(skip|xfail)' "$HD_TEST" 2>/dev/null | wc -l | tr -d ' '
echo -n "unseeded_rng: ";  grep -rcE 'random\.(random|randint|choice|shuffle)|np\.random\.' "$HD_SRC" --include='*.py' 2>/dev/null | n
echo -n "wallclock: ";     grep -rcE 'time\.time\(\)|datetime\.now\(\)' "$HD_SRC" --include='*.py' 2>/dev/null | n
echo -n "coverage: ";      python3 -m pytest --cov="$HD_SRC" --cov-report=term -q "$HD_TEST" 2>/dev/null | awk '/^TOTAL/{print $NF; f=1} END{if(!f)print "n/a"}'
echo -n "importlinter: ";  python3 -m importlinter.cli lint >/dev/null 2>&1 && echo PASS || echo FAIL
echo -n "findings_bug: ";  grep -c "^- \*\*Loại:\*\* BUG$" FINDINGS.md 2>/dev/null || echo 0
