# Kết quả thực thi

Thực thi: 2026-10-05T11:41:03.976718+07:00

| Notebook | Số đo thực tế | Ảnh |
|---|---|---|
| [01_delta_basics](notebooks/01_delta_basics.ipynb) | 2 commits; schema rejected; tier added; 2 groups | [PNG](screenshots/nb01_delta_basics.png) |
| [02_optimize_zorder](notebooks/02_optimize_zorder.ipynb) | 200 → 55 files; speedup 9.58×; pruning 55.0× | [PNG](screenshots/nb02_optimize_zorder.png) |
| [03_time_travel](notebooks/03_time_travel.ipynb) | MERGE 100K; 5 versions incl. RESTORE; negative scores = 0 | [PNG](screenshots/nb03_time_travel.png) |
| [04_medallion](notebooks/04_medallion.ipynb) | 200,000 → 190,052 rows; Gold 7×3 = 21 groups | [PNG](screenshots/nb04_medallion.png) |
| [05_iceberg_catalog](notebooks/05_iceberg_catalog.ipynb) | pruning 10×; field ID 4; specs [1, 2]; 5,500 rows | [PNG](screenshots/nb05_iceberg_catalog.png) |
| [06_maintenance](notebooks/06_maintenance.ipynb) | compaction 18.2×; skip 90.0%; 3 orphans removed; 20→3 snapshots; checkpoint | [PNG](screenshots/nb06_maintenance.png) |
| [07_vectors_multimodal](notebooks/07_vectors_multimodal.ipynb) | amplification 200.0×; int8 5.80×; recall 0.904; fidelity 1.000; stale hits 8 | [PNG](screenshots/nb07_vectors_multimodal.png) |
| [08_agents_provenance](notebooks/08_agents_provenance.ipynb) | replay 1,578/1,578 steps; 5 turns→1 read; 4 buckets; excluded 334 | [PNG](screenshots/nb08_agents_provenance.png) |

8/8 notebook hoàn tất mọi assertion. Metric chi tiết: [execution.json](evidence/execution.json).
Giải thích và giới hạn: [RESULTS.md](RESULTS.md). Timing có thể đổi giữa các lần chạy.
Thông tin, cách tái lập và trạng thái gửi bài: [INFO.md](INFO.md).
