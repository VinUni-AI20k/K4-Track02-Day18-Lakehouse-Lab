# INFO — K4-Track02-Day18 Lakehouse Lab

- Ho ten: Nguyen Minh Tuan
- MSSV: 2A202602850
- Ma bai: K4-Track02-Day18
- Repo: K4-Track02-Day18-NguyenMinhTuan-2A202602850-Lakehouse-Lab
- Duong chay: lightweight (deltalake + pyiceberg + DuckDB + Polars, offline sau khi cai deps)
- NB1–NB4: lightweight (khong dung Spark/Docker)
- Python: 3.11.9 (tags/v3.11.9, MSC v.1938 64 bit AMD64)
- OS: Windows-10-10.0.19045-SP0 (PowerShell, PYTHONUTF8=1)
- Lib: deltalake 1.6.6, pyiceberg 0.12.0, duckdb 1.5.6, polars 1.44.2
- Ngay chay: 2026-10-05, tat ca 8 notebook lightweight tren duong local `_lakehouse/`

## Kiem tra tong hop (Part C)

| Buoc | Lenh | Ket qua |
|---|---|---|
| Smoke | `scripts/verify_lite.py` | **9/9 PASS** |
| Pytest | `python -m pytest -q` | **24/24 PASS** |
| Runner | `scripts/run_all.py` | **8/8 PASS** (41.9s) |

```
PASS 01_delta_basics.py 0.8s      PASS 05_iceberg_catalog.py 2.1s
PASS 02_optimize_zorder.py 16.1s  PASS 06_maintenance.py 16.8s
PASS 03_time_travel.py 0.8s       PASS 07_vectors_multimodal.py 1.3s
PASS 04_medallion.py 1.6s         PASS 08_agents_provenance.py 2.2s
```

## So do chinh theo rubric (do tren may nay)

| NB | Tieu chi | So do | Nguong |
|---|---|---|---|
| NB1 | commit JSON / bad write / `tier` | 2 commit (v0 overwrite, v1 append) · Cast error Int64 · 2 nhom tier | — |
| NB2 | speedup hoac files-pruned | **7.7x** va **55.0x** (1/55 file chua user_id=4242); 200 -> 55 file | >=3x / >=10x |
| NB3 | history / MERGE / RESTORE | 5 version · MERGE 100K 0.16s (50K update + 50K insert) · RESTORE 0.04s, `score<0` = 0 | >=5 version |
| NB4 | Silver<Bronze / Gold | 200,000 -> 190,052 (-9,948) · Gold 24 rows = 8 ngay x 3 model | >=7 ngay x 3 model |
| NB5 | pruning / field_id / spec | **10x** · `latency_millis` giu `field_id=4` · spec `[1, 2]` · 5,500 rows doc duoc | >=5x / >=2 spec |
| NB6 | 5 job | compaction 200->11 (18x) · clustering skip 90% · vacuum 16.1 MB · Iceberg 20->3 snapshot · 3 orphan + 17 manifest list · checkpoint + `_last_checkpoint` | >=10x / >=50% |
| NB7 | amplification / int8 / recall / bug | **200x** · **5.8x** (83%) · recall@10 0.904 · fidelity 1.000 · bang 0 / index 8 hits · CDF 8 deletes | >=5x / >=3x / >=0.80 / >=0.95 |
| NB8 | pin / cache / confirm / buckets | pinned v0 1,578 buoc khoi bang len 1,978 · 5 turns -> 1 catalog read · `input_required` · 4 bucket + UNCLASSIFIED 334/2,000 loai | — |

## Ghi chu ve gioi han (README + CHECKPOINTS)

- NB6 chi dung `retention_hours=0` tren du lieu scratch cua lab; khong ap dung cho du lieu that.
- `VACUUM` cua `deltalake` (delta-rs 1.6.6) chi thu hoi file da bi **tombstone**; 3 orphan chua tung commit van lai. Spark VACUUM co buoc list directory — khong nen **gia dinh** engine cua minh lam duoc.
- `expire_snapshots` cua PyIceberg 0.12.0 chi giam metadata (20 -> 3 snapshot) va **khong** xoa file vat ly (avro 40 -> 40). Job 3 va Job 4 phai noi nhau.
- NB7: Delta protocol khong co kieu vector co dinh chieu; `fixed_size_list<float>[256]` doc len thanh `list<float>`, phai cast `emb::FLOAT[256]` khi query DuckDB.
- NB8 chi la **mo phong offline**: cache do o `list_tables` (khong phai `tools/list`), co `confirmed` do ben goi truyen (khong phai authorization boundary), replay chi so **so buoc** chua so noi dung, task handle/poll gia lap local. Mapping provenance chi minh hoa — gan CC-BY-4.0 vao `public_domain` khong chinh xac ve mat phep, va `user-owned` + consent khong chung minh da kiem tra opt-out khi scraping. Khong dung mapping nay de ket luan quyen su dung du lieu that.
