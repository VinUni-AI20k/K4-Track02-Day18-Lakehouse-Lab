# Screenshot checklist

Chụp trực tiếp từ các notebook đã thực thi trong `submission/notebooks/`:

- `nb01_delta_log.png`: action types/metadata/add trong commit JSON, lỗi `thirty → Int64`, schema có `tier`.
- `nb02_optimize.png`: 200 → 55 files, speedup và pruning ratio.
- `nb03_restore.png`: MERGE, history 5 version có RESTORE, `score < 0 = 0`.
- `nb04_gold.png`: Bronze/Silver counts và bảng Gold theo date/model.
- `nb05_iceberg.png`: pruning 10×, field ID 4 và spec IDs `[1, 2]`.
- `nb06_maintenance.png`: file reduction, skip rate, orphan sweep, snapshots và checkpoint.
- `nb07_vectors.png`: amplification, int8/recall/topic fidelity và lifecycle bug.
- `nb08_agents.png`: pinned replay, catalog read, confirmation/task và provenance partitions.

Không dùng số trong checklist thay cho output. Ảnh phải hiển thị output thật đang có trong notebook.
