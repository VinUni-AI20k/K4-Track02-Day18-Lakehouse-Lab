# Khai báo sử dụng AI

Công cụ: **OpenAI Codex**. Người dùng yêu cầu đọc Markdown, hoàn thành bài lab,
sau đó chỉ định dùng `uv` để tải thư viện. Không sử dụng sub-agent.

Phạm vi hỗ trợ:

- Đọc README, RULES, SUBMISSION, RUBRIC, CHECKPOINTS và hai bản bonus brief.
- Cài môi trường lightweight bằng uv, sinh dữ liệu giả theo scripts của đề,
  chạy smoke, pytest và tám notebook.
- NB1: thay cờ enforcement PASS cố định bằng kết quả exception thực tế,
  kiểm tra version/số dòng không đổi và in commit JSON.
- NB2: bổ sung assertion ít nhất 100 file ban đầu.
- NB3: lưu metrics MERGE; kiểm tra 100K source, 50K update, 50K insert,
  và 150K dòng sau RESTORE.
- NB4: in toàn bộ Gold, kiểm tra coverage, p50/p95, cost, error_rate;
  đối chiếu toàn bộ chỉ số với phép tổng hợp Polars độc lập từ Silver.
- NB8: kiểm tra số dòng trainable loại đúng UNCLASSIFIED.
- Viết công cụ thực thi Jupytext qua kernel Jupyter, bảo toàn cell output,
  xuất metrics JSON và bổ sung diễn giải bằng Markdown cell.
- Render các đoạn output đã lưu thành PNG bằng Pillow 11.1.0 có sẵn trong
  Python nền. Không sử dụng AI tạo ảnh hay thay đổi số liệu để tạo bằng chứng.
- Soạn INFO, reflection, báo cáo và mô tả PR để người nộp rà soát.
- Theo yêu cầu bổ sung của người dùng, soạn bonus A về LLM observability:
  6 trang architecture, một diagram, 6 decisions/12 alternatives, 6 failure modes,
  cost model Decimal và MVP một tuần. Tra cứu tài liệu/giá official AWS và Iceberg
  ngày 05/10/2026; lưu JSON giá S3 và giả định capacity/compression riêng với số đo.
- Viết và thực thi PoC PyIceberg một writer: crash sau commit/trước checkpoint,
  replay không đếm đôi, late correction, stale revision, conflict và snapshot lineage.
  Cài môi trường kiểm tra riêng bằng uv. Render PDF bằng ReportLab, kiểm tra từng
  trang PNG bằng PyMuPDF (máy không có Poppler), kiểm tra cấu trúc và số học.

Không bỏ assertion, hạ ngưỡng rubric hoặc dựng output giả. Tất cả số liệu
được lấy từ lần thực thi trên workspace này. Giá và tên model trong fixture
là dữ liệu minh họa của đề, không được xác nhận là thông tin dịch vụ hiện hành.
Không chạy Spark, không đánh giá hệ thống production hay tuân thủ pháp luật.
Bonus là bản thiết kế và PoC local; không tạo AWS resources hoặc chứng minh
throughput 1B/ngày. Tỷ số nén >=4:1 và giới hạn tenant/peak là điều kiện phải đo.
Retention đọc 7 ngày, purge vật lý tối đa 24h tiếp theo được khai rõ để review.

Giới hạn: các lần chạy do Codex thực hiện; không khẳng định người nộp đã tự
chạy hoặc hiểu toàn bộ kết quả. Reflection là bản AI hỗ trợ soạn và cần người
nộp xem lại. Chưa thực hiện commit, push, PR hay gửi bài qua kênh lớp.
