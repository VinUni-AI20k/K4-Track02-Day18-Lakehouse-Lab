# Hướng Dẫn & Danh Sách Ảnh Minh Chứng (Screenshots Guide)

Thư mục này chứa ảnh chụp minh chứng cho cả 8 notebook thực thi theo đúng tiêu chuẩn tại [RUBRIC.md](../../docs/RUBRIC.md) và [SUBMISSION.md](../../docs/SUBMISSION.md).

Mỗi ảnh tương ứng với một notebook, ghi lại số liệu đo lường thực tế, bảng tổng hợp và các assertion kiểm tra đã `PASS`.

---

## Danh Sách 8 Ảnh Minh Chứng

| Tên File Ảnh | Notebook Tương Ứng | Tiêu Chí Đo Lường Theo Rubric |
|---|---|---|
| [`nb01_delta_log.png`](nb01_delta_log.png) | `01_delta_basics` | Thấy rõ file JSON trong `_delta_log/`, lịch sử giao dịch commit, schema enforcement chặn ghi sai kiểu `age='thirty'`, và `tier` được thêm thành công khi dùng `schema_mode='merge'`. |
| [`nb02_optimize.png`](nb02_optimize.png) | `02_optimize_zorder` | Số file trước/sau (200 $\rightarrow$ 56 file), speedup $\ge 3\times$ hoặc pruning ratio $\ge 10\times$ (đo được $56\times$), và dải min/max stats của `user_id` gom cụm chính xác mục tiêu 4242. |
| [`nb03_time_travel.png`](nb03_time_travel.png) | `03_time_travel` | Lịch sử giao dịch $\ge 5$ versions bao gồm thao tác `RESTORE`, kết quả MERGE 100K dòng thành công, và số dòng lỗi `score < 0` sau restore về đúng bằng 0. |
| [`nb04_medallion.png`](nb04_medallion.png) | `04_medallion` | Ba tầng Bronze, Silver, Gold đều có trên ổ đĩa; Silver dedup giảm số dòng so với Bronze; bảng Gold phủ đủ $\ge 7$ ngày $\times$ 3 models với p50, p95, `cost_usd` dương và `error_rate` trong $[0, 1]$. |
| [`nb05_iceberg_catalog.png`](nb05_iceberg_catalog.png) | `05_iceberg_catalog` | Tỷ lệ loại trừ partition ẩn (hidden partition pruning) $\ge 5\times$ khi filter trên `ts`; trường `latency_millis` giữ nguyên `field_id=4` sau khi đổi tên; $\ge 2$ partition spec IDs cùng tồn tại và toàn bộ dữ liệu vẫn đọc được. |
| [`nb06_maintenance.png`](nb06_maintenance.png) | `06_maintenance` | Bảng tổng kết 5 jobs bảo trì: Compaction giảm $\ge 10\times$ file; Clustering bỏ qua $\ge 50\%$ file; Snapshot Expiry thu hồi dung lượng Delta và hạ Iceberg còn 3 snapshots; xóa sạch 3 Delta orphans và stranded Iceberg manifest lists; sinh checkpoint Parquet và pointer `_last_checkpoint`. |
| [`nb07_vectors_multimodal.png`](nb07_vectors_multimodal.png) | `07_vectors_multimodal` | Đo độ khuếch đại đọc ngẫu nhiên (amplification $\ge 5\times$); nén lượng tử hóa int8 nhỏ hơn $\ge 3\times$ với recall $\ge 0.80$ và topic fidelity $\ge 0.95$; truy vấn vector SQL trả về đúng lân cận cùng chủ đề; tái hiện lỗi vòng đời (0 hits trong lakehouse, $> 0$ hits trên external index cũ) và cơ chế khắc phục qua Change Data Feed (CDF). |
| [`nb08_agents_provenance.png`](nb08_agents_provenance.png) | `08_agents_provenance` | Silver phân vùng theo `agent_version`; Gold có cả 2 policy; training run pin version và replay khớp số bước; lớp MCP mô phỏng cache catalog (5 turns $\rightarrow$ 1 catalog read) và yêu cầu xác nhận `input_required` trước thao tác hủy; đủ 4 bucket provenance với `UNCLASSIFIED` bị loại khỏi tập huấn luyện; xóa dữ liệu chủ thể thành công. |

---

## Cách Tự Chụp Thêm Từ Trình Duyệt Jupyter Lab (Tùy Chọn)

Nếu bạn muốn mở trực tiếp giao diện Jupyter Lab trên trình duyệt để chụp thêm ảnh màn hình thực tế:
1. Chạy lệnh mở Jupyter Lab:
   ```powershell
   .\.venv\Scripts\python.exe -m jupyter lab --notebook-dir=submission/notebooks --no-browser
   ```
2. Mở trình duyệt truy cập đường dẫn xuất hiện trên terminal (ví dụ: `http://localhost:8888/lab`).
3. Mở từng notebook trong `submission/notebooks/`, cuộn đến các cell có kết quả đo lường và bảng `Deliverable checks`, dùng phím tắt `Win + Shift + S` để chụp vùng màn hình cần lưu.
