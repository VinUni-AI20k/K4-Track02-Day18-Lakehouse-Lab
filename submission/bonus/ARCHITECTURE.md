# K4-Track02-Day18 — Architecture Brief: Multimodal Legal RAG Lakehouse (10M Documents)

**Author:** Thiều Quang Vinh  
**Student ID (MSSV):** 2A202602877  
**Assignment Code:** K4-Track02-Day18  
**Topic:** D — Multimodal RAG trên 10 triệu document pháp lý  
**Target Repository:** `K4-Track02-Day18-ThieuQuangVinh-2A202602877-Lakehouse-Lab`  

---

## 1. Problem Statement

Hệ thống RAG cho văn phòng luật sư tại Việt Nam phục vụ tra cứu trên kho dữ liệu gồm **10 triệu tài liệu PDF pháp lý** (văn bản quy phạm, nghị định, án lệ, hồ sơ tố tụng) chứa cả văn bản, bảng biểu phức tạp và ảnh chụp scan con dấu, chữ ký.

### Các con số định lượng và ràng buộc cốt lõi:
1. **Quy mô dữ liệu:** 10 triệu tài liệu PDF (~2 MB/file) $\rightarrow$ **20 TB raw storage**. Quá trình OCR và phân tích layout bóc tách ra **30 tỷ tokens**, được chia thành **150 triệu text chunks** (~200 tokens/chunk, kèm ảnh trích xuất và bounding box).
2. **Vòng đời Embedding:** Mô hình nhúng ngôn ngữ (Embedding Model) sẽ được **tái huấn luyện / nâng cấp ít nhất 2 lần** trong vòng đời hệ thống (ví dụ: v1 `bge-m3` $\rightarrow$ v2 `vietnamese-legal-embedding` $\rightarrow$ v3 `multimodal-law-embedding`).
3. **Độ trễ khắt khe:** Thời gian truy vấn tìm kiếm (Retrieval Latency) **p95 < 200 ms** trên toàn bộ không gian 150 triệu vector chunks.
4. **Ràng buộc pháp lý bất biến (5-Year Reproducibility):** Khi một bản án hoặc kết luận bào chữa trích dẫn một văn bản pháp lý tại phiên bản lịch sử cụ thể (ví dụ: Nghị định X áp dụng tại thời điểm tranh chấp năm 2026), kết quả retrieval và nội dung trích xuất phải **tái lập chính xác 100% sau 5 năm (năm 2031)**, bất kể việc embedding model hay văn bản luật đã trải qua nhiều lần sửa đổi/bãi bỏ sau đó.
5. **Rào cản kỹ thuật:** Lưu trữ multimodal không được gây hiện tượng *Row Group Amplification* (làm nghẽn I/O); cập nhật model không được phá hủy snapshot cũ; và hệ sinh thái phải tránh lỗi *Lifecycle Bug* (xóa/sửa văn bản trong kho nhưng vector vẫn tồn tại ở index ngoài).

---

## 2. Architecture Diagram

Kiến trúc áp dụng mô hình **Medallion Architecture kết hợp Hybrid Storage Layout** và **Catalog Control Plane (Nessie/Iceberg)** để quản lý trọn vẹn vòng đời tài liệu và vector embeddings:

```
[Raw Legal PDFs (10M Files, 20TB)]
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INGESTION & OCR PIPELINE (Ray Core / Spark + Tesseract/LayoutLMv3)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────────┐
│ BRONZE LAYER (Object Store S3/MinIO) │  │ BRONZE METADATA TABLE (Delta Lake)│
│ - Raw PDFs (20 TB Immutable)         │  │ - doc_id, file_uri, md5_hash      │
│ - Extracted PNGs (Tables/Seals)      │  │ - ingestion_timestamp, source     │
│ [Pointer-based Layout — No Blobs]    │  │ [Delta ACID Log + Schema Enforce] │
└──────────────────────────────────────┘  └─────────────────┬─────────────────┘
                                                            │
                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SILVER LAYER: CURATED CHUNKS & EMBEDDINGS (Lance Format + Delta Metadata)    │
│ - Partition Key: `embedding_model_version` (v1, v2, v3)                     │
│ - Columns: chunk_id, doc_id, text, bbox_json, blob_uri, emb: vector[1024]   │
│ - Change Data Feed (CDF) kích hoạt: Bắt sự kiện xóa/sửa văn bản luật        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ GOLD LAYER: HYBRID SEARCH & LEGAL SERVING (p95 < 200ms)                      │
│ - Dense Vector Index: Lance IVF-PQ (int8 quantized, centroids in RAM)       │
│ - Sparse Keyword Index: BM25 / DuckDB FTS over chunks                        │
│ - Cross-Encoder Reranker: Top-100 Candidates → Top-10 Context               │
│ - Catalog Branching & Tagging: Nessie/Iceberg Git-for-Data (v2026-AUG-TAG)  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
             [LLM Context Generation with Legal Citation & Version Hash]
```

### 4 Khái niệm Day 18 được áp dụng cụ thể:
1. **Medallion Architecture (Bronze $\rightarrow$ Silver $\rightarrow$ Gold):** Tách biệt rành mạch giữa dữ liệu thô (Bronze PDF pointers), dữ liệu làm sạch phân mảnh có vector (Silver Chunks), và chỉ mục phục vụ truy vấn tối ưu hóa (Gold Lance Index).
2. **Pointer-based Multimodal Layout (Khắc phục Row-Group Amplification - NB7):** Tuyệt đối không nhúng binary file PDF/ảnh vào trong bảng Parquet. Dữ liệu nhị phân lưu ở Object Storage (S3), bảng Silver chỉ lưu `blob_uri` và metadata text. Tránh việc đọc ngẫu nhiên một chunk làm giải nén cả Row Group 12.5 MB (tiết kiệm I/O hơn 200 lần như thực nghiệm NB7).
3. **Lance Table Format & int8 Quantization (NB7):** Sử dụng cấu trúc lưu trữ dạng cột tối ưu cho vector ngẫu nhiên (Lance) kết hợp lượng hóa vector sang int8, giảm 4–5× dung lượng đĩa và cho phép sub-second vector search mà không cần cluster RAM đắt đỏ.
4. **Catalog Branching & Immutable Version Tagging (Nessie / Iceberg - NB5, NB8):** Quản lý trạng thái kho pháp lý bằng các Tag bất biến (`git tag` cho Lakehouse). Truy vấn bản án năm 2026 sẽ ghim phiên bản qua `VERSION AS OF` hoặc Nessie Tag, bảo tồn khả năng tái lập 100% trong 5 năm mà không sợ lệnh `VACUUM` xóa nhầm file vật lý.

---

## 3. Key Decisions & Rejected Alternatives

### Quyết định 1: Multimodal Storage Layout cho 10 triệu văn bản PDF
- **Tôi chọn:** **Hybrid Pointer Architecture** — File PDF gốc và ảnh trích xuất lưu trên S3 Object Storage dưới dạng immutable objects; các bảng Delta/Parquet trong Lakehouse chỉ lưu URI con trỏ (`blob_uri`), bounding box, và văn bản đã trích xuất.
- **Tôi loại:** **Inline Binary Blobs (Lưu mảng byte PDF trực tiếp trong cột Parquet)** vì hiện tượng *Row Group Amplification* (đã chứng minh bằng thực nghiệm ở NB7, khuếch đại đọc tới 200×). Khi GPU hoặc worker cần nạp 1 văn bản hay 1 chunk ngẫu nhiên, engine buộc phải nạp và giải nén toàn bộ Row Group chứa nhiều megabytes ảnh/PDF xung quanh, làm nghẽn băng thông I/O và sập bộ nhớ đệm.
- **Tôi loại:** **Pure POSIX Shared File System (NFS / GlusterFS / CephFS)** vì không có Transaction Log, không hỗ trợ ACID commit, không thể rollback khi batch OCR 100,000 file bị lỗi giữa chừng, và không có metadata versioning để tái lập sau 5 năm.

### Quyết định 2: Table Format và Engine lưu trữ Embeddings
- **Tôi chọn:** **Lance Format kết hợp Delta Lake Metadata** — Dùng Delta Lake quản lý catalog, metadata và bảng văn bản; dùng Lance Format để quản lý các partition vector embeddings.
- **Tôi loại:** **Pure Delta Lake + DuckDB Brute-Force Array Scan** vì mặc dù giải pháp này lưu trữ đồng nhất trên cùng một bảng Parquet (NB7), nhưng với quy mô 150 triệu vector (dim=1024), việc quét tuần tự vét cạn (brute-force scan) sẽ mất tối thiểu 3–8 giây cho mỗi truy vấn, vi phạm hoàn toàn ràng buộc SLA p95 < 200 ms của văn phòng luật.
- **Tôi loại:** **Vector Database độc lập tách rời (Milvus / Pinecone / Weaviate)** vì gây ra *Lifecycle Bug* kinh điển (NB7). Khi một văn bản luật hết hiệu lực hoặc bị yêu cầu gỡ bỏ theo quyền xóa dữ liệu cá nhân (GDPR/Nghị định 13), việc đồng bộ 1 chiều sang Vector DB ngoài luôn có độ trễ (sync skew) và hoàn toàn không thể hỗ trợ Time Travel về snapshot cách đây 5 năm.

### Quyết định 3: Chiến lược Quản lý Vòng đời & Versioning Embeddings (2 lần regenerate)
- **Tôi chọn:** **Multi-Model Version Partitioning trong cùng Table** — Phân vùng bảng Silver Chunks theo cột `embedding_model_version` (ví dụ: `v1_bgem3`, `v2_legal_law`, `v3_multimodal`), kết hợp ghim `model_card` và model metadata vào Catalog.
- **Tôi loại:** **In-Place Overwrite (Ghi đè cột embedding cũ khi nâng cấp model)** vì thao tác này xóa sổ vĩnh viễn không gian vector của model cũ. Khi một bản án năm 2026 cần thẩm định lại đúng kết quả retrieval mà hệ thống RAG thời đó đã cung cấp, việc mất vector v1 sẽ làm mất hoàn toàn tính *Reproducible* sau 5 năm.
- **Tôi loại:** **Tạo bảng Lakehouse độc lập mới hoàn toàn (`legal_chunks_v1`, `legal_chunks_v2`)** vì gây trùng lặp 1.5 TB văn bản và metadata trích xuất, phân mảnh catalog quản lý, gây khó khăn cho việc chạy A/B testing giữa các model và làm phức tạp hóa các công cụ kiểm toán (lineage audit).

### Quyết định 4: Lựa chọn Vector Index và Quantization
- **Tôi chọn:** **Inverted File with Product Quantization (IVF-PQ) kết hợp int8 Scalar Quantization trên Lance** — Nén vector 1024-dim từ float32 (4 KB/vector) xuống int8 (1 KB/vector), tạo chỉ mục IVF-PQ phân chia thành 4,096 clusters (centroids).
- **Tôi loại:** **Hierarchical Navigable Small World (HNSW) thuần trên RAM** vì 150 triệu vector 1024-dim với đồ thị HNSW đòi hỏi hơn 1.2 TB RAM lưu trữ liên tục. Chi phí máy chủ RAM lớn đội ngân sách lên gấp nhiều lần, thời gian khôi phục khi restart pod mất hàng chục phút.
- **Tôi loại:** **Flat Unindexed (Lưu trữ vector thô không đánh index)** vì độ phức tạp tìm kiếm là $O(N)$, không thể phân tán để đạt độ trễ < 200 ms trên 150M records.

### Quyết định 5: Catalog Control Plane & Bảo tồn Snapshot 5 năm
- **Tôi chọn:** **Project Nessie (Git-for-Data REST Catalog) kết hợp S3 Object Lock (Compliance Mode)** — Quản lý trạng thái bảng theo commit hash và tags (tương tự git tag). Mỗi khi ban hành án lệ hoặc chốt năm pháp lý, hệ thống gắn một Tag bất biến (`legal-year-2026-v1`).
- **Tôi loại:** **Hive Metastore truyền thống** vì không có tính năng rẽ nhánh (branching), không hỗ trợ immutable tagging, không theo dõi metadata tree 3 tầng theo snapshot như Iceberg/Delta, và rất dễ xảy ra race condition khi ghi đồng thời.
- **Tôi loại:** **Delta VACUUM mặc định (`retention_hours = 168`)** vì lệnh VACUUM thông thường sẽ tự động quét dọn và xóa vĩnh viễn các file Parquet cũ sau 7 ngày để tiết kiệm đĩa (như đã thấy ở NB6), phá hủy hoàn toàn khả năng Time Travel của hệ thống sau 5 năm.

---

## 4. Failure Modes (Kịch bản 3 giờ sáng)

### Failure Mode 1: Lệnh bảo trì Lakehouse định kỳ xóa nhầm dữ liệu lịch sử cần tái lập 5 năm (Tied to Day 18: Time Travel & VACUUM)
- **Kịch bản:** Vào lúc 3:00 AM, một cron job bảo trì chạy `dt.vacuum(retention_hours=720)` nhằm giải phóng dung lượng đĩa theo khuyến nghị FinOps. Lệnh này xóa các Parquet data files của các văn bản luật từ năm 2026. Sáng hôm sau, luật sư mở lại hồ sơ vụ án cũ yêu cầu tái hiện kết quả tra cứu năm 2026 thì nhận lỗi: `FileNotFoundException: part-00042-...parquet has been vacuumed`.
- **Cách phát hiện (Detection):**
  - Hệ thống kiểm tra tính toàn vẹn (Integrity Monitor) chạy định kỳ 6 tiếng/lần, thực hiện lệnh `plan_files()` trên danh sách 100 "Golden Legal Tags" lịch sử trong Catalog Nessie. Nếu phát hiện số file thực tế nhỏ hơn số file ghi nhận trong snapshot metadata, lập tức bắn cảnh báo Alert P0 (PagerDuty) trước khi người dùng gặp lỗi.
- **Kế hoạch Rollback & Phòng ngừa (Mitigation):**
  - *Phòng ngừa gốc:* Tất cả các data file thuộc snapshot được gắn thẻ pháp lý (Legal Tag) được lưu trữ tại S3 Bucket có bật **S3 Object Lock (Legal Hold / Retention Compliance Mode)**. Lệnh `VACUUM` trên Delta/Iceberg sẽ bị chặn ở tầng storage (Access Denied) nếu cố xóa file được bảo hộ.
  - *Rollback:* Catalog Nessie lưu trữ trọn vẹn cây commit metadata. Khôi phục lại trạng thái catalog từ commit log và đồng bộ lại các file Parquet từ bản sao lưu thứ cấp (Cross-Region Backup).

### Failure Mode 2: Lệch pha mô hình Embedding và chỉ mục chưa đồng bộ hoàn tất (Tied to Day 18: Lifecycle Skew & Model Skew)
- **Kịch bản:** Đội ngũ Data Science tiến hành nâng cấp từ Model v1 sang Model v2. Quá trình tính toán 150 triệu vector chạy được 70% thì worker bị crash do OOM. Một API RAG pod khởi động lại và vô tình chuyển sang dùng query encoder v2 trong khi partition v2 mới chỉ có 70% dữ liệu, dẫn đến 30% văn bản luật biến mất khỏi kết quả tìm kiếm.
- **Cách phát hiện (Detection):**
  - Metadata Gatekeeper: Trước khi cho phép router chuyển hướng traffic sang model mới, một health-check tự động kiểm tra số lượng bản ghi `count(*)` của partition `embedding_model_version = 'v2'` phải khớp chính xác 100% với số lượng văn bản trong Silver table. Nếu chưa khớp, metadata đánh dấu `is_active = False` và chặn router.
- **Kế hoạch Rollback & Khắc phục:**
  - Nhờ **Catalog Branching (Nessie)**, toàn bộ quá trình regenerate 150M vector diễn ra trên nhánh phụ `reindex-model-v2`. Nhánh chính `main` của hệ thống serving vẫn hoàn toàn trỏ vào commit của `model-v1`.
  - Khi có sự cố, chỉ cần hủy bỏ nhánh `reindex-model-v2` mà không ảnh hưởng 1 mili-giây nào đến môi trường production. Sau khi fix lỗi và chạy đủ 100%, một lệnh `merge` nguyên tử (atomic swap) chuyển đổi sang v2 với downtime = 0 ms.

### Failure Mode 3: Văn bản luật cập nhật đính chính / xóa bỏ vi phạm quyền dữ liệu nhưng vector cũ vẫn tồn tại (Tied to Day 18: Change Data Feed & Lifecycle Bug)
- **Kịch bản:** Tòa án ban hành quyết định xóa bỏ thông tin cá nhân của một đương sự trong bản án công khai. Người quản trị thực hiện `DELETE` trên bảng Silver. Tuy nhiên, chỉ mục vector phục vụ RAG vẫn trả về tên và thông tin nhạy cảm của đương sự trong các câu trả lời của chatbot RAG.
- **Cách phát hiện (Detection):**
  - Trình kiểm toán tự động chạy test kiểm tra định kỳ (như cell Lifecycle check ở NB7): Lấy danh sách ID đã xóa trong bảng Silver và truy vấn trực tiếp vào Vector Index. Nếu số kết quả trả về $> 0$, kích hoạt cảnh báo vi phạm tuân thủ pháp lý (Compliance Alert).
- **Kế hoạch Rollback & Khắc phục:**
  - Áp dụng **Delta Change Data Feed (CDF)** trên bảng Silver. Mọi lệnh `DELETE` phát sinh sự kiện `_change_type = 'delete'`.
  - Bộ lập chỉ mục Lance đăng ký nhận sự kiện CDF này và tự động kích hoạt Deletion Vectors trên file Lance tương ứng để loại bỏ vector ngay lập tức ở thời điểm truy vấn (Query-time filter) mà không cần chờ xây dựng lại toàn bộ chỉ mục.

---

## 5. Back-of-the-Envelope Cost Estimation (Tính toán chi phí chi tiết)

### A. Dung lượng Lưu trữ (Storage Math)
- **Raw PDFs (10 triệu file):** $10,000,000 \times 2 \text{ MB} = 20 \text{ TB}$.
- **Silver Chunks & Metadata:** 150 triệu chunks, trung bình 500 bytes text + bbox = $75 \text{ GB}$ (nén Parquet còn $\approx 35 \text{ GB}$).
- **Vector Embeddings (dim=1024):**
  - Định dạng int8: $150,000,000 \times 1,024 \text{ bytes} = 153.6 \text{ GB}$ / model.
  - Tổng 3 phiên bản model (1 gốc + 2 lần regenerate): $153.6 \times 3 \approx 460.8 \text{ GB}$.
- **Vector Index (IVF-PQ Codebook + Centroids):** $\approx 30 \text{ GB}$ / model $\times 3 = 90 \text{ GB}$.
- **Tổng dung lượng đĩa active:** $\approx 20 \text{ TB}$ (Raw) + $\approx 600 \text{ GB}$ (Lakehouse Parquet & Lance).

### B. Chi phí Lưu trữ Hàng tháng (Cloud Storage - S3 Tiers)
- **Tầng Cold (Raw PDFs - 20 TB):** S3 Glacier Flexible Retrieval ($0.0036 / GB / tháng)  
  $\rightarrow 20,000 \text{ GB} \times \$0.0036 = \mathbf{\$72 / \text{tháng}}$.
- **Tầng Hot/Warm (Silver Chunks, Metadata, Lance Vectors - 600 GB):** S3 Standard ($0.023 / GB / tháng)  
  $\rightarrow 600 \text{ GB} \times \$0.023 = \mathbf{\$13.8 / \text{tháng}}$.
- **Bản sao lưu 5 năm (Nessie Legal Snapshots - 1 TB):** S3 Glacier Deep Archive ($0.00099 / GB / tháng)  
  $\rightarrow 1,000 \text{ GB} \times \$0.00099 = \mathbf{\$1.0 / \text{tháng}}$.
- **Tổng chi phí lưu trữ (Storage Total):** $\approx \mathbf{\$86.8 / \text{tháng}}$.

### C. Chi phí Tính toán Truy vấn Phục vụ (Serving Compute)
- **Cấu hình cụm RAG Serving:** 2 nodes `c6i.2xlarge` (8 vCPU, 16 GB RAM / node) chạy Lance Search + DuckDB Hybrid Retriever.
  - Bộ nhớ RAM chỉ cần giữ centroids của 4,096 clusters và inverted list pointers ($\approx 4 \text{ GB}$ RAM/node). Các vector chunks được đọc qua zero-copy Memory-Mapped I/O trực tiếp từ SSD NVMe cục bộ.
  - Chi phí 2 nodes on-demand: $2 \times \$0.34 / \text{giờ} \times 730 \text{ giờ/tháng} = \mathbf{\$496.4 / \text{tháng}}$.

### D. Chi phí Tính toán Tái tạo Embeddings (Embedding Regeneration Cost)
- **Khối lượng:** 150 triệu chunks $\times 200 \text{ tokens} = 30 \text{ tỷ tokens}$.
- **Throughput tính toán:** 1 GPU NVIDIA L4 (hoặc A10G) chạy model embedding tối ưu TensorRT với batch size 256 đạt tốc độ $\approx 1,500 \text{ chunks/giây}$.
- **Thời gian cần thiết:** $\frac{150,000,000 \text{ chunks}}{1,500 \text{ chunks/s}} = 100,000 \text{ giây} \approx 27.8 \text{ giờ GPU}$.
- **Chi phí thuê cụm GPU (Spot instance 4x L4 / `g6.12xlarge` $\approx \$2.50 / giờ):**
  - Thời gian chạy trên cụm 4 GPU: $\frac{27.8}{4} \approx 7 \text{ giờ}$.
  - Chi phí cho 1 lần regenerate toàn bộ 150 triệu vector: $7 \text{ giờ} \times \$2.50 = \mathbf{\$17.5 / \text{lần}}$.
  - Hai lần regenerate trong vòng đời hệ thống tiêu tốn chưa đến **\$35** tiền điện toán GPU!

### E. Tổng Hợp Ngân Sách FinOps Hàng Tháng
$$\text{Tổng chi phí vận hành} = \text{Storage (\$86.8)} + \text{Serving Compute (\$496.4)} + \text{Catalog & Data Transfer (\$50)} \approx \mathbf{\$633.2 / \text{tháng}}$$
*(Mức chi phí này thấp hơn rất nhiều so với ngân sách của một văn phòng luật trung bình, chứng minh tính khả thi kinh tế cực cao của kiến trúc).*

---

## 6. One-Week MVP Slice & Feasibility Plan

Để chứng minh kiến trúc hoạt động trong **1 tuần làm việc**, không triển khai toàn bộ 10 triệu văn bản mà xây dựng một **Vertical Slice** hoàn chỉnh trên tập mẫu:

### A. Phạm vi Slice MVP (Scope)
- **Tập dữ liệu:** 10,000 văn bản pháp luật tiêu biểu (~150,000 chunks văn bản, 500 ảnh bảng biểu/con dấu).
- **Mục tiêu chứng minh:** Khẳng định 3 cơ chế kỹ thuật khó nhất:
  1. *Pointer layout* đọc blob không bị khuếch đại I/O.
  2. *Hybrid search* đạt p95 < 50 ms trên tập mẫu.
  3. *Embedding version migration* và *5-year reproducibility* bằng version pinning.

### B. Lịch trình 5 ngày thực hiện
- **Ngày 1 (Ingestion & Layout):** Viết script bóc tách 10,000 PDF sang Bronze table dạng pointer (`blob_uri`) và lưu 150,000 chunks vào bảng Silver Delta Lake.
- **Ngày 2 (Embedding & Lance Table):** Sinh vector v1 (`bge-m3`), lượng hóa int8, ghi vào bảng Lance với phân vùng `embedding_model_version = 'v1'`. Xây dựng chỉ mục IVF-PQ.
- **Ngày 3 (Hybrid Retriever):** Viết module truy vấn kết hợp BM25 (DuckDB) và Vector Search (Lance). Đo đạc latency p95.
- **Ngày 4 (Simulate Model Migration & Version Pinning - Phần khó nhất):**
  - Sinh vector cho model v2 (`v2_legal`) trên 150,000 chunks.
  - Ghi partition mới `embedding_model_version = 'v2'`.
  - Ghim version cũ vào Catalog với thẻ tag `legal-case-2026-v1`.
  - Thực hiện bài kiểm tra đối sánh: Query trên tag `v1` và tag `v2` chứng minh kết quả của tag `v1` được bảo tồn nguyên vẹn 100%.
- **Ngày 5 (Stress Test & Verification):** Mô phỏng xóa 100 tài liệu pháp lý, kiểm tra xem chỉ mục có loại bỏ lập tức (Zero Stale Index) nhờ Change Data Feed hay không.

### C. Tiêu chí Nghiệm thu (Acceptance Criteria)
1. **Latency:** Truy vấn Hybrid Retrieval p95 $\le 80 \text{ ms}$ trên 150,000 chunks.
2. **Reproducibility:** Replay truy vấn với tham số `version_tag='v1'` trả về danh sách `chunk_id` và trích dẫn giống hệt 100% kết quả trước khi model v2 xuất hiện.
3. **No Lifecycle Bug:** Xóa tài liệu `doc_id = 999` $\rightarrow$ kết quả tìm kiếm trên bảng Silver trả về 0 hits, và Vector search trả về 0 hits.
