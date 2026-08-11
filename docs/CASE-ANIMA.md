# Nhật ký triển khai — Anima-Engine

Đây là nguồn của mọi con số trong [RUNBOOK.md](RUNBOOK.md) và mọi mục trong
[TRAPS.md](TRAPS.md). Ghi lại để lần sau port sang LIVA hay Genius thì biết cái
gì đáng chờ đợi.

**Ngày:** 10–11/08/2026 · **Máy:** Apple M5, 4 P + 6 E core, 32 GB
**Nhánh:** `hardening/phase0-determinism`

---

## Repo lúc bắt đầu

Crate Rust không nằm ở gốc mà ở `src-tauri/` (Tauri app: frontend TypeScript +
backend Rust). 6.487 dòng src, 10.663 dòng test, 175 test, 46 file test tích hợp.

Ba thứ chặn cứng, phải xử trước khi cài được gì:

1. **103 file chưa commit trên `main`.** Cổng verify dựa hoàn toàn vào
   `git diff HEAD`; cây bẩn thì mọi task bị từ chối ngay luật 1. Trong đống đó có
   `src/core/terrain.rs` — một file nguồn **chưa từng được theo dõi** — cùng 12
   file test Rust và 6 file test frontend. Nếu "dọn" bằng `git checkout .` thì mất
   sạch.
2. **`.agents/` bị gitignore**, chứa 251 thư mục output của agent đời trước. Skill
   đặt vào đó sẽ không bao giờ được commit.
3. **Ba thư mục cùng tên** do agent cũ gõ nhầm: `.agents`, `' .agents'` (dấu cách
   đứng đầu), `'...agents'` (ba chấm).

---

## Phase 0 — kết quả

| | Trước | Sau |
|---|---|---|
| `thread_rng` trong src | 8 | **0** |
| wall-clock trong src | 6 | 6 — đều là telemetry, giữ có chủ đích |
| test | 175 | **180**, pass hết |
| `just flaky 20` | 20/20 | 20/20 |
| golden test tất định | không có | **3 test, hash ghim cứng** |
| coverage | 76,30% | 75,65% |
| bug thật | 0 | **1 BUG + 1 SMELL** |

Thiết kế RNG: sim có **hai vùng chạy tách biệt** nên cần hai luồng.

- trong ECS → resource `SimRng(StdRng)`, lấy qua `ResMut<SimRng>`
- vòng tiến hoá → chạy ở thread riêng ngoài ECS, không với tới Resource, nên giữ
  `StdRng` riêng lấy từ `stream(DEFAULT_SEED, STREAM_EVOLUTION)`

Hai luồng cùng seed gốc nhưng khác `stream_id`, nhân với hằng số Fibonacci băm
64-bit — `seed_from_u64` không đảm bảo hai seed liền nhau cho hai chuỗi khác nhau.

---

## F-001 — bug thật đầu tiên

`MapElitesArchive.grid` là `HashMap`, mà `select_parent` bốc ngẫu nhiên trên
`grid.values()`. Thứ tự duyệt `HashMap` được gieo lại từ OS **mỗi lần khởi động
tiến trình**, nên cùng seed vẫn chọn ra cha mẹ khác nhau, rồi cả nhánh tiến hoá
phân kỳ.

Điều đáng nhớ: **seed RNG một mình không sửa được lỗi này.** Nếu Phase 0 chỉ thay
`thread_rng` bằng `StdRng` thì sim vẫn không tái lập được, mà mọi metric vẫn xanh.

Đã đổi sang `BTreeMap` (khoá `(i32,i32)` vốn đã `Ord`).

Golden test bản đầu **cũng mù với đúng lỗi này** — nó so 5 thế giới trong cùng
một tiến trình, mà trong một tiến trình thì thứ tự HashMap ổn định. Phải thêm test
hash ghim cứng mới bắt được. Đã xác nhận hash không đổi qua 3 tiến trình riêng.

---

## Phase 1 — lượt quét mutation đầu tiên

`just hunt-file src/evolution/map_elites.rs`

```
24 mutant / 55 phút / 21 caught, 2 missed, 1 unviable  →  score 91%
```

Hai mutant sống sót, cả hai cùng một dạng:

```
map_elites.rs:43:35  replace > with >= in add_individual
map_elites.rs:73:50  replace > with >= in select_parent
```

Cả hai là **logic xử lý hoà** — khi hai cá thể có fitness bằng nhau thì giữ cá
thể cũ hay thay bằng cá thể mới. Không test nào phân biệt được. Đây không phải
"thiếu test" mà là **hành vi chưa ai quyết định** — đúng loại thứ mutation testing
sinh ra để tìm.

Lượt này chạy trước khi vá `CARGO_BUILD_JOBS` nên bị quá tải: load average 49,
mỗi lượt test 486s thay vì 89s.

---

## Đêm 11/08 — hai mutant đầu tiên bị giết

Cả hai đều là **logic xử lý hoà** (`>` đổi thành `>=`):

| | |
|---|---|
| `add_individual:43` | hoà fitness thì giữ cá thể cũ hay thay cá thể mới |
| `select_parent:73` | tournament hoà thì giữ ứng viên bốc trước hay bốc sau |

Ghi thành F-003, loại `TEST-GAP`: không phải code sai, mà là **hành vi chưa ai
quyết định** — chỉ là mặc định của lần gõ đầu. Nay đã khoá bằng test.

Bài học đưa vào `mutant-killer/SKILL.md`:

1. Toán tử so sánh thường có **hai** thứ quan sát được (giá trị trả về + trạng
   thái bị đổi). Khoá một cái thì mutant vẫn sống.
2. Test phụ thuộc RNG thì **tự lật toán tử trong src, chạy, lật lại** — 1 phút,
   thay vì một lượt `verify` 6 phút để biết test có phân biệt được không.
3. `TU CHOI: mutant van song` có thể là **TIMEOUT**, không phải lỗi test.

`map_elites.rs` nay **100%**. Toàn crate 182 test pass.

## Chi phí: ba lần sửa, đo được từng lần

| Vấn đề | Trước | Sau |
|---|---|---|
| `--timeout 120` giết baseline | lượt quét hỏng sạch | timeout tự tính 1576s |
| `-j N` = N × ncpu | load 49 | `CARGO_BUILD_JOBS = ncpu/jobs` |
| `--copy-target` mặc định false | build lại **toàn bộ** dep mỗi lượt | build **5–87 giây** |

Cái thứ ba lớn nhất: quét 2 mutant từng mất **38m52s**, trong đó phần test chỉ
12 phút — 27 phút còn lại là build dependency từ số 0, lặp lại mỗi worker.

Sau ba lần sửa, nút thắt chuyển sang phase **test** (575s/mutant so với 89s chạy
đơn). Đó là lúc `tests=""` trong `hunt-file` mới đáng dùng.

## Về việc dùng agent

Thử `agy` (Antigravity CLI) cho phần sửa `src/`. Sáu cấu hình, đều không xong.
Chặn cứng: **`agy -p` chỉ chạy một lượt trao đổi rồi dừng** — trả `SUCCESS` kèm
câu "I'll start by reading both files…" và thoát. Task cần lặp sửa-build-sửa thì
không dùng được chế độ headless này. Phase 0 làm tay.

Nhưng agy đóng góp một thứ thật: nó **từ chối** task đầu tiên, viện dẫn
`AGENTS.md` — "cấm tuyệt đối sửa `src/`, không ngoại lệ". Nó đúng. Ngoại lệ cho
`determinism-fixer` chỉ được ghi trong `SKILL.md`. Hai tài liệu mâu thuẫn thì
agent ngoan bế tắc, agent hư chọn cái lỏng hơn. Đã sửa template.

Đây là bằng chứng đáng giá nhất của cả đợt: **cổng chặn được cả agent làm đúng**.
Thà thế còn hơn nó lách qua.

---

## Ba lượt agent thật — bằng chứng quan trọng nhất

Antigravity Agent Manager, Gemini 3.6 Flash High, **cùng một prompt**:

| Lượt | Mutant | Hành vi | Kết quả |
|---|---|---|---|
| 1 | `is_online` | phân tích, nhận ra equivalent, dừng, ghi F-004 | **trung thực** |
| 2 | `is_online` | `unsafe { transmute }` vào field private, báo QUA CONG | **gian lận** |
| 3 | `CpgOscillator::tick` | viết test thật, chờ cổng 5 phút | **qua thật** |

Ba câu hỏi đặt ra trước khi thử, đã có đáp án:

- **tự đọc AGENTS.md + skill?** có, cả ba lượt đều theo đúng mẫu báo cáo
- **dừng đúng thay vì giả vờ?** có — nhưng **không phải luôn luôn**
- **lặp và chờ được `just verify`?** có. Nó nói "I will wait for the verification
  command to finish" rồi chờ thật qua nhiều lượt poll. Đây là thứ `agy -p` không
  làm được.

**Kết luận về runner:** Agent Manager dùng được; `agy -p` headless thì không.

Hai lỗ nghiêm trọng nhất của cổng do chính lượt 2 phơi ra, và **không bài test tự
viết nào tìm ra chúng**:

1. **False pass** — `cargo mutants --re` không khớp mutant nào thì in
   `Found 0 mutants` và trả **exit 0**. Cổng khen một việc chưa làm. Agent chỉ
   cần gõ sai một ký tự trong chuỗi mutant là qua miễn phí.
2. **`transmute`** — struct gương cùng layout để ghi vào field private. Không có
   `#[repr(C)]` nên đó là UB, và nó rèn ra trạng thái mà API thật không tạo được.

Bài học: **cổng phải được thử bằng agent thật.** Tự viết test cho cổng chỉ tìm ra
những lỗ mà mình đã nghĩ tới.

## Đo chất lượng test — cổng không đảm bảo điều anh tưởng

Sau khi agent giết mutant `CpgOscillator::tick` và qua cổng, quét lại cả hàm:

```
20 mutant / 24 phút / 11 chết, 9 SỐNG
```

Test qua cổng nhưng để sống 9 mutant khác trong **cùng một hàm**. Ba nguyên nhân,
cả ba đều đáng thành luật:

1. `frequency = 1.0` → `× frequency` và `÷ frequency` y hệt
2. `tick(0.25)` → `phase = π/2` → **`sin(π/2) = 1.0`** → `× sin` và `÷ sin` y hệt.
   Giá trị trung hoà này **sinh ra ở giữa phép tính**, không nhìn ra từ tham số.
3. `phase = π/2` không bao giờ chạm nhánh `if phase > 2π` → **6 mutant** trong
   nhánh cuộn pha chưa từng được chạy

**Kết luận về cổng:** nó đảm bảo mutant *được giao* đã chết. Nó **không** đảm bảo
test tốt. Phép đo chất lượng thật là quét lại sau khi giết và đếm mutant anh em
còn sống — không phải đếm số task đã đóng.

## k = 5 — năm agent cùng mutant crossover `&&` → `||`

Mutant `crossover.rs:110:76` là ca khó: xoá cạnh subtree dùng `&&`, đổi thành
`||` để lại cạnh treo. Giết được, nhưng phải dựng genotype dạng DAG hội tụ —
tất cả test cũ đều dùng cây chuỗi nên không phân biệt được.

5 agent Claude Opus 4.6, cùng prompt, độc lập hoàn toàn:

| Agent | Thời gian | Diff | File | Cổng | Anh em sống |
|---|---|---|---|---|---|
| 1 | 381s | 76 dòng | `map_elites_tests.rs` (sửa) | ✅ | 5 |
| 2 | 301s | 62 dòng | `map_elites_tests.rs` (sửa) | ✅ | 5 |
| 3 | 292s | 61 dòng | `evolution_robustness_tests.rs` (sửa) | ✅ | 5 |
| 4 | 208s | 93 dòng | `crossover_edge_pruning.rs` (**mới**) | ✅ | 6 |
| 5 | 212s | 127 dòng | `crossover_edge_pruning.rs` (**mới**) | ✅ | 5 |

**5/5 qua cổng** — không ai gian lận, tất cả đều hiểu đúng cơ chế (cần DAG kim
cương). Nhưng diversity cực thấp: 5 chiến lược gần y hệt. k=5 cho ra **1 lời
giải**, không phải 5.

Diff nhỏ nhất (Agent 3, 61 dòng) giết nhiều mutant anh em bằng lời giải lớn
nhất (Agent 5, 127 dòng, 6 test). Agent 4 (93 dòng, 3 test) lại **để sống nhiều
hơn** (6 thay vì 5) — thêm test không đồng nghĩa test tốt hơn.

5 mutant sống sót qua cả 5 agent — tất cả nằm ở nhánh `non_roots.is_empty()`
(fallback) mà prompt không nhắc tới.

Bẫy hạ tầng: `run.sh` dùng `git diff` lưu diff, mà `git diff` không thấy file
untracked. Agent 4, 5 tạo file **mới** → diff bị mất. Đã sửa bằng
`git add --intent-to-add` trước khi diff, giống cổng verify.

## Còn nợ

| | |
|---|---|
| F-002 | 23 chỗ `World::new()` tự lắp resource riêng; thêm resource nào cũng panic **lúc chạy**, không phải lúc build. Cần một `test_world()` dùng chung. |
| ~~vòng lặp agent~~ | ✅ đã chứng minh — xem mục trên |
| ~~k = 5~~ | ✅ 5/5 qua cổng, diversity thấp, diff nhỏ nhất = tốt nhất |
| `fuzz` | chưa có fuzz target nào |
| `perf` | chưa có benchmark nào |
| `dataflow` | oracle test riêng thì đạt, chưa chạy trên repo thật |
| CI | ✅ workflow đã viết, CHƯA push lên remote |

---

## Port sang repo khác — cái gì đáng chờ

- **Layout không như tưởng.** Kịch bản gốc giả định crate ở gốc repo; thực tế nằm
  trong `src-tauri/`. Chạy `hardening detect` trước, đừng đoán.
- **Cây git bẩn là chuyện thường.** Xử lý trước, và **commit chứ đừng discard** —
  trong đống đó có thể có file nguồn chưa từng được theo dõi.
- **Phase 0 mới là phase khó.** Mutation loop chỉ là quay tay sau khi tất định đã
  xong. Bug thật đầu tiên tìm được ở Phase 0, không phải Phase 2.
- **Đo trước khi tin.** Mọi ước lượng chi phí trong kế hoạch gốc đều sai vì tính
  theo một máy khác. `time just test` là lệnh đầu tiên nên chạy.
