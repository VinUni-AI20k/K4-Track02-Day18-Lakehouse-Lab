# Bonus — Topic A: LLM observability ở quy mô 1B requests/ngày

**Đỗ Quang Vinh — 2A202602989** · PoC: [`poc/retention_tokenize_poc.py`](poc/retention_tokenize_poc.py) · output: [`poc/output.txt`](poc/output.txt)

## 1. Problem statement

Một team foundation-model API log mọi request/response: **1B request/ngày × ~5 KB = 5 TB/ngày JSON thô**
(trung bình ~11.6K req/s, giả định peak 3× ≈ 35K req/s). Yêu cầu:

1. Dashboard chi phí & latency **theo tenant**, refresh **mỗi 5 phút**.
2. Prompt/response đầy đủ giữ **7 ngày** cho incident review; sau đó chỉ giữ **aggregate 1 năm**.
3. **PII phải được che trước khi bất kỳ ai đọc được.**
4. Chi phí storage **≤ $5K/tháng**.

Khó vì ba lực kéo ngược nhau. Freshness 5 phút đòi commit liên tục, dễ sinh small files. Retention 7 ngày đòi xoá *vật lý*, trong khi lakehouse giữ lịch sử để time travel. "Che trước khi ai đọc" nghĩa là PII không được chạm tới object storage, kể cả Bronze. Mọi quyết định bên dưới đều quy về các con số này.

## 2. Kiến trúc

```
                  (tokenize TRƯỚC khi chạm storage)                    Unity Catalog OSS: grants, column masks, audit log
 API gateway ──▶ Kafka (24h, 3 replica) ──▶ Flink job ─┬─▶ BRONZE  bronze.llm_raw         Delta · partition day(ts) UTC · giữ 48h
                 lz4, ~2.5 TB/ngày                     │    (body đã token hoá, replay window)
                                                       │
                   HMAC/tenant, alphabet chữ cái ◀─────┘   commit mỗi 60 s · checkpoint mỗi 100 commit
                                                       │
                                                       ├─▶ SILVER  silver.llm_bodies      Delta · day(ts) · Z-ORDER tenant_id · zstd
                                                       │           (prompt/response đã token hoá) · DELETE >7d + VACUUM sau 24h grace
                                                       └─▶ SILVER  silver.llm_meta        Delta · day(ts) · Z-ORDER tenant_id · 90 ngày
                                                                   (narrow: tenant, model, tokens, latency, status, cost)
                                                                          │ CDF (incremental)
                                                                          ▼
                                                           GOLD    gold.tenant_5min       Delta · month(bucket) · 365 ngày
                                                                   (n, p50/p95, tokens, cost, error/rate_limited)
                                                                          │
 Query path:  Dashboard (5') ──▶ Trino ──▶ gold.tenant_5min    ·    Incident review ──▶ Trino ──▶ silver.llm_bodies
              (đọc ~MB)                                              WHERE tenant_id=… AND ts BETWEEN …  (file skipping)
 Ops jobs:    compaction/Z-order hourly (Silver) · VACUUM daily · retention DELETE daily · PII canary 5'
```

**Concept Day18 được áp dụng vào lựa chọn cụ thể** (không chỉ nêu tên):
- **Medallion:** Bronze là token hoá + replay 48h; Silver tách *bodies* (nặng, 7 ngày) khỏi *meta* (nhẹ, 90 ngày); Gold là aggregate 1 năm. Body chỉ lưu một lần ở Silver.
- **Small files → compaction + checkpoint:** commit 60 s thì cần compaction mỗi giờ và checkpoint log (NB2, NB6).
- **Z-order/clustering theo `tenant_id`:** hot path "lọc theo tenant" chỉ đọc vài file mỗi ngày (NB2: 1/55 file).
- **Retention/time travel/VACUUM:** DELETE chỉ ẩn file, VACUUM mới xoá vật lý (NB6, PoC). Grace 24h cho phép RESTORE nếu xoá nhầm.
- **CDF:** Gold cập nhật tăng dần từ Silver meta thay vì quét lại.
- **Catalog & governance:** column mask, audit đọc, quyền theo tenant.
- **FinOps:** tách theo vòng đời; storage + request được tính ở mục 5.

## 3. Quyết định chính và các phương án bị loại

**D1 — Table format.** Tôi chọn **Delta Lake**.
- Loại **Apache Iceberg**: hidden partitioning và partition evolution của nó rất mạnh (NB5). Nhưng yêu cầu số 2 của bài là *xoá vật lý đúng hạn*. Trên stack Python/PyIceberg, NB6 đo được `expire_snapshots` giảm 20 → 3 snapshot mà **xoá 0 file**; phải tự viết orphan sweep. Đó là hai job phải chạy đúng thứ tự, đúng kiểu "expire mà bill không giảm". Delta VACUUM xoá file đã tombstone trong một bước, và PoC chứng minh được (10 → 7 file).
- Loại **Parquet + Hive partition**: không có commit nguyên tử, nên Flink ghi mỗi phút trong khi compaction rewrite sẽ làm reader thấy dữ liệu nửa vời. Không có stats để file skipping. Nếu analyst quên `WHERE dt=…` thì phải quét 1.67 TB/ngày (NB5 đã minh hoạ chi phí của predicate bị quên).

**D2 — Catalog & governance.** Tôi chọn **Unity Catalog OSS**.
- Loại **Hive Metastore**: chỉ quản lý tên bảng → đường dẫn, không có column mask, row filter hay audit log. Yêu cầu "che PII trước khi đọc" và audit incident review sẽ phải làm lại ở từng engine.
- Loại **AWS Glue**: gắn chặt một cloud và IAM. Quyền theo tenant cho 20K tenant bằng IAM policy khó quản lý, và audit đọc phải ghép CloudTrail. Tôi giữ khả năng dùng engine trung lập (Trino, DuckDB, Spark).

**D3 — Partitioning & clustering.** Tôi chọn **partition `day(ts)` theo UTC + Z-ORDER `tenant_id` trong mỗi ngày.**
- Loại **partition theo `tenant_id`**: phân bố tenant rất lệch (vài tenant lớn, hàng nghìn tenant nhỏ). 20K tenant × commit 60 s sinh hàng chục triệu file nhỏ mỗi ngày, tức đúng lỗi small-file của NB2/NB6. Trên S3 tính phí theo request, số file mới là thứ đốt tiền.
- Loại **partition `hour` + `tenant`**: còn tệ hơn về số file, mà dashboard vốn đọc Gold chứ không đọc Silver nên không cần độ mịn này.
- Ranh giới ngày **bắt buộc theo UTC**: NB4 cho thấy `CAST(ts AS DATE)` theo múi giờ máy biến 7 ngày thành 8 ngày thiếu giờ. Ở đây cùng lỗi đó sẽ làm retention xoá lệch 7 giờ dữ liệu (xem F3).

**D4 — Che PII ở đâu.** Tôi chọn **token hoá ngay trong Flink trước khi ghi Bronze**, bằng HMAC-SHA256 với khoá theo tenant lấy từ KMS, và token chỉ gồm chữ cái.
- Loại **redact ở Silver**: Bronze sẽ chứa PII thô, vi phạm yêu cầu 3. Mọi người có quyền đọc Bronze (kỹ sư data, job replay) đều thấy PII.
- Loại **mã hoá toàn bộ cột body**: an toàn nhưng incident review không đọc được nội dung, nên mất mục đích của việc giữ 7 ngày. Mỗi lần đọc phải giải mã, tức đưa khoá ra cho nhiều người.
- Token deterministic theo tenant nên vẫn join được ("cùng email này xuất hiện ở 40 request lỗi") mà không lộ giá trị. Chi tiết rút ra từ PoC: token hex ban đầu khớp nhầm regex số điện thoại ở **0.25%** số token, khiến canary báo 20 "rò rỉ" giả. Token chỉ gồm chữ cái giải quyết triệt để vấn đề này.

**D5 — Vòng đời 7 ngày / 1 năm.** Tôi chọn **bảng bodies riêng; mỗi ngày `DELETE WHERE date < today_utc − 7`; `VACUUM` (retention 24h) chạy hôm sau.**
- Loại **một bảng rộng có TTL**: xoá cột body của dòng cũ nhưng giữ meta nghĩa là rewrite toàn bộ file mỗi ngày (copy-on-write), tức ~1.67 TB ghi lại mỗi ngày chỉ để xoá. Tách bảng thì DELETE theo partition chỉ là thao tác metadata (PoC: không file nào bị rewrite).
- Loại **S3 lifecycle rule xoá prefix > 7 ngày**: storage xoá file sau lưng transaction log. Log vẫn trỏ tới file đã mất, query lỗi "file not found", và time travel/RESTORE không còn đáng tin. Xoá phải đi qua table format.

**D6 — Ingestion.** Tôi chọn **Flink → Delta, commit mỗi 60 s.**
- Loại **Spark Structured Streaming micro-batch 5 phút**: cộng thêm thời gian tính Gold thì freshness thực tế 7–10 phút, vượt SLA 5 phút.
- Loại **Kafka Connect S3 sink + load theo giờ**: freshness tính bằng giờ, và file sink không có ACID (quay lại vấn đề của D1).
- Hệ quả của commit 60 s: ~1 440 commit/ngày/bảng. Cần checkpoint mỗi 100 commit (NB6: reader chỉ đọc 1 checkpoint + vài JSON thay vì 200+) và compaction mỗi giờ.

**D7 — Nén.** Tôi chọn **Parquet + zstd (level 3)** cho bodies.
- Loại **snappy** (mặc định): PoC đo được 3.0× với snappy. zstd thường nén văn bản tốt hơn đáng kể, nhưng tôi vẫn **dùng 3.0× cho phép tính** để có biên an toàn.
- Loại **gzip**: tỷ lệ gần zstd nhưng giải nén chậm hơn nhiều. Incident review quét bodies theo tenant cần đọc nhanh.

## 4. Failure modes (kịch bản 3 giờ sáng)

**F1 — Bão small-file/commit làm dashboard chậm.** Có deploy tăng parallelism Flink 16 → 64, mỗi writer commit riêng, nên log tăng 4× và file trung bình còn ~5 MB.
- *Phát hiện:* metric `avg_file_size(silver, last_hour) < 32 MB`, `num_files/partition > 5 000`, thời gian planning query Gold/Silver > 2 s.
- *Xử lý:* chạy compaction + Z-order ngay cho partition hôm nay; giảm writer hoặc gom commit. Checkpoint giữ thời gian đọc log ổn định. Dữ liệu không mất vì mỗi commit là ACID.
- *Concept:* small files, compaction, checkpoint.

**F2 — Tokenizer bỏ sót định dạng PII mới** (ví dụ `+84 9x.xxx.xxxx` có dấu chấm sau một bản release).
- *Phát hiện:* (a) canary: mỗi 5 phút gửi 100 request giả chứa PII mẫu đã biết, và PII đó phải xuất hiện dưới dạng token ở Silver; (b) detector chạy trên 1% mẫu Silver, *sau khi bỏ token*; vượt 0 là page on-call.
- *Rollback:* thu hồi grant đọc `silver.llm_bodies`. Mỗi commit ghi `tokenizer_version` vào `commitInfo.userMetadata`, nên `DESCRIBE HISTORY` cho biết khoảng version bị ảnh hưởng. Nếu trong 24h thì replay từ Kafka với tokenizer đã sửa. Sau đó DELETE các dòng bị ảnh hưởng và **VACUUM ngoại lệ với retention 0** cho đúng các file đó, vì nếu không thì time travel vẫn giữ PII.
- *Concept:* time travel ↔ quyền xoá; DELETE ≠ xoá vật lý (NB8, PoC).

**F3 — Job retention xoá nhầm ngày.** Cutoff tính theo giờ máy (UTC+7) thay vì UTC, hoặc bug off-by-one, xoá luôn ngày thứ 7.
- *Phát hiện:* assertion trước khi DELETE: số dòng sẽ xoá phải ≈ 1B × số ngày (±20%) và `max(date)` bị xoá phải < `today_utc − 7`. Sau khi DELETE thì đối soát `count(silver.llm_meta)` với `sum(gold.n)` theo ngày.
- *Rollback:* VACUUM chỉ chạy sau **24h grace**, nên `RESTORE TABLE silver.llm_bodies TO VERSION AS OF <trước DELETE>` trả dữ liệu về tức thì (NB3: RESTORE là commit mới, không xoá lịch sử). Grace được tính sẵn trong chi phí (8 ngày bodies).
- *Concept:* time travel/RESTORE, retention.

**F4 — Schema drift từ gateway** (`latency_ms` đổi thành string "123ms").
- *Phát hiện:* schema enforcement của Delta chặn commit (NB1: version 0 → 0). Flink route bản ghi sang `bronze.quarantine` kèm lý do; alert khi tỷ lệ quarantine > 0.1%.
- *Rollback:* không cần, vì bảng không bị bẩn. Muốn chấp nhận cột mới thì đi qua evolution có duyệt (`schema_mode=merge` trong PR), không bật tự động.
- *Concept:* schema enforcement vs evolution.

## 5. Chi phí ước lượng (giá tham chiếu S3 Standard ~$23/TB-tháng, EBS gp3 ~$80/TB-tháng, vCPU ~$0.045/giờ)

**Storage.** Giả định nén 3.0× đo từ PoC, nên 5 TB/ngày thô ≈ **1.67 TB/ngày** Parquet.

| Thành phần | Phép tính | TB | $/tháng |
|---|---|---:|---:|
| Silver bodies | 1.67 TB × (7 ngày + 1 ngày grace) × 1.15 overhead compaction trước VACUUM | 15.4 | 354 |
| Bronze replay | 1.67 TB × 2 ngày | 3.3 | 77 |
| Silver meta (narrow) | 1B dòng × ~50 B × 90 ngày | 4.5 | 104 |
| Gold 5 phút | ≤ 20K tenant × 5 model × 288 bucket × 40 B × 365 ngày | 0.42 | 10 |
| Kafka buffer | 5 TB × ½ (lz4) × 3 replica × 1 ngày, trên gp3 | 7.5 | 600 |
| S3 request | ~200K PUT/ngày (commit 60 s × writer × bảng) + compaction ≈ 7M req × $0.005/1K | — | ~50 |
| **Tổng storage** | | | **≈ $1 195** |

Con số này ≈ **24% ngân sách $5K**. Kafka chiếm phần lớn nhất (50%), nên đòn bẩy đầu tiên khi cần cắt là giảm retention Kafka xuống 12h (−$300), vì Bronze 48h đã là replay window. Dư địa còn lại đủ cho traffic tăng ~4× trước khi chạm trần.

**Compute** (không nằm trong cap nhưng phải biết):
- Flink token hoá: 58 MB/s trung bình, 174 MB/s peak; giả định ~10 MB/s/vCPU cho parse JSON + regex + HMAC nên cần ~6–18 vCPU, autoscale trung bình ~10 vCPU → **$330**.
- Compaction: rewrite ~2 TB/ngày ở ~100 MB/s/vCPU ≈ 5.6 vCPU-giờ/ngày → **~$10** (lấy $50 tính cả overhead).
- Gold streaming 4 vCPU → **$131**.
- Trino 16 vCPU → **$525**.
- Kafka brokers 12 vCPU → **$394**.

Compute ≈ **$1.4K/tháng**; tổng hệ thống ≈ **$2.6K/tháng**.

## 6. MVP một tuần

**Slice:** replay tổng hợp ở quy mô **1/1000** (1M req/ngày ≈ 5 GB), đi đủ đường Bronze → Silver bodies/meta → Gold 5 phút → một query dashboard và một query incident review, chạy 10 ngày dữ liệu mô phỏng.

| Ngày | Việc |
|---|---|
| 1–2 | Generator có seeded PII + Flink (hoặc delta-rs, như PoC) token hoá → Bronze; commit 60 s |
| 3 | Silver bodies/meta, Z-order `tenant_id`, compaction theo giờ, checkpoint |
| 4 | Gold 5 phút qua CDF; query dashboard trên Trino/DuckDB |
| 5 | Diễn tập vận hành: retention + VACUUM; RESTORE trong grace; canary PII; đo nén/bytes để ngoại suy chi phí |

**Tiêu chí nghiệm thu:**
1. **0 PII thô** trong lake với 10K PII mẫu đã gieo (detector chạy sau khi bỏ token).
2. Freshness Gold p95 **< 5 phút** từ lúc request đến.
3. Query `tenant_id = X` trong 1 ngày đọc **≤ 10% số file** (đọc từ stats/log).
4. Sau retention: partition ngày 8 **không còn file vật lý nào**, Gold không đổi; RESTORE trong grace khôi phục được.
5. Chi phí ngoại suy từ bytes/ngày đo được **≤ $5K**.

**Cách kiểm tra cơ chế khó nhất** (xoá vật lý mà không làm hỏng aggregate; token hoá trước landing) đã có trong PoC chạy offline với delta-rs. Kết quả: 6 000 prompt được token hoá, 0 PII thô; DELETE giữ nguyên 10 file trên đĩa; VACUUM còn 7 file, đúng 7 ngày; Gold giữ nguyên 29 003 dòng. Nén đo được là 3.0×, dùng làm đầu vào cho mục 5.

*Nguồn/giả định:* giá S3/EBS/vCPU là giá tham chiếu công khai làm tròn, không phải báo giá. Throughput token hoá là giả định cần đo trong MVP (ngày 5). Số liệu đề bài là giả định của đề.
