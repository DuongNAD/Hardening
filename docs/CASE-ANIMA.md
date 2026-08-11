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

## Còn nợ

| | |
|---|---|
| F-002 | 23 chỗ `World::new()` tự lắp resource riêng; thêm resource nào cũng panic **lúc chạy**, không phải lúc build. Cần một `test_world()` dùng chung. |
| vòng lặp agent | **chưa agent nào đi trọn một lượt giết mutant.** Đây là thứ cả bộ khung tồn tại để làm. |
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
