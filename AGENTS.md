# AGENTS.md — hợp đồng chuẩn cho agy khi làm việc trong repo này

Đọc file này trước khi làm bất kỳ task nào được giao qua agy-driven-development.

## 1. Working directory & git

- Working directory: `/home/manh/PH2-Legal-Chatbot`.
- **KHÔNG được chạy bất kỳ lệnh git nào** (`add`, `commit`, `checkout`, `stash`, `rebase`, ...).
  Gate (Claude) là người duy nhất commit.

## 6. Giữ nguyên comment

**GIỮ NGUYÊN MỌI COMMENT** đã có khi sửa một file đang tồn tại — comment mang lý do
thiết kế, không có test nào bắt được việc mất comment khi rewrite một block.

## 7. Điều kiện dừng

Nếu một bước thất bại: thử lại tối đa **2 lần**. Sau 2 lần thất bại, **dừng lại** và báo
cáo chính xác dòng lỗi (traceback/assertion) — không được đoán tiếp hoặc tự ý đổi hướng.

## 9. Report contract

Ghi báo cáo đầy đủ ra file `<workspace>/task-N-report.md` (workspace path nằm trong
brief). Phần trả lời trực tiếp (stdout) chỉ **dưới 12 dòng**, không kèm code, không kèm
log, không kèm diff — chỉ trạng thái (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT /
BLOCKED) và tóm tắt một dòng.

## Xác minh trước khi báo DONE

Không được tự sửa assertion/expected value trong test cho khớp với số code tạo ra.
Nếu số thực tế chạy ra khác số trong test, dừng lại và báo số thật trong report — đó là
tín hiệu cho gate, không phải lỗi của bạn cần tự vá.
