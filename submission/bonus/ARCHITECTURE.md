# Bonus — Topic A: LLM observability ở quy mô 1B requests/ngày

**Tác giả:** Nguyen Tien Luong · 2A202602378 · K4-Track02-Day18 · bài cá nhân.
**Phạm vi:** thiết kế giả định theo đề bài. Số liệu scale là đầu vào của đề; số liệu đơn giá và hiệu năng ghi rõ là *giả định* hay *đo trong PoC*.

---

## 1. Problem statement

Một team foundation-model API log mọi request/response: **1B req/ngày × ~5 KB = 5 TB/ngày raw** (trung bình 11,6K req/s, 58 MB/s; giả định peak = 3× → 35K req/s, 174 MB/s). Bốn yêu cầu:

1. Dashboard cost & latency theo tenant, **refresh mỗi 5 phút**.
2. Prompt/response đầy đủ giữ **7 ngày** cho incident review; sau đó chỉ giữ aggregate **1 năm**.
3. **PII được redact trước khi bất kỳ ai đọc.**
4. Tổng chi phí storage ≤ **$5K/tháng**.

Vì sao khó: (a) không thể giữ nguyên 365 ngày full text — 456 TB nén 4× ≈ **$10,5K/tháng chỉ riêng S3** (xem §5); (b) "7 ngày rồi xoá" xung đột trực tiếp với time travel và với mọi bản sao dẫn xuất (index tìm kiếm incident) — xoá ở version hiện tại **không** xoá byte vật lý (NB8, NB6); (c) phát hiện PII bằng model trên 100% traffic là không khả thi về chi phí; (d) tải ghi liên tục dễ sinh small-file, và chi phí/độ trễ tăng theo số file chứ không theo dung lượng (NB6).

Giả định được dùng xuyên suốt: nén Parquet+zstd cho text **4×** (cần xác nhận ở MVP); 10K tenant; giá AWS us-east-1 theo bảng giá niêm yết tôi nhớ, **chưa tra lại tại thời điểm viết — phải kiểm tra trước design review**.

## 2. Kiến trúc (một sơ đồ)

```
 API gateways ──(zstd batch, KPL aggregation)──► Kinesis Data Streams (60 shards, 24h replay)   [D3]
                                                          │
                                   Flink on EKS: redact PII in-stream (regex+Luhn+HMAC token)   [D4]
                                  ┌───────────────────────┼─────────────────────────────────────┐
                                  ▼                       ▼                                     ▼
              QUARANTINE (S3, KMS, TTL 24h,      SILVER  Iceberg  llm_calls                GOLD  Iceberg  tenant_metrics_5m
              only the redactor role can read)   redacted full text, 7d                    5-min windows 30d, then hourly 365d
              = replay source if redactor bug    partition day(ts) [hidden] [D5]            produced by Flink windows, watermark 2 min [D7]
                                                 sort (tenant_id, ts) at compaction                       │
                                                          │                                               ▼
   Catalog = control plane: AWS Glue Iceberg catalog [D2]  │                       Athena: dashboards (≈15 MB/query)
   commits are atomic pointer swaps ────────────────────── ┤
                                                          ▼
   Nightly maintenance (Spark procedures) [D6]:  rewrite_data_files(sort) → DELETE day < now-7d → expire_snapshots(24h) → remove_orphan_files(≥3d)
                                                          │
                                  Athena: incident review (tenant + time filter, role-gated, every query audited)
   Reconciler: canaries (PII strings, expired doc ids) probe Silver, snapshots, search index, bucket prefix → alarm     [§4]
```

Khái niệm Day 18 được áp dụng vào lựa chọn cụ thể (không chỉ nêu tên):
**medallion** (quarantine/Bronze → Silver → Gold, mỗi tầng có retention riêng) · **hidden partitioning + catalog** (NB5: lọc trên `ts`, partition `day(ts)` suy ra từ metadata) · **compaction + clustering để file-skipping** (NB2: 55× pruning; NB6: 18× ít file, 90% skip) · **expiry + orphan sweep như một cặp** (NB6) · **time travel/rollback và mặt trái của nó với quyền xoá** (NB3, NB8) · **lifecycle bug của bản sao dẫn xuất** (NB7) · **FinOps theo số file** (NB6: $4/ngày vs $0,08/ngày).

## 3. Quyết định chính và phương án bị loại

| # | Chọn | Loại | Lý do (tradeoff cụ thể) |
|---|---|---|---|
| **D1** Table format | **Iceberg** cho Silver & Gold | **Delta**: partition evolution kém linh hoạt hơn và sink Flink/Trino kém đồng đều hơn Iceberg; phải chọn Z-order/liquid clustering thay vì hidden partitioning. **Hudi**: tối ưu cho upsert theo record key, còn workload này append-only (chỉ có dedup nhẹ) nên trả giá write-path phức tạp mà không dùng lợi thế. | Cần `day(ts)` ẩn để không ai quên predicate: NB5 đo người dùng kiểu Hive quên predicate đọc 10/10 file thay vì 1/10; ở 5 TB/ngày, quên một predicate là quét thêm cả ngày dữ liệu. Partition spec đổi được không cần rewrite (NB5: 2 spec cùng tồn tại) khi phân bố tenant thay đổi. |
| **D2** Catalog | **AWS Glue Iceberg catalog** | **Polaris/Nessie tự host**: portable hơn nhưng thêm một dịch vụ stateful phải on-call. **Hive Metastore**: thêm DB + thread-pool thrift, không có REST spec. | Catalog là control plane (NB5): đây là điểm commit nguyên tử. Team nhỏ nên mua quản trị; metadata Iceberg nằm trên S3 nên chuyển sang REST catalog sau này là đổi cấu hình (call site `load_catalog` không đổi — xem `scripts/lakehouse.py`). Chấp nhận: gắn với AWS ở lớp catalog. |
| **D3** Ingestion | **Kinesis provisioned, 60 shard** (~$680/tháng) | **MSK**: 6 broker + 3,75 TB EBS RF=3 ≈ $1,6K và phải vận hành. **Ghi thẳng S3 micro-batch (không bus)**: rẻ nhất nhưng mất replay 24h và mất fan-out cho hai consumer (redactor, metering); backpressure phải tự xử. | Peak nén ≈ 43 MB/s ⇒ ≥ 44 shard theo băng thông 1 MB/s; 60 shard cho headroom ~35%. Producer gộp bản ghi bằng KPL nên PUT payload unit ≈ 50M/ngày (~$21/tháng). On-demand mode ≈ $0,08/GB × 37,8 TB ≈ $3K — loại. |
| **D4** PII | **Redact trong luồng** (regex + Luhn + HMAC-SHA256 token cho định danh) + **quarantine mã hoá, TTL 24h** chỉ role redactor đọc được | **NER trên 100% traffic**: 1B × ~1.250 token = 1,25e12 token/ngày; ngay cả giả định lạc quan 20K token/s/vCPU cần ~723 vCPU liên tục ≈ **$19K/tháng** — vượt cả ngân sách. **Mask-at-read (view/column mask)**: ai có quyền S3 vẫn thấy PII thô ⇒ vi phạm yêu cầu "redact trước khi ai đọc". **Bỏ raw ngay**: không có đường replay khi redactor có bug. | Token HMAC ổn định nên vẫn join/đếm unique được mà không lộ giá trị. Rủi ro dư được nêu thẳng: regex **không** thấy tên người/địa chỉ tự do ⇒ giảm thiểu bằng (i) NER chỉ trên mẫu 1% để đo *leak rate* liên tục, (ii) giữ Silver text 7 ngày, role-gated, mọi query audit, (iii) canary hằng phút (§4). |
| **D5** Partition & clustering | **`day(ts)` + sort `(tenant_id, ts)` lúc compaction** | **Partition theo `tenant_id`**: 10K tenant × 1.440 commit/ngày ⇒ tới 14,4M file nhỏ/ngày (cận trên) so với 28,8K. **`hour(ts)` + `bucket(32, tenant_id)`**: mỗi partition-giờ ≈ 1,6 GB nên kích thước ổn, nhưng mỗi writer thấy mọi tenant và phải ghi vào cả 32 bucket mỗi phút ⇒ 20 writer × 32 = 640 file/phút ≈ 922K file/ngày, trung bình ~1,4 MB (so với 28,8K file ~43 MB); hash không giải quyết lệch tenant và đổi số bucket sau này là một lần đổi spec. | File đích 256 MB ⇒ ≈ 4,9K file Silver/ngày (1,25 TB nén ÷ 256 MB). Sort theo tenant làm min/max từng file hẹp; tenant trung vị chỉ chạm vài file mỗi ngày (cùng cơ chế NB2 55×, NB6 90% skip). Tenant lớn nhất (giả định 5% traffic) vẫn quét ~5% — chấp nhận, vì đó là query hiếm có role. |
| **D6** Retention | **Nightly: `DELETE day < now−7d` → `expire_snapshots(24h)` → `remove_orphan_files(≥3d)`** | **S3 lifecycle rule trên prefix**: xoá file mà metadata Iceberg vẫn tham chiếu ⇒ bảng hỏng (đọc trả lỗi file missing). **Giữ snapshot 7 ngày để time travel**: dữ liệu "đã xoá" vẫn đọc được qua snapshot cũ ⇒ phá cam kết TTL và nhân đôi chi phí Silver. | PoC (§7) chứng minh chuỗi 3 bước làm byte biến mất và snapshot cũ không còn đọc được; chỉ `DELETE` thì byte vẫn trên đĩa và time travel vẫn trả 100 dòng. Chi phí đổi lại: mất khả năng rollback Silver quá 24h — bù bằng quarantine 24h và replay Kinesis. |
| **D7** Gold & truy vấn | **Flink window 5 phút → Gold Iceberg; Athena** | **Dashboard truy vấn thẳng Silver**: mỗi lần refresh quét hàng chục GB × 57,6K query/ngày. **ClickHouse/Druid**: thêm một hệ lưu trữ phải đồng bộ và phải nhận cả sự kiện xoá (đúng lỗi NB7), vượt ngân sách vận hành. | Gold nhỏ (≈ 0,35 TB) nên Athena quét ~15 MB/query (≈ ngưỡng tối thiểu 10 MB/query). Độ tươi thực tế ≈ cửa sổ 5 phút + watermark 2 phút + commit ⇒ **≤ ~8 phút**; "refresh mỗi 5 phút" được hiểu là tần suất làm mới, nếu cần tươi hơn phải giảm cửa sổ (đánh đổi: nhiều commit hơn). |
| **D8** Tiering | **Không tiering** (S3 Standard cho mọi thứ) | **Standard-IA cho Silver**: tối thiểu tính phí 30 ngày mà dữ liệu chỉ sống ~9 ngày ⇒ $0,0125 × 30/9 ≈ **$0,042/GB-tháng hiệu dụng > $0,023** của Standard. **Glacier cho Gold**: tiết kiệm chỉ ≈ $4–7/tháng trên ~$8 nhưng thêm độ trễ/phí truy xuất. | FinOps đúng chỗ: tiering chỉ có lợi khi dữ liệu nằm đủ lâu và đủ lớn. Đòn bẩy thật là **7 ngày thay vì 365 ngày** và **nén**, không phải tier. |

## 4. Failure modes (3 giờ sáng)

| # | Sự cố | Detect | Rollback / xử lý |
|---|---|---|---|
| **F1** | Deploy redactor lỗi (regex hỏng sau refactor) ⇒ **PII lọt vào Silver** | Canary: mỗi phút bơm chuỗi PII tổng hợp đã biết (email, SĐT, thẻ Luhn-hợp-lệ, `sk-…`) và truy ngược Silver; alarm nếu canary xuất hiện nguyên văn. NER mẫu 1% đo leak rate, alarm khi vượt ngưỡng baseline. | (1) Thu hồi quyền đọc text Silver ngay (tag-based). (2) Rollback deploy. (3) Re-redact các partition ảnh hưởng **từ quarantine 24h**, ghi đè bằng một commit mới. (4) **`expire_snapshots` ngay** các snapshot chứa bản lọt, nếu không time travel (NB3/NB8) vẫn giữ PII. Giới hạn: lọt quá 24h thì không còn nguồn thô — chỉ còn xoá partition. |
| **F2** | Small-file explosion: ai đó đặt trigger 5 giây hoặc thêm writer | Metric: kích thước file trung bình theo partition (SLO ≥ 128 MB sau compaction) và số file/partition; thời gian plan query Athena. Ở trigger 5 s thay vì 1 phút: ≈ 346K file/ngày ≈ 3,6 MB/file. | Đưa trigger về 1 phút, chạy `rewrite_data_files` ngay; nhớ chạy expiry + orphan sweep sau đó (NB6: nén xong dung lượng tạm *tăng* vì ghi trước khi thu hồi — chừa headroom ~1 ngày dữ liệu). Chi phí request đo ở NB6 là hệ quả của số file, không phải dung lượng. |
| **F3** | **Lifecycle bug (Day 18/NB7):** TTL đã xoá Silver nhưng index tìm kiếm incident / bản sao BI vẫn trả nội dung hết hạn | Reconciler hằng đêm: lấy doc id đã hết hạn (đã lưu trước khi DELETE) thăm dò từng bản sao — bảng, snapshot, index, prefix S3; mong đợi 0 hit. PoC cho thấy ở trạng thái lỗi: **200 hit** từ index chưa đồng bộ. | Index đăng ký danh sách xoá (changelog/danh sách id sinh ra từ bước DELETE) thay vì tự đoán; evict rồi chạy lại reconciler. Nguyên tắc: bản sao dẫn xuất không được có TTL dài hơn nguồn. |
| **F4** | Job maintenance chết giữa chừng / writer crash để lại **orphan** (NB6: `VACUUM` của `deltalake` không thấy file chưa từng commit) | So sánh byte dưới prefix S3 với tổng byte file được snapshot hiện tại tham chiếu; alarm khi chênh > 5%. | `remove_orphan_files` với `older_than ≥ 3 ngày` — **age guard bắt buộc**, nếu không sẽ xoá file của writer đang chạy chưa commit và làm hỏng bảng (NB6). Kiểm thử bằng canary orphan giống NB6 sau mỗi lần nâng version engine, vì hành vi expiry/orphan phụ thuộc engine (NB6 chỉ đo đường PyIceberg 0.12, không phải Spark). |
| **F5** | Kinesis replay / at-least-once ⇒ trùng `request_id` làm Gold đếm đôi | Đối soát số bản ghi theo giờ giữa Kinesis → Silver → Gold. Dữ liệu mẫu NB4 có ~5% trùng (9.948/200.000) nên phải coi là bình thường. | Dedup theo `request_id` trong cửa sổ trạng thái 48h trước khi ghi Silver; dựng lại Gold của cửa sổ lỗi từ Silver rồi ghi đè partition (hoặc `rollback_to_snapshot` nếu mới sai < 24h). |

## 5. Ước lượng chi phí (back-of-envelope)

**Dung lượng.** Nén 4×: 5 TB ÷ 4 = **1,25 TB/ngày**. S3 Standard $23/TB-tháng.

| Hạng mục | Tính toán | $/tháng |
|---|---|---:|
| Quarantine (TTL 24h, ~2 ngày tồn tại thực tế) | 1,25 TB × 2 = 2,5 TB × $23 | 58 |
| Silver 7 ngày + trễ xoá + churn compaction | (7 + 2 ngày trễ) × 1,25 + 1,25 TB = 12,5 TB × $23 | 288 |
| Gold: 5-phút 30 ngày + hourly 365 ngày | 10K tenant × ~20 nhóm × 288 cửa sổ = 57,6M dòng/ngày × 300 B ≈ 17 GB/ngày; 30 ngày ≈ 0,17 TB nén 3×; hourly ≈ 0,18 TB ⇒ 0,35 TB × $23 | 8 |
| Metadata & dự phòng | NB5 chỉ ra metadata lớn khi file nhỏ; ở 256 MB/file ≈ 0,1% ⇒ dự phòng phẳng | 20 |
| Request S3 | PUT ≈ 230K/ngày ghi + 157K/ngày compaction (multipart) ≈ $58; GET ≈ 1,15M/ngày ≈ $14 | 72 |
| **Tổng storage + request** | | **446** |

**Compute & dịch vụ** (để thấy tổng thể, không chỉ storage):

| Hạng mục | Tính toán | $/tháng |
|---|---|---:|
| Kinesis | 60 shard × $0,015 × 730 h + PUT units ≈ $21 | 680 |
| Flink/EKS (redact + window + commit) | **PoC đo 12,3 MB/s/core** ⇒ peak 174 MB/s cần ≈ 14,2 vCPU chỉ cho redact; thêm ~16 vCPU cho encode/commit/window ⇒ 4 × c7g.2xlarge × $0,29 × 730 + EKS $73 | 920 |
| Maintenance (Spark spot/OD) | 32 vCPU × 2 h × 30 ngày × $0,036 | 70 |
| Athena – dashboard | 57,6K query/ngày × 15 MB ≈ 26 TB/tháng × $5 | 130 |
| Athena – incident review | 100 query/ngày × 25 GB = 75 TB/tháng × $5 | 375 |
| Glue catalog | | 10 |
| KMS / CloudWatch / audit (dự phòng) | | 150 |
| **Tổng nền tảng** | 446 + 680 + 920 + 70 + 130 + 375 + 10 + 150 | **≈ 2.781** |

⇒ **Storage ≈ $446/tháng (9% trần $5K); cả nền tảng ≈ $2,8K (56%)**, còn ~$2,2K dự phòng.

**Phương án so sánh (để thấy đòn bẩy):**
- Giữ nguyên full text 365 ngày: 1,25 TB × 365 = 456 TB × $23 ≈ **$10,5K** — vượt trần. Nếu không nén: 1.825 TB ≈ **$42K**.
- NER trên 100% traffic: ≈ **$19K/tháng** (giả định 20K token/s/vCPU, $0,036/vCPU-giờ) — loại ở D4.
- Độ nhạy: nếu nén chỉ đạt 2× thay vì 4×, Silver ≈ 25 TB ≈ $575 ⇒ storage ≈ $790 — vẫn ổn. Nếu redactor chậm gấp đôi số đo PoC, phần redact tăng ~14 vCPU (≈ $370/tháng) — vẫn ổn. **Biến rủi ro lớn nhất là hiệu năng và recall của redactor, không phải storage.**

## 6. Slice MVP một tuần

**Phạm vi:** 1% traffic tổng hợp (10M req/ngày, 50 GB/ngày raw, 100 tenant) đi hết đường: generator → redactor → quarantine + Silver Iceberg → Gold 5 phút → nightly maintenance → reconciler. Không làm: multi-AZ, autoscale, UI dashboard thật.

| Ngày | Việc |
|---|---|
| 1–2 | Generator (có PII gắn nhãn + tenant lệch kiểu power-law), redactor, quarantine, Silver `day(ts)` |
| 3 | Gold window 5 phút + watermark; test dedup |
| 4 | Maintenance: compaction sort theo tenant, DELETE, expire, orphan sweep |
| 5 | Reconciler + canary; kịch bản F1–F4 thử thật |
| 6–7 | Đo, sửa, viết kết quả đối chiếu với tiêu chí dưới đây |

**Tiêu chí nghiệm thu (đều kiểm chứng được):**
1. **Redactor:** 0 chuỗi PII đã gắn nhãn còn nguyên văn trong Silver; recall ≥ 99% trên bộ nhãn *có cả mẫu khó* (không chỉ mẫu regex dễ); 0 false positive trên số 16 chữ số không qua Luhn; throughput ≥ số dùng để sizing (12,3 MB/s/core) trên CPU Graviton thật.
2. **TTL thật sự xoá:** sau bước maintenance, grep byte của chuỗi sentinel trong mọi object dưới prefix = 0 (có positive control trước đó); `scan(snapshot_id=…)` của snapshot cũ báo lỗi; 0 hit ở index dẫn xuất và ở reconciler.
3. **File skipping:** query một tenant trung vị trong 1 ngày mở ≤ 2% số file của partition; kích thước file trung bình sau compaction ≥ 128 MB.
4. **Độ tươi Gold:** p95 độ trễ từ event đến Gold ≤ 8 phút.
5. **F1/F2/F4:** mỗi kịch bản bị tạo ra cố ý và alarm kêu trong thời gian đã định; quy trình rollback chạy được.

**Cơ chế khó nhất được kiểm chứng sớm nhất** là (1) redactor (rủi ro chi phí *và* tuân thủ) và (2) xoá thật (rủi ro cam kết). Cả hai đã có spike tại `poc/` (xem §7); MVP thay dữ liệu tổng hợp bằng log thực đã ẩn danh trước khi dùng để kết luận recall.

## 7. PoC đã chạy (`poc/retention_and_redaction_poc.py`)

Chạy: `.venv/Scripts/python.exe submission/bonus/poc/retention_and_redaction_poc.py` từ thư mục gốc repo (PyIceberg 0.12, local). Kết quả thật của lần chạy:

| Phép đo | Kết quả |
|---|---|
| Redactor trên corpus **tổng hợp** 20K tài liệu | 10.216 secret được gài: **0 lọt**, recall 1,0000; 0 false positive Luhn trên số 16 chữ số |
| Throughput redactor (Python `re`, 1 core, máy cá nhân Windows) | **12,3 MB/s** — dùng để sizing ở §5 (thấp hơn giả định ban đầu 30 MB/s của tôi) |
| TTL: sau `DELETE` | còn 700/900 dòng, nhưng byte `SENTINEL-DAY0` **vẫn nằm trên đĩa** và time travel snapshot cũ vẫn đọc được 100 dòng |
| TTL: sau expire + sweep | giải phóng 37,9 KB / 13 file; còn 1 snapshot; byte DAY0/DAY1 = **0 file**; DAY8 vẫn còn; time travel snapshot cũ báo `ValueError` |
| Lifecycle bug | index dẫn xuất còn trả **200** doc hết hạn; sau evict theo danh sách xoá: 0 |

**Giới hạn phải nói thẳng:** (i) recall 1,0 chỉ áp dụng cho *các mẫu do chính tôi gài* — nó chứng minh logic detector và token hoá, **không** chứng minh recall trên log thật; tên người và địa chỉ tự do không được phát hiện; (ii) throughput đo trên một máy x86 Windows với Python, không phải Graviton hay thư viện regex chuyên dụng; (iii) PoC chạy PyIceberg cục bộ — `expire_snapshots` ở đây chỉ gỡ snapshot, file vẫn nằm trên đĩa cho tới bước sweep tự viết (giải phóng 13 file; khớp phát hiện của NB6); Spark `expire_snapshots`/`remove_orphan_files` trên S3 chưa được thử; (iv) không đo Kinesis, Flink, Athena hay giá thật — mọi con số dịch vụ ở §5 là ước tính từ giả định đã ghi.

## Nguồn tham khảo

- Kết quả đo của chính lab này (NB2, NB3, NB4, NB5, NB6, NB7, NB8) và `docs/CHECKPOINTS.md`.
- Apache Iceberg docs — hidden partitioning, `expire_snapshots`, `remove_orphan_files`, `rewrite_data_files`: <https://iceberg.apache.org/docs/latest/>.
- Bảng giá niêm yết AWS (S3, Kinesis Data Streams, EC2, Athena, EKS, Glue): <https://aws.amazon.com/pricing/> — **chưa tra lại tại thời điểm viết, cần xác minh trước khi dùng cho quyết định thật.**
- Bài này không khẳng định tuân thủ một quy định pháp lý cụ thể; nếu triển khai thật cần tra văn bản đang áp dụng cho dữ liệu của tenant.
