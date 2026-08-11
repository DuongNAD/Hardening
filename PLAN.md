# Kế hoạch triển khai — Hardening Kit trên Antigravity

> **Cập nhật 11/08/2026 — kế hoạch này đã chạy thật, không còn là dự định.**
> Kết quả và mọi số đo nằm ở [docs/CASE-ANIMA.md](docs/CASE-ANIMA.md).
> Vận hành hằng ngày: [docs/RUNBOOK.md](docs/RUNBOOK.md).
> Gặp trục trặc: [docs/TRAPS.md](docs/TRAPS.md) — tra theo triệu chứng.
>
> | Phase | Trạng thái |
> |---|---|
> | −1 dọn đường | ✅ 103 file dở dang đã commit, `.gitignore` đã sửa |
> | 0 determinism | ✅ 0 `thread_rng`, golden hash ghim cứng, flaky 20/20 |
> | 1 bật mutation | ✅ `map_elites.rs` **100%** |
> | 2 vòng lặp agent | ✅ Agent Manager đi trọn vòng và qua cổng thật |
> | 3 fuzz + miri | ✅ sau khi tách `anima-core` — trước đó **cả hai đều bị chặn** |
> | 4 dataflow | ✅ tìm ra 3 cặp phụ thuộc vòng |
> | 5 perf | ✅ cổng tự revert khi tối ưu không thắng |
> | k = 5 | ✅ 5/5 qua cổng, diversity thấp — diff nhỏ nhất = tốt nhất |
>
> **Bốn chỗ kế hoạch gốc sai, đã sửa theo số đo thật:**
>
> 1. `k = 5` shard song song trên một máy → **tệ hơn** chạy tuần tự
> 2. chi phí sweep tính theo i5-14600KF → máy thật là M5, và `--copy-target`
>    mới là biến quyết định, không phải số core
> 3. Miri "đáng giá nếu có unsafe quanh wgpu" → Miri **không chạy được** trên
>    crate dính FFI; phải tách crate thuần trước
> 4. ngưỡng "hạ tầng ≤ 200 dòng" → tính cho kit 3 module; 5 module là 273 dòng,
>    và câu hỏi đúng không phải con số mà là *mỗi dòng có chỉ ra được lần hỏng nào*

Bản này giả định base đã dựng xong (nó đã xong: xem [README.md](README.md)).
Phần còn lại là **chạy**, và chạy đúng thứ tự.

Ba model dùng trong Antigravity, và **luật định tuyến**:

| Model | Dùng cho | Không dùng cho |
|---|---|---|
| **Gemini 3.6 Flash** (effort High) | ~85% khối lượng: viết test giết mutant, triage crash, xuất artifact | quyết định kiến trúc |
| **Gemini 3.6 Flash** (effort Low) | task máy móc: liệt kê, format, đọc log, gom báo cáo | bất cứ gì có debug |
| **Gemini 3.1 Pro** | planner đầu phase, trọng tài khi k=5 cho nhiều kết quả, nén repo → artifact 2 trang | grunt work (đắt ~8× mà không hơn) |
| **Claude Opus 4.6** | Phase 0 (sửa `src/`, cần phán đoán), viết/sửa skill, phán quyết đánh đổi | vòng lặp mutant — phí |

Luật vàng: **cái gì có exit code thì giao Flash. Cái gì không có exit code thì
đừng giao agent.**

---

## Phase −1 — Dọn đường (tay, ~20 phút)

Ba thứ chặn cứng, phải xong trước khi cài:

**1. Cây git đang bẩn.** Anima-Engine đang có 103 file thay đổi trên `main`.
Cổng verify dựa hoàn toàn vào `git diff HEAD` — cây bẩn thì mọi task đều bị từ
chối ngay luật 1.

```bash
cd ~/Documents/project/Anima-Engine && git status --porcelain | wc -l
```

Commit hoặc stash cho sạch, rồi tạo nhánh làm việc:

```bash
git checkout -b hardening/phase0-determinism
```

**2. `.agents/` đang bị gitignore** và chứa 251 thư mục agent-output cũ. Skill
đặt vào đó sẽ không được commit. Sửa `.gitignore`:

```
.agents/*
!.agents/skills/
```

**3. Công cụ.** `just` và `cargo-mutants` đã cài. Còn thiếu:

```bash
cargo install cargo-llvm-cov cargo-fuzz cargo-modules cargo-audit critcmp && rustup toolchain install nightly
```

Kiểm lại: `./hardening doctor ~/Documents/project/Anima-Engine`

---

## Phase 0 — Determinism (Ngày 1, **làm tay, không giao agent**)

Đây là phase quan trọng nhất và là phase duy nhất không tự động hoá được, vì thả
`cargo-mutants` vào một test suite flaky sẽ trộn "missed" với "nhiễu" — anh sẽ
mất vài ngày mới nhận ra pipeline đang sinh task rác.

> **Đã làm xong ngày 10/08/2026.** Phase −1 và mục 0.1 dưới đây đã chạy: cây git
> đã sạch (nhánh `hardening/phase0-determinism`), kit đã cài và commit, baseline
> đã chốt. Phần còn lại của Phase 0 — mục 0.3 và 0.4 — vẫn là việc phải làm.

### 0.1 Cài kit + chốt baseline

```bash
cd ~/Documents/project/Hardening && ./hardening init ~/Documents/project/Anima-Engine --modules determinism
```

```bash
cd ~/Documents/project/Anima-Engine && git add justfile AGENTS.md FINDINGS.md .hardening.env scripts .agents/skills && git commit -m "chore: cai hardening kit"
```

```bash
just baseline
```

Điền cột Baseline vào bảng dưới **trước khi làm gì tiếp**. Số hiện đã biết từ
khảo sát ngày 10/08:

Baseline đã đo thật ngày 10/08/2026 (`baseline-2026-08-10.txt`, commit `00e96a5`):

| Metric | Baseline | Target T+30d |
|---|---|---|
| src LOC / test LOC | **6.487 / 10.663** | — |
| test (tất cả pass) | **175** | không giảm |
| `#[ignore]` | **0** | 0 |
| line coverage | **76,30%** | ≥ 80% (đã vượt mốc 70%) |
| `thread_rng` trong src | **8** | 0 |
| wall-clock trong src | **6** | 0 trong đường sim |
| `unsafe` | **2** (`unsafe impl Send/Sync for BrainModel`) | không tăng |
| `HashMap`/`HashSet` | **35** chỗ | chỗ nào ảnh hưởng state → đổi sang có thứ tự |
| clippy pedantic | **898** warning | ≤ 450 |
| **mutant** | **2.002** | score ≥ 80% |
| 1 lần `cargo test --release` | **88 giây** | — |
| flaky (20 lần) | đang đo | 20/20 |
| **bug thật trong FINDINGS.md** | **0** | **> 5** |

Dòng cuối là dòng duy nhất thật sự quan trọng. Các dòng trên là proxy.

### 0.2 Kiểm flaky trước khi sửa gì

```bash
just flaky 20
```

Không đạt 20/20 → đọc `logs/flaky-*.log`, đó chính là danh sách việc của Phase 0.

### 0.3 Khử phi tất định — 8 call site

`just seed-audit` cho danh sách chính xác. Từ khảo sát:

```
src/core/agent_systems.rs:269      src/core/ecs.rs:213, 435, 630, 992
src/evolution/mutation.rs:46       src/evolution/crossover.rs:42
src/evolution/map_elites.rs:57
```

**Mỗi call site = một task.** Đây là chỗ duy nhất dùng **Opus 4.6**, vì nó sửa
`src/` và phải cập nhật mọi caller.

Prompt (dán vào Antigravity, model Opus 4.6):

```
Đọc AGENTS.md và .agents/skills/determinism-fixer/SKILL.md trước.
Task: khử phi tất định tại src-tauri/src/evolution/mutation.rs:46 — ĐÚNG MỘT call site này.
Không đụng call site khác. Kết thúc bằng `just test` và `just flaky 5`.
Báo cáo theo đúng mẫu trong SKILL.md.
```

Quy ước bắt buộc, khai báo một lần rồi mọi task dùng lại:

```rust
pub struct SimRng(pub StdRng);   // bevy_ecs Resource
// khởi tạo: StdRng::seed_from_u64(config.seed)
```

6 chỗ wall-clock: phân loại trước khi sửa. Trong `networking_systems.rs` và
`meta_ai.rs` là telemetry — **giữ nguyên**, chỉ ghi chú. Trong đường chạy sim thì
thay bằng tick counter.

### 0.4 Golden test

Đây là thứ agent không viết hộ được, vì nó định nghĩa "thế nào là cùng một thế giới".

```rust
#[test]
fn determinism_1000_ticks() {
    let hashes: Vec<u64> = (0..5).map(|_| {
        let mut w = World::from_seed(0x5EED);
        for _ in 0..1000 { w.tick(); }
        world_hash(&w)
    }).collect();
    assert!(hashes.windows(2).all(|p| p[0] == p[1]), "sim phi tat dinh: {hashes:?}");
}
```

Cần `fn world_hash(&World) -> u64` — blake3/fxhash trên serialize canonical.
Lưu ý: `HashMap` trong `bevy_ecs` phải được duyệt có thứ tự trước khi hash, nếu
không chính golden test sẽ flaky.

### 0.5 Cổng ra

```bash
just flaky 20
```

**20/20 mới được sang Phase 1.** Chưa đạt thì ở lại đây.

> Giá trị riêng của phase này: kể cả bỏ dở toàn bộ kế hoạch sau bước này,
> Anima-Engine vẫn tốt lên đáng kể. Sim ALife không tái lập được thì không
> nghiên cứu được.

---

## Phase 1 — Bật mutation (Ngày 2)

```bash
cd ~/Documents/project/Hardening && ./hardening init ~/Documents/project/Anima-Engine --modules determinism,mutation
```

### 1.1 Ước lượng chi phí TRƯỚC khi chạy sweep

Đây là chỗ kế hoạch gốc chưa tính, và là rủi ro thực tế lớn nhất.

Số đã đo, không phải ước đoán: **2.002 mutant**, **88 giây** một lần
`cargo test --release`. `cargo mutants` chạy *cả suite* cho *mỗi* mutant, và còn
phải build lại lib mỗi lần:

```
2002 × (88s test + ~40s build) / 6 job ≈ 12 giờ cho MỘT sweep đầy đủ
```

Kết luận thực tế: **`just hunt` không dùng được như thao tác thường ngày.**
Nó là việc chạy qua đêm, một lần, để có bản đồ tổng thể. Ngày thường dùng
`just hunt-file` — quét một module mất vài phút thay vì nửa ngày.

Ba cách cắt chi phí:

1. `just hunt-file <file>` cho công việc hằng ngày — đây là mặc định
2. thêm `exclude_globs` vào `src-tauri/.cargo/mutants.toml`, **kèm lý do** cho
   từng dòng. 2.002 mutant chắc chắn có phần đáng loại (IPC glue, code chỉ log)
3. sweep đầy đủ thì chia theo **ngày**: `just hunt 1` … `just hunt 5`,
   mỗi tối một shard ≈ 2,4 giờ

**Không chạy 5 shard cùng lúc trên một máy.** Kế hoạch gốc nói chạy 5 agent song
song mỗi agent một shard — trên i5-14600KF chúng tranh CPU của nhau và tổng thời
gian tệ hơn chạy tuần tự. Đúng cách: **CPU chạy một sweep, agent tiêu thụ
`missed.txt`.** Agent chỉ chạy `--in-diff`/`--re` (rẻ), nên 5 agent song song ở
bước đó thì không sao.

### 1.2 Tự tay giết 3 mutant — KHÔNG được bỏ qua

```bash
just hunt-file src/evolution/mutation.rs
just list-missed
```

Chọn 3 dòng, tự viết test, tự chạy `just verify "<dòng>"`.

Lý do: nếu anh không tự giết nổi 3 mutant thì anh chưa biết prompt cần nói gì, và
mọi thứ tự động hoá sau đó sẽ nhân bản sự mơ hồ đó lên 500 lần.

Sau 3 cái đó, viết lại phần "Cấm" trong `.agents/skills/mutant-killer/SKILL.md`
theo đúng những chỗ anh vừa suýt làm sai. **Dùng Opus 4.6** cho việc sửa skill này.

---

## Phase 2 — Vòng lặp mutant (Ngày 3–7, Flash làm)

Vòng lặp hằng ngày:

```bash
just hunt-file src/<module>.rs && just list-missed
```

Mỗi dòng = **một** task cho **một** agent. Không bao giờ gộp.

Prompt chuẩn (Antigravity, **Flash 3.6 effort High**):

```
Đọc AGENTS.md rồi dùng skill mutant-killer.
Mutant: src/evolution/mutation.rs:46:5: replace mutate_genotype with ()
Chỉ được ghi trong src-tauri/tests/. Kết thúc bằng hd_verify với đúng dòng mutant trên.
Chưa thấy passed=true thì chưa xong. Tối đa 3 lần thử.
```

Nếu đã cắm MCP, agent gọi `hd_list_tasks` → `hd_verify` thay vì gõ lệnh.

### Áp dụng k = 5

Với mutant khó: chạy 5 agent độc lập **cùng prompt**. Cái nào qua cổng thì giữ;
nhiều cái qua → chọn diff nhỏ nhất (dùng **Pro 3.1** làm trọng tài); không cái
nào qua → **chia nhỏ task**, đừng đổi model.

`0/5` qua cổng nghĩa là **task quá to**, không phải model quá kém.

### Cổng ra

`just mutation-score` ≥ 80%, hoặc mọi mutant còn lại đã có `exclude_globs` kèm lý do.

---

## Phase 3 — Fuzz + Miri (chạy nền, song song Phase 2)

```bash
./hardening init ~/Documents/project/Anima-Engine --modules determinism,mutation,fuzz
```

Phần này **tốn 0 token** và thường cho bug nghiêm trọng nhất.

**Cảnh báo về Miri với repo này:** Miri không chạy được code có FFI, mà
Anima-Engine phụ thuộc tauri/wgpu/burn. `just miri` sẽ hỏng nếu chạy cả suite.
Chỉ chạy trên `--lib` với filter hẹp, nhắm vào code Rust thuần: `evolution/`,
`physics/spatial.rs`.

Hai `unsafe impl Send for BrainModel` / `Sync` ở `src/ai/model.rs:61-62` là hai
**lời hứa** về soundness mà compiler không kiểm được. Miri cũng không bắt được
trực tiếp. Đây là việc đọc tay — đáng làm sớm, và đáng là mục F-001 trong
`FINDINGS.md` nếu `BrainModel` thật sự chứa con trỏ không Send.

Fuzz target đầu tiên nên nhắm hàm thuần, dễ sinh input:
`mutate_genotype`, `crossover`, spatial hash.

Scheduled Task trong Antigravity, 02:00 hằng đêm: `just nightly`
Sáng hôm sau giao **Flash effort High** + skill `crash-triage`. Triage thôi,
**không fix** — fix nằm trong `src/`, đó là việc của anh.

---

## Phase 4 — Dataflow audit (Ngày 8+)

```bash
./hardening init ~/Documents/project/Anima-Engine --modules determinism,mutation,fuzz,dataflow
```

Prompt (**Pro 3.1**, vì cần đọc rộng):

```
Dùng skill dataflow-audit. Xuất dataflow.json cho src-tauri/src/.
KHÔNG đọc dataflow-truth.dot trước khi viết claim.
Kết thúc bằng hd_dataflow_verify. Tối đa 3 lần sửa.
```

Đây cũng là chỗ dùng **kỹ thuật nén**: cho Gemini đốt 300–500K token đọc toàn
repo, xuất ra **artifact 2 trang** (phương án / đánh đổi / bằng chứng `file:line`
/ mâu thuẫn code-vs-doc). Mang đúng 2 trang đó sang chat hỏi kiến trúc. Gemini
không cần giỏi để làm việc này, chỉ cần chăm.

---

## Phase 5 — Perf guard (Ngày 14+, nhánh riêng)

```bash
git checkout -b hardening/perf-hotpath
./hardening init . --modules determinism,mutation,perf
just bench-baseline && git add -A && git commit -m "chore: perf baseline"
```

Module duy nhất agent được sửa `src/`. Cổng đổi từ "diff nằm trong tests/" sang
"benchmark phải thắng thật" — không thắng thì `perf_gate.sh` tự `git checkout`
revert. Agent không có quyền bàn.

Bắt buộc profile trước (`samply`), cấm đoán hot path.

---

## Lịch trình

| Ngày | Việc | Ai làm |
|---|---|---|
| D0 | Phase −1: dọn git, sửa .gitignore, cài công cụ | **Anh** |
| D1 | Phase 0: determinism + baseline + golden test | **Anh** (+ Opus 4.6 cho từng call site) |
| D2 | Bật mutation, ước lượng chi phí sweep | Anh |
| D3 | **Tự tay giết 3 mutant**, sửa lại skill | **Anh** + Opus 4.6 |
| D4–D7 | Vòng lặp mutant | Flash High |
| D4+ | Miri/fuzz nightly | CPU, 0 token |
| D8+ | Dataflow audit | Pro 3.1 |
| D14+ | Perf guard, nhánh riêng | Flash High |

---

## Bảng failure mode

| Kiểu hỏng | Dấu hiệu | Đã chặn ở đâu |
|---|---|---|
| Agent sửa src cho mutant chết | `git diff src/` không rỗng | verify luật 1 |
| Tạo file test mới để lách luật | luật 2–6 không bắt được gì | `git add --intent-to-add` trước khi diff |
| Test rỗng ("không panic") | mutant vẫn sống sau khi thêm test | verify luật 5 + luật 8 |
| Nới assertion cũ cho pass | test xanh mà chất lượng giảm | verify luật 3 |
| Báo cáo sáo rỗng | không có `file:line` | mẫu báo cáo bắt buộc trong SKILL.md |
| Context rot | agent lặp lại, quên luật | horizon < 20 tool call, hand-off qua file |
| Flaky lọt lưới | mutation score dao động | `just flaky 20` là cổng ra Phase 0 |
| Hạ tầng phình thành dự án | scripts > 200 dòng | đếm hằng tuần, cắt |

---

## Tiêu chí dừng / abort

Dừng và xem lại nếu:

- Sau D7, `FINDINGS.md` có **0 bug thật** → verifier chọn sai mục tiêu; đổi mục
  tiêu chứ đừng thêm token
- Tổng `scripts/` vượt 200 dòng → đang xây nhầm thứ
- Anh dành > 1 giờ/ngày đọc output agent → cổng verify chưa đủ chặt
- Mutation score tăng nhưng không bug nào lộ ra → đang farm metric, không phải
  hardening

---

## Port sang repo khác

**LIVA** (`liva-desktop/src-tauri`, 166 LOC, 4 test): copy nguyên xi.
Repo còn nhỏ — cài `determinism` trước, chưa cần mutation.

**Genius** (Python, `ag_core` 13.176 LOC, 265 test): kit đã có sẵn bộ Python.

```bash
./hardening init ~/Documents/project/Genius --modules determinism,mutation
```

Đổi verifier: `mutmut` thay `cargo-mutants`, `pytest-randomly` bắt phụ thuộc thứ
tự test, `hypothesis` thay `proptest`. Riêng dataflow thì **`import-linter`** là
oracle gần như hoàn hảo cho pipeline FastAPI — khai contract (`layers`,
`forbidden`, `independence`) trong `.importlinter`, exit nonzero khi vi phạm.
Skill giữ nguyên cấu trúc, chỉ đổi lệnh.

---

## Điều kế hoạch này KHÔNG làm được

Kiến trúc trên **nhân bản sự cẩn thận, không nhân bản sự sáng suốt.**

Nó không cho biết CVT/PGA-MAP-Elites có phải lựa chọn đúng không, world model có
mâu thuẫn nội tại không, hay Project Genesis nên đơn giản hoá tới đâu. Verifier
chỉ kiểm được thứ anh **đã biết cách kiểm**.

Những câu hỏi đó cần ít token nhưng nhiều suy nghĩ — giữ cho chat, hoặc cho chính
anh, và đừng đổ quota vào.
