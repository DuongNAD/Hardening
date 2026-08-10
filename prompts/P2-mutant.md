# Phase 2 — giết mutant  (model: Gemini 3.6 Flash, effort High)

Đọc AGENTS.md rồi dùng skill mutant-killer.

Mutant: `<dán nguyên một dòng từ `just list-missed`>`

Chỉ được ghi trong `<crate>/tests/`. Kết thúc bằng:
    hd_verify với target = đúng dòng mutant trên
(hoặc `just verify "<dòng mutant>"` nếu không có MCP)

Chưa thấy `passed=true` / `QUA CONG` thì chưa xong. Tối đa 3 lần thử.
Không trả lời được "hành vi nào quan sát được sẽ sai" → dừng, báo cần refactor.
