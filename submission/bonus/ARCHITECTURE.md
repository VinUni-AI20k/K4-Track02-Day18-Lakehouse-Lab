# KIẾN TRÚC LAKEHOUSE CHO HỆ THỐNG LLM OBSERVABILITY TẠI QUY MÔ 1 TỶ REQUESTS/NGÀY

**Tác giả:** Nguyễn Thành Nam  
**Mã sinh viên:** 2A3202602694  
**Chủ đề lựa chọn:** Topic A — LLM Observability ở quy mô 1B requests/ngày (1 Billion requests/day)  
**Phạm vi:** Architecture Brief bảo vệ trước Hội đồng Thẩm định Kỹ thuật (Design Review)  

---

## 1. Problem Statement (Tuyên bố bài toán & Ràng buộc cốt lõi)

Hệ thống cung cấp dịch vụ Foundation Model API xử lý trung bình **1.000.000.000 (1 tỷ) requests/ngày**. Mỗi request có payload trung bình ~5 KB (bao gồm metadata, prompt, completion, latency, token usage), tương ứng khối lượng dữ liệu thô sinh ra là **5 TB/ngày** (150 TB/tháng, 1.8 PB/năm chưa nén).

### Các yêu cầu và ràng buộc nghiêm ngặt:
1. **SLA Dashboard phân tích:** Cung cấp dashboard trực quan hóa chi phí (cost) và độ trễ (latency p50/p95/p99) theo từng `tenant_id`, chu kỳ cập nhật dữ liệu (freshness) tối đa **mỗi 5 phút**, thời gian phản hồi truy vấn **p95 < 2 giây**.
2. **Chính sách vòng đời (Retention & Lifecycle):**
   - Dữ liệu chi tiết chứa toàn bộ prompt/response thô được lưu trữ **đúng 7 ngày** phục vụ điều tra sự cố (incident review) và kiểm tra chất lượng mô hình, sau đó phải tự động thu hồi/xóa vĩnh viễn.
   - Dữ liệu tổng hợp (aggregates) phục vụ báo cáo tài chính và xu hướng sử dụng theo tenant được lưu giữ trong vòng **1 năm (365 ngày)**.
3. **Bảo mật & Quyền riêng tư (Privacy & PII):** Thông tin định danh cá nhân (PII: email, số điện thoại, API key, thẻ tín dụng) phải được phát hiện và mã hóa/tokenization ngay tại thời điểm ghi vào tầng Bronze, ngăn chặn tuyệt đối việc dữ liệu PII nhạy cảm rò rỉ tới người dùng, analyst hoặc downstream jobs.
4. **Trần ngân sách FinOps cố định:** Tổng chi phí lưu trữ (Storage budget) trên Cloud Object Storage bị giới hạn trần cứng là **≤ $5.000 / tháng**.

---

## 2. Architecture Diagram (Sơ đồ Kiến trúc Tổng thể)

Hệ thống triển khai theo mô hình **Medallion Architecture 3 tầng** chuẩn mực, kết hợp hạ tầng Cloud Storage tiering và bộ điều phối bảng Lakehouse (Delta Lake / Apache Iceberg).

```
                      INGESTION PATH (Peak: ~25.000 req/s)
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           │ LLM Gateway / Inference Proxy (Rust / Envoy)        │
           │ Streaming Payload Buffer + In-Flight PII Tokenizer  │
           └──────────────────────────┬──────────────────────────┘
                                      │ Streaming Micro-batch (60s)
                                      ▼
    ═════════════════════════════════════════════════════════════════════════════
    TẦNG BRONZE: RAW LOGS (Append-Only Landing Zone)
    Storage: S3 Standard / MinIO Hot Tier (Retention: 7 ngày)
    Format : Delta Lake Table (`bronze.llm_calls_raw`)
    Layout : Partition theo `event_date` (yyyy-mm-dd)
    Security: PII đã được Tokenized / Salted HMAC-SHA256 tại Ingestion
    ═════════════════════════════════════════════════════════════════════════════
                                      │
                                      │ Continuous Spark Structured Streaming (5-min trigger)
                                      │ JSON Parse, Schema Validation & Dedup by `request_id`
                                      ▼
    ═════════════════════════════════════════════════════════════════════════════
    TẦNG SILVER: CLEANED & CURATED CALLS
    Storage: S3 Standard -> S3 Express / One Zone (Retention: 7 ngày)
    Format : Delta Lake with Z-ORDER (`[tenant_id, event_time]`)
    Layout : Partition theo `event_date`, Target File Size: 128 MB (Snappy Parquet)
    Mục đích: Phục vụ Incident Investigation, Deep-dive Analysis, Error Debugging
    ═════════════════════════════════════════════════════════════════════════════
                                      │
                                      │ Micro-batch Aggregate Job (5-minute rolling cadence)
                                      │ Group By (tenant_id, window(event_time, 5m), model)
                                      ▼
    ═════════════════════════════════════════════════════════════════════════════
    TẦNG GOLD: TENANT BUSINESS METRICS
    Storage: S3 Infrequent Access (Retention: 365 ngày)
    Format : Delta Lake / Iceberg Catalog Table (`gold.tenant_hourly_metrics`)
    Layout : Partition theo `metric_date`, Z-ORDER theo `tenant_id`
    Metrics: p50/p95/p99 latency, prompt/completion tokens, cost_usd, error_rate
    ═════════════════════════════════════════════════════════════════════════════
                                      │
                    QUERY PATH (Ad-hoc BI & Customer Dashboards)
                                      │
         ┌────────────────────────────┴────────────────────────────┐
         │ Query Engines: DuckDB / Trino / Photon (Stat Skipping)  │
         │ Point Query: `WHERE tenant_id = 't_123' AND date = ...` │
         │ Latency: p95 < 200 ms (Gold) | p95 < 1.8 s (Silver)     │
         └─────────────────────────────────────────────────────────┘
```

### Các concepts Day18 được tích hợp trực tiếp:
1. **Medallion Layout & Ingestion Contract:** Phân tầng dữ liệu nghiêm ngặt; Bronze cô lập dữ liệu thô, Silver chuẩn hóa/dedup, Gold nén chiều dữ liệu phục vụ dashboard thời gian thực.
2. **ACID Transaction Log & File Compaction:** Giải quyết dứt điểm Small-File Problem thông qua cơ chế tự động auto-compacting với `target_size = 128 MB`.
3. **Data Skipping & Multi-dimensional Clustering (Z-ORDER):** Sắp xếp đồng vị trí theo `(tenant_id, event_time)` giúp các câu truy vấn lọc theo tenant bỏ qua (prune) > 95% số file Parquet không liên quan.
4. **Lifecycle Expiry & VACUUM Coordination:** Thực thi chính sách thu hồi dung lượng tự động, xâu chuỗi giữa snapshot expiry và vật lý vacuum sau 7 ngày để tuân thủ ngân sách FinOps.

---

## 3. Quyết định Kiến trúc Chính & Đánh đổi (Key Decisions & Rejected Alternatives)

Mỗi quyết định dưới đây là một kết quả phân tích kỹ thuật thấu đáo, có so sánh định lượng với ít nhất hai giải pháp thay thế.

---

### Quyết định 1: Định dạng bảng lưu trữ (Table Format) — Chọn Delta Lake
- **Lựa chọn:** **Delta Lake (v3.2+)** làm định dạng bảng nền tảng cho cả 3 tầng Bronze, Silver và Gold.
- **Lý do & Lợi thế:**
  - Delta Lake hỗ trợ xuất sắc tính năng **Z-ORDER** và **Liquid Clustering** trên nhiều cột phân tán (`tenant_id`, `event_time`) với chi phí tính toán thấp.
  - Tích hợp tính năng **Deletion Vectors** (từ Delta 2.4+) cho phép thực hiện cập nhật/xóa bản ghi PII hoặc GDPR requests mà không phải rewrite lại toàn bộ file Parquet 128 MB.
  - Hỗ trợ **Change Data Feed (CDF)** native, cho phép tầng Silver và Gold stream các bản ghi mới/thay đổi mà không cần quét lại toàn bộ partition.
- **Alternative 1 bị loại — Apache Iceberg:**
  - *Lý do loại:* Mặc dù Iceberg có Hidden Partitioning rất mạnh, nhưng khả năng Z-order / Micro-clustering của Iceberg (qua Spark procedure `rewrite_data_files`) đòi hỏi tài nguyên tính toán shuffle lớn hơn nhiều so với Delta khi chạy trên các micro-batch 5 phút. Ngoài ra, Deletion Vectors của Iceberg (Equality Deletes v2) gây suy giảm nghiêm trọng hiệu năng đọc (read-amplification) đối với các công cụ query như Trino/DuckDB khi số lượng delete files tăng lên.
- **Alternative 2 bị loại — Apache Hudi:**
  - *Lý do loại:* Hudi hỗ trợ Merge-On-Read (MOR) tốt cho write tốc độ cao, nhưng độ phức tạp vận hành của Hudi timeline metadata quá lớn, cộng đồng hỗ trợ cho các lightweight reader như DuckDB/Polars kém ổn định hơn Delta-rs và PyIceberg.

---

### Quyết định 2: Chiến lược phân vùng và gom cụm (Partitioning & Clustering Strategy)
- **Lựa chọn:** **Partition theo `event_date` (yyyy-mm-dd)** kết hợp **Z-ORDER theo `[tenant_id, event_time]`** ở tầng Silver và Gold.
- **Lý do & Lợi thế:**
  - Ở quy mô 1 tỷ req/ngày, việc partition theo `tenant_id` sẽ tạo ra hơn 50.000 thư mục con mỗi ngày (nếu có 50.000 tenants), gây ra thảm họa **Metadata Explosion** và **Small-File Problem** cấp tính trên S3 (quá nhiều file < 1 MB).
  - Phân vùng theo `event_date` chia đều 5 TB/ngày thành một không gian lưu trữ đồng nhất, cho phép job xóa dữ liệu 7 ngày hoạt động cực kỳ đơn giản bằng cách drop toàn bộ partition folder cũ.
  - Bên trong mỗi partition ngày, Z-ORDER theo `[tenant_id, event_time]` sẽ gom các bản ghi của cùng một khách hàng vào 1 hoặc 2 file Parquet liền kề. Kết quả: truy vấn dashboard lọc theo tenant chỉ đọc đúng 0,1% số file của ngày hôm đó (Pruning ratio > 50×).
- **Alternative 1 bị loại — Phân vùng trực tiếp theo `tenant_id` (Physical Hive Partitioning):**
  - *Lý do loại:* Gây bùng nổ phân mảnh thư mục (partition sprawl). Các tenant nhỏ (low-volume) chỉ sinh vài KB log mỗi giờ, tạo ra hàng triệu file tí hon, vi phạm quy tắc 128 MB của Parquet.
- **Alternative 2 bị loại — Chỉ partition theo ngày và không cluster (Random Append):**
  - *Lý do loại:* Dữ liệu của mỗi tenant bị rải rác ngẫu nhiên trên toàn bộ 40.000 file của một ngày. Khi tenant xem dashboard, query engine buộc phải tải và quét toàn bộ 5 TB của ngày hôm đó, khiến latency vượt quá 60 giây và chi phí quét S3 tăng vọt.

---

### Quyết định 3: Xử lý bảo mật PII — Tokenization & Hashing tại tầng Ingestion
- **Lựa chọn:** **Pseudonymization & Salting Tokenization tại Ingestion Gateway (Rust Proxy)** trước khi ghi vào Bronze.
- **Lý do & Lợi thế:**
  - Tại tầng Proxy/Gateway, một engine regex hiệu năng cao (Hyperscan) quét các trường `prompt` và `response` để nhận diện các mẫu PII (Email, Phone, Credit Card, SSN, API Keys).
  - Các giá trị PII được thay thế bằng token dạng: `[PII_EMAIL_hash]` với hàm băm `HMAC-SHA256(val, secret_salt)`. Secret salt được lưu trữ trong AWS KMS / HashiCorp Vault với chu kỳ xoay khóa (key rotation) định kỳ.
  - Dữ liệu rơi vào tầng Bronze đã hoàn toàn ẩn danh, cho phép mở rộng quyền truy cập kiểm toán cho đội ngũ kỹ sư và data analyst mà không vi phạm GDPR hay ISO 27001.
- **Alternative 1 bị loại — Redact / Tokenize sau đó ở tầng Silver (Post-processing ETL):**
  - *Lý do loại:* Dữ liệu PII thô sẽ tồn tại trên tầng Bronze ít nhất 5 đến 15 phút. Nếu có sự cố rò rỉ tại tầng lưu trữ Bronze hoặc nhân viên nội bộ có quyền truy cập storage, dữ liệu nhạy cảm sẽ bị phơi bày hoàn toàn.
- **Alternative 2 bị loại — Mã hóa toàn bộ dữ liệu (Envelope Encryption per Row):**
  - *Lý do loại:* Mã hóa toàn bộ nội dung dòng khiến Parquet mất hoàn toàn khả năng nén (Snappy/ZSTD không thể nén chuỗi ngẫu nhiên được mã hóa) và vô hiệu hóa hoàn toàn cơ chế Data Skipping / Min-Max stats, làm dung lượng lưu trữ tăng gấp 4 lần.

---

### Quyết định 4: Chiến lược Ingestion & Deduplication — Micro-batch 60s & Window Dedup
- **Lựa chọn:** **Spark Structured Streaming với Trigger 60 giây**, ghi vào Bronze; tầng Silver dedup bằng **Stateful Streaming với Watermark 15 phút** dựa trên `request_id`.
- **Lý do & Lợi thế:**
  - Micro-batch 60 giây tại Ingestion cho phép gom đủ dữ liệu (~3,5 GB / phút) để ghi các file Parquet kích thước lớn ngay từ đầu, hạn chế sinh small-files.
  - Tầng Silver sử dụng cơ chế Watermark 15 phút (`withWatermark("event_time", "15 minutes").dropDuplicates(["request_id"])`). Mọi bản ghi gửi lại (network retry) trong vòng 15 phút đều bị lọc bỏ tự động mà chỉ tốn lượng RAM trạng thái tối thiểu (~2 GB RAM state store).
- **Alternative 1 bị loại — Streaming liên tục (Continuous Processing với Trigger 1s):**
  - *Lý do loại:* Ghi mỗi giây sẽ sinh ra 86.400 commit/ngày và hàng triệu file Parquet dung lượng vài chục KB. Hệ thống sẽ sập sau chưa đầy 6 giờ do nghẽn metadata log của Lakehouse.
- **Alternative 2 bị loại — Batch deduplication theo ngày (Nightly Deduplication):**
  - *Lý do loại:* Vi phạm nghiêm trọng SLA dashboard 5 phút. Khách hàng và hệ thống giám sát không thể chờ đến cuối ngày mới có dữ liệu sạch để phát hiện lỗi.

---

### Quyết định 5: Chiến lược Lưu trữ & FinOps Tiering — S3 Lifecycle + VACUUM
- **Lựa chọn:** **S3 Standard cho 7 ngày đầu**, tự động **chuyển Gold sang S3 Standard-Infrequent Access (IA)**, và cấu hình **Delta VACUUM RETAIN 168 HOURS (7 ngày)**.
- **Lý do & Lợi thế:**
  - Bronze và Silver chỉ cần tồn tại 7 ngày. Sau khi hết 7 ngày, một job định kỳ kích hoạt lệnh xóa partition (`DELETE WHERE event_date < CURRENT_DATE - 7`) kết hợp `VACUUM bronze RETAIN 168 HOURS` để giải phóng hoàn toàn dung lượng vật lý trên S3.
  - Bảng Gold có dung lượng cực nhỏ (chỉ ~150 MB/ngày sau khi aggregate) nên được giữ 365 ngày trên tầng lưu trữ S3 Infrequent Access ($0.0125/GB-tháng), tối ưu tuyệt đối chi phí dài hạn.
- **Alternative 1 bị loại — Lưu toàn bộ 150 TB/tháng trên S3 Standard không xóa:**
  - *Lý do loại:* Chi phí lưu trữ tháng đầu tiên là $3.450, nhưng sau 1 năm tích lũy 1,8 PB, chi phí sẽ vượt quá **$41.400 / tháng**, vượt gấp 8 lần ngân sách CFO cho phép.
- **Alternative 2 bị loại — Đẩy toàn bộ Bronze/Silver vào S3 Glacier Flexible Archive sau 24h:**
  - *Lý do loại:* Glacier có thời gian tối thiểu lưu giữ (minimum retention charge) là 90 ngày. Nếu xóa sau 7 ngày, AWS vẫn phạt tiền lưu trữ đủ 90 ngày. Ngoài ra, việc đọc lại dữ liệu điều tra sự cố mất từ 3–5 giờ để khôi phục (restore delay), vi phạm yêu cầu incident response.

---

## 4. Failure Modes & Kịch bản Khắc phục Sự cố 3:00 AM (Disaster Recovery & Rollback)

Mọi hệ thống quy mô lớn đều sẽ gặp sự cố. Dưới đây là 3 kịch bản lỗi chí mạng tại thời điểm 3:00 AM và quy trình khắc phục:

---

### Kịch bản 1: Pipeline Ingestion bị ngắt đột ngột lúc đang nén file (Crash Mid-Compaction) dẫn tới Orphan Files
- **Triệu chứng & Phát hiện:**
  - Cảnh báo FinOps CloudWatch kích hoạt lúc 3:15 AM: Dung lượng bucket S3 tăng thêm 400 GB nhưng số lượng record trong dashboard `DeltaTable.count()` không thay đổi.
  - Reader bắt đầu gặp độ trễ cao khi quét thư mục do có nhiều file rác không được commit.
- **Nguyên nhân gốc rễ:**
  - Job bảo trì `OPTIMIZE` đang đọc 1.000 file nhỏ và chuẩn bị ghi 10 file lớn thì worker node của Spark bị Spot Instance Termination (AWS thu hồi máy ảo). Các file Parquet mới đã được ghi một phần xuống S3 nhưng transaction log chưa nhận commit `add`. Đây là các **Uncommitted Orphan Files** mà lệnh `VACUUM` log-based thông thường không thể nhìn thấy.
- **Quy trình Rollback & Khắc phục:**
  1. Chạy công cụ rà soát Orphan chuyên dụng: Quét danh sách file thực tế trên storage và so sánh với tập hợp các file hợp lệ trong transaction log mới nhất (`live_files = dt.file_uris()`).
  2. Áp dụng quy tắc an toàn **Age Guard (min_age = 6 hours)** để đảm bảo không xóa nhầm các file đang được ghi bởi các writer in-flight khác.
  3. Lọc danh sách các file orphan có tuổi thọ > 6 giờ và gọi lệnh xóa trực tiếp thông qua S3 Batch Delete API.
  4. Khởi động lại job `OPTIMIZE` trên một On-Demand Spark instance để đảm bảo quá trình compaction hoàn tất trọn vẹn.

---

### Kịch bản 2: Model Gateway triển khai phiên bản mới bị lỗi sinh schema dị biệt (Poison Micro-batch & Schema Drift)
- **Triệu chứng & Phát hiện:**
  - Alert PagerDuty lúc 3:20 AM: Tầng Silver streaming job bị crash liên tục với lỗi `DeltaError: Schema mismatch detected`.
  - Một team phát triển vừa release gateway mới, đổi trường `latency_ms` (integer) thành `latency_ms: {client: 12, server: 45}` (JSON struct lồng nhau) mà không thông báo.
- **Nguyên nhân gốc rễ:**
  - Vi phạm Schema Enforcement tại tầng Silver. Toàn bộ pipeline ghi nhận độ trễ (pipeline lag) tăng từ 2 phút lên 20 phút do luồng xử lý bị chặn.
- **Quy trình Rollback & Khắc phục:**
  1. Cấu hình tầng Ingestion kích hoạt cơ chế **Dead-Letter Queue (DLQ)**: Mọi payload có schema không tương thích được tự động chuyển hướng vào bảng `bronze.llm_calls_quarantine` thay vì làm nghẽn luồng xử lý chính.
  2. Sử dụng tính năng **Schema Evolution có kiểm soát**: Đối với các trường hợp mở rộng hợp lệ, áp dụng migration script thêm cột mới `latency_breakdown` (struct) và giữ nguyên cột cũ `latency_ms` (bằng tổng latency).
  3. Nếu dữ liệu rác đã vô tình lọt vào một vài batch của Silver trước khi fail, kích hoạt lệnh **Delta Time Travel Rollback**:
     ```python
     dt = DeltaTable("s3://lakehouse/silver/llm_calls")
     target_version = dt.history()[2]["version"] # Quay về version trước khi deploy lỗi
     dt.restore(target_version)
     ```
  4. Lệnh RESTORE hoàn tất trong 0.2 giây, khôi phục bảng Silver về trạng thái trong sạch hoàn toàn mà không làm mất lịch sử audit.

---

### Kịch bản 3: Khách hàng VIP yêu cầu xóa dữ liệu khẩn cấp (Right-to-be-Forgotten / Tenant Offboarding)
- **Triệu chứng & Phát hiện:**
  - Một khách hàng doanh nghiệp VIP chấm dứt hợp đồng và yêu cầu xóa toàn bộ lịch sử trò chuyện LLM của họ trong vòng 1 giờ theo điều khoản hợp đồng.
  - Nếu thực hiện xóa truyền thống bằng cách rewrite toàn bộ 35 TB dữ liệu của 7 ngày, cụm Spark sẽ quá tải và dashboard của các tenant khác bị treo (lock contention).
- **Quy trình Xử lý & Khắc phục:**
  1. Kích hoạt tính năng **Deletion Vectors (DVs)** của Delta Lake:
     ```sql
     DELETE FROM silver.llm_calls WHERE tenant_id = 'tenant_vip_999';
     ```
  2. Nhờ có Deletion Vectors, Delta Lake không ghi lại các file Parquet 128 MB mà chỉ ghi một tệp bitmap siêu nhẹ (vài KB) đánh dấu các dòng cần xóa. Thao tác hoàn tất trong vòng **dưới 15 giây**.
  3. Lập tức phát tán sự kiện xóa sang **Change Data Feed (CDF)** để hệ thống đồng bộ bên ngoài (như vector store hay cache) thu hồi dữ liệu ngay lập tức.
  4. Lập lịch cho job compaction ban đêm (Off-peak maintenance) thực hiện rewrite vật lý nhằm dọn sạch hoàn toàn dấu vết vật lý trên đĩa lưu trữ.

---

## 5. Ước tính Chi phí Chi tiết (Back-of-Envelope FinOps Cost Calculation)

Dưới đây là bảng tính toán chi phí cụ thể, minh bạch cho quy mô **1 tỷ requests/ngày** trên nền tảng AWS us-east-1.

### 5.1. Khối lượng dữ liệu sinh ra (Data Volume Math)
- **Số requests:** 1.000.000.000 req/ngày = 11.574 req/giây (Peak: ~25.000 req/giây).
- **Kích thước trung bình:** 5 KB/req thô (JSON).
- **Tổng dung lượng thô:** $1.000.000.000 \times 5\text{ KB} = 5.000\text{ GB} = \mathbf{5\text{ TB/ngày}}$ (Raw uncompressed).
- **Dung lượng sau nén Parquet + Snappy:**
  - Log text và token có tỷ lệ nén trung bình là **3,5 : 1**.
  - Dung lượng lưu trữ thực tế tại Bronze/Silver: $5\text{ TB} / 3,5 \approx \mathbf{1,43\text{ TB/ngày}}$.

### 5.2. Tính toán dung lượng lưu trữ ổn định (Steady-State Storage Math)
1. **Tầng Bronze (Lưu 7 ngày):**
   - $1,43\text{ TB/ngày} \times 7\text{ ngày} = \mathbf{10,01\text{ TB}}$.
2. **Tầng Silver (Cleaned + Z-Order, Lưu 7 ngày):**
   - Bỏ trường dư thừa, chỉ giữ các trường cần thiết, nén tốt hơn: ~1,1 TB/ngày.
   - $1,1\text{ TB/ngày} \times 7\text{ ngày} = \mathbf{7,70\text{ TB}}$.
3. **Tầng Gold (Aggregated Rollups theo 5 phút, Lưu 365 ngày):**
   - Mỗi ngày: 50.000 tenants × 288 chu kỳ (5 phút) × 3 models = ~10 triệu dòng/ngày.
   - Dung lượng Gold nén: ~150 MB/ngày = 0,00015 TB/ngày.
   - Dung lượng 365 ngày: $0,00015\text{ TB} \times 365 \approx \mathbf{0,055\text{ TB}}$ (chỉ khoảng 55 GB).
4. **Metadata & Delta Transaction Log Overhead:**
   - Ước tính chiếm ~3% dung lượng bảng: $\approx \mathbf{0,53\text{ TB}}$.
- **Tổng dung lượng Storage hoạt động liên tục (Steady-State):**
  $$\text{Total Storage} = 10,01 + 7,70 + 0,055 + 0,53 = \mathbf{18,3\text{ TB}}$$

### 5.3. Chi phí Storage hàng tháng (Monthly Storage Cost)
- Đơn giá S3 Standard: **$0,023 / GB-tháng** = $23,00 / TB-tháng.
- Chi phí lưu trữ Bronze + Silver (S3 Standard):
  $$\text{Cost}_{\text{Bronze+Silver}} = (10,01\text{ TB} + 7,70\text{ TB} + 0,53\text{ TB}) \times \$23,00 = 18,24\text{ TB} \times \$23,00 = \mathbf{\$419,52 / \text{tháng}}$$
- Chi phí lưu trữ Gold (S3 Standard-IA @ $0,0125 / GB-tháng):
  $$\text{Cost}_{\text{Gold}} = 55\text{ GB} \times \$0,0125 = \mathbf{\$0,69 / \text{tháng}}$$
- Chi phí S3 API Requests (PUT, GET, LIST):
  - PUT requests (Inflow: micro-batch 60s = 1.440 PUT/ngày/layer): ~100.000 PUTs/tháng = $0,50.
  - GET requests (Query & Dashboard: 50.000 queries/ngày): 1,5 triệu GETs/tháng @ $0,0004/1.000 = $0,60.
- **Tổng chi phí Storage hàng tháng:** $\approx \mathbf{\$421 / \text{tháng}}$  
  *(Con số này thấp hơn rất nhiều so với trần ngân sách **$5.000 / tháng**; quỹ dự phòng còn lại hơn $4.500/tháng sẵn sàng cho các đợt bùng nổ traffic).*

### 5.4. Chi phí Compute ước tính (Monthly Compute Estimate)
- **Ingestion & Micro-batch ETL (Spark Streaming trên EMR / Kubernetes Spot):**
  - Cụm gồm 4 nodes `c6g.2xlarge` (8 vCPU, 16 GB RAM) chạy liên tục với giá Spot Instance (~$0,136/giờ/node).
  - Chi phí compute: $4 \times \$0,136 \times 730\text{ giờ} \approx \mathbf{\$397 / \text{tháng}}$.
- **Dashboard Query Engine (Serverless Trino / DuckDB on Fargate):**
  - Chi phí phục vụ query dashboard: $\approx \mathbf{\$280 / \text{tháng}}$.
- **Tổng chi phí toàn hệ sinh thái (Storage + Compute):** $\mathbf{\$421 + \$397 + \$280 = \$1.098 / \text{tháng}}$  
  *(Cực kỳ tối ưu, hiệu quả FinOps vượt trội).*

---

## 6. Kế hoạch Xây dựng MVP trong 1 Tuần (One-Week MVP Plan & Verification)

Để chứng minh tính khả thi của kiến trúc trước khi triển khai sản xuất, đội ngũ sẽ phát triển một lát cắt sản phẩm tối thiểu (Thin Shippable Slice) trong vòng 5 ngày làm việc:

| Ngày | Hạng mục thực hiện (Milestone) | Tiêu chí nghiệm thu (Acceptance Criteria) |
|---|---|---|
| **Thứ 2** | Dựng Ingestion Gateway giả lập + PII Tokenizer | Băm thành công Email/Phone thành SHA256 Token với throughput ≥ 20.000 req/s trên 1 node. |
| **Thứ 3** | Thiết lập bảng Bronze Delta Lake & Micro-batch Stream | Ghi thành công 50 triệu records/ngày vào Bronze; kiểm tra transaction log commit đúng hạn. |
| **Thứ 4** | Xây dựng pipeline Silver (Dedup) + Z-ORDER theo Tenant | Silver loại bỏ 100% duplicate `request_id`; Z-order gom file thành công về dải target 128 MB. |
| **Thứ 5** | Xây dựng pipeline Gold Metrics + Phục vụ Dashboard DuckDB | Bảng Gold sinh ra đầy đủ p50/p95 latency và cost theo từng tenant; truy vấn phản hồi < 200 ms. |
| **Thứ 6** | Thử nghiệm cơ chế khó nhất: Rollback & Xóa Retention 7 ngày | Chạy thử nghiệm xóa giả định và chứng minh S3 storage thu hồi bytes vật lý sau lệnh VACUUM. |

### Cách kiểm tra cơ chế khó nhất (Hardest Mechanism Verification):
- **Cơ chế khó nhất:** Đảm bảo **Data Skipping bằng Z-Order** hoạt động hiệu quả khi có hàng nghìn tenant cùng ghi dữ liệu, kết hợp với việc **thu hồi bytes vật lý đúng 7 ngày** mà không làm hỏng các truy vấn đang đọc.
- **Quy trình kiểm thử:**
  1. Nạp 10 triệu records giả lập của 500 tenants khác nhau vào bảng Silver.
  2. Kích hoạt `dt.optimize.z_order(["tenant_id", "event_time"])`.
  3. Đo lường tỷ lệ pruning bằng `plan_files()` hoặc kiểm tra min/max stats trong transaction log: Yêu cầu truy vấn `WHERE tenant_id = 'target_tenant'` phải bỏ qua **≥ 90% số file** Parquet.
  4. Thực hiện xóa dữ liệu ngày cũ nhất (`DELETE WHERE event_date = 'day_01'`) và chạy `VACUUM` với retention thử nghiệm = 0. Kiểm tra bằng lệnh filesystem để chứng thực kích thước thư mục trên đĩa giảm đi tương ứng với dung lượng đã xóa.
