# Thông tin bài nộp

- Họ tên: Mai Huy Hoang (tên theo repository cá nhân).
- MSSV: 2A202602685.
- Mã bài: K4-Track02-Day18.
- Đường chạy: lightweight cho cả NB1–NB8; không dùng Spark.
- Python: 3.12.3.
- Hệ điều hành: Ubuntu 24.04.5 LTS, Linux x86_64.
- Fork cá nhân: https://github.com/huyhoang1706/K4-Track02-Day18-MaiHuyHoang-2A202602685-Lakehouse-Lab
- Phần thực hiện: toàn bộ phần bắt buộc; bỏ bonus theo yêu cầu.

## Kiểm tra và đọc bằng chứng

Smoke: 9/9 check; pytest: 24/24; headless runner: 8/8 notebook.
Chi tiết lệnh và output nằm trong `evidence/`. Tám notebook trong `notebooks/`
được thực thi bằng Jupyter kernel của `.venv`, có output từng cell, assertion và
phần giải thích tiếng Việt. `RESULTS.md` trích output tổng hợp từ lần thực thi này.
Screenshots chụp các trang HTML chứa nguyên văn output tổng hợp; đây là ảnh browser
của bằng chứng đã lưu, không phải ảnh giao diện Jupyter hay ảnh dựng số liệu.
`evidence/environment.json` và `evidence/requirements-lock.txt` ghi phiên bản thực tế.

## Tái lập

```bash
make setup
make smoke
make data
make data-ai
make test
make run-all
.venv/bin/python scripts/prepare_submission.py
```

Script cuối lưu 8 notebook, transcript, HTML evidence, kết quả và môi trường.
Chạy notebook đã nộp với Jupyter kernel thuộc `.venv`, cwd là repo hoặc một thư mục
con trong repo; cell bootstrap tự tìm repo. `_lakehouse/` được sinh cục bộ và bị
Git bỏ qua; không cần tải model, API key hay Docker khi thực thi.

## Các sửa đổi so với đề bài

- NB1: thay cờ enforcement hardcoded bằng kết quả exception thật, xác nhận
  rejected write không tăng version/số dòng; in nguyên văn transaction log.
- NB3: lưu và kiểm tra MERGE metrics: 50.000 update + 50.000 insert.
- NB4: đặt DuckDB timezone UTC để nhóm ngày đúng với Bronze UTC và không phụ
  thuộc timezone máy; kiểm tra mọi cặp ngày/model, percentile, chi phí, error rate
  và storage. In toàn bộ Gold để kiểm tra được từng dòng.
- Không bỏ assertion, hạ ngưỡng hoặc sửa dữ liệu để ép PASS.

Đọc `AI_USAGE.md` về phạm vi hỗ trợ AI và `REFLECTION.md` về anti-pattern.

Kiểm tra headless cuối dùng `LAKEHOUSE_ROOT=/tmp/lakehouse-final-clean make run-all`
trên thư mục dữ liệu ban đầu chưa tồn tại, xác nhận notebook tự sinh prerequisite
và chạy đủ từ storage sạch. Đây là chạy sạch dữ liệu, dùng môi trường dependencies
đã cài ở trên. Thời gian và metric có thể thay đổi khi chạy lại.
