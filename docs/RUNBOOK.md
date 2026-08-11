# Runbook — vận hành hằng ngày

Số trong tài liệu này **đo thật** trên Anima-Engine, máy Apple M5 (4 P-core +
6 E-core, 32 GB), ngày 11/08/2026. Không có con số nào là ước đoán.

---

## Số nền, để biết cái gì là bình thường

| | |
|---|---|
| suite chạy một mình | **89 giây** (180 test) |
| suite dưới `-j 4` (tranh CPU) | **263 giây** |
| build một mutant (có `--copy-target`) | **5–87 giây** |
| build một mutant (không có) | build lại **toàn bộ** dependency |
| test một mutant (4 worker tranh CPU) | **575 giây** |
| quét `map_elites.rs` (24 mutant) | **55 phút** |
| toàn crate | **2.006 mutant** |
| đĩa cho cây build tạm | **6 GB × số job** |

Con số quan trọng nhất là dòng cuối cùng suy ra: quét toàn crate ở nhịp này là
**~77 giờ**. Đó là lý do `just hunt` là việc chạy qua đêm, không phải thao tác
hằng ngày. Ngày thường dùng `just hunt-file`.

Nếu số của anh lệch xa mấy dòng trên, dừng lại tra [TRAPS.md](TRAPS.md) trước khi
chạy tiếp — gần như chắc chắn có cấu hình sai, không phải máy yếu.

---

## Vòng lặp hằng ngày

### 1. Sinh task (CPU làm, 0 token)

```bash
just hunt-file src/<module>.rs
```

Glob thì **nhớ nháy**: `just hunt-file 'src/evolution/*.rs'`.

Quét một file mất vài phút tới một giờ tuỳ kích thước. `--iterate` đã bật nên
mutant đã chết ở lượt trước được bỏ qua — **lượt sau luôn rẻ hơn lượt trước**.

```bash
just tasks 5
```

In ra 5 prompt hoàn chỉnh, dán thẳng cho agent. Mỗi prompt **một** agent, không
bao giờ gộp. Muốn xem danh sách thô thì `just list-missed`.

```bash
just mutation-score
```

### 2. Giao việc

Mỗi task một agent, model **Gemini 3.6 Flash effort High**. Prompt mẫu ở
[../prompts/P2-mutant.md](../prompts/P2-mutant.md). Dán **nguyên cả dòng** mutant,
kể cả dấu hai chấm và khoảng trắng.

Với mutant khó, chạy 5 agent độc lập cùng một prompt (`k = 5`). Cái nào qua cổng
thì giữ; nhiều cái qua thì chọn diff nhỏ nhất. **Không cái nào qua thì chia nhỏ
task, đừng đổi model.** `0/5` nghĩa là task quá to.

Năm agent song song thì không sao — mỗi con chỉ verify **một** mutant nên gần như
không tốn CPU. Đừng nhầm việc này với chạy 5 shard cùng lúc; cái đó thì tệ hơn
(xem TRAPS).

### 3. Cổng phán

```bash
just verify "src/evolution/map_elites.rs:43:35: replace > with >= in MapElitesArchive::add_individual"
```

Chỉ có `QUA CONG` mới là xong. Cổng tự chạy `cargo mutants --re` để xác nhận
mutant thật sự chết — không tin lời khai của agent, kể cả của chính anh.

### 4. Ghi bug thật

Mutant sống sót thường không phải "thiếu test", mà là **hành vi chưa ai quyết
định**. Nếu trong lúc viết test anh phát hiện code sai thật, ghi vào
`FINDINGS.md` rồi mới sửa.

Đây là metric duy nhất đáng tin. Mutation score chỉ là proxy.

---

## Chạy nền, 0 token

Đặt Scheduled Task trong Antigravity, 02:00 hằng đêm:

```bash
just nightly
```

Sáng hôm sau:

```bash
just crashes
```

Có crash thì giao agent **triage** (skill `crash-triage`), không giao fix — fix
nằm trong `src/`, đó là việc của người.

---

## Đọc kết quả

| Kết quả | Nghĩa là | Làm gì |
|---|---|---|
| `caught` | test hiện có đã bắt được | không cần làm gì |
| `missed` | không test nào phân biệt được hành vi | **task** |
| `unviable` | code mutate không compile | bỏ qua, cargo-mutants tự loại |
| `timeout` | test chạy quá lâu | **không phải task** — chỉnh `mutants.toml`, đừng viết test |

Nhầm `timeout` thành `missed` là cách nhanh nhất để sinh hàng trăm task rác.
`mutants.toml` đặt `timeout_multiplier = 6.0` chính để tránh chuyện đó.

---

## Cổng phải giữ

| Cổng | Lệnh | Ngưỡng |
|---|---|---|
| tất định | `just flaky 20` | 20/20 |
| tất định (bằng chứng) | `just test` | golden hash không đổi |
| phạm vi ghi + chất lượng test | `just verify "<mutant>"` | `QUA CONG` |
| hiệu năng (nhánh riêng) | `just perf-gate` | thắng có ý nghĩa thống kê |

Golden hash đổi có đúng hai nguyên nhân: sim vừa mất tính tất định (đi sửa), hoặc
hành vi sim đổi có chủ ý (cập nhật hằng số **trong cùng commit** với thay đổi đó).
Không có nguyên nhân thứ ba.

---

## Khi nào dừng lại

- Sau một tuần mà `FINDINGS.md` vẫn rỗng → verifier chọn sai mục tiêu. Đổi mục
  tiêu, đừng đổ thêm token.
- Tổng `scripts/` vượt 200 dòng → đang xây nhầm thứ.
- Anh dành hơn 1 giờ/ngày đọc output agent → cổng chưa đủ chặt.
- Mutation score tăng mà không bug nào lộ ra → đang farm metric, không phải
  hardening.

Chỉ số cần bảo vệ nhất không phải quota, mà là **số giờ anh ngồi đọc output**.
