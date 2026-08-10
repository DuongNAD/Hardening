# Phase 4 — dataflow audit  (model: Gemini 3.1 Pro)

Dùng skill dataflow-audit. Xuất `dataflow.json` cho `<crate>/<src>/`.

KHÔNG đọc `dataflow-truth.dot` trước khi viết claim — đọc trước là gian lận và
sẽ lộ ở bước invariant.

Mỗi `invariant` phải là mệnh đề kiểm được. Cấm "data flows", "passes data".
Kết thúc bằng hd_dataflow_verify. Tối đa 3 lần sửa.
