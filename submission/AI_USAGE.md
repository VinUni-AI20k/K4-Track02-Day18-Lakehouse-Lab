# Khai báo sử dụng AI

**Công cụ:** Claude Code (model Claude Opus 5.5), chạy trong VS Code trên máy cá nhân.

## AI đã làm gì

- Đọc README, `docs/SUBMISSION.md`, `RUBRIC.md`, `CHECKPOINTS.md`, `RULES.md` và mã nguồn 8 notebook.
- Tạo venv, cài `requirements.txt`, chạy smoke test, sinh dữ liệu, chạy `pytest` và `run_all.py`.
- Chuyển notebook sang `.ipynb`, thực thi bằng `nbconvert` và chép vào `submission/notebooks/`.
- Đề xuất và áp dụng hai sửa đổi mã (giữ nguyên tiêu chí, không hạ ngưỡng):
  - NB1: thay cờ schema-enforcement hardcode bằng cờ lấy từ exception thật + kiểm tra version không đổi.
  - NB4: phát hiện lệch múi giờ khi `CAST(ts AS DATE)` (UTC+7 → 8 ngày lệch), sửa bằng
    `SET TimeZone = 'UTC'`; thêm kiểm tra chất lượng Gold.
- Viết nháp Markdown "Giải thích kết quả" cho từng notebook, `INFO.md` và reflection.
- Render screenshots từ output đã lưu trong `.ipynb` (không gõ tay số liệu).
- **Bonus:** viết nháp `bonus/ARCHITECTURE.md` (chọn topic, quyết định, failure modes, mô hình chi phí)
  và PoC `bonus/poc/poc_pii_retention.py`. Kết quả PoC trong tài liệu lấy từ lần chạy thật; đơn giá cloud
  là giả định tham chiếu bảng giá công khai, đã ghi rõ trong tài liệu.

## AI không làm gì

- Không tạo số liệu hay output giả: mọi con số trong giải thích lấy từ output thực thi trên máy này.
- Không bỏ assertion hay hạ ngưỡng nào; chỉ thêm kiểm tra.

## Phần tôi tự chịu trách nhiệm

Tôi đã đọc lại các giải thích, đối chiếu với output và có thể giải thích cơ chế của từng kết quả
(transaction log, file skipping theo min/max stats, copy-on-write MERGE, hidden partitioning,
field id, tombstone vs orphan, row-group amplification, lifecycle của embeddings, version pin).
