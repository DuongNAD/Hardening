# Hardening Kit

Bộ khung verifier cắm được vào **bất kỳ repo nào** (Rust / Python), chọn chức
năng lúc cài, và phơi ra cho Antigravity dưới dạng **MCP server**.

Một câu tóm tắt: *dùng quota để **sinh**, dùng CPU để **phát hiện**, dùng chương
trình để **phán**.* Model không bao giờ được tự chứng nhận công việc của mình.

```
Chất lượng = sức mạnh verifier × k (số lần thử) ÷ độ dài horizon
```

## Tài liệu

| Đọc khi | File |
|---|---|
| vận hành hằng ngày, số đo thật, cách đọc kết quả | [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| **có gì đó hỏng** — tra theo triệu chứng | [docs/TRAPS.md](docs/TRAPS.md) |
| kế hoạch triển khai từng phase | [PLAN.md](PLAN.md) |
| nhật ký triển khai thật, nguồn của mọi con số | [docs/CASE-ANIMA.md](docs/CASE-ANIMA.md) |
| prompt dán thẳng vào Antigravity | [prompts/](prompts) |

## Trạng thái

| Phần | |
|---|---|
| cổng verify (8 luật, Rust + Python) | ✅ test đủ đường từ chối |
| cài đặt, dò layout | ✅ đúng trên Anima-Engine, LIVA, Genius |
| MCP server trong Antigravity | ✅ chạy đúng môi trường thật |
| module `determinism` | ✅ đã dùng thật, tìm ra 1 bug |
| module `mutation` | ✅ lượt quét đầu 91% — nhưng **chưa agent nào đi trọn một lượt** |
| module `fuzz` / `perf` / `dataflow` | ⚠️ có script, chưa chạy trên repo thật |

Dòng áp chót là cảnh báo quan trọng nhất: cả bộ khung này tồn tại để một agent
nhận mutant → viết test → qua cổng. Việc đó chưa xảy ra lần nào.

---

## 1. Ba thành phần

| Thành phần | File | Vai trò |
|---|---|---|
| CLI cài đặt | `./hardening` | detect layout, chọn module, rải file vào repo đích |
| Bộ khung | `kit/` | justfile + scripts + skills, tham số hoá qua `.hardening.env` |
| MCP server | `mcp/server.py` | 11 tool cho agent Antigravity, chỉ stdlib Python |

Không có bước nào hardcode đường dẫn của một dự án cụ thể. Cùng bộ này chạy được
trên Anima-Engine, LIVA, Genius.

---

## 2. Chức năng (chọn khi cài)

| Module | Cho gì | Cổng exit-code |
|---|---|---|
| `determinism` | Khử RNG/đồng hồ/thứ tự hash. **Nền tảng, luôn được cài kèm.** | `just flaky 20` → 20/20 |
| `mutation` | Vòng lặp giết mutant, khối lượng chính của agent | `just verify "<mutant>"` |
| `fuzz` | Fuzz + Miri chạy nền ban đêm, 0 token | `just crashes` rỗng |
| `dataflow` | Ép "phân tích luồng dữ liệu" thành artifact máy đối chiếu được | `just dataflow-verify` |
| `perf` | Module **duy nhất** agent được sửa `src/`, tự revert nếu không thắng | `just perf-gate` |

```bash
./hardening modules
```

---

## 3. Cài

```bash
./hardening detect ~/Documents/project/Anima-Engine
```

```bash
./hardening doctor ~/Documents/project/Anima-Engine
```

```bash
./hardening init ~/Documents/project/Anima-Engine --modules determinism,mutation
```

Không truyền `--modules` thì nó hỏi bằng menu. Sau khi cài, **phải commit bộ
khung** — nếu không cổng verify sẽ từ chối mọi task (và nói rõ lý do):

```bash
git add justfile AGENTS.md FINDINGS.md .hardening.env scripts .agents/skills && git commit -m "chore: cai hardening kit"
```

Gỡ ra: `./hardening uninstall <repo> [--yes]` (giữ lại `AGENTS.md`, `FINDINGS.md`).

---

## 4. Cắm vào Antigravity

Antigravity đọc cấu hình MCP tại **`~/.gemini/config/mcp_config.json`** (không
phải `~/.antigravity`). Thêm khối `hardening` trong
[antigravity-config.example.json](mcp/antigravity-config.example.json) vào
`mcpServers` có sẵn, sửa `HARDENING_REPO` cho đúng repo đang làm.

`PATH` trong khối `env` là bắt buộc: Antigravity khởi chạy server với môi trường
tối thiểu, không kế thừa `PATH` của shell — thiếu `~/.cargo/bin` là server không
thấy `just` và `cargo`.

Kiểm tra server sống:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 mcp/server.py
```

### Tool agent nhìn thấy

| Tool | Dùng khi |
|---|---|
| `hd_detect` | chưa biết repo trông thế nào |
| `hd_status` | trước khi sửa — cho biết vùng ghi duy nhất, cảnh báo nếu đang lệch phạm vi |
| `hd_baseline` | một lần, trước mọi thứ |
| `hd_flaky` | cổng ra Phase 0 |
| `hd_seed_audit` | liệt kê nguồn phi tất định còn lại |
| `hd_hunt` | sinh danh sách mutant sống (tốn CPU, 0 token) |
| `hd_list_tasks` | lấy task — mỗi dòng một task |
| **`hd_verify`** | **cổng duy nhất.** `passed=true` mới là xong |
| `hd_crashes` | crash fuzz chưa triage |
| `hd_dataflow_verify` | đối chiếu dataflow.json với đồ thị thật |
| `hd_finding_add` | ghi bug thật vào FINDINGS.md (validate cứng) |

Server **không** cho chạy shell tuỳ ý. Chỉ 11 động từ, mỗi cái một lệnh cố định.

---

## 5. Skill

`hardening init` chỉ rải skill của module được chọn vào `.agents/skills/`, và
symlink `.claude/skills` → cùng chỗ. Một file `SKILL.md` chạy không sửa đổi trên
Antigravity, Claude Code, Codex, Gemini CLI.

| Skill | Module |
|---|---|
| `determinism-fixer` | determinism — skill **duy nhất** được sửa `src/`, chỉ trên nhánh Phase 0 |
| `mutant-killer` | mutation |
| `crash-triage` | fuzz |
| `dataflow-audit` | dataflow |
| `perf-guard` | perf |

Nhiều repo để `.agents/` trong `.gitignore` → skill sẽ không được commit.
`hardening init` phát hiện và nhắc; sửa thành:

```
.agents/*
!.agents/skills/
```

---

## 6. Cổng verify kiểm gì

`scripts/verify.sh` — 8 luật, mỗi luật một đường từ chối, tất cả đã test:

1. chỉ được ghi trong `<crate>/<tests>/` (+ `FINDINGS.md`)
2. cấm thêm `#[ignore]` / `#[should_panic]` / `@pytest.mark.skip`
3. cấm xoá hoặc sửa dòng có assertion sẵn có
4. cấm RNG / đồng hồ phi tất định trong test
5. cấm assertion rỗng nghĩa (`is_ok()`, truthy đứng một mình)
6. có mutant mà không thêm assertion nào → chưa làm
7. test phải pass 3 lần liên tiếp
8. mutant chỉ định phải **thật sự chết** (`cargo mutants --re`)

Hai điểm kỹ thuật đáng lưu, cả hai đều là lỗi thật lộ ra khi test:

- diff được lấy **sau** `git add --intent-to-add`, vì `git diff HEAD` không thấy
  file untracked — không có bước đó thì agent chỉ cần tạo file test *mới* là
  lách sạch luật 2–6
- luật 8 chạy `cargo mutants --output mutants.verify`, vì mặc định nó ghi đè
  `mutants.out/` — tức là mỗi lần một agent verify xong là **xoá sạch
  `missed.txt`**, danh sách task của cả đội

Bản Python cũng có đủ 8 luật; `pytest-randomly` là tuỳ chọn (thiếu thì bỏ qua
kiểm thứ tự test, không chặn công việc).

---

## 7. Tiêu chí dừng

Đọc `FINDINGS.md`, không đọc mutation score. Sau một tuần mà `FINDINGS.md` vẫn
rỗng → verifier chọn sai mục tiêu; đổi mục tiêu chứ đừng đổ thêm token.

Chỉ số cần bảo vệ nhất không phải quota, mà là **số giờ ngồi đọc output agent**.
Mọi thứ ở đây tồn tại để chỉ phải đọc thứ đã qua cổng.

Kế hoạch triển khai từng bước: [PLAN.md](PLAN.md).
