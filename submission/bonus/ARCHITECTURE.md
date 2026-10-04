# Kiến trúc Lakehouse cho LLM Observability @ 1B request/ngày

> **Bài nộp bonus cá nhân** — K4-Track02-Day18. Topic A (LLM observability).
> Người làm: Dương Hà Đức Anh · MSSV 2A202602977.
> Số liệu trong đề là **đầu vào giả định** của bài toán, không phải thống kê đã kiểm chứng.

---

## 1. Problem statement (≤ 200 từ)

`FleetAPI` là API foundation-model phục vụ **1B request/ngày**; mỗi request/response
trung bình **5 KB**, tổng **~5 TB/ngày raw**. Bốn ràng buộc cứng định hình thiết kế:
(1) dashboard **cost & latency theo tenant** refresh **mỗi 5 phút**; (2) prompt/response
đầy đủ giữ **7 ngày** cho incident review, sau đó chỉ giữ **aggregates 1 năm**;
(3) **PII phải redact trước khi bất kỳ ai đọc**; (4) tổng chi phí storage **≤ \$5.000/tháng**.

Cái khó nằm ở chỗ các ràng buộc kéo ngược nhau. Truy vấn theo tenant cần dữ liệu gần
như tức thời (hot), nhưng ghi liên tục 5 TB/ngày lại sinh **hàng nghìn file nhỏ mỗi giờ** —
phá hỏng đúng cái truy vấn nhanh mà dashboard cần. PII-redact tại ingest mâu thuẫn với
incident review cần nội dung gốc. Giữ 7 ngày full-text (~35 TB steady-state) trong ngân
sách \$5K buộc phải **phân tầng storage** và coi compaction là **SLO**, không phải việc
dọn dẹp tùy hứng.

---

## 2. Architecture diagram

Một diagram, thể hiện **7 concept Day 18** được áp dụng (đánh dấu `[D18-n]`):

```
                    ┌────────────────────────────────────────────────────────────┐
  1B req/day ──────▶ │  INGEST  (streaming micro-batch, ~5s)                      │
  ~5 TB/day         │   • tokenize PII tại landing            [D18-3 governance] │
                    │   • write Delta append-only             [D18-1 ACID/log]   │
                    └───────────────┬────────────────────────────────────────────┘
                                    │  CDF enabled                 [D18-5 CDF]
              ┌─────────────────────┼──────────────────────────────────────┐
              ▼                     ▼                                      ▼
   ┌──────────────────┐   ┌──────────────────┐                ┌───────────────────┐
   │ BRONZE (raw)     │   │ SILVER (norm)    │                │  GOLD (aggregates)│
   │ tenant,ts,payload│   │ parsed fields,   │                │  tenant×model×hour│
   │ tokenized text   │──▶│ latency,cost,    │───────────────▶│  p50/p95 latency  │
   │ partition        │   │ tokens, PII-safe │                │  cost_usd, err_%  │
   │  day(ts)         │   │ partition day(ts)│                │  partition day(ts)│
   │ retention 7d     │   │ Z-ORDER tenant   │                │  retention 365d   │
   │ [D18-2 hidden pt]│   │ [D18-2 z-order]  │                │  [D18-4 medallion]│
   └────────┬─────────┘   └────────┬─────────┘                └─────────┬─────────┘
            │  OPTIMIZE + checkpoint nightly   [D18-6 maintenance]        │
            ▼                      ▼                                      ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │  CATALOG (REST) — control plane: schemas, snapshots, hidden specs [D18-7]  │
   └───────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │  query path
                    ┌───────────────┴────────────────┐
                    │  Trino / DuckDB (dashboard 5') │
                    │  prune by day(ts) → tenant      │
                    └────────────────────────────────┘
```

**Concept Day 18 áp dụng vào lựa chọn cụ thể (không chỉ name-drop):**

| # | Concept | Áp dụng ở đâu, cụ thể |
|---|---|---|
| D18-1 | Delta transaction log / ACID | Bronze append-only; mọi ghi là một commit JSON trong `_delta_log/`, cho phép time travel & RESTORE khi sự cố. |
| D18-2 | Hidden partitioning + Z-ORDER | `day(ts)` là partition ẩn (engine tự suy từ filter `ts`), `Z-ORDER tenant` để prune theo tenant — trực tiếp giảm bytes scan của dashboard. |
| D18-3 | Governance / PII tại Bronze | Token hóa **tại landing**, trước mọi reader; không phụ thuộc quy ước "đọc thì nhớ redact". |
| D18-4 | Medallion Bronze→Silver→Gold | Ba tầng với retention khác nhau; Gold 365 ngày, Bronze/Silver 7 ngày. |
| D18-5 | Change Data Feed (CDF) | Silver→Gold incremental: Gold chỉ đọc thay đổi thay vì full rescan mỗi 5 phút. |
| D18-6 | Maintenance (OPTIMIZE/checkpoint/vacuum) | Job nightly nén file nhỏ + ghi checkpoint để `_delta_log` không phình; vacuum theo retention. |
| D18-7 | Catalog là control plane | REST catalog tách metadata khỏi data; schema/snapshot/partition spec là object được version hóa. |

---

## 3. Quyết định kiến trúc & alternatives đã loại

### 3.1 Table format — **Delta Lake** ✅
- Loại **Iceberg**: hidden partitioning và REST catalog rất tốt, nhưng hệ này ghi
  streaming tần suất cao + cần CDF cho incremental Gold; Delta CDF (`_change_type`
  insert/update/delete) và `RESTORE` đã kiểm chứng trong lab (NB7/NB3). Iceberg đổi lại
  lợi thế multi-engine — nhưng ở đây query engine chính là một (Trino/DuckDB).
- Loại **Hudi**: mạnh về upsert streaming, nhưng hệ sinh thái Python/`deltalake` và
  chi phí vận hành compaction table-service phức tạp hơn so với nhu cầu append-heavy này.

### 3.2 Layout — **hidden `day(ts)` + Z-ORDER `tenant`** ✅
- Loại **Hive-style partition theo `tenant`**: cardinality tenant cao (giả định 10K) →
  hàng chục nghìn partition nhỏ/ngày, mỗi partition vài chục MB → chính là small-file
  problem của NB2, và partition explosion làm metadata phình.
- Loại **không partition**: dashboard 5 phút phải scan toàn bộ 5 TB/ngày — không thể đạt
  p95 mục tiêu. `day(ts)` cho prune theo thời gian; Z-ORDER tenant cho prune theo tenant
  mà **không** tăng số partition.

### 3.3 PII — **token hóa tại Bronze landing** ✅
- Loại **redact ở Silver**: dữ liệu gốc tồn tại nguyên văn ở Bronze, bất kỳ ai có quyền
  đọc Bronze (hoặc khôi phục backup) đều thấy PII → vi phạm yêu cầu (3).
- Loại **mã hóa cột bằng KMS, giữ ciphertext**: an toàn at-rest nhưng mọi aggregation vẫn
  phải giải mã để tính (ví dụ đếm tenant) → đẩy PII vào đường truy vấn; token hóa một chiều
  (HMAC) giữ tính joinable mà không lộ giá trị.

### 3.4 Retention — **Bronze/Silver 7 ngày + Gold 365 ngày** ✅
- Loại **giữ full 30 ngày**: 30 × 5 TB = 150 TB, vượt ngân sách dù ở IA (\$0,0125/GB-mo →
  ~\$1.875/mo chỉ riêng raw, chưa tính Silver).
- Loại **Glacier hóa raw sau 7 ngày**: yêu cầu chỉ giữ *aggregates* sau 7 ngày, không phải
  raw; Glacier retrieval (giờ–phút) vô nghĩa cho incident review vốn cần trong ngày.

### 3.5 Ingestion — **streaming micro-batch + Delta, CDF bật** ✅
- Loại **Kafka + batch hourly**: latency 1 giờ phá ràng buộc dashboard 5 phút.
- Loại **một writer mỗi request (Lambda/request)**: 1B commit/ngày vào `_delta_log` → commit
  log bùng nổ, xung đột optimistic-concurrency, không thể OPTIMIZE kịp.

### 3.6 Query engine — **Trino (ad-hoc) + DuckDB (nhúng cho panel nóng)** ✅
- Loại **Databricks SQL**: nhanh nhưng khóa vendor và đơn giá compute cao; ngân sách \$5K
  mong manh.
- Loại **PostgreSQL**: không scale scan 5 TB/ngày, và mất prune theo partition/Z-order của
  định dạng bảng mở.

### 3.7 Catalog — **REST catalog** ✅
- Loại **Hive Metastore**: gắn chặt Hive/Thrift, không phải chuẩn mở, khó multi-engine.
- Loại **catalog nằm trong tên thư mục (path-based)**: mất control plane để version hóa
  schema/spec, không có điểm chốt cho governance.

---

## 4. Failure modes (3 giờ sáng) — detection & rollback

| # | Sự cố | Detection | Rollback |
|---|---|---|---|
| **F1** | **Small-file explosion** — micro-batch 5s sinh hàng nghìn file/partition; dashboard p95 vọt từ 1,8s lên 12s. *(Day18: compaction)* | Alert trên **số file/partition** và `numFiles` từ `get_add_actions()`; p95 dashboard. | Chạy `OPTIMIZE` khẩn trên partition nóng; tạm tăng batch 5s→60s để giảm tốc độ sinh file; giữ SLO file/partition. |
| **F2** | **Breaking schema write** — deploy nhầm đổi kiểu `cost_usd` float→string, job Silver fail, Gold cũ trộn kiểu. *(Day18: schema evolution + time travel)* | Schema enforcement **chặn** ghi sai → job fail to; hoặc phát hiện qua schema diff trong catalog. | `RESTORE` bảng về version commit tốt cuối cùng (NB3); sửa writer rồi replay từ Bronze bằng CDF. |
| **F3** | **PII leak** — bug token hóa bỏ sót một field (ví dụ email trong `metadata.extra`). *(Day18: governance)* | Scan định kỳ: regex PII trên mẫu Silver/Bronze; audit log mọi lần đọc PII; alert khi hit > 0. | `RESTORE` về version trước khi leak; chạy lại pipeline token hóa trên cửa sổ bị ảnh hưởng; xoay khóa HMAC; mở incident review. |
| **F4** | **Deletion request bị "sống lại"** — xóa theo yêu cầu GDPR, nhưng time travel/deletion vectors vẫn phục hồi được dữ liệu đã xóa. *(Day18: deletion vectors / vacuum)* | Kiểm tra `VACUUM ... dry_run` sau khi xóa; test "đọc lại version cũ có thấy bản ghi không". | `VACUUM` với retention phù hợp để dọn tombstone, hết hạn snapshot cũ; xác nhận không còn version nào truy hồi được bản ghi. |

---

## 5. Ước lượng chi phí (back-of-envelope)

**Giả định đơn giá** (S3 us-east-1, công khai): Standard \$0,023/GB-tháng; Standard-IA
\$0,0125/GB-tháng. Compression Parquet+zstd trên text JSON ≈ **3,3×** → Silver ≈ 1,5 KB/req.

**Storage (steady-state, 30 ngày):**

| Tầng | Dung lượng | Đơn giá | \$/tháng |
|---|---|---|---:|
| Bronze raw (7 ngày) trên **Standard-IA** | 5 TB/ngày × 7 = **35 TB** = 35.840 GB | \$0,0125 | **\$448** |
| Silver parsed+tokenized (7 ngày) trên **Standard** | 1,5 TB/ngày × 7 = **10,5 TB** = 10.752 GB | \$0,023 | **\$247** |
| Gold aggregates (365 ngày) | 10K tenant × 24 h × 365 ≈ 87,6M row × ~250 B ≈ **22 GB** | \$0,023 | **\$0,5** |
| `_delta_log` + checkpoint | ~**0,3 TB** | \$0,023 | **\$7** |
| | | **Storage subtotal** | **≈ \$703** |

**Compute:**

| Hạng mục | Tính toán | \$/tháng |
|---|---|---:|
| Ingestion streaming (token hóa + write), 4 vCPU spot 24/7 | 4 × \$0,03/h × 720 h | \$86 |
| OPTIMIZE + checkpoint nightly | ~1,5 TB/ngày rewrite, serverless ~\$0,20/TB-rewrite | \$9 |
| Dashboard refresh (incremental qua CDF, ~5 GB/lần × 288 lần/ngày) | 1,44 TB/ngày × 30 × \$5/TB scan | \$216 |
| Ad-hoc Trino (analyst) | ~8 TB/tháng scan × \$5/TB | \$40 |
| | **Compute subtotal** | **≈ \$351** |

**Tổng ≈ \$1.054/tháng**, thấp hơn trần **\$5.000** ~4,7× → phần dư dành cho đỉnh traffic,
backfill và chi phí egress/request. *Ghi chú:* nếu bỏ incremental Gold mà full-rescan mỗi
5 phút (5 TB × 288/ngày = 1,44 PB/tháng × \$5/TB ≈ **\$7.200/mo**), **một mình nó đã vượt
ngân sách** — đây là lý do CDF (D18-5) là quyết định tài chính, không chỉ kỹ thuật.

---

## 6. MVP một tuần — slice nhỏ nhất chứng minh kiến trúc

**Mục tiêu:** một đường ống chạy được từ request giả lập → dashboard panel, chứng minh
**hai** mechanism khó nhất: (a) token hóa PII không thể đảo ngược, và (b) prune theo
`day(ts)`+tenant thực sự giảm bytes đọc.

| Ngày | Việc | Tiêu chí nghiệm thu |
|---|---|---|
| 1 | Bronze: sinh 10M request giả (giống `generate_ai_data.py`), ghi Delta append-only, bật CDF. | `_delta_log/` có ≥ 2 commit; `load_cdf()` trả insert events. |
| 2 | Token hóa PII tại ingest (HMAC-SHA256, salt từ secret manager). | Không tìm thấy email/SĐT thô bằng regex trên Bronze; join theo token vẫn đúng. |
| 3 | Silver: parse field, tính `latency_ms`, `cost_usd`, `error`; ghi partition `day(ts)`, Z-ORDER tenant. | Silver < Bronze (dedup); `get_add_actions()` có min/max để skip. |
| 4 | Gold: rollup tenant×model×hour qua CDF incremental. | Gold có p50/p95/cost/error cho ≥ 7 ngày × 3 model. |
| 5 | Query path: Trino/DuckDB đọc Gold, đo bytes-pruned khi filter `ts`+tenant. | Prune ≥ 5× trên `plan_files()`/scan stats; p95 panel < 2 s. |
| 6 | Maintenance + failure drill: OPTIMIZE, checkpoint; diễn tập F2 (ghi sai schema → RESTORE). | Files giảm ≥ 10×; RESTORE đưa bảng về đúng version. |
| 7 | Đóng gói: script tái lập + 1 ảnh dashboard; viết README acceptance. | Chạy lại từ clean checkout ra cùng số liệu. |

**Cách kiểm tra mechanism khó nhất (PII):** unit test khẳng định (i) regex PII = 0 hit trên
Bronze, (ii) hai giá trị email khác nhau → hai token khác nhau, (iii) cùng email → cùng
token (joinable), (iv) không tồn tại API giải mã token trong codebase. Nếu test này xanh,
phần rủi ro nhất của thiết kế coi như feasible; các phần còn lại là kỹ thuật đã biết.

---

## 7. Nguồn & phạm vi giả định

- Số liệu scale/latency/budget: **đầu vào của đề bài** (BONUS-CHALLENGE.md, Topic A).
- Đơn giá S3: mức công khai us-east-1 (Standard \$0,023/GB-mo, Standard-IA \$0,0125/GB-mo);
  đơn giá compute scan \$5/TB là giả định mô hình, cần đối chiếu hóa đơn thật.
- Hành vi kỹ thuật (CDF, time travel, hidden partitioning, `plan_files`, checkpoint,
  vacuum-misses-orphans) được **kiểm chứng trong chính lab này** (NB2–NB7 và `tests/test_lab18.py`).
- Đây là *architecture brief*, không phải cam kết tuân thủ pháp lý; với PII, văn bản áp dụng
  cần được luật sư xác nhận tại thời điểm triển khai.

## Phụ lục — PoC (optional)

`submission/bonus/poc/poc_tokenize_pin.py` — spike ~90 dòng chứng minh mechanism khó nhất:
token hóa PII một chiều + ghim version Delta + prune theo thời gian, chạy offline từ clean
checkout bằng `.venv`.
