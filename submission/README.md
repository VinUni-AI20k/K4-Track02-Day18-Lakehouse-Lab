# Hồ sơ bài nộp K4-Track02-Day18

## Kết quả theo rubric

| NB | Bằng chứng chính | Kết quả trên máy này | Ảnh |
|---:|---|---|---|
| 1 | Delta log, enforcement, evolution | Commit JSON hiển thị; bad write bị chặn; tier được thêm | screenshots/nb01_delta_log.png |
| 2 | Small files, OPTIMIZE, Z-order | 200 → 55 file; speedup 12,7×; pruning 55× | screenshots/nb02_optimize.png |
| 3 | MERGE, time travel, RESTORE | 5 version; score âm sau restore = 0 | screenshots/nb03_history_restore.png |
| 4 | Bronze → Silver → Gold | 200.000 → 190.052 dòng; 8 ngày × 3 model | screenshots/nb04_gold.png |
| 5 | Iceberg catalog/evolution | pruning 10×; metadata:data ≈ 2,90:1; field ID 4→4; 2 spec đang có file | screenshots/nb05_iceberg.png |
| 6 | Maintenance | compaction 18×; skip 90%; VACUUM 16,1 MB; xóa 3 orphan + 17 manifest list; còn 3 snapshot; checkpoint hợp lệ | screenshots/nb06_maintenance.png |
| 7 | Blob/vector lifecycle | amplification 200×; int8 5,8×; recall 0,904; fidelity 1,0; stale hits 0→8→0 qua 8 CDF delete | screenshots/nb07_vectors.png |
| 8 | Agent provenance | 2 policy; replay v0=1.578 bước khi v1=1.978; 5→1 catalog read; input_required + task completed; loại 334 dòng; subject current=0/old=8 | screenshots/nb08_provenance.png |

## Cổng tái lập

- Smoke: 9/9 PASS.
- Pytest: 24/24 PASS.
- Headless notebooks: 8/8 PASS.
- Mỗi notebook có output thật, assertion và phần Nhận xét kết quả.

Thông tin môi trường nằm trong INFO.md; reflection và khai báo AI nằm trong
REFLECTION.md và AI_USAGE.md.

## Bonus — Topic A: LLM observability ở quy mô lớn

- [Architecture brief](bonus/ARCHITECTURE.md): thiết kế lakehouse cho 1 tỷ request/ngày và 5 TB raw/ngày, kèm quyết định kiến trúc, mô hình chi phí, failure modes và kế hoạch MVP 7 ngày.
