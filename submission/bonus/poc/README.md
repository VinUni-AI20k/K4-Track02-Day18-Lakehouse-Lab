# PoC — PII tokenization + schema contract + "0 PII trên đĩa"

PoC này chứng minh cơ chế khó nhất của [ARCHITECTURE.md](../ARCHITECTURE.md): **không có PII thô ở bất kỳ đâu trên đĩa,
kể cả trong lịch sử time travel**. Nó chạy được với chính stack lightweight của lab (PyIceberg + SQLite catalog + DuckDB),
không cần mạng hay API key.

## Chạy

Chạy từ thư mục gốc repo, sau khi đã cài `requirements.txt`:

```powershell
.\.venv\Scripts\python.exe submission/bonus/poc/pii_tokenize_medallion.py
```

```bash
.venv/bin/python submission/bonus/poc/pii_tokenize_medallion.py
```

Dữ liệu được ghi vào `_lakehouse/iceberg/poc_bonus/` (thư mục này đã nằm trong `.gitignore`) và bị reset mỗi lần chạy.

## Các bước PoC thực hiện

| Bước | Cơ chế | Kiểm tra (assert) |
|---|---|---|
| 1 | Writer tokenize email/phone/user bằng HMAC-SHA256 deterministic trước khi `append` | Quét mọi file Parquet trên đĩa: 0 match regex PII |
| 2 | Schema contract: batch có cột ngoài allowlist (`user_email`) bị reject sang DLQ | Không tạo snapshot mới |
| 3 | Gold: p50/p95/cost theo tenant cho mỗi bucket 5 phút, tính trên dữ liệu đã tokenize | 36 dòng, p50 ≤ p95 |
| 4 | Failure drill F1: writer lỗi commit PII thô → detect → `rollback_to_snapshot` → `expire_snapshots` → sweep file không còn được tham chiếu | Sau rollback, đĩa **vẫn còn** PII; sau expire + sweep thì 0 match; dữ liệu sạch còn nguyên 10,000 dòng |

Bài học quan trọng nhất của bước 4: **rollback chỉ đổi con trỏ snapshot hiện tại**. Dữ liệu bị lộ vẫn nằm trên đĩa và vẫn
đọc được qua time travel, cho đến khi snapshot bị expire và file bị sweep. Đây cũng là hai hành vi NB6 và NB8 đã đo được.

## Giới hạn

- Lần chạy đầu, detector báo **66 false positive**: token HMAC dạng hex đôi khi toàn chữ số
  (`<USER:010560272435>`), nên regex số điện thoại khớp vào giữa token. Đã sửa bằng word boundary. Bài học:
  detector và định dạng token phải được thiết kế cùng nhau, nếu không alert F1 sẽ báo động giả liên tục.
- Detector dùng regex cho email và số di động Việt Nam. Production cần thêm bộ phân loại PII
  (tên, địa chỉ, CCCD...) và phải đo tỉ lệ bỏ sót.
- Bước sweep tự tính phép hiệu tập hợp (giống `find_iceberg_orphans` trong NB6) và không có age guard, vì PoC chạy
  một mình. Production phải có age guard để không xóa file của writer đang chạy (xem cảnh báo trong NB6).
- Key HMAC lấy từ biến môi trường `PII_HMAC_KEY`, mặc định là một key chỉ dùng cho lab. Production đặt key trong KMS
  và có quy trình xoay key.
