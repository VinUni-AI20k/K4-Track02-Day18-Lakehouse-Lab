# K4-Track02-Day18 — Báo cáo Xác thực và Hướng dẫn Tái lập (Verification & Reproducibility)

- **Học viên:** Trần Tuấn Tú
- **MSSV:** 2A202602840
- **Mã bài lab:** K4-Track02-Day18 · Data Lakehouse Architecture
- **Đường chạy:** Lightweight path (`deltalake` 1.x, `pyiceberg`, `duckdb`, `polars`)
- **Môi trường:** Python 3.12.3 trên Linux (Ubuntu 24.04 LTS x86_64)

---

## 1. Kết quả Kiểm thử Toàn diện (Validation Summary)

Tất cả các bài kiểm tra đều được thực thi cục bộ từ đầu đến cuối với dữ liệu độc lập, đạt trạng thái **100% PASS**:

| Bộ kiểm tra | Lệnh thực thi | Kết quả | Thời gian | Ghi chú |
|---|---|:---:|:---:|---|
| **Smoke Test** | `python scripts/verify_lite.py` | **9/9 PASS** | 1.8s | Kiểm tra Delta, Iceberg catalog, vector DuckDB, Arrow zero-copy |
| **Pytest Suite** | `pytest -q` | **24/24 PASS** | 3.3s | Kiểm tra toàn bộ invariants, kiểu vector, schema, du, to_arrow |
| **Notebook Runner** | `python scripts/run_all.py` | **8/8 PASS** | 37.0s | Chạy headless tuần tự 8 notebook và kiểm tra assertions |
| **Bonus PoC** | `python submission/bonus/poc/poc_llm_observability.py` | **PASS** | 2.5s | Tokenize PII 118K req/s, Z-order skip 98% files, Gold metrics |

---

## 2. Hướng dẫn Tái lập Kết quả (Step-by-Step Reproduction)

Từ thư mục gốc của repository, chạy tuần tự các lệnh sau:

### Bước 1: Khởi tạo môi trường
```bash
make setup      # Tạo .venv và cài đặt dependencies
make smoke      # 9 bài kiểm tra nhanh (offline sau khi cài gói)
```

### Bước 2: Sinh dữ liệu kiểm thử
```bash
make data       # Sinh 200,000 dòng Bronze LLM traces cho NB4
make data-ai    # Sinh multimodal corpus & trajectory traces cho NB7 và NB8
```

### Bước 3: Chạy toàn bộ kiểm thử
```bash
make test       # Chạy 24 bài kiểm thử pytest
make run-all    # Thực thi tuần tự cả 8 notebooks lightweight
```

### Bước 4: Kiểm chứng Bonus PoC Spike (Tùy chọn)
```bash
./.venv/bin/python submission/bonus/poc/poc_llm_observability.py
```

---

## 3. Bằng chứng Sản phẩm Nộp trên Fork Cá nhân

Toàn bộ artifact được lưu trữ tại fork GitHub:
🔗 [https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab)

1. [**8 Notebooks đã thực thi**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/tree/main/submission/notebooks): Đầy đủ outputs, không có cell lỗi, lưu tại `submission/notebooks/`.
2. [**Ảnh chụp kết quả**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/tree/main/submission/screenshots): 8 ảnh chất lượng cao phủ từ NB1 đến NB8 tại `submission/screenshots/`.
3. [**Bài phản tư (Reflection)**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/blob/main/submission/REFLECTION.md): 177 từ về anti-pattern *Blind Vacuuming & Orphan Accumulation*.
4. [**Khai báo AI**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/blob/main/submission/AI_USAGE.md): Kê khai minh bạch công cụ và phạm vi hỗ trợ theo `docs/RULES.md`.
5. [**Architecture Brief & PDF**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/tree/main/submission/bonus): Tài liệu thiết kế hệ thống LLM Observability 1B req/ngày (`ARCHITECTURE.md` và `ARCHITECTURE.pdf`).
6. [**Mã nguồn PoC**](https://github.com/ngaiTu29s1/K4-Track02-Day18-TranTuanTu-2A202602840-Lakehouse-Lab/blob/main/submission/bonus/poc/poc_llm_observability.py): Script spike chạy được kiểm chứng tokenization và Z-order skipping.

---

## 4. Phạm vi & Giới hạn Kiểm chứng (Scope & Limitations)

- **Mô phỏng PoC:** PoC là bản thử nghiệm cục bộ (local spike); throughput production 1B req/ngày, khả năng bao phủ PII bằng mô hình NER phức tạp và an toàn concurrency ở quy mô hàng trăm nodes là mục tiêu của thiết kế MVP cần kiểm chứng tiếp trên cụm thực tế.
- **Đường Spark/Docker:** Container Spark / Apple container không được chạy lại trong bài nộp này do học viên chọn thực hiện toàn diện trên đường lightweight tiêu chuẩn (deltalake 1.x, pyiceberg, duckdb, polars).
- **Tính toàn vẹn mã nguồn:** Toàn bộ kiểm thử được chạy mà không sửa đổi hoặc hạ thấp bất kỳ điều kiện assertion/ngưỡng đánh giá nào của đề bài gốc.
