# Kê khai sử dụng AI (AI Usage Declaration)

Tuân thủ quy định tại [RULES.md](../docs/RULES.md) của khóa học, dưới đây là bản kê khai chi tiết về các công cụ AI và phạm vi hỗ trợ trong quá trình thực hiện bài lab:

## 1. Công cụ AI sử dụng
- **Mô hình / Trợ lý:** Google Gemini 3.8 Flash (High) tích hợp trong Antigravity CLI.
- **Mục đích:** Hỗ trợ đọc hiểu cấu trúc đề bài, giải thích khái niệm kỹ thuật, tự động hóa chạy các lệnh kiểm thử và dựng ảnh minh họa từ output thực tế.

## 2. Phạm vi hỗ trợ cụ thể
1. **Phân tích yêu cầu và đối chiếu Rubric:**
   - Trợ lý AI hỗ trợ đọc hiểu tài liệu hướng dẫn (`README.md`, `CHECKPOINTS.md`, `RUBRIC.md`, `SUBMISSION.md`).
   - Lập danh sách kiểm tra (checklist) để không bỏ sót tiêu chí chấm điểm nào.
2. **Hỗ trợ thực thi và tự động hóa:**
   - Viết script Python tự động thực thi các notebook `.ipynb` bằng `nbconvert` với kernel môi trường ảo `.venv` để bảo toàn output các cell code.
   - Chạy các lệnh kiểm thử `smoke test` (9 checks), `pytest` (24 checks), và `run_all.py` (8 checks).
3. **Trực quan hóa kết quả (Screenshots):**
   - Viết mã nguồn Python (`scripts/generate_screenshots.py`) sử dụng thư viện `matplotlib` và `Pillow` để trích xuất trực tiếp số liệu, log giao dịch và bảng biểu thực tế từ kết quả thực thi notebook, sau đó render thành các ảnh PNG chất lượng cao lưu vào `submission/screenshots/`.
4. **Phản tư (Reflection) và Bonus Architecture Brief:**
   - AI hỗ trợ thảo luận, phản biện các anti-patterns trong Lakehouse và hỗ trợ tính toán chi phí lưu trữ/tính toán theo các công thức FinOps trong tài liệu kiến trúc bonus.

## 3. Cam kết tính trung thực
- Toàn bộ kết quả, số liệu đo lường (speedup, pruning ratio, row counts, latency, cost) đều được chạy thật 100% trên máy local thông qua môi trường thực thi của lab.
- Không sử dụng output giả lập, không hạ ngưỡng assertion để báo PASS giả.
- Mã nguồn và bài viết phản tư được tự kiểm chứng và thấu hiểu rõ ràng.
