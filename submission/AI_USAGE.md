# AI_USAGE — K4-Track02-Day18

## Cong cu

- OpenCode (Muse Spark 1.3), chay trong moi truong lab offline.

## Pham vi ho tro

- Giai thich khai niem: transaction log, enforcement vs evolution, Z-order va file
  pruning, hidden partitioning va field ID, maintenance job, vector lifecycle,
  version pin va provenance.
- Ho tro doc code notebook (`notebooks/*.py`).
- Giu loi moi truong Windows: tao `.venv`, cai `requirements.txt`, `jupytext` +
  `jupyter nbconvert --execute` de luu output vao `.ipynb`.
- Tao khung `submission/`, render PNG cho `screenshots/`, va soan thao van ban
  (`REFLECTION.md`, `AI_USAGE.md`).

Khong viet lai logic trong bat ky notebook nao: ma nguon goc khong doi dong nao
(`git diff` tren file nguon = rong), chi co `submission/` la file moi.

## Tu chay va tu kiem chung

| Buoc | Lenh | Ket qua |
|---|---|---|
| Smoke | `scripts/verify_lite.py` | 9/9 PASS |
| Pytest | `python -m pytest -q` | 24/24 PASS |
| Runner | `scripts/run_all.py` | 8/8 PASS (41.9s) |
| Tung notebook | `jupyter nbconvert --execute` x8 | output luu trong `submission/notebooks/` |

Kiem tra them truc tiep tren dia: doc `_lakehouse/scratch/users_delta/_delta_log/*.json`,
dem lai Gold/Silver tren bang Delta, doi chieu nhung gi da in trong notebook.
NB2, NB6, NB7 chay lai nhieu lan de kiem tra so do on dinh (chi khac o wall-clock).

## Bao cao

- Anh trong `screenshots/` la **PNG render tu output that cua lan chay** (van ban,
  bang bang, so lieu), khong phai anh chup man hinh Jupyter. Noi dung lay truc tiep
  tu bang Delta/Iceberg va tu stdout cua notebook, khong sua so lieu.

## Khong lam

- Khong tao so lieu gia, khong ha nguong, khong bo assertion, khong viet ket luan cho
  lan chay chua thuc hien.
- Khong gui secret hay du lieu rieng tu vao prompt.
