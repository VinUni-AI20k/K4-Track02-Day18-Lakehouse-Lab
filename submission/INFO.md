# Thông tin bài nộp

- Họ tên: **Trần Đại Nhân** (`TranDaiNhan`).
- MSSV: **2A202602642**.
- Mã bài: **K4-Track02-Day18**.
- Repository: [K4-Track02-Day18-TranDaiNhan-2A202602642-Lakehouse-Lab](https://github.com/hugebenevolence/K4-Track02-Day18-TranDaiNhan-2A202602642-Lakehouse-Lab).
- Đường chạy: **lightweight cho đủ NB1–NB8**; NB1–NB4 không dùng Spark.
- Môi trường: **CPython 3.11.16 x64**, Windows 11 Home Single Language,
  build **10.0.26200**. Dùng môi trường riêng `.venv` do uv tạo.
- Ngày thực thi: **05/10/2026, UTC+7**; timestamp chính xác trong
  [execution.json](evidence/execution.json).
- Dependencies thực thi: [requirements-lock.txt](requirements-lock.txt).
  Môi trường xuất PDF tách riêng: [requirements-artifacts.txt](requirements-artifacts.txt).
- Nguồn bài gốc: upstream VinUni-AI20k, baseline commit `f5d65ee`.
- Phạm vi AI: [AI_USAGE.md](AI_USAGE.md). Không dùng API key, model download
  hoặc dữ liệu thật của khách hàng; corpus được sinh bằng scripts của đề.

## Đọc bài

- [Bảng tổng hợp số đo thực tế](SUMMARY.md).
- [Notebook có output](notebooks/) và [ảnh kết quả](screenshots/).
- [Giải thích từng notebook](RESULTS.md), [reflection](REFLECTION.md).
- [Bonus architecture brief](bonus/ARCHITECTURE.md), [bản PDF 5 trang](bonus/ARCHITECTURE.pdf).
- [Log kiểm tra](logs/) và [metrics/hash thực thi](evidence/execution.json).

Ảnh chụp từ Chrome headless hiển thị HTML được trích trực tiếp từ output cell
bằng chứng cuối notebook. HTML nguồn nằm trong `evidence/`; đây là trang trình
bày output đã chạy, không phải ảnh giao diện Jupyter tương tác hay output giả.

## Tái lập trên Windows PowerShell

Chạy từ gốc repository. Cài lần đầu cần mạng; các notebook dùng dữ liệu local.
Nếu `py -3.11` trỏ đến Python đã gỡ, dùng `uv venv --python 3.11 .venv`.

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r submission/requirements-lock.txt
$env:PYTHONUTF8 = '1'
$env:LAKEHOUSE_ROOT = Join-Path (Get-Location) '_lakehouse'
.\.venv\Scripts\python.exe scripts/verify_lite.py
.\.venv\Scripts\python.exe scripts/generate_data_lite.py
.\.venv\Scripts\python.exe scripts/generate_ai_data.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_all.py
.\.venv\Scripts\python.exe scripts/build_submission.py
```

`build_submission.py` chạy từng notebook bằng Jupyter kernel của chính `.venv`,
dừng ngay nếu có lỗi, giữ output `.ipynb`, transcript và metrics/hash. Notebook
có cell bootstrap để cũng chạy được khi mở từ `submission/notebooks/`.
Không chạy đồng thời hai bản của cùng notebook: nguồn đề reset các bảng lab.
Generator NB4 có UUID ngẫu nhiên nên ID/file hash thay đổi khi tái tạo; seed
giữ phân phối dữ liệu. Tên file, transaction time và timing không cố định.

Để tái tạo PDF và screenshots (cần Chrome/Edge, font Arial của Windows):

```powershell
uv venv --python 3.11 .venv-artifacts
uv pip install --python .venv-artifacts/Scripts/python.exe -r submission/requirements-artifacts.txt
.\.venv-artifacts\Scripts\python.exe scripts/render_submission.py
.\.venv\Scripts\python.exe scripts/validate_submission.py
```

`validate_submission.py` đối chiếu metric với output notebook và hash file,
kiểm các ngưỡng rubric, 8 ảnh PNG và reflection ≤200 từ. Đánh giá chất lượng
giải thích và bonus vẫn thuộc người chấm; không tự quy đổi PASS thành điểm.

## Trạng thái gửi bài

Bài được chuẩn bị trong working tree local. Chưa commit/push, chưa mở PR hoặc
gửi liên kết qua kênh lớp. Không xem việc có thư mục submission là đã gửi bài.
Khi người nộp đã kiểm tra và chốt nội dung, dùng tiêu đề PR:

```text
[K4-Track02-Day18] TranDaiNhan - 2A202602642 - Lakehouse Lab [+bonus]
```

PR về repo đề bài và liên kết repo + PR + commit SHA thực tế phải gửi theo
`docs/SUBMISSION.md`. Ngày deadline cụ thể phụ thuộc lịch lớp/key coach.
