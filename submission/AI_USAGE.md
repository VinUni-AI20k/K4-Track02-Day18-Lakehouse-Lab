# Khai Báo Sử Dụng Trợ Lý Trí Tuệ Nhân Tạo (AI Usage Disclosure)

- **Họ và tên sinh viên:** Hoàng Anh Tú
- **MSSV:** 20220055
- **Mã bài lab:** K4-Track02-Day18 Lakehouse Lab

---

### 1. Công cụ AI sử dụng
- **Mô hình / Công cụ:** Google Antigravity (Powered by Gemini 3.8 Flash).

### 2. Phạm vi và mục đích hỗ trợ
Học viên sử dụng AI như một công cụ hỗ trợ lập trình (pair-programmer) và rà soát kỹ thuật trong các khâu:

1. **Thiết lập và quản lý môi trường:**
   - Tạo môi trường ảo `.venv` với Python 3.11 và cài đặt dependencies thông qua `uv`.
   - Kiểm tra và tự động hóa quy trình smoke test (`verify_lite.py`), sinh dữ liệu (`generate_data_lite.py`, `generate_ai_data.py`).
2. **Chuyển đổi và thực thi Notebooks:**
   - Chuyển đổi các file nguồn Jupytext `.py` sang định dạng `.ipynb`.
   - Thực thi tuần tự các notebook qua kernel máy cục bộ, lưu lại toàn bộ đầu ra (outputs, stdout, logs).
3. **Phân tích lý thuyết và biên soạn tài liệu:**
   - Soạn thảo các Markdown cell giải thích cơ chế chuyên sâu (Schema Enforcement, Z-order Data Skipping, Time Travel/Restore, Medallion Dedup, Iceberg Hidden Partitioning, Maintenance Garbage Collection, Vector Quantization, Agent Trajectory Replay & Provenance) theo đúng các tiêu chí trong `RUBRIC.md`.
   - Biên soạn tài liệu kiến trúc Lakehouse cho phần Bonus Challenge (`ARCHITECTURE.md`) theo Topic C (CDC Ride-hailing Việt Nam tuân thủ Nghị định 13/2023/NĐ-CP).
   - Soạn thảo `REFLECTION.md` tóm tắt anti-pattern "Forgotten Deletes" (đảm bảo đúng quy định ≤ 200 từ).
4. **Kiểm thử chất lượng (QA):**
   - Chạy kiểm tra bộ test tự động (`pytest` 24/24 PASS và `run_all.py` 8/8 PASS).
   - Hướng dẫn học viên chụp ảnh màn hình kết quả thực tế trên giao diện Jupyter Lab.

### 3. Cam kết liêm chính học thuật
- Toàn bộ các notebook đều được thực thi trên môi trường máy thật của học viên, các số liệu đo đạc (speedup, pruning ratio, snapshot count, latency, token cost...) là số liệu thực tế được sinh ra trong quá trình chạy.
- Không có bất kỳ hành vi làm giả output (fake output), bỏ qua assertion kiểm thử hay can thiệp sai lệch kết quả.
