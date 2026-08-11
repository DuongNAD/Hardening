#!/usr/bin/env bash
# CỔNG CHỐNG GIAN LẬN (Python). Agent KHÔNG được tự chứng nhận.
# Dùng: ./scripts/verify.sh ["<mutant id từ mutmut>"]
set -uo pipefail
set -e
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
# shellcheck disable=SC1091
source .hardening.env

TARGET="${1:-}"
GUARD="$HD_TEST/"
# pytest-randomly la thu tot nhung khong bat buoc. Thieu no ma van ep `-p randomly`
# thi cong se tu choi ca test hop le — false negative chan sach cong viec.
RAND=""
python3 -c "import pytest_randomly" 2>/dev/null && RAND="-p randomly"

reject() { printf 'TU CHOI: %s\n' "$*" >&2; exit 1; }

# --- Luật 1: chỉ được ghi trong tests/ ---
CHANGED=$( { git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u | grep -v '^$' || true)
# Artifact do chinh cong cu sinh ra — khong phai agent sua.
ART_RE='(^|/)(Cargo\.lock|target/|mutants\.out/|logs/|__pycache__/|\.pytest_cache/|\.hypothesis/|\.mutmut-cache|baseline-.*\.txt|dataflow-truth\..*)'
BAD=$(echo "$CHANGED" | grep -v "^${GUARD}" | grep -v '^FINDINGS.md$' | grep -vE "$ART_RE" | grep -v '^$' || true)
# Bộ khung tự nó chưa commit thì lỗi là của người cài, không phải của agent.
KIT_RE='^(justfile|AGENTS\.md|FINDINGS\.md|\.hardening\.env|scripts/|\.agents/skills|\.claude/skills|.*/\.cargo/mutants\.toml)'
NONKIT=$(echo "$BAD" | grep -vE "$KIT_RE" | grep -v '^$' || true)
if [ -n "$BAD" ] && [ -z "$NONKIT" ]; then
  reject "bo khung hardening chua duoc commit. Chay:
  git add justfile AGENTS.md FINDINGS.md .hardening.env scripts .agents/skills && git commit -m 'chore: cai hardening kit'"
fi
[ -n "$NONKIT" ] && reject "sua file ngoai ${GUARD} va FINDINGS.md:
$NONKIT"

# --- Diff PHAI gom ca file untracked. Khong co dong nay thi agent chi can tao
#     file test MOI la lach sach luat 2..5. Day la lo thung lon nhat cua cong. ---
git add --intent-to-add -- "$GUARD" >/dev/null 2>&1 || true
DIFF=$(git diff HEAD -- "$GUARD" || true)
ADDED=$(echo "$DIFF"   | grep '^+' | grep -v '^+++' || true)
REMOVED=$(echo "$DIFF" | grep '^-' | grep -v '^---' || true)

# --- Luật 2: không được vô hiệu hoá test ---
echo "$ADDED" | grep -qE '@pytest\.mark\.(skip|xfail)' && reject "them skip/xfail"

# --- Luật 3: không được xoá assertion ---
echo "$REMOVED" | grep -qE '(^|[[:space:];])assert[[:space:]]' && reject "xoa hoac sua dong co assertion san co"

# --- Luật 4: test phải tất định ---
echo "$ADDED" | grep -qE '(random\.(random|randint|choice|shuffle)|np\.random\.(rand|randn|randint)|time\.time\(\)|datetime\.now\(\))' \
  && reject "test dung RNG/dong ho phi tat dinh"

# --- Luật 5: không chấp nhận assert rỗng nghĩa ---
N_ANY=$(echo "$ADDED"    | grep -cE 'assert[[:space:]]' || true)
N_STRONG=$(echo "$ADDED" | grep -cE 'assert[[:space:]][^#]*(==|!=|<|>| in | is False| is True|pytest\.approx|pytest\.raises)' || true)
if [ "$N_ANY" -gt 0 ] && [ "$N_STRONG" -eq 0 ]; then
  reject "chi co assertion rong nghia (truthy/not-None) — khong quan sat duoc hanh vi"
fi

# --- Luat 6: co mutant ma khong them assertion nao thi khong the coi la xong ---
if [ -n "$TARGET" ] && [ "$N_ANY" -eq 0 ]; then
  reject "khong them assertion nao — task chua duoc lam"
fi

# --- Luật 7: ổn định 3 lần, đảo thứ tự ---
for i in 1 2 3; do
  python3 -m pytest -q $RAND "$HD_TEST" >/dev/null 2>&1 || reject "test khong on dinh o lan $i"
done

# --- Luật 8: mutant phải chết ---
# mutmut 3.x: lenh `result-ids` da bi bo. Dung `results` roi loc ': survived'.
if [ -n "$TARGET" ]; then
  # B1 — chay rieng mutant do. PHAI chay TRUOC moi phep kiem: chinh `run` la
  # thu sinh ra catalog trong thu muc mutants/, va `show` doc tu catalog do.
  # `|| true` BAT BUOC: script chay voi `set -e` + `pipefail`, nen mutmut tra ma
  # loi se giet script NGAY TAI DAY, truoc khi toi duoc cau tu choi co giai thich.
  # Nguoi dung chi thay exit 1 cam lang, khong biet vi sao.
  mutmut run "$TARGET" 2>&1 | tail -2 || true

  # B2 — mutant PHAI ton tai. Khong kiem thi go sai ten se cho qua mien phi,
  # dung lo FALSE PASS nhu ban Rust. `mutmut show` nem FileNotFoundError khi ten
  # khong co trong catalog.
  mutmut show "$TARGET" >/dev/null 2>&1 \
    || reject "KHONG tim thay mutant '$TARGET'. Dan lai NGUYEN dong tu 'just list-missed'. Cong khong the ket luan gi."

  # B3 — `mutmut results` CHI liet ke mutant con SONG; mutant chet khong xuat
  # hien. Nen phep kiem la: khong duoc co mat trong danh sach survived.
  mutmut results 2>/dev/null | grep -F "$TARGET" | grep -q ': survived' \
    && reject "mutant van song sau khi them test"
fi

echo "QUA CONG"
