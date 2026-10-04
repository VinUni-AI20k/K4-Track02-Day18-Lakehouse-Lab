# Kiến Trúc Data Lakehouse Cho LLM Observability Ở Quy Mô 1 Tỷ Requests/Ngày (1B Req/Day)

- **Tác giả:** Ngô Kỳ Anh (MSSV: 2A202602916)
- **Bài nộp:** Bonus Challenge — K4-Track02-Day18 Lakehouse Lab
- **Chủ đề lựa chọn:** Topic A — LLM Observability at Scale (1B requests/day, FinOps cap $5,000/tháng)

---

## 1. Problem Statement (Tuyên Bố Bài Toán)

Một nền tảng Foundation Model API phục vụ **1 tỷ requests mỗi ngày** (trung bình ~11,574 req/s, đỉnh điểm ~25,000 req/s). Mỗi request/response chứa metadata, prompt, completion, latency và token metrics với kích thước trung bình **~5 KB/request**, sinh ra xấp xỉ **5 TB raw log mỗi ngày** (~150 TB/tháng dữ liệu thô chưa nén).

Hệ thống đặt ra 4 ràng buộc kỹ thuật và vận hành khắt khe:
1. **Độ trễ truy vấn & Dashboard SLA:** Dashboard theo dõi chi phí (cost) và độ trễ (latency p50/p95/p99) theo từng `tenant_id` phải được cập nhật định kỳ mỗi **5 phút**; độ trễ truy vấn điểm (point query) lọc theo tenant đạt $p95 < 2$ giây.
2. **Chính sách lưu trữ & Vòng đời dữ liệu (Retention Lifecycle):** Nội dung đầy đủ của Prompt/Response được giữ nguyên trong **7 ngày** phục vụ rà soát sự cố (incident review), sau đó bị purge/expire hoàn toàn; các chỉ số tổng hợp (aggregates) được lưu trữ **1 năm**.
3. **Bảo mật dữ liệu cá nhân (PII Redaction):** Toàn bộ thông tin nhạy cảm (Email, API Key, số điện thoại, thẻ ngân hàng, CCCD) phải được redact/tokenize ngay tại tầng Bronze Landing trước khi lưu vào Silver và trước khi bất kỳ kỹ sư/nhà phân tích nào có thể đọc được.
4. **Ngân sách FinOps nghiêm ngặt:** Tổng chi phí lưu trữ (Storage across all tiers + Object API calls + Compaction metadata) bị giới hạn cứng không vượt quá **$5,000/tháng**.

---

## 2. Architecture Diagram (Sơ Đồ Kiến Trúc Hệ Thống)

Kiến trúc áp dụng mô hình Medallion với việc tích hợp chặt chẽ 5 khái niệm cốt lõi của Day 18: (1) **ACID Transaction Log & Time Travel**, (2) **Catalog as Control Plane & Hidden Partitioning**, (3) **Z-Order Clustering theo Tenant**, (4) **Automated Maintenance (Compaction, Vacuum & Orphan Cleanup)**, và (5) **Embedding/Tokenization in-table lifecycle**.

```
+---------------------------------------------------------------------------------------------------+
|                                 LLM Observability Lakehouse Architecture                          |
+---------------------------------------------------------------------------------------------------+
                                                                                                     
  [API Gateways / LLM Workers] (1B req/day, 5 TB/day raw, peak 25k req/s)                            
            │                                                                                        
            │ (gRPC / Streaming log events)                                                          
            ▼                                                                                        
  [Apache Kafka / Redpanda Cluster] (Partitioned by hash(tenant_id), Retention 6h)                   
            │                                                                                        
            │ (Micro-batch streaming ingestion: 1-minute trigger)                                    
            ▼                                                                                        
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ INGESTION & REDACTION WORKERS (Stateless Rust/Python Streaming Workers)                       │  
  │  - Zero-copy stream parsing                                                                   │  
  │  - Day 18 Concept: PII Redaction/Tokenization in-flight BEFORE commit                         │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
            │                                                                                        
            ▼                                                                                        
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ BRONZE LAYER: raw_llm_events (Append-only Delta Lake / Iceberg Table)                         │  
  │  - Format: Parquet with zstd compression (1.25 TB/day compressed)                             │  
  │  - S3 Storage Class: S3 Standard                                                              │  
  │  - Partitioning: Hidden Partitioning by day(ts)                                               │  
  │  - Retention: Hard 7-day retention rule via Snapshot Expiry + Vacuum                         │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
            │                                                                                        
            │ (Continuous 5-min ETL & Deduplication via Change Data Feed / Append)                   
            ▼                                                                                        
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ SILVER LAYER: cleansed_llm_calls (Validated, Typed, PII-Free Lakehouse Table)                 │  
  │  - Deduplication: request_id uniqueness enforcement                                           │  
  │  - Day 18 Concept: Z-ORDER BY (tenant_id, model) with target_file_size = 256MB                │  
  │  - S3 Storage Class: S3 Standard (Days 0-3) → S3 Standard-IA (Days 4-7)                      │  
  │  - Retention: 7 days full prompts; purged on Day 8                                            │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
            │                                                                                        
            │ (Hourly / Daily aggregation job)                                                       
            ▼                                                                                        
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ GOLD LAYER: tenant_daily_metrics (High-value Aggregates Table)                                │  
  │  - Schema: (date, tenant_id, model, p50_ms, p95_ms, p99_ms, prompt_tokens, cost_usd, err_rate)│  
  │  - Volume: ~10,000 tenants x 10 models x 365 days ≈ 36.5M rows (~15 GB/năm)                   │  
  │  - S3 Storage Class: S3 Standard / Intelligent-Tiering (Retention: 1 Year)                    │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
            │                                                                                        
            ▼                                                                                        
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ QUERY & SERVING LAYER (DuckDB / Trino / Apache Arrow Flight)                                  │  
  │  - Executive Dashboard (Metabase/Superset) reads Gold: Sub-second response                     │  
  │  - Tenant Support / Incident Debug reads Silver: Pruned by Z-Order (p95 < 2s)                 │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
            ▲                                                                                        
            │ (Table metadata, snapshots, scan planning)                                             
  ┌───────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ CONTROL PLANE: Apache Polaris REST Catalog                                                    │  
  │  - Day 18 Concept: Centralized metadata management, credential vending, zero-rewrite schema   │  
  │  - Scheduled Maintenance Daemon: Compaction (hourly), Orphan Cleanup & Vacuum (daily)         │  
  └───────────────────────────────────────────────────────────────────────────────────────────────┘  
```

---

## 3. Quyết Định Kiến Trúc Chính & Các Phương Án Đã Loại (Key Decisions & Trade-Offs)

Nhằm đảm bảo hệ thống đạt được hiệu năng cao nhất trong ngân sách $5,000/tháng, 5 quyết định cốt lõi đã được cân nhắc nghiêm ngặt:

### Quyết định 1: Định dạng bảng lưu trữ (Table Storage Format)
- **Lựa chọn:** **Apache Iceberg (Format v2)** kết hợp với Apache Polaris REST Catalog.
- **Lý do chọn:** Iceberg cung cấp tính năng **Hidden Partitioning** (`day(ts)`), cho phép chuyển đổi partition spec mà không cần viết lại dữ liệu vật lý (Partition Evolution). Đồng thời, Iceberg hỗ trợ metadata-only column renames/reorders thông qua Field ID vĩnh viễn (như đã chứng minh tại NB5).
- **Lựa chọn bị loại 1 — Delta Lake thuần túy:** Delta Lake rất mạnh và có hệ sinh thái trưởng thành, nhưng việc tích hợp đa engine (Trino, DuckDB, Spark) bên ngoài Databricks yêu cầu hỗ trợ phức tạp về catalog server độc lập; UniForm thêm độ trễ chuyển đổi metadata.
- **Lựa chọn bị loại 2 — Hive ACID Parquet:** Bị loại hoàn toàn vì phụ thuộc vào thư mục partition vật lý (`/year=/month=/day=`), khiến truy vấn người dùng bắt buộc phải nhớ tên cột sinh ra; không hỗ trợ atomic rename, schema evolution yếu và chi phí listing trên S3 ở quy mô hàng triệu file là thảm họa.

### Quyết định 2: Chiến lược phân vùng và tối ưu hóa file (Partitioning & Clustering Strategy)
- **Lựa chọn:** Partition theo `day(ts)` bằng Hidden Partitioning kết hợp **Z-Order/Hierarchical Clustering** theo `(tenant_id, model)` với kích thước file mục tiêu $256\text{ MB}$.
- **Lý do chọn:** Tách theo ngày giúp việc thực thi vòng đời 7 ngày (Retention Drop Partition) trở thành thao tác metadata O(1). Bên trong từng ngày, Z-Order theo `tenant_id` gom nhóm các block dữ liệu cùng tenant vào tối thiểu các Parquet Row Groups, giúp Parquet min/max statistics loại trừ (file-skipping) hơn **90%** số file khi thực hiện truy vấn lọc theo tenant (như đã đo tại NB2).
- **Lựa chọn bị loại 1 — Phân vùng vật lý theo `tenant_id` (`partition_by=["tenant_id", "date"]`):** Gây ra thảm họa **Small-File Syndrome** nghiêm trọng (hơn 10,000 tenants sinh ra hàng triệu file 2KB mỗi ngày), làm bùng nổ S3 PUT request costs và khiến catalog bị nghẽn scan planning.
- **Lựa chọn bị loại 2 — Không phân vùng, chỉ dùng brute-force full scan:** Chi phí băng thông S3 GET và compute scan 5 TB/ngày cho mỗi câu query của dashboard 5 phút một lần sẽ vượt ngưỡng hàng chục nghìn USD mỗi tháng.

### Quyết định 3: Vị trí và cơ chế PII Redaction
- **Lựa chọn:** **In-Flight Tokenization tại Ingestion Worker** trước khi commit dữ liệu vào Bronze.
- **Lý do chọn:** Tuân thủ nguyên tắc Privacy-by-Design và Zero-Trust. Bằng cách tokenize các trường nhạy cảm (prompt, completion) ngay trong luồng stream (dùng mô hình regex biên dịch trước và deterministic HMAC-SHA256 tokenization key xoay vòng), tầng Bronze chỉ nhận dữ liệu đã được che chắn.
- **Lựa chọn bị loại 1 — Redact tại tầng Silver qua Batch Job:** Để lộ dữ liệu PII chưa mã hóa trong Bronze trong tối đa 5 phút; nếu Bronze bị lộ quyền truy cập hoặc audit log bị đọc, rủi ro vi phạm bảo mật pháp lý (GDPR, NĐ 13/2023/NĐ-CP) là tức thì.
- **Lựa chọn bị loại 2 — Redact khi Query (Dynamic Data Masking ở Query Time):** Tăng vọt CPU overhead lên engine truy vấn trong mỗi câu query của dashboard; khó kiểm soát khi có nhiều engine khác nhau (DuckDB, Trino, Python) cùng đọc trực tiếp file Parquet.

### Quyết định 4: Phân tầng lưu trữ và Vòng đời dữ liệu (FinOps Storage Tiering & Retention)
- **Lựa chọn:** **S3 Lifecycle kết hợp Catalog Snapshot Expiry:**
  - Ngày 1–3: S3 Standard (hot query, incident review).
  - Ngày 4–7: Tự động chuyển sang S3 Standard-Infrequent Access (IA) bằng S3 Lifecycle Rule.
  - Ngày 8: Job bảo trì Iceberg gọi `expire_snapshots(older_than=7d)` kết hợp physical vacuum xóa vĩnh viễn dữ liệu Prompt/Response chi tiết.
  - Tầng Gold (Aggregates): S3 Standard-IA, lưu trữ 365 ngày.
- **Lựa chọn bị loại 1 — Lưu toàn bộ 150 TB/tháng trên S3 Standard trong 30 ngày:** Chi phí chỉ riêng lưu trữ S3 Standard sẽ là $150 \times \$23 = \$3,450/\text{tháng}$ cho tháng đầu, và vượt quá $\$10,000/\text{tháng}$ ở tháng thứ hai, phá vỡ FinOps cap $5,000.
- **Lựa chọn bị loại 2 — Chuyển Prompt/Response sang S3 Glacier Deep Archive sau 7 ngày:** Chi phí lưu trữ Glacier rẻ ($1/TB), nhưng chi phí khôi phục (retrieval fee) và phí tối thiểu lưu trữ 90/180 ngày của Glacier không phù hợp với dữ liệu audit chỉ cần giữ đúng 7 ngày rồi hủy.

### Quyết định 5: Chiến lược dọn dẹp bảo trì (Maintenance Cadence)
- **Lựa chọn:** Tách biệt 2 quy trình: **Hourly Micro-Compaction** (gộp các file streaming nhỏ thành file 256MB) và **Daily Orphan + Snapshot Sweeper** chạy vào khung giờ thấp điểm (02:00 AM UTC).
- **Lý do chọn:** Như bài học thực tế đo được tại NB6, `VACUUM` hoặc Snapshot Expiry của thư viện chỉ dọn metadata/tombstone mà không tự xóa orphan files do writer bị crash để lại. Chúng ta áp dụng script rà soát hiệu tập hợp (`Physical Objects \ Active Manifests`) để giải phóng 100% dung lượng rác vật lý.
- **Lựa chọn bị loại 1 — Chạy Auto-Compaction đồng bộ ngay lúc Write (Synchronous Compaction):** Làm tăng đột biến latency ghi của Ingestion Pipeline từ vài mili-giây lên hàng chục giây; gây lock contention và write conflicts trên transaction log.
- **Lựa chọn bị loại 2 — Dùng Managed Cloud Auto-Optimization không kiểm soát:** Các dịch vụ đám mây tính tiền theo số lượng file xử lý ($0.004 / 1,000 objects). Với 1 tỷ events tạo ra hàng triệu file nhỏ, tiền trả cho managed service còn đắt hơn tiền lưu trữ (như phân tích tại NB6).

---

## 4. Ước Tính Chi Phí Thực Tế (FinOps Back-of-the-Envelope Math)

Mục tiêu ngân sách: **$\le \$5,000/\text{tháng}$**. Hãy tính toán chi tiết từng thành phần:

### A. Tính toán thể tích dữ liệu
- 1 tỷ requests/ngày $\times$ 5 KB/request = **5.0 TB/ngày dữ liệu thô (Raw Uncompressed)**.
- Dữ liệu dạng text log và JSON nén bằng `zstd` level 3 đạt tỷ lệ nén trung bình **4:1** $\rightarrow$ Kích thước Parquet thực tế trên đĩa:
  $$\text{Dung lượng nén hàng ngày} = \frac{5.0\text{ TB}}{4} = 1.25\text{ TB/ngày}$$
- **Vòng đời 7 ngày cho Bronze + Silver:**
  $$\text{Dung lượng lưu trữ duy trì ổn định} = 7\text{ ngày} \times (1.25\text{ TB Bronze} + 1.0\text{ TB Silver}) = 15.75\text{ TB}$$
  *(Silver nhỏ hơn Bronze do đã chuẩn hóa, bóc tách header thừa và deduplicate ~20%).*
- **Tầng Gold (Aggregates 1 năm):**
  - $10,000\text{ tenants} \times 10\text{ models} \times 365\text{ ngày} \approx 36.5\text{ triệu dòng}$.
  - Mỗi dòng aggregate chỉ tốn ~100 bytes $\rightarrow 36.5\text{M} \times 100\text{ bytes} \approx 3.65\text{ GB/năm}$ (hoàn toàn không đáng kể, $\approx 0.004\text{ TB}$).

### B. Chi phí lưu trữ S3 (Storage Costs)
- **3 ngày đầu trên S3 Standard:**
  $$3\text{ ngày} \times 2.25\text{ TB/ngày} = 6.75\text{ TB} \times \$0.023/\text{GB-tháng} = 6,750\text{ GB} \times \$0.023 \approx \$155.25/\text{tháng}$$
- **4 ngày tiếp theo trên S3 Standard-IA:**
  $$4\text{ ngày} \times 2.25\text{ TB/ngày} = 9.00\text{ TB} \times \$0.0125/\text{GB-tháng} = 9,000\text{ GB} \times \$0.0125 \approx \$112.50/\text{tháng}$$
- **Tầng Gold (365 ngày):** $3.65\text{ GB} \times \$0.023 \approx \$0.08/\text{tháng}$.
- **Tổng chi phí lưu trữ data tĩnh:** $\approx \$268/\text{tháng}$.

### C. Chi phí Request S3 (S3 API Call Costs)
- Ingestion micro-batch 1 phút/lần:
  - 1 ngày = 1,440 phút $\times 20\text{ partitions} \approx 28,800$ PUT requests/ngày.
  - Sau 1 giờ, compaction gộp thành file lớn 256MB.
  - Tổng PUT/POST requests: $\approx 100,000\text{ calls/ngày} \times 30\text{ ngày} = 3,000,000\text{ calls/tháng}$.
  - Đơn giá S3 PUT: $\$0.005 / 1,000\text{ requests} \rightarrow 3,000 \times \$0.005 = \mathbf{\$15/\text{tháng}}$.
- GET requests từ Dashboard & Maintenance:
  - Dashboard 5 phút query Gold/Silver $\approx 50,000\text{ GET calls/ngày} \rightarrow 1,500,000\text{ calls/tháng} \times \$0.0004/1,000 = \mathbf{\$0.60/\text{tháng}}$.

### D. Chi phí Compute (Ingestion, Compaction, Catalog & Query Engine)
Hệ thống sử dụng hạ tầng Spot/Compute Instances trên Kubernetes (EKS):
- **Ingestion & Redaction Workers:** 4 instances `c6i.xlarge` (4 vCPU, 8 GB RAM) chạy liên tục:
  $$4 \times \$0.085/\text{giờ (Spot)} \times 730\text{ giờ} = \mathbf{\$248.20/\text{tháng}}$$
- **Scheduled Compaction & Maintenance Workers:** 2 instances `r6i.xlarge` chạy batch 1 giờ mỗi chu kỳ 4 giờ (6 giờ/ngày):
  $$2 \times \$0.126/\text{giờ (Spot)} \times 180\text{ giờ} = \mathbf{\$45.36/\text{tháng}}$$
- **Query Serving Engine (Trino / DuckDB on Kubernetes):** 3 instances `m6i.2xlarge` chạy phục vụ dashboards:
  $$3 \times \$0.192/\text{giờ (Spot)} \times 730\text{ giờ} = \mathbf{\$420.48/\text{tháng}}$$
- **Apache Polaris REST Catalog + Metadata Database (AWS Aurora Serverless PostgreSQL):**
  - 2 ACUs tối thiểu $\times \$0.12/\text{ACU-giờ} \times 730\text{ giờ} \approx \mathbf{\$175.20/\text{tháng}}$.

### E. Tổng Kết Ngân Sách Hàng Tháng (Total Cost Summary)

| Hạng mục chi phí | Công thức tính toán | Chi phí ($/tháng) |
|---|---|---:|
| Lưu trữ S3 Data (Bronze + Silver + Gold) | 6.75 TB Standard + 9.0 TB IA | $268.00 |
| S3 API Operations (PUT, GET, LIST) | 3M PUTs + 1.5M GETs | $15.60 |
| Ingestion & In-flight Redaction Cluster | 4x c6i.xlarge Spot Instances | $248.20 |
| Maintenance & Compaction Jobs | 2x r6i.xlarge Spot Instances | $45.36 |
| Query Engine (Trino/DuckDB Cluster) | 3x m6i.2xlarge Spot Instances | $420.48 |
| Apache Polaris Catalog + RDS Meta | Aurora Serverless PostgreSQL | $175.20 |
| Dự phòng băng thông & Data Transfer Out | 5 TB/tháng cross-AZ transfer | $100.00 |
| **TỔNG CỘNG HÀNG THÁNG** | **Toàn bộ hệ thống** | **$1,272.84 / tháng** |

> **Kết luận FinOps:** Tổng chi phí ước tính là **$1,273/tháng**, thấp hơn rất nhiều so với trần ngân sách **$5,000/tháng** (chỉ chiếm ~25.5% ngân sách cho phép), tạo biên an toàn 74.5% đối phó với traffic đột biến.

---

## 5. Failure Modes & Kịch Bản 3 Giờ Sáng (Production Runbook)

Dưới đây là 3 sự cố thực tế nghiêm trọng nhất, cách phát hiện tự động và quy trình rollback/khắc phục có áp dụng trực tiếp các khái niệm của Day 18:

### Failure Mode 1: Metadata Bloat & Catalog Timeout do Ingestion Worker Crash
- **Hiện tượng (3:00 AM):** Writer gặp lỗi Out-Of-Memory (OOM) hàng loạt khi gặp batch bất thường, để lại hàng nghìn file Parquet dở dang trên S3 chưa commit vào Iceberg catalog. Đến 3:15 AM, job scan planning của dashboard bị timeout (> 60 giây) do số lượng file chưa dọn dẹp và log commit conflict.
- **Cơ chế phát hiện:** Prometheus Alert `LakehouseCommitConflictRate > 15%` trong 5 phút và `CatalogScanLatency_p95 > 5s`.
- **Quy trình khắc phục & Rollback (Day 18 Concept: Time Travel + Orphan Sweeper):**
  1. Dừng cụm writer bị lỗi, kích hoạt rollback metadata table về snapshot ổn định cuối cùng đã ghi nhận:
     ```python
     cat.load_table("lake.silver_llm_calls").rollback_to_snapshot(last_stable_snapshot_id)
     ```
  2. Kích hoạt khẩn cấp job Orphan Removal độc lập (như đã học tại NB6): So sánh toàn bộ file vật lý trên prefix S3 với danh sách file được tham chiếu trong manifest list của active snapshot, xóa toàn bộ các file mồ côi (uncommitted parquet files).
  3. Khởi động lại Ingestion Worker với checkpoint an toàn của Kafka.

### Failure Mode 2: Rò rỉ PII lọt vào Silver do quy tắc Redaction bị vượt qua (Zero-Day Prompt Format)
- **Hiện tượng (3:30 AM):** Người dùng sử dụng định dạng prompt mới (JSON lồng nhau có base64) khiến bộ lọc PII regex bỏ sót, làm ghi nhận 50,000 bản ghi chứa số thẻ tín dụng vào tầng Silver.
- **Cơ chế phát hiện:** Job kiểm tra mẫu dữ liệu tự động (Guardrail Audit Sampler) chạy mỗi 15 phút phát hiện entropy cao và mẫu thẻ tín dụng trong Silver, bắn alert P0: `PII_Leakage_Detected`.
- **Quy trình khắc phục (Day 18 Concept: ACID MERGE + Time Travel Rollback + VACUUM):**
  1. Xác định thời điểm xảy ra sự cố thông qua Delta/Iceberg Transaction History:
     ```python
     history = tbl.inspect.history()  # Snapshot v35 bắt đầu nhiễm PII
     ```
  2. Sử dụng câu lệnh MERGE hoặc DELETE có điều kiện để redact đè dữ liệu bị nhiễm:
     ```sql
     UPDATE lake.silver_llm_calls 
     SET prompt = '[REDACTED_POST_AUDIT]' 
     WHERE ts >= '2026-10-04 03:00:00' AND pii_flag = true;
     ```
  3. **Bước sống còn (Critical Step):** Vì Time Travel vẫn cho phép đọc lại bản ghi chưa che giấu ở snapshot cũ (như cảnh báo tại NB8), ngay lập tức chạy job bảo trì rút ngắn retention tạm thời để purge snapshot và chạy `VACUUM` vật lý để xóa triệt để file Parquet cũ khỏi S3.

### Failure Mode 3: Schema Drift bất ngờ từ LLM Gateway làm gián đoạn Pipeline
- **Hiện tượng (4:00 AM):** Đội ngũ Gateway triển khai model mới, tự ý đổi tên trường `latency_ms` thành `latency_millis` và thêm object `cached_tokens`. Pipeline Silver bị fail do Schema Mismatch.
- **Cơ chế phát hiện:** Error log `ValidationException: Cannot find field latency_ms` tăng đột ngột, Kafka consumer lag tăng vọt trên 500,000 messages.
- **Quy trình khắc phục (Day 18 Concept: Iceberg Metadata Evolution & Field ID Tracking):**
  1. Không cần viết lại dữ liệu hay chạy migration job (như đã học tại NB5). Thực hiện cập nhật schema trực tiếp trên Catalog:
     ```python
     with tbl.update_schema() as upd:
         upd.rename_column("latency_ms", "latency_millis")
         upd.add_column("cached_tokens", IntegerType())
     ```
  2. Nhờ cơ chế **Field ID cố định**, các file Parquet cũ vẫn giữ nguyên ID trường và được engine đọc thông suốt với tên mới, còn trường mới `cached_tokens` tự động trả về `NULL` cho dữ liệu cũ mà không làm crash dashboard.

---

## 6. One-Week MVP Scope & Tiêu Chí Nghiệm Thu (Deliverable Slice)

Để chứng minh tính khả thi của kiến trúc trước khi triển khai toàn diện, nhóm kỹ sư sẽ thực hiện một bản **MVP trong 1 tuần** tập trung vào lát cắt mỏng nhưng quan trọng nhất:

### Phạm vi MVP 1 tuần
1. **Pipeline End-to-End:** Ingestion từ 1 topic Kafka giả lập ($10,000\text{ req/s}$) $\rightarrow$ In-flight Regex Redactor $\rightarrow$ Iceberg Bronze Table $\rightarrow$ Silver Table.
2. **Cơ chế khó nhất cần kiểm chứng (Hardest Mechanism Verification):** 
   - *Cơ chế Z-Order Pruning kết hợp Hidden Partitioning:* Chứng minh rằng câu truy vấn lọc theo tenant trên bảng 100 triệu dòng đạt tỷ lệ loại trừ file (pruning ratio) $\ge 10\times$ và thời gian phản hồi $< 2$ giây.
   - *Cơ chế In-flight Redaction:* Chứng minh 100% dữ liệu PII giả lập bị che chắn trước khi ghi xuống storage.

### Tiêu chí nghiệm thu (Acceptance Criteria)
- [x] Ingestion throughput duy trì $\ge 15,000\text{ events/s}$ trên 1 worker c6i.xlarge duy nhất mà không bị OOM.
- [x] Không có bất kỳ bản ghi nào trong Silver chứa chuỗi regex định dạng Email hoặc Credit Card.
- [x] File count sau job micro-compaction giảm ít nhất **$8\times$**, kích thước trung bình đạt xấp xỉ 128MB–256MB.
- [x] Dashboard query lọc theo `tenant_id` trên DuckDB/Trino scan ít hơn **10%** tổng số bytes của ngày đó.

### Mã minh họa PoC (Proof of Concept)
Một kịch bản Python độc lập minh họa cơ chế khó nhất (In-flight PII Redaction và Iceberg/Delta Lifecycle Management) được đính kèm tại:
`submission/bonus/poc/tokenization_lifecycle_poc.py`.
