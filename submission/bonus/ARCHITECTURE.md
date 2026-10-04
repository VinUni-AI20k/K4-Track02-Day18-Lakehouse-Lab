# Bonus A — LLM Observability ở 1B requests/ngày

**Tác giả:** Nguyễn Vũ Huy · 2A202602662 · K4-Track02-Day18
**PoC:** [`poc/pii_tokenize_cluster.py`](poc/pii_tokenize_cluster.py), output thật ở [`poc/run_output.txt`](poc/run_output.txt)

---

## 1. Problem statement

Một team cung cấp foundation-model API ghi log mọi request/response: **1B request/ngày × ~5 KB = 5 TB/ngày raw**,
trung bình ~11.6K req/s, giả định peak gấp 3 lần (~35K req/s). Có bốn yêu cầu:

1. Dashboard cost & latency **theo tenant**, refresh mỗi **5 phút**.
2. Prompt/response đầy đủ giữ **7 ngày** để review sự cố; sau đó chỉ giữ **aggregates 1 năm**.
3. **PII phải được redact trước khi bất kỳ ai đọc được.**
4. Tổng chi phí **storage ≤ $5K/tháng**.

**Vì sao khó.**
- Số tenant lớn và lệch (vài tenant chiếm phần lớn traffic). Partition theo tenant sẽ sinh ra hàng trăm nghìn file nhỏ mỗi ngày.
- PII nằm lẫn trong **free text**, không ở cột riêng, nên masking theo cột không đủ.
- Time travel và backup giữ lại mọi version cũ. "Xóa sau 7 ngày" vì vậy phải xóa **vật lý**, không chỉ xóa logic.
- 5 TB/ngày mà lưu nguyên cả năm thì vượt ngân sách khoảng 30 lần (xem §5).

## 2. Architecture

```
 API gateways (N regions)
      │  JSON events (~5 KB)        ┌──────────── control plane ─────────────┐
      ▼                             │ Unity Catalog: grants, audit log đọc,  │
 Kafka (24h retention, zstd)        │ lineage; vault chỉ role `pii-breakglass`│
      │                             └────────────────────────────────────────┘
      ▼
 Stream job (Spark Structured Streaming, trigger 1 phút, exactly-once checkpoint)
      │  ① TOKENIZE PII trước khi ghi (HMAC-SHA256, key KMS) ──► PII_VAULT (Delta, KMS, 7d TTL)
      ▼
 BRONZE  llm_raw            Delta · Parquet zstd · partition (ingest_date, ingest_hour)
         prompt/response đã tokenize · schema enforced + cột `_extra` (cũng được tokenize)
         ② giữ 7 ngày → drop partition + VACUUM 24h          [retention / time travel]
      │  ③ OPTIMIZE + Z-ORDER(tenant_id) mỗi giờ đã đóng     [compaction / file skipping]
      ▼
 SILVER  llm_calls          dedup request_id (MERGE), bỏ text, chỉ giữ metrics (~60 B/row)
         partition ingest_date · Z-ORDER(tenant_id, model) · CDF on · giữ 30 ngày
      │  ④ Change Data Feed → incremental aggregate mỗi 5 phút   [CDC / incremental]
      ▼
 GOLD    tenant_5min (30 ngày) ──rollup──► tenant_hourly (365 ngày)
         p50/p95 latency, tokens, cost_usd, error_rate · Z-ORDER(tenant_id)
      │  ⑤ RESTORE / time travel nếu job Gold ghi sai          [time travel]
      ▼
 Dashboard (Trino/DuckDB service, cache 5 phút) · Incident review (đọc Bronze, token) ·
 Break-glass re-identify (join vault, có audit + phê duyệt)
```

**Các concept Day18 được áp dụng vào lựa chọn cụ thể:**
- **Medallion.** Bronze giữ text đã tokenize, Silver chỉ giữ metrics, Gold giữ aggregates. Retention khác nhau theo tầng: 7 ngày / 30 ngày / 365 ngày.
- **ACID + schema enforcement.** Một batch có field lạ sẽ bị chặn, hoặc bị đưa vào cột `_extra` (và `_extra` cũng đi qua tokenizer).
- **Compaction + Z-order** cho hot path "filter by tenant".
- **Time travel / RESTORE** để rollback Gold.
- **Retention / VACUUM** để xóa PII về mặt vật lý.
- **Change Data Feed** để cập nhật Gold incremental.
- **Catalog** làm control plane cho grants và audit.
- **FinOps:** budget storage được tính ở §5.

## 3. Các quyết định chính và alternatives đã loại

### D1 — Table format: chọn **Delta Lake**
- **Loại Iceberg.** Iceberg có hidden partitioning và catalog trung lập, đó là ưu điểm thật (NB5). Nhưng ở đây filter thời gian dùng `ingest_date` do chính pipeline sinh ra, nên lợi ích hidden partitioning nhỏ. Ngược lại, pipeline cần **CDF** để Gold incremental, cần streaming sink exactly-once và MERGE dedup. Trên Spark/Delta các tính năng này chín hơn. NB6 cũng cho thấy expiry của PyIceberg không tự xóa file vật lý, thêm một job phải tự chain.
- **Loại Hudi.** Merge-on-Read mạnh cho upsert dày đặc, nhưng log ở đây gần như append-only (dedup chỉ ~1%). Đổi lại sẽ phải vận hành thêm compaction MoR và timeline service, không đáng.
- **Loại Parquet thuần + Hive partition.** Không có ACID: reader có thể đọc file của batch đang ghi dở. Không có time travel để rollback, và không có transaction log để biết file nào là orphan.

### D2 — Ingestion: chọn **micro-batch 1 phút** (Spark Structured Streaming)
- **Loại streaming từng event (Flink commit vài giây).** SLA chỉ là 5 phút, latency thấp hơn không mang lại giá trị. Ngược lại, commit liên tục tạo hàng triệu file nhỏ: NB2 đo 200 file nhỏ làm point query chậm 16.6× so với sau OPTIMIZE. Commit dày còn tăng xung đột optimistic concurrency với job compaction.
- **Loại batch hourly.** Vi phạm SLA 5 phút.
- **Chi phí của lựa chọn này.** 1 phút × 24 h = 1,440 commit/ngày cho mỗi bảng. Cần checkpoint log (NB6: cứ 100 commit có một checkpoint) và compaction mỗi giờ.

### D3 — PII: chọn **tokenize deterministic (HMAC-SHA256) ngay trong stream, trước khi ghi Bronze; vault tách riêng**
- **Loại redact ở Silver.** Khi đó PII thô vẫn nằm trong Bronze, và còn sống tiếp trong mọi version cũ có thể time travel. NB8 cho thấy xóa ở version hiện tại không xóa version cũ. Điều này vi phạm yêu cầu "redact trước khi bất kỳ ai đọc".
- **Loại mã hóa cột / masking view.** PII nằm lẫn trong free text chứ không ở cột riêng. Masking view còn phụ thuộc việc *mọi* engine tuân thủ policy: một ai đó đọc thẳng file Parquet là bypass được.
- **Loại hash một chiều không có vault.** Incident review đôi khi phải re-identify, ví dụ khi khách hàng báo lỗi kèm email. Vault cho phép làm việc này qua quy trình break-glass có audit.
- **Vì sao chọn deterministic.** Cùng một email luôn ra cùng một token, nên vẫn đếm được distinct user và join được qua các bảng.
- **Bằng chứng PoC:** 240,000 dòng, **0** email / **0** phone thô trong Bronze, token không phân biệt hoa thường.
- **Giới hạn.** Regex chỉ bắt PII có cấu trúc (email, số điện thoại, số giấy tờ). Tên người và địa chỉ trong free text cần thêm một bước NER; đó là rủi ro còn mở, ghi ở §4.

### D4 — Layout: chọn **partition `(ingest_date, ingest_hour)` + Z-order `tenant_id`**
- **Loại partition theo `tenant_id`.** Giả sử 10K tenant × 24 giờ = 240K partition/ngày. Phần lớn là tenant nhỏ, nên mỗi partition chỉ có một file vài KB, đúng small-file explosion của NB2/NB6. Metadata sẽ phình: NB5 đo metadata bằng 293% dữ liệu khi file nhỏ.
- **Loại chỉ partition theo date, không clustering.** Mỗi file chứa trộn mọi tenant, nên min/max stats không loại được file nào. PoC đo được: trước Z-order, lọc 1 tenant phải mở **120/120** file.
- **Kết quả với lựa chọn này (PoC):** sau Z-order chỉ đọc **2/47** file, tức skip **96%**. Partition theo giờ ingest còn giúp xóa theo retention ở mức metadata: drop đúng các partition quá 7 ngày.

### D5 — Format file / nén: chọn **Parquet + zstd** (level 3)
- **Loại snappy.** Nén nhanh hơn, nhưng thường cho file lớn hơn zstd khoảng 20–40% với log văn bản. Ở 7–9 TB Bronze thì chênh khoảng $40–80/tháng storage và nhiều byte phải scan hơn.
- **Loại JSON.gz ở Bronze.** Không có column pruning: dashboard chỉ cần `tenant_id, latency` cũng phải giải nén toàn bộ prompt. NB7 đo projection pushdown chỉ đọc 1.2 KB / 12.5 MB khi blob nằm trong cột riêng.

### D6 — Lifecycle: chọn **xóa Bronze sau 7 ngày bằng drop partition + VACUUM 24h; Gold hourly giữ 365 ngày**
- **Loại S3 lifecycle rule đẩy file Bronze sang IA/Glacier.** Lifecycle rule đổi storage class *dưới* một bảng Delta mà transaction log không biết. Glacier làm file không đọc được, nên query và time travel lỗi. Ngoài ra yêu cầu đề là *không giữ* raw sau 7 ngày (data minimization), không phải giữ rẻ hơn.
- **Loại giữ hết raw 1 năm.** ~365 TB sau nén × ~$22/TB ≈ **$8K/tháng**, vượt budget, và giữ PII lâu hơn mức cần.
- **Lưu ý từ NB6.** VACUUM chỉ xóa file đã bị tombstone. File do writer crash để lại thì cần một job orphan sweep riêng, xem F4.

### D7 — Catalog / governance: chọn **Unity Catalog** (grants + audit đọc + lineage)
- **Loại AWS Glue + Lake Formation.** Phải quản lý quyền ở hai nơi. Hỗ trợ Delta qua manifest kém hơn, và không có audit log ở mức bảng/cột đồng nhất cho mọi engine.
- **Loại Hive Metastore.** Không có fine-grained grants: không thể tách quyền đọc `pii_vault` khỏi quyền đọc Bronze.
- **Rủi ro vendor lock-in.** Giảm bằng cách giữ dữ liệu ở định dạng mở (Delta/Parquet trên S3). Nếu sau này cần đổi catalog thì có thể migrate (topic F).

## 4. Failure modes (3 giờ sáng)

| # | Sự cố | Phát hiện | Rollback / khắc phục |
|---|---|---|---|
| F1 | **Deploy lỗi job Gold** (bảng giá sai) → `cost_usd` của mọi tenant sai, khách hàng thấy hóa đơn sai | Job reconcile mỗi 5 phút so `SUM(cost)` Gold với Silver theo giờ; alert khi lệch > 0.5% | **Time travel / RESTORE** Gold về version cuối cùng đã pass reconcile (NB3: RESTORE chỉ ghi metadata, < 1 phút). Sửa job, đọc lại Silver qua **CDF** cho các cửa sổ bị ảnh hưởng. Bronze/Silver không đổi |
| F2 | **Upstream thêm field mới mang PII** (`tool_args` chứa số điện thoại) | Schema enforcement chặn batch, hoặc field rơi vào `_extra` (cũng được tokenize). Scanner chạy hằng giờ trên mẫu 1% mọi cột string. Alert nếu có match | Dừng stream (offset Kafka được giữ 24h nên không mất dữ liệu). Thêm field vào tokenizer. `DELETE`/rewrite các dòng bị lộ, rồi **VACUUM retention ngắn** để version cũ chứa PII bị xóa vật lý. Đánh đổi: mất time travel của khoảng đó (NB6/NB8). Lưu audit log ai đã đọc bảng trong khoảng lộ |
| F3 | **Compaction job chết** → file nhỏ tăng vọt, dashboard > 5 phút, chi phí GET tăng | Metric `numFiles` và kích thước file trung bình theo partition giờ (SLO: ≥ 128 MB). Đo freshness lag từ event ts tới commit Gold | Chạy lại OPTIMIZE + Z-order cho các giờ bị bỏ sót (idempotent). Writer tự tăng trigger interval khi lag cao. Dashboard tạm đọc Gold đã có, không quét Bronze |
| F4 | **Orphan files từ writer crash** → dung lượng S3 thật lớn hơn dung lượng bảng báo cáo, bill tăng âm thầm | So S3 Inventory hằng ngày với tổng `size` trong log; alert nếu chênh > 5% | Orphan sweep: lấy *file trên S3 − file được log tham chiếu*, có **age guard ≥ 24h** (NB6: VACUUM của delta-rs không thấy loại file này). Chạy dry-run trước, sau đó mới xóa |
| F5 | **Tokenizer tokenize nhầm chính token** (regex phone khớp chuỗi hex bên trong token) | Số entry trong vault tăng bất thường so với số distinct user; test hồi quy trên corpus mẫu | **Đã gặp thật trong PoC:** lần chạy đầu vault có 10,032 entry thay vì 10,000, và scanner báo 1,507 "phone" ở Bronze. Sửa bằng word boundary trong regex. Thêm test này vào CI của tokenizer |

## 5. Ước lượng chi phí (back-of-envelope)

**Giả định.** S3 Standard ~$23/TB-tháng (bậc 50 TB đầu, us-east-1). PUT $0.005/1K, GET $0.0004/1K.
EBS gp3 ~$0.08/GB-tháng. EC2 m6i.2xlarge ~$0.384/h on-demand. Tất cả là **giá niêm yết tham khảo**, cần tra lại theo region thực tế.
**Tỷ lệ nén Parquet zstd so với JSON raw được giả định là 5×**; MVP phải đo lại trên log thật, xem §6.

### Storage (budget cap $5K)

| Thành phần | Phép tính | Dung lượng | $/tháng |
|---|---|---:|---:|
| Bronze (text đã tokenize) | 5 TB/ngày ÷ 5 = 1 TB/ngày × (7 ngày + 1 ngày chờ VACUUM + ~1 ngày tạm do compaction ghi đè) | ~9 TB | ~$207 |
| Silver (metrics, không text) | 1B × ~60 B = 60 GB/ngày × 30 ngày | ~1.8 TB | ~$41 |
| Gold 5-phút | 10K tenant × 10 model × 288 slot × ~100 B ≈ 2.9 GB/ngày × 30 ngày (giả định thưa, mọi tenant đều active, cận trên) | ~0.09 TB | ~$2 |
| Gold hourly | 2.4M dòng/ngày × 100 B = 0.24 GB/ngày × 365 ngày | ~0.09 TB | ~$2 |
| PII vault | distinct PII value, giả định ≤ 50 GB | 0.05 TB | ~$1 |
| Kafka (EBS, RF=3, 24h) | 5 TB/ngày ÷ 4 (zstd producer) × 3 replica | ~3.75 TB | ~$300 |
| S3 requests | PUT ≈ (1,440 × ~20 writer × 2 bảng + compaction) ≈ 70K/ngày → 2.1M/tháng ≈ $11; GET dashboard ≈ 50M/tháng ≈ $20 | — | ~$31 |
| **Tổng storage** | | **~14.8 TB** | **≈ $584** |

Kết quả nằm dưới cap **$5K** khoảng 8.5 lần. Kiểm tra độ nhạy:
- Nếu nén chỉ đạt **2×**, Bronze ≈ 2.5 TB/ngày × 9 ngày = 22.5 TB → $518, tổng ≈ **$895**. Vẫn dưới cap.
- Nếu giữ raw 1 năm (đã loại ở D6): 365 TB × ~$22 ≈ **$8K**, vượt cap.

### Compute (ngoài cap storage, nhưng phải trình bày)

| Job | Ước lượng | $/tháng |
|---|---|---:|
| Stream ingest + tokenize (peak 35K req/s, ~175 MB/s) | 6 × m6i.2xlarge (48 vCPU) × 730 h × $0.384 | ~$1,680 |
| OPTIMIZE + Z-order mỗi giờ (~42 GB/giờ đã nén) | ~2 node-giờ/ngày spot (~$0.15/h) × 30 → thêm buffer, làm tròn | ~$60 |
| Gold incremental mỗi 5 phút (đọc CDF Silver) | 2 × m6i.2xlarge luôn bật | ~$560 |
| Query service cho dashboard | 2 × m6i.2xlarge | ~$560 |
| Kafka brokers | 3 × m6i.large × $0.096 × 730 | ~$210 |
| **Tổng compute** | | **≈ $3.1K** |

**Sanity check tokenizer.** PoC xử lý 240K dòng (sinh dữ liệu + regex + HMAC + ghi Delta) trong khoảng 7–10 s trên 1 core laptop, tức ~25–35K dòng/s/core. Peak 35K req/s chỉ cần vài core cho phần tokenize, nên 48 vCPU là dư cho parse JSON, tokenize và ghi. Payload thật dài hơn payload PoC, nên MVP phải benchmark lại.

## 6. MVP một tuần

**Phạm vi.** Replay **1 ngày log thật đã lấy mẫu** (~10M request, 3 tenant lớn + 50 tenant nhỏ) qua Kafka local → stream → Bronze/Silver/Gold → một dashboard p95/cost theo tenant. Chạy 1 region, chưa HA.

| Ngày | Việc |
|---|---|
| 1 | Schema Bronze + tokenizer (từ PoC) + test hồi quy PII (gồm case F5) |
| 2 | Stream job micro-batch 1 phút → Bronze; checkpoint exactly-once; đo tỷ lệ nén thật |
| 3 | Silver (MERGE dedup) + CDF → Gold 5 phút; job reconcile |
| 4 | OPTIMIZE/Z-order mỗi giờ; metric numFiles/freshness; dashboard |
| 5 | Drill: retention (drop partition + VACUUM), RESTORE Gold (F1), dò PII leak (F2), orphan sweep (F4) |

**Tiêu chí nghiệm thu (đo được):**
1. Scanner chạy trên **100%** dòng Bronze: **0** email/phone thô. PoC hiện tại: 0 / 240,000.
2. Query lọc 1 tenant **skip ≥ 90%** file sau Z-order. PoC: 96% (2/47 file).
3. Freshness từ event tới Gold **p95 ≤ 5 phút**, đo bằng `max(event_ts)` so với thời điểm commit Gold.
4. Drill F1: RESTORE Gold về version tốt và reconcile pass trở lại trong **< 10 phút**.
5. Drill retention: sau VACUUM, partition ngày thứ 8 **không còn file vật lý**. Time travel về version trước đó báo lỗi thiếu file, và đó là hành vi mong muốn.
6. Đo tỷ lệ nén thật: nếu **< 2×** thì phải xem lại bảng chi phí ở §5 trước khi scale.

**Mechanism khó nhất và cách kiểm chứng.** "PII không bao giờ chạm tới bảng đọc được" được kiểm chứng bằng PoC: tokenize *trước* khi ghi, scanner trên mọi cột string, token deterministic. Chạy PoC:
`.venv\Scripts\python.exe submission/bonus/poc/pii_tokenize_cluster.py`

Script chạy offline bằng stack của lab và in 6 check PASS. Số đo latency của PoC (lọc tenant: 331 ms → 36 ms, nhanh hơn 9.2×) chạy trên laptop nên dao động giữa các lần chạy. Số file bị skip (2/47) là số xác định từ metadata nên ổn định hơn.

## 7. Giới hạn và nguồn tham khảo

**Giới hạn:**
- Các số scale là đầu vào của đề, không phải số đo từ hệ thống thật.
- Giá cloud là giá tham khảo.
- Tokenizer chưa xử lý PII phi cấu trúc (tên người, địa chỉ); cần NER và đánh giá recall riêng.
- Bài này không đánh giá việc tuân thủ pháp lý.

**Nguồn tham khảo:**
- Delta Lake docs: OPTIMIZE / Z-order, VACUUM, Change Data Feed, RESTORE (delta.io).
- AWS S3 pricing page; Amazon EC2 on-demand pricing (tra cứu tháng 10/2026, cần kiểm tra lại).
- Lab Day18: NB2 (small files, Z-order), NB3 (RESTORE), NB5 (metadata overhead), NB6 (VACUUM / orphan / expiry), NB7 (projection pushdown), NB8 (xóa ở version hiện tại ≠ xóa vật lý).
