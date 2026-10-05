# Thông tin người nộp

| Mục | Nội dung |
|---|---|
| Họ và tên | Phung Thanh An |
| MSSV | 2A202603006 |
| Mã bài | K4-Track02-Day18 |
| Đường chạy | **Lightweight** cho cả 8 notebook (deltalake + pyiceberg + DuckDB + Polars; không Spark, không Docker) |
| Hệ điều hành | $PRETTY_NAME |
| Python | Python 3.12.14 |
| Cài đặt | `make setup` (uv venv) |

## Kết quả kiểm tra

| Lệnh | Kết quả |
|---|---|
| `make smoke` | 9/9 PASS |
| `make test` | 24 passed |
| `make run-all` | 8/8 passed (17.1s) |

## Số liệu chính

| NB | Kết quả | Ngưỡng |
|---|---|---|
| NB2 | 200 → 55 file; speedup 10.5×; pruning 55× (1/55 file chứa user_id=4242) | ≥100 file, ≥3× hoặc ≥10× |
| NB3 | 5 version, có RESTORE; score<0 sau restore = 0 | ≥5 version |
| NB4 | Bronze 200,000 → Silver 190,052 (dedup 9,948) → Gold 7 ngày × 3 model | Silver<Bronze, ≥7 ngày |

## Ghi chú

- Không sửa logic hay ngưỡng của notebook đề bài; có thêm Markdown cell giải thích số liệu
  và một cell kiểm tra bổ sung ở NB4 (p50≤p95, cost>0, error_rate∈[0,1]).
- File thêm vào repo: `docs/HUONG-DAN-LAB.md` (ghi chú quy trình) và
  `scripts/check_submission.py` (script chỉ đọc, soát bài nộp trước khi commit).
- Khai sử dụng AI: xem [AI_USAGE.md](AI_USAGE.md).
