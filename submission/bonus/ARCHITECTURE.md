# Bonus — Lakehouse click-stream 10 TB/ngày dưới trần ngân sách $8K/tháng (Topic E)

Tác giả: Lê Phan Việt Cương — MSSV 2A202602641 · Bài cá nhân · K4-Track02-Day18

> Mọi con số dưới đây tái lập được bằng `poc/cost_model.py` (output lưu ở `poc/cost_model_output.txt`). Đơn giá S3/EC2 là **giá niêm yết giả định** (us-east-1); tôi chưa đối chiếu với trang giá hiện hành, nên phải kiểm tra lại trước khi dùng thật. Tỷ lệ nén 5× cũng là giả định cần kiểm chứng ở MVP.

## 1. Problem statement

Một team consumer-app analytics sinh **10 TB/ngày click events** (JSON thô). Đề yêu cầu giữ **365 ngày**, với SLA: 7 ngày gần nhất p95 < 2 s; 8–90 ngày p95 < 30 s; > 90 ngày "best effort, < 5 phút". Trần cứng của CFO: **$8K/tháng cho storage trên mọi tier**.

Vì sao khó:
- Lưu 365 ngày ở S3 Standard là 3,650 TB × $23/TB ≈ **$84K/tháng** (JSON thô) — vượt trần ~10×. Ngay cả sau khi nén 5× (730 TB) vẫn là ~$16.8K, nên **bắt buộc phải tiering**.
- Tiering làm xuất hiện hai cái bẫy: S3 lifecycle chỉ chuyển Standard → Standard-IA sau tối thiểu 30 ngày, còn compaction/rewrite tạo object mới nên **reset đồng hồ tuổi object**.
- Tier lạnh rẻ lưu nhưng **đắt khi đọc**: một `SELECT *` không giới hạn trên tier lạnh có thể tốn ~$16.5K *một truy vấn* (mục 5). Ngân sách thất bại ở đường đọc, không ở đường lưu.

Nhịp ghi: 10 TB/ngày ≈ 116 MB/s thô; sau nén ~2 TB/ngày ≈ 23 MB/s.

## 2. Sơ đồ kiến trúc

```
 click events (JSON)                                         ┌─────────────── GOVERNANCE ───────────────┐
        │                                                    │ Glue catalog (Iceberg REST/Glue)         │
        ▼                                                    │ query guard: bắt buộc predicate ingest_day│
 Kafka (7d buffer) ──► Streaming ingest (Spark, commit 1 phút)│ + scan quota (TB/query) + billing alarm │
        │                    │ schema enforce + PII tokenize  └──────────────────────────────────────────┘
        ▼                    ▼
 ┌─────────────┐   ┌──────────────────────────────────────────────────────────────────────┐
 │ BRONZE      │   │ Iceberg table `clicks`  partition = day(ingest_ts) (hidden)          │
 │ raw landing │──►│ sort order (app_id, event_type)  · Parquet+zstd · target file 256 MB  │
 │ 48h (rẻ)    │   └───────┬───────────────────────────┬──────────────────────┬───────────┘
 └─────────────┘           │ HOT 0–7d                   │ WARM 8–90d           │ COLD 91–365d
                           ▼ S3 Standard (14 TB)        ▼ S3 Standard-IA(166TB)▼ Glacier Instant Retr. (550 TB)
                  hourly compaction (<24h partitions)   ▲ tier-down job @ day 7  ▲ lifecycle IA→GIR @ day 90
                           │                            │ rewrite + sort, PUT trực tiếp StorageClass=IA
                           └─────────── SILVER/GOLD: dedup + aggregate theo (ngày, app) ──► dashboard
 QUERY PATH:  Trino (spot) ──► catalog ──► manifest pruning (ingest_day, app_id) ──► đúng tier cần đọc
 MAINTENANCE: expire_snapshots (7d) ──► orphan sweep (cặp bắt buộc, NB6) ──► rollback bằng snapshot nếu job hỏng
```

Day18 concepts được dùng cho quyết định cụ thể: **medallion** (Bronze 48h → Silver dedup → Gold aggregates), **hidden partitioning + partition evolution** (Iceberg, NB5), **compaction + clustering/sort** (NB2/NB6), **snapshot expiry + orphan sweep như một cặp** (NB6), **time travel/rollback** cho failure mode, **FinOps tiering**, **catalog làm control plane** (NB5).

## 3. Quyết định chính và alternatives đã loại

**D1 — Table format: Iceberg.** Loại **Delta OSS**: thay đổi partition spec (ví dụ day → hour khi lượng tăng) phải ghi lại toàn bộ bảng, tức ~730 TB rewrite, trong khi Iceberg đổi spec chỉ áp dụng cho dữ liệu mới (NB5: 2 spec cùng tồn tại, 0 rewrite). Loại **Hive-style Parquet thuần**: không có hoán đổi file nguyên tử, nên reader sẽ thấy trạng thái dở dang khi tier-down job viết lại partition, và không có snapshot để rollback. Đánh đổi chấp nhận: Iceberg không có Z-order dựng sẵn như `delta-rs`, phải dùng sort order + rewrite.

**D2 — Partitioning: `day(ingest_ts)`, sort theo `(app_id, event_type)` trong partition.** Loại **partition theo `event_ts`**: sự kiện đến muộn (mất mạng) sẽ ghi vào partition cũ *đã ở tier IA/GIR*, tạo file nhỏ ở tier lạnh và có thể phải rewrite cả partition đã tiering. Loại **partition theo `app_id`**: cardinality cao và lệch (vài app chiếm phần lớn lưu lượng) → hàng chục nghìn partition nhỏ và metadata phình (NB5: metadata:data 283% ở file nhỏ). Loại **partition theo giờ**: 24× partition, mỗi partition ~83 GB còn ổn nhưng không cần cho ngưỡng 2 s khi đã có sort theo app_id; để dành làm bước *partition evolution* nếu p95 hot không đạt.

**D3 — Cơ chế tiering: job tier-down tại ngày 7 ghi trực tiếp `StorageClass=STANDARD_IA`, rồi lifecycle IA → Glacier IR tại ngày 90.** Loại **chỉ dùng lifecycle Standard → IA**: object phải ở Standard ≥ 30 ngày, nên ngày 8–30 vẫn trả giá Standard: (30−7) ngày × 2 TB × ($23−$12.5)/TB = **+$483/tháng** (cost_model). Loại **S3 Intelligent-Tiering**: có phí giám sát theo số object, tier IA chỉ kích hoạt sau 30 ngày không truy cập, và truy cập bất thường làm chi phí khó dự đoán — không hợp với trần cứng. Loại **Deep Archive** cho > 90 ngày: rẻ hơn (~$1/TB) nhưng restore mất hàng giờ, vi phạm "< 5 phút", và dữ liệu không truy vấn trực tiếp được.

**D4 — Định dạng/nén: Parquet + zstd, file mục tiêu 256 MB.** Loại **JSON/gzip giữ nguyên**: không column pruning, mọi truy vấn đọc toàn bộ 5 KB/dòng (NB7: column pruning là thứ khiến scan phân tích rẻ). Loại **ORC** và **Avro**: không có lợi thế rõ cho Trino/Spark ở đây và hệ sinh thái Iceberg-Parquet được dùng phổ biến hơn; Avro là row-oriented nên mất lợi thế cột. Loại **Snappy**: nén kém hơn zstd; mỗi 10% dung lượng thêm làm tổng storage tăng ~$460/tháng (10% của $4,597), nên chọn nén chặt hơn và chấp nhận tốn thêm CPU.

**D5 — Compaction: commit 1 phút, compaction hằng giờ cho partition < 24h, tier-down tại ngày 7; không bao giờ rewrite partition ≥ 8 ngày.** Loại **compaction liên tục**: chi phí compute cao và tranh chấp commit với writer. Loại **không compaction**: 1,440 commit/ngày để lại hàng chục nghìn file nhỏ/ngày (NB6: 200 → 11 file, và chi phí request tăng theo *số file*). Loại **rewrite cả partition cũ định kỳ**: mỗi rewrite sinh object mới ở Standard, reset đồng hồ lifecycle và phát sinh phí trả hai lần (NB6: dữ liệu tạm tăng lên khi compaction).

**D6 — Query engine & catalog: Trino trên spot + Glue catalog.** Loại **Athena**: tính $5/TB đã quét, nên khối lượng quét lớn của dashboard bám theo cả trần ngân sách và khó nén bằng quota ở cấp cluster; loại **Spark cho truy vấn tương tác**: khởi động job làm p95 < 2 s khó đạt. Catalog: loại **Hive Metastore tự vận hành** (thêm ops, điểm lỗi) và **Nessie** (branching không cần cho bài toán này, thêm thành phần phải duy trì).

**D7 — Guardrail đường đọc: bắt buộc predicate `ingest_day`, quota TB/query, cảnh báo billing.** Loại **chỉ monitor chi phí sau sự việc**: một truy vấn lạnh không lọc đã tốn ~$16.5K — vượt ngân sách trước khi cảnh báo kịp. Loại **chặn người dùng truy cập tier lạnh**: vi phạm SLA > 90 ngày "best effort".

## 4. Failure modes (3 giờ sáng)

| # | Sự cố | Phát hiện | Rollback / xử lý |
|---|---|---|---|
| F1 | **Tier-down job viết hỏng/thiếu dữ liệu** (tie với *time travel*): job rewrite partition ngày 7 sang IA, cam kết snapshot mới nhưng đếm dòng lệch | Job tự đối chiếu `count(*)` + checksum theo partition giữa snapshot trước/sau; alarm khi lệch ≠ 0 | `rollback_to_snapshot` về snapshot trước job (đang còn vì expiry chỉ chạy sau 7 ngày); sweep orphan sau đó. Đây chính là cặp expire + orphan của NB6 — expire quá sớm sẽ mất khả năng rollback |
| F2 | **Quét lạnh không giới hạn** làm vỡ ngân sách (~$16.5K/truy vấn) | Quota TB/query ở Trino resource group; CloudWatch alarm trên `Retrieval bytes` Glacier IR; Cost Anomaly Detection | Hủy truy vấn tự động khi vượt quota; bật bắt buộc predicate; nếu đã phát sinh, ghi nhận và hạ quota — chi phí đã tiêu không rollback được, nên phòng ngừa là biện pháp chính |
| F3 | **Small-file explosion** do ingest lỗi (consumer lag rồi xả bù) | Số data file/partition và kích thước file trung bình qua `inspect.files`; alarm khi avg < 32 MB | Compaction khẩn cho partition hot; giới hạn trigger interval của writer (NB6: chi phí theo số file, không theo GB) |
| F4 | **Schema drift từ producer** (đổi kiểu `user_id`, thêm cột) | Schema enforcement chặn ghi sai kiểu (NB1); cột mới bị từ chối đến khi opt-in | Bản ghi sai vào dead-letter ở Bronze; evolution là thay đổi có chủ đích theo field-ID, không rewrite file (NB5) |
| F5 | **Sự kiện đến muộn ghi vào partition lạnh** | Đếm file mới theo partition ≥ 8 ngày tuổi | Nhờ D2 (partition theo `ingest_ts`) sự kiện muộn luôn đi vào partition hot của hôm nay, nên không chạm tier lạnh |

## 5. Ước lượng chi phí (cost_model.py)

Giả định: JSON 10 TB/ngày → Parquet+zstd 5× = **2 TB/ngày**; trạng thái ổn định = 365 ngày × 2 = **730 TB**.

| Hạng mục | Tính | $/tháng |
|---|---|---:|
| Hot, S3 Standard | 7 ngày × 2 TB = 14 TB × $23/TB | 322 |
| Warm, Standard-IA | 83 ngày × 2 TB = 166 TB × $12.5/TB | 2,075 |
| Cold, Glacier Instant Retrieval | 275 ngày × 2 TB = 550 TB × $4/TB | 2,200 |
| **Tổng storage** | | **4,597** |
| Retrieval IA (giả định quét 40 TB/tháng sau pruning × $10/TB) | | 400 |
| Retrieval GIR (10 TB/tháng × $30/TB) | | 300 |
| Ingest: 6 × m6i.2xlarge × 730 h × $0.384 × 0.4 (spot/savings) | | 673 |
| Trino: 4 × m6i.4xlarge × 730 h × $0.768 × 0.4 | | 897 |
| Compaction/tier-down: 10 nodes × 1 h × 30 ngày × $0.384 | | 115 |
| **Tổng all-in** | | **6,982** |

Kết luận: storage một mình ($4.6K) nằm dưới trần $8K; cộng cả retrieval + compute vẫn **$6,982, dư $1,018 (~13%)**. Hai biến nhạy nhất: (a) tỷ lệ nén — nếu chỉ đạt 3.5× thì storage tăng ~43% lên ~$6.6K, all-in ~$9K và **vượt trần**; (b) lượng dữ liệu retrieval — cả hai đều được kiểm chứng trong MVP. Đối chiếu: không tiering (730 TB Standard) = $16.8K; JSON thô Standard = $84K.

## 6. MVP một tuần

Lát cắt nhỏ nhất chứng minh kiến trúc: **1 ngày dữ liệu thật/mô phỏng (10 TB hoặc mẫu 1% = 100 GB, rồi ngoại suy) đi qua Iceberg + tier-down, đo ba rủi ro lớn nhất.**

| Ngày | Công việc |
|---|---|
| 1–2 | Dựng bảng Iceberg (Glue), partition `day(ingest_ts)`, sort `(app_id,event_type)`; ingest mẫu; **đo tỷ lệ nén thực** và kích thước file |
| 3 | Compaction hourly; kiểm tra số file/partition và metadata:data |
| 4 | **Cơ chế khó nhất:** tier-down job ghi trực tiếp `StorageClass=STANDARD_IA` và xác nhận (`head-object`) rằng các file đã đúng class; reader đang chạy không lỗi khi swap file |
| 5 | Guardrail: quota Trino + alarm; chạy cố ý một truy vấn không lọc trên mẫu và xác nhận bị chặn |
| 6 | Chạy benchmark p95 cho hot (< 2 s) và warm (< 30 s) trên mẫu; gọi lại cost_model với số đo thật |
| 7 | Chạy F1: cố ý làm hỏng tier-down và `rollback_to_snapshot`; chạy expire + orphan sweep |

**Tiêu chí nghiệm thu:** (1) tỷ lệ nén thực ≥ 4× (nếu < 3.5× phải xem lại ngân sách); (2) 100% file của partition ngày 7 đúng StorageClass sau tier-down và `count(*)` trước/sau bằng nhau; (3) hot p95 < 2 s, warm p95 < 30 s trên mẫu; (4) truy vấn không lọc bị chặn trước khi quét; (5) rollback F1 khôi phục đúng số dòng trong < 10 phút; (6) cost_model với số đo thật ≤ $8K.

**Cách kiểm chứng cơ chế khó nhất (tier-down):** so sánh danh sách object và storage class bằng S3 inventory/`head-object` với danh sách file trong snapshot mới nhất (`inspect.files`), cộng chạy truy vấn song song suốt lúc swap để xác nhận reader không thấy lỗi. Nếu writer Iceberg của stack không đặt được storage class trực tiếp, phương án dự phòng là S3 Batch Operations copy sang IA rồi cập nhật tham chiếu — phải đánh giá riêng vì đổi đường dẫn file.

## 7. Giới hạn của bài

Đơn giá, tỷ lệ nén, lượng retrieval và khả năng đặt storage class qua writer Iceberg đều là **giả định chưa được kiểm chứng**; MVP được thiết kế để kiểm chứng chúng, không để chứng minh thiết kế đúng. p95 hot/warm chưa đo. Bài không đề cập tuân thủ pháp lý (click-stream có thể chứa định danh người dùng; PII được tokenize tại ingest chỉ là phác thảo).

## 8. Nguồn tham khảo

- Notebook của chính lab này: NB1 (schema enforcement), NB2/NB6 (compaction, clustering, expiry, orphan sweep), NB5 (hidden partitioning, partition evolution), NB7 (column pruning). Các số đo lấy từ output đã chạy trong `submission/notebooks/`.
- Đơn giá và quy tắc lifecycle (giả định, chưa đối chiếu lại): AWS S3 pricing, https://aws.amazon.com/s3/pricing/ ; AWS S3 lifecycle transition considerations (quy tắc tối thiểu 30 ngày ở Standard trước khi sang Standard-IA), https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html
- Apache Iceberg docs (hidden partitioning, partition evolution, maintenance): https://iceberg.apache.org/docs/latest/
- Mô hình chi phí: `poc/cost_model.py` (tự viết cho bài này).
