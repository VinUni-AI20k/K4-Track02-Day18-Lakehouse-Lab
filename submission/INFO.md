# Thông tin bài nộp

| Mục | Giá trị |
|---|---|
| Họ tên | Hoàng Thái Đạt |
| MSSV | 2A202602959 |
| Mã bài | K4-Track02-Day18 |
| Repository | https://github.com/Liber72/K4-Track02-Day18-HoangThaiDat-2A202602959-Lakehouse-Lab |
| Đường chạy | Lightweight cho cả NB1–NB8 |
| Python | 3.11.3 |
| Hệ điều hành | Windows, build 10.0.26200, x86_64 |
| Cài dependencies |  requirements.txt |
| Phạm vi | Phần bắt buộc NB1-NB8 và bonus A, bản local để review |

Phiên bản đo thực tế: deltalake **1.6.6**, pyiceberg **0.12.0**, DuckDB **1.5.6**,
Polars **1.44.2**, PyArrow **25.0.1**, NumPy **2.4.6**,
JupyterLab **4.6.4**, Jupytext **1.19.6**, nbclient **0.11.0**, pytest **9.1.1**.
Danh sách đầy đủ nằm trong [requirements-lock.txt](evidence/requirements-lock.txt).

Smoke 9/9, pytest 24/24, scripts headless 8/8; notebook có output được thực thi
bằng kernel Jupyter sử dụng đúng Python `.venv`. Xem [README](README.md)
và [số liệu gốc](evidence/metrics.json).

Các PNG trong `screenshots/` render nguyên văn các đoạn stdout đã lưu trong
notebook, có nhãn `OUTPUT RENDER`; đây không phải ảnh chụp giao diện Jupyter.
Công cụ UI không có trình duyệt khả dụng trong phiên này. Nếu coach yêu cầu
ảnh giao diện, mở các notebook đã có output và chụp bổ sung.

Codex thực thi và chuẩn bị artifacts trên máy theo yêu cầu của người nộp.
Thông tin họ tên được suy ra từ repo, cần đối chiếu lại trước khi nộp.
Phạm vi AI được khai trong [AI_USAGE.md](AI_USAGE.md).
Người nộp cần tự đọc, chạy lại và giải thích kết quả theo [RULES.md](../docs/RULES.md).
Repo hiện chứa bài hoàn thiện ở local; chưa commit/push hoặc gửi PR/kênh lớp trong phiên này.
