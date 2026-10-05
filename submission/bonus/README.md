# Bonus A - bản để người nộp review

Deliverable chính là [ARCHITECTURE.md](ARCHITECTURE.md); bản [PDF 6 trang](ARCHITECTURE.pdf)
được render từ cùng nguồn. Không có triển khai AWS, tài nguyên trả phí, commit hay push.

| Yêu cầu của đề/rubric | Vị trí để kiểm tra |
|---|---|
| Problem statement <=200 từ | Mục 1, đếm theo whitespace trong validation |
| Một diagram và >=4 concepts Day18 áp dụng | Mục 1: medallion, ACID snapshots, partition/clustering, catalog, retention/GC, lineage, governance |
| >=5 decisions, mỗi decision >=2 alternatives | Mục 2-3: D1-D6, tổng 6 decisions và 12 alternatives |
| >=3 failure modes, detect + rollback, có Day18 | Mục 4: F1-F6; F2 time travel/GC, F3 schema evolution/lineage |
| Storage + compute với phép tính và nguồn | Mục 5, cost script và evidence giá public |
| Slice MVP một tuần, acceptance và hardest mechanism | Mục 6, ngày 1-7, crash/replay/correction và gates |
| Optional notebook 50-150 dòng, có output | [Jupytext source](poc/replay_safe.py), [ipynb](poc/replay_safe.ipynb), [kết quả](evidence/poc-result.json) |
| Giới hạn 3-6 trang | PDF có đúng 6 trang; đã xem PNG từng trang |

Kiểm tra tổng hợp lưu ở [validation.json](evidence/validation.json), checksum artifacts
ở [artifact-sha256.json](evidence/artifact-sha256.json). Không tự nhận điểm của coach.

## Chạy từ clean checkout bằng uv

PoC không phụ thuộc dữ liệu lab hay warehouse có sẵn. Chạy từ repo root trên PowerShell:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .\.venv\Scripts\python.exe -r submission/bonus/requirements-bonus.txt
.\.venv\Scripts\python.exe -X utf8 submission/bonus/poc/replay_safe.py
.\.venv\Scripts\python.exe -X utf8 submission/bonus/tools/execute_poc.py
.\.venv\Scripts\python.exe -X utf8 submission/bonus/tools/cost_model.py
.\.venv\Scripts\python.exe -X utf8 submission/bonus/tools/render_architecture.py
.\.venv\Scripts\python.exe -X utf8 submission/bonus/tools/validate_bonus.py
```

Để giữ môi trường lab hiện có, chỉ chạy dòng `uv pip install` vào `.venv` đó;
không cần tạo lại venv. Notebook cũng mở/rerun trực tiếp từ thư mục `poc/` được,
miễn chọn kernel đã cài dependencies. Code tự tìm repo root và tạo scratch mới
bên dưới `_lakehouse/bonus-replay-*`, giải phóng SQLite handles rồi dọn scratch
khi chạy thành công. Không dùng AWS credentials/network trong PoC/cost/render/validate.

Đã kiểm tra PoC trong **venv riêng không kế thừa dependencies của lab**,
cài bằng uv từ requirements bonus; lưu stdout trong `evidence/clean-environment.log`.
Notebook có 3 code cells; warning PyIceberg "Delete operation did not match any
records" khi upsert đầu tiên là delete phía match trên bảng rỗng, assertions vẫn chạy.
Trên sandbox Windows, Jupyter đặt ACL file kết nối bị chặn; lần thực thi đã cấp quyền
chạy thành công. Không bật insecure-writes để vượt qua cơ chế ACL.

## Evidence giá và render

Giá S3 lưu kèm SKU, region, unit, effective date, thời điểm tải và offer version
trong [JSON](evidence/aws-s3-price-evidence.json). Muốn cập nhật giá, chạy
`tools/fetch_price_evidence.py` rồi cost model; bước fetch cần Internet và làm thay đổi
evidence. Kinesis/Fargate/Glue/Athena dùng rates public được kiểm tra 05/10/2026,
liên kết chính thức trong architecture và cost model; không gọi account API.

Renderer hiện dùng Arial/Consolas có sẵn trên Windows. Trên Linux cần đổi FONTDIR/
FONT_FILES sang font TTF tương đương hỗ trợ tiếng Việt. PDF đi kèm đọc được mọi máy;
PoC/cost model không có phụ thuộc font hay Windows. Poppler không có trên máy này;
PyMuPDF được dùng để render PNG kiểm tra ở `tmp/pdfs/bonus/` (scratch, không phải bài nộp).

## Ba điểm cần đọc kỹ khi bảo vệ thiết kế

- Nén detail >=4:1, 10K tenant/3 model và peak 5x là assumptions phải đo; tháng 31 ngày
  storage+Kinesis khoảng 4.971,56 USD, chỉ dư 28,44 USD ngoài reserve 100 USD. Case 3:1
  không đạt cap; budget alarm không tự tạo bảo đảm hard cap.
- Full detail đọc 7 ngày, physical purge tối đa 24h sau TTL. Nếu yêu cầu xóa mọi byte
  đúng giây thứ 7 ngày thì phải sửa cơ chế và review lại; chi phí hiện đã tính 8 ngày occupancy.
- PoC chứng minh logic một writer, replay và snapshot lineage trên fixture nhỏ.
  Nó không chứng minh throughput 1B/ngày, redaction toàn diện hay GC/IAM trên AWS.

Khai báo AI ở [AI_USAGE.md](../AI_USAGE.md); người nộp cần tự review, rerun và giải thích.
Tên PR dự thảo ở [PULL_REQUEST.md](../PULL_REQUEST.md) có `[+bonus]`; không tạo PR trong phiên này.
