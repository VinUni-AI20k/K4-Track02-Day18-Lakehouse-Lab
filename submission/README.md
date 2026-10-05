# Bài làm Lakehouse Lab — Hoang Thai Dat — 2A202602959

Bài bắt buộc được thực thi trên Windows/Python 3.11.3 bằng đường lightweight.
Dependencies được cài bằng **uv**. Bộ bài nộp gồm tám notebook có output và
diễn giải, tám ảnh render kết quả, reflection, thông tin người nộp và khai AI.
Bonus A nằm trong [bonus/ARCHITECTURE.md](bonus/ARCHITECTURE.md), kèm PDF 6 trang,
PoC đã chạy và phép tính chi phí. Xem [hướng dẫn/checklist bonus](bonus/README.md).
Tất cả được chuẩn bị ở local để review, không push hoặc tạo PR.

| Notebook | Kết quả từ output đã lưu | Bằng chứng |
|---|---|---|
| [NB1 — Delta basics](notebooks/01_delta_basics.ipynb) | 2 commit JSON; `age='thirty'` bị chặn; thêm tier; 2 nhóm tier | [PNG](screenshots/01_delta_basics.png) |
| [NB2 — Optimize/Z-order](notebooks/02_optimize_zorder.ipynb) | 200 → 55 file; median 205,72 → 18,24 ms; speedup 11,28×; pruning 55× | [PNG](screenshots/02_optimize_zorder.png) |
| [NB3 — Time travel](notebooks/03_time_travel.ipynb) | MERGE 100K: 50K update + 50K insert; history 5 version gồm RESTORE; score âm = 0 | [PNG](screenshots/03_time_travel.png) |
| [NB4 — Medallion](notebooks/04_medallion.ipynb) | Bronze 200.000 → Silver 190.052; Gold 8 ngày × 3 model; đối chiếu Gold độc lập PASS | [PNG](screenshots/04_medallion.png) |
| [NB5 — Iceberg/catalog](notebooks/05_iceberg_catalog.ipynb) | Lọc ts: 10 → 1 file, pruning 10×; field ID 4 giữ nguyên; spec 1/2; đọc đủ 5.500 dòng | [PNG](screenshots/05_iceberg_catalog.png) |
| [NB6 — Maintenance](notebooks/06_maintenance.ipynb) | Compact 200 → 11 file (18,18×); skip 90%; vacuum thu hồi 16.908.228 B; xóa 3 orphan; Iceberg 20 → 3 snapshot, sweep 17 list; checkpoint tồn tại | [PNG](screenshots/06_maintenance.png) |
| [NB7 — Vectors/multimodal](notebooks/07_vectors_multimodal.ipynb) | Amplification 200,05×; int8 nhỏ 5,80×; recall@10 0,904; fidelity 1,000; lifecycle bug 0 hit trong bảng / 8 ở index cũ; CDF 8 delete | [PNG](screenshots/07_vectors_multimodal.png) |
| [NB8 — Agents/provenance](notebooks/08_agents_provenance.ipynb) | 2 policy; pin v0 replay 1.578 bước (latest 1.978); 5 lượt list/1 read; input_required; task completed; loại 334 UNCLASSIFIED; subject 8 → 0 | [PNG](screenshots/08_agents_provenance.png) |

Các ngưỡng đo được đạt rubric; đây không phải điểm do giảng viên chấm.
Số liệu máy đọc được ở [metrics.json](evidence/metrics.json).
Notebook giữ output gốc, execution count và timestamp từng code cell; Markdown
cuối notebook giải thích cơ chế và giới hạn phép đo.

## Kiểm tra đã thực hiện

- [Smoke](evidence/smoke.log): 9/9 checks.
- [Pytest](evidence/pytest.log): 24/24 tests. Có cảnh báo ghi cache do sandbox Windows;
  không có test thất bại.
- [Headless runner](evidence/run-all.log): 8/8 notebook PASS, 46,8 giây ở lần chạy ghi log.
- [Kiểm tra artifacts](evidence/submission-validation.log): đủ tám notebook, tất cả
  code cell đã chạy theo thứ tự, không error output; metrics trùng output; đủ tám PNG;
  các ngưỡng số học đạt yêu cầu; reflection 199 từ theo cách đếm whitespace.
- [SHA-256](evidence/artifact-sha256.json): checksum của notebook và ảnh.

PNG được render từ stdout thực tế, không phải ảnh chụp giao diện ứng dụng;
nhãn trên ảnh nêu rõ nguồn notebook. Nếu coach yêu cầu screenshot giao diện,
cần chụp bổ sung từ notebook đã lưu. Lần đầu tạo kernel trong sandbox Windows
bị chặn khi Jupyter thiết lập ACL file kết nối; lần chạy được cấp quyền đã hoàn tất
tám notebook. Không thay đổi cơ chế bảo vệ file kết nối.

## Tái lập bằng uv trên PowerShell

Chạy từ thư mục gốc repository:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
uv pip install --python .\.venv\Scripts\python.exe pillow nbclient
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/verify_lite.py
.\.venv\Scripts\python.exe scripts/generate_data_lite.py
.\.venv\Scripts\python.exe scripts/generate_ai_data.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_all.py
.\.venv\Scripts\python.exe scripts/prepare_submission.py
.\.venv\Scripts\python.exe scripts/validate_submission.py
```

`prepare_submission.py` thực thi mỗi notebook trong kernel riêng, dùng đúng Python
đang chạy script; notebook có bootstrap tìm repo nên cũng mở/chạy lại được từ
`submission/notebooks/`. Script ghi đè bản output trước đó khi chạy lại.
Nếu chỉ muốn tạo lại PNG từ output đã có:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_submission.py --render-only
```

Trong lần thực thi này, Pillow 11.1.0 có sẵn ở Python nền được dùng riêng để render
ảnh; kernel vẫn chỉ dùng dependencies `.venv`. Với clean setup, file
hai lệnh `uv pip install` phía trên cài thêm Pillow/nbclient vào `.venv`.
[requirements-lock.txt](evidence/requirements-lock.txt) ghi đầy đủ phiên bản
dependencies kernel đã dùng. Để tái lập đúng phiên bản, cài lockfile thay cho
requirements chính, rồi cài Pillow nếu Python nền chưa có sẵn.

## Đọc kết quả đúng phạm vi

NB4 có tám ngày thực tế dù generator tạo timestamp trong bảy ngày UTC.
DuckDB trên máy có `TimeZone = Asia/Saigon`; `CAST(ts AS DATE)` dùng múi giờ
session nên khoảng này cắt qua tám ngày lịch địa phương. Bài giữ nguyên query
của đề; coverage vẫn đạt yêu cầu ≥ 7 ngày × 3 model. Khi dashboard cần ngày UTC,
phải đặt TimeZone UTC hoặc chuyển đổi rõ ràng trước khi group. Cost dùng giá
minh họa của đề.

NB6 đo hành vi deltalake 1.6.6 và PyIceberg 0.12.0 trong scratch local; orphan
sweep minh họa không thay thế GC production có retention, coordination và kiểm
tra mọi snapshot/reader đang dùng.

NB7 amplification là tỷ số byte từ footer row group, không phải trace I/O.
Recall/fidelity đo trên fixture tổng hợp với 100 query và top-k có self-match;
không suy rộng sang corpus production. External index được mô phỏng bằng bản
sao bảng; CDF đã phát delete nhưng chưa có consumer áp dụng delete vào index.

NB8 là mô phỏng offline. Cache được đo ở `list_tables`; `confirmed` là cờ caller
truyền; replay kiểm tra row count; bốn bucket không phải chứng chỉ tuân thủ.
CC-BY trong fixture được gán `public_domain` dù giấy phép có điều kiện ghi công.
Subject delete chỉ áp dụng current version, không xóa các bản lịch sử.

## Hoàn tất nộp bài

Đọc và đối chiếu [INFO.md](INFO.md), tự xem lại [REFLECTION.md](REFLECTION.md)
và [AI_USAGE.md](AI_USAGE.md), rồi chạy lại những phần cần giải thích.
Mô tả PR chuẩn bị ở [PULL_REQUEST.md](PULL_REQUEST.md).
Chưa commit/push hoặc tạo PR trong phiên này. Khi nộp, cần liên kết repository,
PR và commit SHA qua kênh lớp theo [SUBMISSION.md](../docs/SUBMISSION.md).
Không commit `.venv/`, `_lakehouse/`, cache hay blobs sinh ra.
