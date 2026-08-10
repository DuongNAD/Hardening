# Phase 0 — khử phi tất định  (model: Claude Opus 4.6)

Đọc AGENTS.md và .agents/skills/determinism-fixer/SKILL.md trước.

Task: khử phi tất định tại `<file>:<line>` — ĐÚNG MỘT call site này.
Không đụng call site khác, kể cả khi thấy chúng ngay bên cạnh.

Quy ước bắt buộc: RNG lấy từ resource `SimRng(StdRng)`, seed truyền tường minh
từ config. Không `from_entropy()` trong đường chạy sim.

Kết thúc bằng `just test` (số test pass phải BẰNG trước khi sửa) và `just flaky 5`.
Báo cáo theo đúng mẫu trong SKILL.md.
