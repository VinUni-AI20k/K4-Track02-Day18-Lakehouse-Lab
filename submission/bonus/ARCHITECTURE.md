# LLM observability: 1 tỷ request/ngày

Trần Đại Nhân · 2A202602642 · K4-Track02-Day18 · 05/10/2026

## 1. Bài toán và ranh giới thiết kế

Hệ thống giả định nhận 1 tỷ request/ngày, mỗi log 5 KB: 5 TB raw/ngày.
Dashboard latency, lỗi và cost theo tenant phải cập nhật trong 5 phút.
Prompt/response đã che PII được tra cứu trong 7 ngày; sau đó chỉ aggregates
được giữ trong 1 năm. Không có người đọc PII nguyên bản. Ngân sách storage
tối đa 5.000 USD/tháng. Khó nhất là vừa xử lý retry, vừa bảo đảm retention
thực sự thu hồi nội dung mà không phá reader hoặc tạo bản sao ngoài kiểm soát.

Giả định thiết kế: 10.000 tenant, 3 model, peak bằng 5 lần trung bình trong
2 giờ/ngày; nén payload 4:1; log đến trễ tối đa 24 giờ. Ngày là UTC, tháng
30 ngày; KB/GB/TB dùng hệ thập phân. SLA 5 phút áp dụng dữ liệu đã đến ingress;
sự kiện đến muộn được sửa vào cửa sổ cũ khi đến, không thể có trong dashboard
trước khi hệ thống nhận được. Số này là đầu vào thiết kế, chưa phải benchmark.

## 2. Kiến trúc và luồng đọc/ghi

```text
API -> Sanitizer (deny on uncertainty, no raw payload logs)
         | redacted event + stable request_id
         v
     Durable queue (redacted, <=24h replay)
         |
         +-> Immutable payload packs (ZSTD, <=1h age span)
         |       URI + offset + checksum; expires at age 7d
         v
 Bronze Delta envelopes -> Silver Delta facts -> Gold Delta 5m
   ACID + source offset      dedup / contract      sums + sketches
   hourly generation        tenant clustering     retained 365d
         |                        |                    |
         +--- Catalog + expiry ledger + read leases ---+
                                  |                    |
                         incident read gateway    serving cache
                         payload access audit     tenant dashboard
```

Bronze giữ envelope đã sanitize, URI payload và offset nguồn. Silver định kiểu,
dedup theo `(tenant_id, request_id)`, ghi `source_version` và `transform_version`.
Gold lưu count, error_count, tổng token, cost và sketch phân phối latency;
p95 của ngày phải merge sketch, không lấy trung bình các p95 5 phút.
Giá có `price_version`, effective time và model để backfill không dùng giá mới
cho request cũ. Cache phục vụ có watermark `gold_version`; công bố cache sau
khi commit Gold thành công, không giả định transaction xuyên nhiều bảng.

Medallion, ACID, clustering, catalog, version pin và lifecycle đều có vai trò
cụ thể trong sơ đồ. Incident gateway kiểm quyền tenant và thời hạn trước
khi đọc payload; analyst chỉ được Gold. Catalog ánh xạ tên logic sang các
generation còn sống, schema, owner và ngày hết hạn. Object policy chặn đọc
trực tiếp nên biết URI không đủ quyền truy cập.

<!-- pagebreak -->

## 3. Quyết định kiến trúc và alternatives

**D1. Chọn Delta cho envelope/fact/aggregate.** MERGE và version history phù
hợp retry, backfill và rollback như NB3–NB4. Loại Parquet thuần vì phải tự làm
commit atomic và quản lý file đang sống. Loại Iceberg trong MVP vì nhóm giả
định đã vận hành Spark/Delta; đổi engine làm tăng phần cần kiểm thử. Iceberg
có field ID và partition evolution tốt như NB5; nếu nhiều engine thành yêu
cầu chính, đánh giá lại bằng compatibility matrix, không dual-write ngay.

**D2. Chọn catalog dịch vụ nhỏ với registry trong PostgreSQL HA, Spark làm
writer duy nhất.** Registry quản lý generation, owner, lease và expiry ledger;
log Delta vẫn là nguồn trạng thái transaction. Loại SQLite local vì không phù
hợp nhiều service/HA. Loại truy cập theo path không có registry vì không biết
ai còn dùng generation sắp xóa. Không tự nhận registry là REST Iceberg catalog;
REST catalog cho Iceberg không tự quản lý được Delta. Quyền thực thi ở IAM và
gateway, catalog không thay thế object ACL.

**D3. Chọn generation theo giờ, cluster Silver theo tenant.** Mỗi giờ khoảng
52 GB payload nén, nên vài trăm pack 256 MB là hợp lý. Fact có ngày/giờ phục
vụ lọc và vòng đời; compaction target 256 MB, trigger khi median <32 MB hoặc
file count vượt budget. Loại partition theo 10.000 tenant vì sparse tenant
tạo small files. Loại một bảng payload sống mãi rồi VACUUM tùy tiện vì file
rewrite có thể kéo nội dung quá retention. Hourly generation làm registry phức
tạp hơn; đổi lại có thể retire toàn bộ phạm vi tuổi mà không dựa vào latest
snapshot. NB2/NB6 là bằng chứng cơ chế, không chứng minh target production.

**D4. Chọn payload pack ZSTD với URI/offset trong bảng.** Gateway đọc range
đúng record nhờ frame ZSTD độc lập cho từng record, không nén nguyên pack
thành một stream; pack không trộn record chênh tuổi quá một giờ. Loại blob inline
trong fact vì rewrite/retention liên đới với payload và random-read amplification
của NB7. Loại một object mỗi request: 30 tỷ PUT/tháng, request overhead có thể
chi phối. 256 MB là target ingest, pack đóng sớm nếu giới hạn tuổi tới; record
index và checksum giúp phát hiện offset sai. Compression ratio phải đo bằng
mẫu sanitized, không mượn tỷ lệ 4:1 của văn bản thường cho ảnh hoặc ciphertext.

**D5. Chọn Gold incremental và serving cache đọc-only.** Loại quét lại toàn bộ
7 ngày mỗi 5 phút vì scan 35 TB raw để cập nhật một cửa sổ nhỏ. Loại giữ một
data warehouse chứa thêm toàn bộ prompt vì nhân bản chi phí và retention.
Cache là derived state có thể rebuild từ Gold; cost/error dùng sum và count,
latency dùng sketch có error bound được nghiệm thu. Đặt budget 60 giây queue,
120 giây xử lý, 60 giây publish, 60 giây dư địa: tổng 300 giây.

**D6. Chọn sanitize trước durable storage và gateway theo tenant.** Loại chỉ
mask ở dashboard vì operator vẫn có thể đọc raw. Loại regex-only cho production
vì tên/địa chỉ trong văn bản tự do không được bao phủ. Kết hợp detector, rule
và structured allowlist; event chưa đủ tin cậy giữ trong vùng xử lý mã hóa,
không human-readable, timeout thì bỏ payload và ghi lỗi không chứa PII.
Không hứa detector tuyệt đối đúng: leakage test là điều kiện rollout.

<!-- pagebreak -->

## 4. Retention, correctness và failure modes

**Retire generation thay vì VACUUM 0 trên bảng đang dùng.** Nội dung chi tiết
tối đa 7 ngày kể từ event time (không reset tuổi khi retry). Pack có expiry
bằng tuổi record sớm nhất; do vậy có thể xóa sớm tối đa một giờ. Nếu business
yêu cầu đủ chính xác 168 giờ cho từng record, dùng pack nhỏ hơn hoặc per-record
encryption key; đây là tradeoff phải chốt khi nghiệm thu, không gọi đó là
retention chính xác. Trước expiry 10 phút gateway không cấp lease đọc vượt hạn.
Worker chờ/cancel lease, retire catalog generation, xóa toàn bộ prefix cùng
mọi version file của generation, queue copy và cache liên quan; ledger ghi
ack. Object versioning tắt ở payload prefix; lifecycle chỉ là backstop vì
xóa lifecycle có thể bất đồng bộ. Sweep kiểm tra lại object inventory.

Gold không chứa prompt, subject_id hoặc request_id; giữ 365 ngày rồi retire
partition. Source version chỉ phục vụ audit lineage, không bảo đảm replay
payload sau expiry. Không giữ backup chi tiết vượt retention. Backup Gold và
registry không chứa nội dung; deletion ledger được replay trước khi cấp quyền
sau disaster recovery. Time travel chi tiết bị giới hạn bởi generation còn
sống: không cam kết vừa quên nội dung vừa phục hồi nó vô hạn.

**F1. Writer crash sau commit, trước ack queue.** Detect bằng source offset,
duplicate counters và batch ledger. Reconsume batch với khóa idempotency,
MERGE event theo ID; rebuild Gold cửa sổ bị ảnh hưởng từ Silver thay vì cộng
lại tổng. Đối chiếu row count và checksum trước publish. Không dùng delivery
exactly-once của queue làm bằng chứng exactly-once end-to-end. [S1]

**F2. Schema/type đổi làm chi phí tăng sai.** Contract chặn sai kiểu ngay tại
Bronze; canary kiểm nonnegative token, model hợp lệ, price_version. Alert khi
reject >0,1% hoặc cost/request nhảy >30% so baseline tương đương. Pin Gold
version tốt gần nhất; dừng publish, sửa transform rồi rebuild trong cửa sổ
Silver còn sống. RESTORE tạo commit mới; downstream dùng version publication
ledger để tránh cộng đúp. [S2]

**F3. Retention worker xóa file reader đang dùng.** Detect lease timeout,
MissingFile và inventory lệch ledger. Dừng sweep khi ledger lỗi; reader được
cancel trước expiry và nhận lỗi có thể thử lại nếu dữ liệu chưa hết hạn.
Trước hạn có thể dùng version còn giữ; sau xóa không có rollback payload.
Khôi phục catalog trỏ tới file đã xóa không cứu dữ liệu. Test crash giữa từng
bước retire/ack là gate bắt buộc; safety lấy từ toàn bộ generation, không
copy helper NB6 vốn chỉ xét latest Delta files.

**F4. PII detector lọt hoặc queue lag >5 phút.** Canary dùng PII giả đánh dấu;
alert khi xuất hiện marker ở zone có người đọc. Revoke quyền payload, vô hiệu
generation lỗi, xóa bản sao/pack và sửa detector; không rollback về raw. Với
lag >60 giây, autoscale trong budget; >300 giây đánh dấu dashboard stale và
ghi vi phạm SLA. Replay queue trong 24 giờ; quá cửa sổ phải báo mất dữ liệu.

**F5. Small files hoặc orphan tăng.** Theo dõi p50 file bytes, planning p95,
physical/live ratio và rewrite amplification. Dừng writer lỗi, compact phạm
vi nóng, sweep sau age guard và xác nhận không lease/writer. Snapshot expiry
và xóa vật lý là hai bước riêng; NB6 cho thấy không được chỉ nhìn snapshot
count rồi kết luận đã giảm bill.

<!-- pagebreak -->

## 5. Capacity và chi phí có thể kiểm toán

Mọi đơn giá dưới đây là **giả định planning**, không phải báo giá đã chốt.
Đối chiếu trang giá nhà cung cấp trước procurement [S4]. Dùng 23 USD/TB-tháng
cho object storage, 0,05 USD/vCPU-giờ, PUT 0,005 USD/1.000, GET 0,0004
USD/1.000. Giả định cùng region; chưa có egress Internet hay multi-region DR.

**Throughput:** 1.000.000.000 / 86.400 = 11.574 request/s trung bình;
raw 57,87 MB/s, peak 289,35 MB/s. Nén 4:1 cho payload 1,25 TB/ngày.
64 vCPU thường trực chỉ đủ nếu sanitize đạt tối thiểu 1 MB/s/vCPU;
peak 320 vCPU (thêm 256) trong 2 giờ. 320 MB/s có ít dư địa so peak,
nên gate load test bắt buộc; thấp hơn phải tăng capacity hoặc đổi giả định.

**Dung lượng steady state:**

- Payload 7 ngày: 5 / 4 × 7 = **8,75 TB**.
- Bronze envelope 50 B/request nén: 0,05 × 7 = **0,35 TB**.
- Silver fact 100 B/request nén: 0,10 × 7 = **0,70 TB**.
- Rewrite headroom chỉ trên envelopes/facts: (0,35 + 0,70) × 30% = **0,315 TB**.
- Gold: 10.000 tenant × 3 model × 288 cửa sổ/ngày × 1.024 B =
  8,84736 GB/ngày; ×365 = **3,2292864 TB**. 1 KiB gồm sketch và keys;
  nếu sketch lớn hơn phải đo lại. Sparse groups chỉ làm giảm estimate này.
- Bản phục vụ 30 ngày Gold: **0,2654208 TB**; metadata/ledger dự phòng **0,10 TB**.
- Tổng online **13,7097072 TB**, ×23 = **315,32 USD/tháng**.
- Backup Gold thêm 3,2292864 TB ×23 = **74,27 USD/tháng**.
- Queue 24h payload đã nén 1,25 TB ×3 replica ×23 = **86,25 USD/tháng**
  là storage-equivalent allowance; broker compute nằm mục fixed overhead.
- Tổng storage-equivalent **475,85 USD/tháng**; kể cả buffer 2× là
  **951,69 USD/tháng**, dưới cap 5.000. Chỉ cap storage được đề giới hạn.

**Compute + requests/tháng:** ingestion 64×720×0,05 = 2.304 USD;
burst 256×2×30×0,05 = 768 USD; maintenance 32×2×30×0,05 = 96 USD;
query/cache 16×720×0,05 = 576 USD; registry/broker/monitoring overhead giả
định 500 USD. Tổng compute **4.244 USD**. Request allowance 4 triệu PUT và
50 triệu GET là 20+20 = **40 USD**; pack giảm PUT payload về khoảng
1,25 TB/256 MB ×30 ≈146.485 thay vì 30 tỷ. GET còn phụ thuộc incident usage.
Tổng kế hoạch **4.759,85 USD/tháng**, gồm storage chưa nhân buffer.

**Sensitivity:** nén chỉ 2:1 làm payload tăng 8,75 TB và queue tăng
3,75 TB-replica, thêm 287,50 USD/tháng; cap storage vẫn còn dư.
Nhưng sanitize chỉ đạt 0,25 MB/s/core cần khoảng 4× capacity, compute sẽ
chi phối. Cardinality 100.000 tenant làm Gold/backup/cache tăng 9 lần phần
tương ứng. Không dùng phép tính storage rẻ để tuyên bố toàn hệ thống rẻ.

<!-- pagebreak -->

## 6. MVP một tuần và nghiệm thu

**Ngày 1:** dựng generator 10 triệu events, 100 tenant, retry 5%, late event
và PII canary giả; record source offsets, expected aggregates và checksum.
Lưu cấu hình seed cùng phiên bản generator. Không đưa PII thật vào PoC.

**Ngày 2:** sanitizer + queue + Bronze; đo bytes/s/core, rejected records và
bytes/request sau nén. Fault injection sau commit/trước ack; replay 3 lần
không tăng số request duy nhất. Detector phải chặn toàn bộ corpus canary
đã định nghĩa; kết quả này chưa chứng minh bao phủ mọi PII thực tế.

**Ngày 3:** Silver MERGE + Gold + cache; so count, token, cost với oracle
batch; p50/p95 so exact quantile, sai số tương đối <=1% trên phân phối test.
Inject late event rồi kiểm cửa sổ cũ được sửa, không cộng lại toàn batch.

**Ngày 4:** cơ chế khó nhất: hourly-generation expiry với đồng hồ test rút
gọn, reader lease và object inventory. Kill worker trước/sau retire, trước/
sau xóa và trước/sau ack; restart không hồi sinh expired content. Thử giữ
reader qua hạn, restore registry backup và thử gọi URI trực tiếp. Nghiệm thu:
không truy cập nội dung hết hạn, không xóa generation chưa đến hạn, zero
expired objects sau cửa sổ cleanup đã thỏa thuận (MVP 60 giây). Nếu yêu cầu
7 ngày là hạn xóa vật lý tuyệt đối không có grace, cần key revocation đúng
hạn và kiểm định crypto-erasure riêng; không tự coi sweep 60 giây là đạt.

**Ngày 5:** đo file count/pruning trước sau compaction; target giảm >=10×
và skip >=50% cho tenant fixture. Theo dõi bytes bị rewrite và orphan.
So phép đo với NB2/NB6; không extrapolate timing tuyến tính lên 1 tỷ events.

**Ngày 6:** tải kéo dài 2 giờ ở 11.574 request/s và burst 57.870 request/s
bằng generator riêng; đo p95 freshness <=300 giây, reject rate, backpressure,
throughput/core và compression. Capacity test này cần hạ tầng ngoài laptop;
chỉ đánh dấu đạt sau khi có log. MVP 10 triệu events chứng minh correctness,
không đủ chứng minh SLA full-scale.

**Ngày 7:** runbook, cost ledger, version publication audit, restore test;
review lại các tradeoff retention theo giờ và detector coverage. Rollout chỉ
qua khi toàn bộ gate có bằng chứng; nếu không, giữ canary tenant và sửa
bottleneck. Không cần dựng thêm vector DB, multi-region hay catalog migration
để chứng minh slice observability này.

## 7. Bằng chứng hiện có và nguồn

Lab hiện có chứng minh cơ chế local: NB3 MERGE/RESTORE, NB4 dedup/Gold, NB6
maintenance và NB8 pin version. Chưa triển khai hệ thống production trên sơ
đồ, retention worker, PII detector hay load test 1 tỷ request/ngày. Không nộp
PoC riêng vì đề cho phép architecture brief; acceptance tests ở trên là kế
hoạch kiểm chứng phần còn chưa được chứng minh.

- [S1 — Delta streaming, idempotent writes](https://docs.delta.io/delta-streaming/).
- [S2 — Delta utility, RESTORE và VACUUM](https://docs.delta.io/delta-utility/).
- [S3 — Delta optimizations, compaction và Z-order](https://docs.delta.io/optimizations-oss/).
- [S4 — Amazon S3 pricing, categories storage/request](https://aws.amazon.com/s3/pricing/).
- [S5 — Iceberg schema và partition evolution](https://iceberg.apache.org/docs/latest/evolution/).

Nguồn chính thức được đối chiếu ngày 05/10/2026. Mức giá trong phép tính
là giả định tách biệt với nội dung trang giá; các quyết định và capacity
estimate là đề xuất của bài, không phải cam kết của tài liệu nguồn.
