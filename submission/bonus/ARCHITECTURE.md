# Bonus — Lakehouse cho Multimodal RAG trên 10 triệu văn bản pháp lý (Topic D)

**Lò Văn Long — 2A202602541** · K4-Track02-Day18 · PoC: [`poc/reproducible_retrieval_poc.ipynb`](poc/reproducible_retrieval_poc.ipynb)

> Số liệu quy mô lấy từ đề, cộng các giả định ở mục 2. Giá cloud là giả định để tính toán, cần đối chiếu
> bảng giá hiện hành. Nhận định pháp lý chỉ là điểm xuất phát nghiên cứu, không phải tư vấn pháp lý.

## 1. Problem statement

Một văn phòng luật Việt Nam cần RAG trên **10 triệu PDF** (bản án, văn bản quy phạm, hợp đồng; gồm text,
ảnh scan và bảng), khoảng **30 tỉ token** sau khi chia chunk. Ràng buộc:

1. Retrieval p95 **< 200 ms** (chưa tính thời gian LLM sinh câu trả lời), đỉnh 30 QPS.
2. Embedding được **tạo lại ít nhất 2 lần** trong 5 năm khi nâng model.
3. Kết quả retrieval mà một bản án trích dẫn phải **tái lập được sau 5 năm**, kể cả khi model đã đổi,
   văn bản bị sửa hay rút, và snapshot cũ đã bị dọn.
4. Văn bản chứa dữ liệu cá nhân của đương sự: cần phân quyền theo vụ việc và quy trình xử lý yêu cầu xóa
   (điểm xuất phát: NĐ 13/2023/NĐ-CP).
5. Ngân sách vận hành giả định **≤ $4.000/tháng**.

Bài toán khó vì ba yêu cầu kéo ngược nhau: latency cần index ANN trong RAM (thay đổi liên tục, kết quả
xấp xỉ), tái lập cần dữ liệu bất biến 5 năm, còn quyền xóa và maintenance lại cần xóa dữ liệu cũ.

## 2. Giả định quy mô (dùng xuyên suốt)

| Đại lượng | Giá trị → kết quả |
|---|---|
| PDF | 10M × 12 trang × 1,2 MB → **120M trang, 12 TB**; 50% là scan cần OCR (60M trang) |
| Vector mỗi thế hệ model | 30 tỉ token ÷ 500 = 60M chunk + 6M vùng bảng/hình (5% số trang) → **66M vector, dim 1.024** |
| Dung lượng embedding | float32: 66M × 4.096 B = **270 GB**; int8: 66M × 1.024 B = **68 GB** |
| Text Silver | 120 GB raw × 2 bảng (pages, chunks), nén zstd ~3×, cộng layout → **~100 GB** |
| Tải truy vấn | 500 luật sư × 100 query/ngày = 50K/ngày, đỉnh ~15 QPS → thiết kế cho **30 QPS** |
| Citation log | 50K/ngày × ~2 KB → 100 MB/ngày → **~180 GB sau 5 năm** |

## 3. Kiến trúc

```text
 INGEST                                                             QUERY (p95 < 200 ms)
 PDF ──sha256──► [Object store] pdf/<sha256>.pdf                    Luật sư ─► API (auth + ACL theo vụ việc)
   (pointer, không inline: NB7 đo 200× amplification)                 │ ① encode query bằng emb-vN đã pin (15 ms)
        ▼                                                             ▼
 BRONZE legal.docs_raw (Iceberg, append-only)            ┌ HNSW int8 @release R ┐  ┌ BM25 @release R ┐
   doc_id, doc_version, sha256, license, access_level    │ filter ACL/court/year│  │ số hiệu, "Điều" │
        │ OCR + layout (GPU spot); data contract         └──────────┬───────────┘  └────────┬────────┘
        ▼                                                           └── RRF + rerank top-50 ┘
 SILVER legal.pages            years(issued_date)  (hidden partition, NB5)          │ ② ghi citation
        legal.chunks           doc_id, doc_version, chunk_no, text, pii_tags        ▼
        legal.chunk_embeddings identity(model_version) + bucket(16, doc_id)   GOLD legal.retrieval_log
        │  ③ build index từ snapshot đã TAG → tag rel-YYYYMM-embN (5 năm)        tag, snapshot_ids, model
        ▼                                                    ▲ ④ replay      hashes, top-k id + score
 GOLD   legal.index_builds (tag, snapshot_ids, golden recall@10, p95)
 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
 CATALOG (REST, control plane): ACL/row filter, tag + branch, credential vending
 MAINTENANCE: compaction đêm · expire snapshot KHÔNG tag > 30 ngày · sweep = trên đĩa − ∪ file MỌI ref (NB6)
 CHANGELOG: xóa / rút văn bản ─► evict khỏi HNSW + BM25 ≤ 15 phút (NB7)
```

| Concept Day 18 | Áp dụng vào lựa chọn cụ thể |
|---|---|
| Medallion | Bronze: pointer + provenance; Silver: trang/chunk/embedding; Gold: index build + citation log |
| Catalog là control plane | REST catalog giữ ACL, tag/branch; index build chỉ đọc qua catalog |
| ACID, time travel, version pin | Tag release, citation log ghi `snapshot_id` (NB3, NB8); re-embed trên branch rồi commit nguyên tử |
| Hidden partitioning, partition evolution | `years(issued_date)`; thêm `identity(model_version)` mà không ghi lại dữ liệu (NB5) |
| Maintenance | Expire có tag + sweep tôn trọng mọi ref (NB6) |
| Vector/multimodal + FinOps | Pointer cho blob, int8 + rerank, lifecycle qua changelog (NB7); int8 tiết kiệm ~$3.200/tháng |

## 4. Quyết định chính và các alternative đã loại

**D1. SoR là Apache Iceberg v2 + REST catalog.** Yêu cầu 5 năm cần giữ *vài* snapshot rất lâu và expire
phần còn lại. Iceberg có **tag** với retention riêng (`max-ref-age-ms`); PoC đo được: expire snapshot đang
có tag bị chặn (*"is protected"*).
- Loại **Delta Lake**: time travel phụ thuộc retention của *cả bảng*. Giữ 5 năm nghĩa là ngừng VACUUM
  (giữ mọi file cũ; NB6: một lần compaction đã làm data tăng 10,1 → 16,1 MB) hoặc DEEP CLONE mỗi release
  (~370 GB/lần).
- Loại **Lance làm SoR**: random access tốt và có ANN sẵn, nhưng Trino/Spark và ACL tập trung của hạ tầng
  giả định đã chạy trên Iceberg; dùng Lance làm nguồn sự thật pháp lý cần thêm tích hợp audit và ACL.

**D2. Embedding float32 nằm trong bảng SoR; index phục vụ chỉ là bản dẫn xuất.**
- Loại **vector DB làm SoR**: NB7 tái hiện lifecycle bug (bảng 0 hit, index ngoài 8 hit); index ANN thay
  đổi liên tục, không có snapshot để giữ 5 năm.
- Loại **chỉ lưu int8**: NB7 đo int8 nhỏ hơn 5,8× nhưng recall@10 = 0,904; mất float32 thì không rerank
  hay replay chính xác được nếu model cũ đã bị gỡ. Giữ float32 chỉ tốn ~$20/tháng.
- Loại **chỉ giữ embedding của model mới nhất**: PoC đo query v1 trên embedding v2 cho overlap top-5 =
  **0,00**. Replay cần đúng thế hệ embedding và encoder (khóa bằng hash) của release đó.

**D3. PDF và trang lưu theo pointer content-addressed (`pdf/<sha256>.pdf`, trang = `(sha256, page_no)`).**
- Loại **inline blob trong Parquet**: mở trang được trích dẫn là truy cập ngẫu nhiên; NB7 đo amplification
  bằng đúng số dòng của row group (200×).
- Loại **render sẵn 120M ảnh trang**: ~18 TB, khoảng $450/tháng, cho thứ chỉ cần khi người dùng mở; render
  khi cần rồi cache. sha256 vừa là khóa dedup vừa là bằng chứng toàn vẹn trong citation log.

**D4. HNSW + int8, rerank top-50, 1 shard ~95 GB × 2 replica, blue/green từ snapshot đã tag; chạy cùng BM25
cho định danh chính xác (số hiệu, "Điều 51").**
- Loại **brute-force SQL trong lakehouse**: NB7 đo 9 µs/vector (dim 256), nên 66M vector dim 1.024 tốn
  66e6 × 9 µs × 4 ≈ **40 phút/query**.
- Loại **IVF-PQ trên đĩa**: rẻ RAM, nhưng PQ nén còn 64–128 B/vector làm recall giảm sâu hơn int8, phải
  rerank rộng hơn và khó giữ p95. Bỏ sót án lệ tốn kém hơn chậm thêm 30 ms.
- Loại **HNSW float32**: 66M × 4.352 B ≈ 287 GB RAM mỗi replica, tức 3 node thay vì 1, thêm ~$3.200/tháng.

**D5. Layout: `chunks` partition `years(issued_date)`; `chunk_embeddings` partition `identity(model_version)`
+ `bucket(16, doc_id)`, sort theo `doc_id`.** Build index quét trọn một model_version (expire hay bỏ một thế
hệ chỉ cần thao tác metadata); rút văn bản chỉ ghi lại ~1/16 số file; analyst lọc theo ngày qua hidden
partition (NB5: pruning 10×).
- Loại **partition theo `doc_id`**: 10M partition sinh small files (NB6: 200 file 51 KB tốn phí request
  gấp 50 lần 4 file).
- Loại **không partition**: mỗi lần re-embed hay bỏ thế hệ cũ phải ghi lại 270 GB. Partition evolution
  (NB5: spec 1 và 2 cùng tồn tại, 0 file bị ghi lại) cho phép thêm `model_version` về sau.

**D6. Vòng đời:** expire snapshot không tag sau 30 ngày; tag giữ 5 năm (+ legal hold); orphan sweep tính
trên **mọi ref**, age guard 3 ngày; PDF > 2 năm sang tier lạnh.
- Loại **giữ mọi snapshot**: metadata phình (NB5: 288% dữ liệu khi commit dày), plan scan chậm dần.
- Loại **expire sau 7 ngày**: phá trích dẫn. NB6 cho thấy expire của PyIceberg chỉ bỏ tham chiếu
  (40 → 40 avro), nên phải ghép với sweep, và sweep chỉ nhìn `main` sẽ xóa file của tag (F2).

**D7. Governance:** ACL theo vụ việc ở catalog/engine và ở payload filter của index; tag PII ở Silver; quy
trình xóa so với legal hold có ghi log.
- Loại **redact PII tại Bronze**: bản án cần tên đương sự để trích dẫn đúng, và redact thì không đảo ngược được.
- Loại **để app RAG tự lọc quyền**: chỉ một bug ở app là lộ cả kho.

Quy trình xóa: `main` xóa ngay rồi evict khỏi index ≤ 15 phút; tag chỉ giữ dữ liệu bị xóa khi có căn cứ
legal hold, nếu không thì tạo release đã redact và bỏ tag cũ. PoC: văn bản bị rút có 0 dòng ở `main`,
10 dòng ở tag.

## 5. Failure modes (kịch bản 3 giờ sáng)

| # | Sự cố | Phát hiện | Rollback / khắc phục |
|---|---|---|---|
| F1 | Job re-embed model v3 chết ở 60%; nếu commit từng batch vào `main`, bảng trộn v2 + v3 và index thành rác mà không báo lỗi (PoC: overlap 0,00). *ACID, branch* | Index build assert `count(distinct model_version) = 1`; golden set 200 câu (luật sư gán nhãn) recall@10 ≥ release trước − 2%, không đạt thì không promote | Re-embed ghi vào **branch** `reembed-v3`, chỉ fast-forward vào `main` khi đủ 100% và qua golden set; serving alias giữ index cũ (blue/green); file chưa commit là orphan, sweep dọn |
| F2 | Orphan sweep chỉ tính file của `main`, xóa data file mà chỉ tag còn tham chiếu; lộ ra nhiều tháng sau khi replay gặp `FileNotFound`. *Maintenance, tag* | Job "release integrity" hằng ngày: mỗi tag chạy `plan_files()`, HEAD + checksum từng file, replay 20 citation ngẫu nhiên và so top-k | Object store bật versioning/soft delete 30 ngày nên khôi phục được; sửa sweep: tập được tham chiếu = ∪ file của mọi branch/tag, age guard 3 ngày (NB6) |
| F3 | OCR đổi output (`page_no` = "12a", bảng thành JSON lồng); writer "ép được thì ghi" gán sai trang mà không báo (NB1: `'31'`→31, `1.5`→1). *Schema evolution* | Data contract Bronze→Silver: kiểu nghiêm ngặt, `1 ≤ page_no ≤ page_count`, tỷ lệ null, số chunk/trang lệch ±10% thì quarantine | Rollback Silver về snapshot trước (time travel); rename/thêm cột qua field ID (NB5) để không hỏng reader cũ |
| F4 | Consumer changelog của index chết lúc 01:00, văn bản đã rút vẫn được trả (NB7: 0 vs 8 hit). *Lifecycle* | Lag (snapshot `chunks` − snapshot index đã áp dụng) > 15 phút thì gọi on-call; đối soát số `doc_id` hằng đêm; canary query trên văn bản đã xóa phải 0 hit | Replay incremental scan giữa hai snapshot; lệch lớn thì rebuild index (4–6 h), trong lúc đó API post-filter theo deny-list `doc_id` |

## 6. Chi phí ước lượng

Đơn giá giả định: storage nóng **$25/TB-tháng**, lạnh **$5**; node 128 GB **$800/tháng** ($1,1/h); node
64 GB **$365** ($0,5/h); GPU 24 GB **$730** ($1,0/h). Throughput giả định: embed 25K token/s, OCR 20 trang/s mỗi GPU.

| Hạng mục | Phép tính | $/tháng |
|---|---|---:|
| PDF raw | 2,4 TB nóng × $25 + 9,6 TB lạnh × $5 | 108 |
| Silver + embedding float32 + log | 0,1 TB × $25 + 3 thế hệ × 0,27 TB × $25 + 0,18 TB × $25 | 27 |
| Versioning/soft delete (+10%) | | 14 |
| HNSW int8 (95 GB/replica) | 2 node × $800 | 1.600 |
| BM25 (~60 GB index) | 2 node × $365 | 730 |
| Query encoder + reranker | 1 GPU (dự phòng encoder trên CPU, chậm hơn) | 730 |
| Catalog + Postgres metadata | | 100 |
| Ingest +100K PDF/tháng | OCR 0,6M trang ÷ 20/s ≈ 8,3 GPU-h + embed 0,3 tỉ token ÷ 25K/s ≈ 3,3 GPU-h + compaction ~$10 | 25 |
| Re-embed (khấu hao) | (33 tỉ token ÷ 25K/s = 367 GPU-h + ảnh 33 h) ≈ $400/lần × 2 ÷ 60 tháng | 13 |
| **Tổng** | | **≈ $3.350** |

Backfill một lần: OCR 60M trang ÷ 20/s ≈ 833 GPU-h ≈ $830, cộng embed ~$400. **RAM cho index chiếm ~48%
chi phí**, nên int8 là quyết định FinOps lớn nhất (D4). Ngược lại, giữ float32 và các thế hệ cũ suốt 5 năm
chỉ tốn ~$20/tháng.

**Ngân sách latency p95 (MVP phải đo):** gateway 10 + encode 15 + max(HNSW 30, BM25 50) + RRF 1 + rerank 60
+ snippet 10 + mạng 20 ≈ **166 ms**, còn dư 34 ms.

## 7. MVP 1 tuần

**Slice:** 50K PDF (1 tòa án, 2 năm; ~600K trang, ~300K chunk) trên MinIO + Iceberg catalog.
- N1: Bronze theo pointer + data contract.
- N2: OCR → Silver.
- N3: model A, tag `rel-A`, HNSW + golden set 200 câu.
- N4: API hybrid + citation log, đo p95.
- N5: re-embed model B trên branch → promote `rel-B`; rút văn bản.
- N6: maintenance + chaos test F1, F2, F4.
- N7: replay `rel-A`; benchmark 10M vector tổng hợp trên 1 node.

**Tiêu chí nghiệm thu:**
1. p95 < 200 ms ở 30 QPS trên 300K chunk và trên benchmark 10M vector (cơ sở để ngoại suy lên 66M).
2. **100%** citation của `rel-A` (≥ 200) replay đúng top-k sau khi re-embed, rút văn bản, expire và sweep.
3. Văn bản bị rút: 0 hit trên `main` và index trong ≤ 15 phút.
4. Kill re-embed ở 60% thì `main` không bị trộn; lỗi "sweep chỉ nhìn main" được job integrity bắt trong ≤ 24 h.
5. Golden recall@10 của B ≥ A − 2%.

**Kiểm tra cơ chế khó nhất** (tái lập qua nâng cấp model + rút văn bản + expire): PoC (mục 8) chứng minh
ở quy mô nhỏ; MVP lặp lại trên dữ liệu thật. Ở 66M vector, replay là audit offline: tính lại cosine chính
xác cho top-k đã log, rồi job batch quét partition `model_version` của tag (270 GB) để xác nhận không chunk
nào vượt điểm hạng k.

## 8. PoC — bằng chứng khả thi

[`poc/reproducible_retrieval_poc.py`](poc/reproducible_retrieval_poc.py) (113 dòng, kèm `.ipynb` đã chạy;
pyiceberg 0.12 + numpy, offline, 3.000 chunk tổng hợp). Kết quả trên máy mình:

| Kiểm tra | Kết quả |
|---|---|
| Replay 50 citation từ tag `rel-2026-10-v1` sau re-embed v2, xóa v1 khỏi `main`, rút văn bản và expire | **50/50** khớp top-5 |
| Expire snapshot đang có tag | bị chặn: *"is protected and cannot be expired"* |
| Văn bản bị rút (doc 262) | `main` 0 dòng, tag 10 dòng |
| Query v1 trên embedding v2 / query v2 trên v2 | overlap top-5 **0,00** / **0,99** |

Giới hạn: dùng SQL catalog cục bộ; "model v2" là phép xoay không gian v1 để tách riêng lỗi trộn không gian;
replay dùng exact search; chưa thử ghi vào branch (để MVP N5).

## Nguồn tham khảo

- Apache Iceberg Table Spec — *Snapshot References*, *Snapshot Retention*: https://iceberg.apache.org/spec/
- PyIceberg API (`manage_snapshots`, `expire_snapshots`, `delete`): https://py.iceberg.apache.org/api/
- Delta Lake Protocol (retention, VACUUM, checkpoint): https://github.com/delta-io/delta/blob/master/PROTOCOL.md
- Malkov & Yashunin, *Efficient and robust ANN search using HNSW graphs*, arXiv:1603.09320
- Lance format: https://lancedb.github.io/lance/ · Nghị định 13/2023/NĐ-CP (cần kiểm tra văn bản đang hiệu lực)
- Số đo của chính mình: NB1, NB5, NB6, NB7, NB8 trong `submission/notebooks/`
