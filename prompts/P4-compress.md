# Nén repo thành artifact 2 trang  (model: Gemini 3.1 Pro)

Đọc toàn bộ `<crate>/<src>/`. Được phép đốt nhiều token — đó là mục đích.

Xuất ra ĐÚNG 2 trang, cấu trúc cố định:
1. Phương án đang dùng (mỗi mục 1 câu + `file:line`)
2. Đánh đổi đã chọn, và cái gì bị hy sinh
3. Mâu thuẫn giữa code và tài liệu (`*.md` ở gốc repo)
4. 3 câu hỏi kiến trúc mà verifier KHÔNG kiểm được

Không tóm tắt chức năng. Không khen. Không đề xuất refactor.
Đây là bản để mang sang chat hỏi, không phải báo cáo.
