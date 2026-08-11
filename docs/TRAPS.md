# Bẫy đã sập — tra theo triệu chứng

Mỗi mục dưới đây là một lỗi **đã xảy ra thật** khi dựng và triển khai bộ khung
này, không phải phỏng đoán. Sắp theo triệu chứng anh sẽ thấy trên màn hình, vì
đó là thứ anh có trong tay lúc đang bí.

Cái chung của gần hết danh sách: **lỗi không báo là lỗi.** Nó báo "chậm", báo
"pass", hoặc không báo gì.

---

## cargo-mutants

### `cargo test failed in an unmutated tree, so no mutants were tested`

Đếm mutant đứng yên ở `0/N` mãi mãi, CPU chạy vài phút rồi tắt.

**Nguyên nhân:** baseline (cây chưa mutate) vượt `--timeout`. Cờ `--timeout` trên
dòng lệnh **đè lên** `minimum_test_timeout` trong `.cargo/mutants.toml` — hai chỗ
cấu hình đánh nhau, dòng lệnh thắng.

**Sửa:** đừng truyền `--timeout` cho `hunt`. Để `mutants.toml` quyết:

```toml
timeout_multiplier = 6.0
minimum_test_timeout = 180
```

Đo thời gian suite chạy một mình trước (`time just test`); `minimum_test_timeout`
phải lớn hơn con số đó **nhiều lần**, vì dưới song song nó chậm đi mấy lần.

---

### `TU CHOI: mutant van song` nhưng thật ra là TIMEOUT

Cổng báo mutant còn sống. Đọc kỹ output mới thấy:

```
WARN An explicit test timeout is recommended when using --baseline=skip;
     using 300 seconds by default
TIMEOUT  ... 130s build + 300s test
```

**Nguyên nhân:** ngược hẳn với mục trên, và đây là chỗ dễ đánh đồng nhất.
`verify` chạy với `--baseline skip` nên cargo-mutants **không có baseline để tự
tính timeout** — nó rơi về mặc định 300s. Suite mất 89s chạy đơn và tới 263s khi
tranh CPU, nên 300s là quá sát.

| Lệnh | `--baseline` | `--timeout` |
|---|---|---|
| `hunt` | chạy | **không truyền** — để mutants.toml tính |
| `verify` | skip | **bắt buộc truyền** — không có gì để tính |

**Sửa:** `verify` truyền `--timeout 900` (chỉnh qua `VERIFY_TIMEOUT`).

**Vì sao đây là lỗi tệ nhất trong cả hệ thống:** cổng sai theo hướng **bi quan**.
Agent sẽ viết thêm test cho một mutant vốn đã chết, lặp đủ 3 lần rồi báo thất
bại — đốt quota vào việc không tồn tại, mà log nhìn qua thì hoàn toàn hợp lý.

---

### Quét mutation chậm khủng khiếp, phần lớn thời gian là build

24 mutant mất 55 phút. Quét lại chỉ 2 mutant vẫn mất 39 phút, trong đó phần test
chỉ 12 phút.

**Nguyên nhân:** `--copy-target` mặc định **false**. Log nói thẳng:

```
Copied source tree total_bytes=1404973 total_files=147 reflink_used=true
```

Chỉ chép 1,4 MB source — `target/` không được chép, nên **mỗi cây tạm build lại
toàn bộ dependency từ số 0**, và điều đó lặp lại mỗi lượt quét, mỗi worker. Với
tauri + wgpu + burn thì đó là gần như toàn bộ thời gian.

**Sửa:** `--copy-target true`. Build từ "toàn bộ dep" xuống **5–87 giây**.

Trên APFS bản chép dùng reflink (copy-on-write) nên 13 GB `target/` gần như
không tốn byte đĩa nào — đo được đĩa trống còn **tăng** sau khi bật, vì cây tạm
cũ được dọn.

Sau khi vá, nút thắt chuyển sang phase **test** (575s/mutant so với 89s chạy
đơn). Lúc đó mới đáng nghĩ tới thu hẹp tập test binary.

---

### `just hunt-file 'src/x/*.rs'` in ra usage rồi thoát

**Nguyên nhân:** thiếu nháy quanh `{{file}}` trong recipe → shell bung glob thành
nhiều đường dẫn, mà `--file` chỉ nhận một giá trị.

**Sửa:** `--file "{{file}}"` trong justfile, và **luôn đặt glob trong nháy** khi
gọi: `just hunt-file 'src/evolution/*.rs'`.

---

### CPU đỏ rực, load average gấp 5 lần số core

`-j 4` mà load lên 49 trên máy 10 core.

**Nguyên nhân:** `-j N` chạy N tiến trình **cargo**, và mỗi cargo lại tự build với
**toàn bộ** số core. Song song thật là `N × ncpu`, không phải `N`.

**Đo được:** một lượt test mất 486s trung bình, trong khi suite chạy đơn chỉ 89s
— chậm gấp hơn 5 lần.

**Sửa:** siết `CARGO_BUILD_JOBS` sao cho `jobs × CARGO_BUILD_JOBS ≈ ncpu`.
Justfile trong kit tự tính. Đây là trường hợp **giảm song song lại nhanh hơn**.

---

### Danh sách task biến mất sau khi agent verify xong

`just list-missed` đang có 20 dòng, một agent chạy `just verify` xong thì còn 0.

**Nguyên nhân:** `cargo mutants` ghi đè `mutants.out/` mỗi lần chạy, kể cả khi
chỉ test đúng một mutant. `missed.txt` bị xoá sạch — mất danh sách task của cả đội.

**Sửa:** `verify` phải dùng `--output mutants.verify` riêng. Kit đã làm.

---

### Chạy 5 shard song song không nhanh hơn

**Nguyên nhân:** shard sinh ra để chia việc qua **nhiều máy** hoặc **nhiều ngày**.
Trên một máy, tổng khối lượng CPU không đổi — số core không tăng. Thêm vào đó mỗi
worker giữ một bản sao cây nguồn: `-j 4` chiếm **24 GB** đĩa; 5 shard × 4 job là
~120 GB.

**Sửa:** một lượt, `-j` khớp core. Muốn nhiều lượt thì chạy **tuần tự** —
`--iterate` nhớ mutant đã chết ở `previously_caught.txt` nên lượt sau rẻ hơn hẳn.

---

## Cổng verify

### Cổng báo `QUA CONG` nhưng chưa test gì — FALSE PASS

Agent báo xong, cổng xác nhận, mutant vẫn sống nguyên.

**Nguyên nhân:** luật "mutant phải chết" chạy `cargo mutants --re "<chuỗi mutant>"`
rồi chỉ đọc exit code. Nhưng khi regex không khớp mutant nào:

```
Found 0 mutants to test
 WARN No mutants found under the active filters
EXIT=0
```

**Exit 0.** Cổng kết luận "mutant đã chết" trong khi nó chưa test gì.

Hai đường dẫn tới đây, cả hai đều dễ xảy ra:
- agent **gõ sai một ký tự** trong chuỗi mutant → qua cổng miễn phí
- mutant đã bị loại trong `mutants.toml` → y hệt

**Sửa:** không tin exit code suông. Cổng phải khẳng định có **đúng một** mutant
được test và nó `caught`:

```bash
echo "$OUT" | grep -q "Found 0 mutants" && reject "khong tim thay mutant nao khop"
echo "$OUT" | grep -qE "[0-9]+ caught"  || reject "khong xac nhan duoc mutant da chet"
```

**Vì sao đây là loại tệ nhất:** cổng sai theo hướng **lạc quan**. Nó khen một công
việc chưa làm, và im lặng. Mọi số đo sau đó đều nhiễm.

---

### Agent dùng `transmute` để rèn trạng thái private

Test pass, mutant chết, nhìn qua thì hoàn hảo:

```rust
struct MirrorStruct { _a: A, _b: B, is_online: AtomicBool }   // cùng layout
let mirror: &MirrorStruct = unsafe { std::mem::transmute(&tracker) };
mirror.is_online.store(true, Ordering::SeqCst);
```

**Hai vấn đề, cái nào cũng đủ để từ chối:**

1. Struct gốc không có `#[repr(C)]` → Rust **không đảm bảo** thứ tự field. Đây là
   undefined behavior; hôm nay chạy được là may, mai đổi compiler là hỏng.
2. Nó **không test hành vi**. Nó rèn ra một trạng thái mà API công khai không bao
   giờ tạo được, rồi khẳng định về trạng thái đó.

**Sửa:** cấm `unsafe`/`transmute`/`from_raw_parts` trong vùng test. API công khai
không tạo được trạng thái cần test thì đó là mutant **cần refactor** — dùng
`just skip` kèm lý do, hoặc báo lại. Không phải chỗ để sáng tạo.

---

### Agent tạo file test mới và lách sạch mọi luật

Luật cấm `#[ignore]`, cấm assertion rỗng nghĩa… đều không bắt được gì.

**Nguyên nhân:** `git diff HEAD` **không thấy file untracked**. Agent chỉ cần viết
test vào file *mới* là toàn bộ luật soi diff trở nên vô hình.

**Sửa:** `git add --intent-to-add -- <vùng ghi>` trước khi lấy diff. Đây là lỗ
thủng lớn nhất từng có của cổng, và nó **pass im lặng** — không có triệu chứng nào
ngoài việc chất lượng test tệ dần.

---

### Luật "cấm xoá assertion" không bắt được gì

**Nguyên nhân:** regex `^-\s*assert` chỉ khớp assertion đứng riêng một dòng. Sửa
`fn t() { assert_eq!(a, b); }` thành `fn t() { }` thì dòng bị xoá bắt đầu bằng
`fn`, không phải `assert`.

**Sửa:** soi *toàn bộ* dòng bị xoá, không neo vào đầu dòng.

---

### `.hardening.env` không được commit

Clone repo về máy khác là mọi script hỏng.

**Nguyên nhân:** rất nhiều `.gitignore` có `*.env` để chặn secret. Nó nuốt luôn
`.hardening.env` — file config layout mà mọi script đều `source`.

**Sửa:** thêm `!.hardening.env`. `hardening init` nay tự làm.

---

### Skill không được commit

**Nguyên nhân:** `.gitignore` có `.agents/` (thư mục output của agent đời trước).

**Sửa:** đổi thành hai dòng — ignore nội dung, giữ lại skill:

```
.agents/*
!.agents/skills/
```

---

## Agent

### Agent từ chối làm Phase 0, viện dẫn AGENTS.md

> "Tôi không thể thực hiện task này vì nó vi phạm luật trong AGENTS.md:
> **Cấm tuyệt đối** sửa bất kỳ file nào trong `src/`."

**Nguyên nhân:** ngoại lệ cho `determinism-fixer` chỉ được ghi trong `SKILL.md`,
còn `AGENTS.md` nói "không ngoại lệ". Agent đọc `AGENTS.md` trước và coi đó là
luật tối cao.

**Đây là hệ thống chạy đúng, không phải agent hỏng.** Hai tài liệu mâu thuẫn thì
agent ngoan bế tắc, agent hư chọn cái lỏng hơn. Cả hai đều tệ.

**Sửa:** `AGENTS.md` phải tự nêu bảng ngoại lệ, ràng buộc theo nhánh. Kit đã có.

---

### Test pass nhưng phân phối xác suất sụp

Test lấy 1000 mẫu, tất cả ra cùng một kết quả.

**Nguyên nhân:** `rng` được tạo **trong** vòng lặp lấy mẫu, nên mỗi vòng lặp lại
đúng một chuỗi số.

**Sửa:** khai báo `rng` **ngoài** mọi vòng lặp. Áp dụng cho cả code sim: RNG của
vòng tiến hoá phải sống suốt đời thread, không tạo lại mỗi epoch.

---

## mutmut (Python)

### Mọi lệnh mutmut trong script đều lỗi

Kit ban đầu viết theo **mutmut 2.x**; bản 3.x đổi API và không tương thích ngược:

| 2.x | 3.x |
|---|---|
| `mutmut result-ids survived` | **đã bỏ** — dùng `mutmut results` rồi lọc `': survived'` |
| `--paths-to-mutate <dir>` | `source_paths` trong `setup.cfg` mục `[mutmut]` |
| cache `.mutmut-cache` | thư mục `mutants/` — nhớ gitignore |

Tên mutant có dạng `<module>.x_<hàm>__mutmut_<N>`.

**Bẫy riêng:** `mutmut results` **chỉ liệt kê mutant còn SỐNG**. Mutant chết
không xuất hiện — nên không dùng nó để kiểm "mutant có tồn tại không". Muốn kiểm
tồn tại thì dùng `mutmut show <tên>`, nó ném `FileNotFoundError` khi tên sai.

Và `show` đọc từ catalog do `run` sinh ra, nên thứ tự bắt buộc là **`run` trước,
`show` sau**.

---

### Cổng thoát im lặng, exit 1 mà không nói lý do

Chạy `verify` thấy exit 1 nhưng không có dòng `TU CHOI` nào.

**Nguyên nhân:** script mở `set -e` cùng `set -o pipefail`. Khi `mutmut` hoặc
`cargo mutants` trả mã khác 0 — mà đó **chính là trường hợp mutant còn sống** —
shell giết script ngay tại dòng đó, trước khi tới câu từ chối có giải thích.

Nghĩa là đường quan trọng nhất của cổng lại là đường im lặng nhất.

**Sửa:** `|| true` sau pipeline, hoặc `set +e` bao quanh rồi đọc `$?`:

```bash
set +e
OUT=$( cargo mutants ... 2>&1 )
RC=$?
set -e
```

**Lỗi này chỉ lộ ra khi test đường THẤT BẠI.** Test đường thành công thì mọi thứ
trông hoàn hảo — mutant chết, exit 0, không ai chạm tới nhánh chết người.

---

## Antigravity CLI (`agy`)

Bốn thứ phải đúng cùng lúc thì `agy` mới chạy. Sai cái nào cũng cho lỗi khó đoán.

| Triệu chứng | Nguyên nhân | Sửa |
|---|---|---|
| `invalid model selection (--model "<nguyên prompt>")` | Go flag parser dừng ở đối số không phải cờ | đặt **mọi cờ trước** `-p` |
| `--effort is not supported for model "claude-..."` | `--effort` chỉ dùng cho model Gemini | bỏ `--effort` khi dùng model Claude |
| trả lời "để tôi tìm thư mục dự án trước…" | không thấy workspace | thêm `--add-dir <đường dẫn repo>` |
| `no output produced — a tool required the "command" permission` | thiếu allow-rule | thêm `command(cargo)`, `command(just)` vào `permissions.allow` trong `~/.gemini/antigravity-cli/settings.json` |

**Giới hạn không vượt được:** `agy -p` chỉ chạy **một lượt trao đổi** rồi dừng.
Nó trả `status: SUCCESS` kèm câu "I'll start by reading both files…" và thoát.
Task cần lặp sửa-build-sửa thì **không dùng được chế độ này**.

Cấu hình MCP của Antigravity nằm ở `~/.gemini/config/mcp_config.json`, **không
phải** `~/.antigravity`. Khối `env.PATH` là bắt buộc — Antigravity khởi chạy MCP
server với môi trường tối thiểu, không kế thừa `PATH` của shell, nên thiếu
`~/.cargo/bin` là server không thấy `just`/`cargo`.

---

## Bash trên macOS

macOS ship **bash 3.2** (2007). Script viết cho bash 4+ chết ngay dòng đầu.

| Không dùng được | Thay bằng |
|---|---|
| `declare -A` (associative array) | hàm `case ... esac` tra bảng |
| `case` bên trong `$( ... )` | thêm ngoặc mở: `case "$x" in (a\|b) ...` |
| `ls a b c` để hỏi "có ít nhất một cái" | vòng lặp `[ -f ... ]` — `ls` trả lỗi khi **thiếu bất kỳ cái nào** |

Cái thứ ba nguy hiểm nhất vì nó **sai âm thầm**: nhận diện repo Python thất bại,
không có thông báo lỗi nào.

---

## Tất định

### Seed RNG rồi mà sim vẫn không tái lập được

**Nguyên nhân:** ở đâu đó có vòng lặp trên `HashMap`/`HashSet`. `RandomState` được
gieo lại từ OS **mỗi lần khởi động tiến trình**, nên thứ tự duyệt đổi giữa các
lần chạy. Bốc ngẫu nhiên trên iterator đó thì seed cố định cũng vô nghĩa.

Đây là F-001 trong Anima-Engine: `select_parent` chọn trên `grid.values()` của
một `HashMap`.

**Sửa:** `BTreeMap`/`BTreeSet`, hoặc sort trước khi duyệt. Chỉ cần đổi ở những
chỗ thứ tự **ảnh hưởng state**, không phải mọi chỗ.

---

### Golden test pass nhưng không chứng minh được gì

**Nguyên nhân:** test so N thế giới trong **cùng một tiến trình**. Trong một tiến
trình thì thứ tự HashMap ổn định — nên nó mù với đúng loại lỗi nguy hiểm nhất.

**Sửa:** ghim một hash cố định trong test. Đó mới là thứ so được **giữa các lần
chạy**. Kèm luôn một test khẳng định hash **phân biệt được** hai trạng thái khác
nhau — thiếu nó thì hai test kia pass kể cả khi sim hỏng hoàn toàn.

Băm thì phải: **lượng tử hoá float** trước (`-0.0` và `0.0` băm khác nhau) và
**sắp xếp** trước (thứ tự duyệt entity phụ thuộc bố cục archetype).

---

### `just flaky 20` đạt 20/20 nhưng sim vẫn không tất định

**Không mâu thuẫn.** `flaky` chỉ chứng minh **test suite ổn định**. Nếu chưa test
nào khẳng định chặt trên kết quả phụ thuộc RNG thì suite vẫn xanh trong khi sim
phi tất định hoàn toàn.

Bằng chứng tất định là **golden test**, không phải `flaky`.

---

## Số đo

### `baseline.sh` báo còn `thread_rng` khi src đã sạch

**Nguyên nhân:** `grep -c 'thread_rng'` đếm cả dòng chú thích nhắc tới tên hàm.

**Sửa:** đếm lời gọi thật (`rand::thread_rng()`) và loại dòng bắt đầu bằng `//`.
Một số đo sai lệch làm hỏng đúng thứ mà baseline sinh ra để bảo vệ.
