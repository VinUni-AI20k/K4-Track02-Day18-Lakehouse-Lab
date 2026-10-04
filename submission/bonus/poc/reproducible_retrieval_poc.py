# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # PoC (topic D) — Retrieval tái lập được qua nâng cấp embedding model
#
# **Cơ chế khó nhất của thiết kế:** một bản án trích dẫn kết quả retrieval tại release R1.
# Sau đó (1) embedding được tạo lại bằng model mới, (2) một văn bản bị rút khỏi kho,
# (3) maintenance expire các snapshot cũ. Năm năm sau vẫn phải chạy lại đúng top-k của R1.
#
# Cách làm: bảng Iceberg `chunk_embeddings` partition theo `model_version`. Mỗi release là một
# **tag** trên snapshot. Mỗi câu trả lời ghi `citation_log` (tag, snapshot, model, top-k).
# Chạy offline bằng stack của lab (pyiceberg + numpy); embedding là dữ liệu tổng hợp.
# "Model v2" ở đây là một phép xoay trực giao của không gian v1: thứ tự láng giềng được giữ nguyên,
# nên mọi sai lệch đo được đều do **trộn không gian vector**, không do chất lượng model.
#
# Chạy từ gốc repo sau `pip install -r requirements.txt`:
# `python submission/bonus/poc/reproducible_retrieval_poc.py` (catalog nằm ở `_lakehouse/iceberg/bonus_poc`).

# %%
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa

REPO = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "scripts" / "lakehouse.py").exists())
sys.path.insert(0, str(REPO / "scripts"))
import generate_ai_data as gen  # noqa: E402
from lakehouse import catalog, namespace, reset_catalog  # noqa: E402

CAT, DIM, N, K = "bonus_poc", 64, 3_000, 5
reset_catalog(CAT)
cat = catalog(CAT)
ns = namespace(cat, "legal")
rng = np.random.default_rng(7)
emb_v1, _ = gen.make_embeddings(rng, N, DIM, 8)              # "model v1"
rot, _ = np.linalg.qr(rng.normal(size=(DIM, DIM)))           # "model v2" = a different vector space
emb_v2 = emb_v1 @ rot
SCHEMA = pa.schema([pa.field("chunk_id", pa.int64(), nullable=False), pa.field("doc_id", pa.int64()),
                    pa.field("model_version", pa.string()), pa.field("emb", pa.list_(pa.float32()))])


def batch(emb: np.ndarray, mv: str) -> pa.Table:
    vecs = pa.FixedSizeListArray.from_arrays(pa.array(emb.astype("float32").ravel()), DIM)
    return pa.table({"chunk_id": np.arange(N), "doc_id": np.arange(N) // 10, "model_version": [mv] * N,
                     "emb": vecs.cast(pa.list_(pa.float32()))}, schema=SCHEMA)


def encode(qid: int, mv: str) -> np.ndarray:
    """Encoder đã lưu trữ (pin theo version): query = vector của chunk qid + nhiễu cố định."""
    base = emb_v1 if mv == "emb-v1" else emb_v2
    q = base[qid] + np.random.default_rng(qid).normal(scale=0.05, size=DIM) @ (np.eye(DIM) if mv == "emb-v1" else rot)
    return q / np.linalg.norm(q)


def search(tbl, snapshot_id: int, q: np.ndarray, mv: str) -> list[int]:
    """Exact cosine top-k trên đúng snapshot + model_version (đường replay, không dùng ANN)."""
    t = tbl.scan(snapshot_id=snapshot_id, row_filter=f"model_version == '{mv}'").to_arrow()
    if t.num_rows == 0:
        return []
    m = np.stack(t.column("emb").to_numpy(zero_copy_only=False))
    return t.column("chunk_id").to_numpy()[np.argsort(-(m @ q))[:K]].tolist()


# %% [markdown]
# ## 1. Release R1: model v1 → tag `rel-2026-10-v1`, ghi citation log cho 50 câu hỏi

# %%
tbl = cat.create_table(f"{ns}.chunk_embeddings", schema=SCHEMA)
with tbl.update_spec() as spec:
    spec.add_identity("model_version")
tbl = cat.load_table(f"{ns}.chunk_embeddings")
tbl.append(batch(emb_v1, "emb-v1"))
tbl = cat.load_table(f"{ns}.chunk_embeddings")
r1 = tbl.current_snapshot().snapshot_id
tbl.manage_snapshots().create_tag(r1, "rel-2026-10-v1").commit()

queries = rng.choice(N, size=50, replace=False).tolist()
citation_log = [{"qid": q, "tag": "rel-2026-10-v1", "snapshot_id": r1, "model": "emb-v1",
                 "topk": search(tbl, r1, encode(q, "emb-v1"), "emb-v1")} for q in queries]
print(f"R1 snapshot={r1}  rows={tbl.scan().to_arrow().num_rows:,}  citations logged={len(citation_log)}")
print("ví dụ:", citation_log[0])

# %% [markdown]
# ## 2. Nâng cấp model (v2), xóa v1 khỏi `main`, rút một văn bản, rồi expire snapshot cũ

# %%
WITHDRAWN = citation_log[0]["topk"][0] // 10                   # doc_id của chunk đứng đầu câu trích dẫn đầu tiên
cat.load_table(f"{ns}.chunk_embeddings").append(batch(emb_v2, "emb-v2"))
cat.load_table(f"{ns}.chunk_embeddings").delete(delete_filter="model_version == 'emb-v1'")
cat.load_table(f"{ns}.chunk_embeddings").delete(delete_filter=f"doc_id == {WITHDRAWN}")
tbl = cat.load_table(f"{ns}.chunk_embeddings")
head = tbl.current_snapshot().snapshot_id
untagged = [s.snapshot_id for s in tbl.snapshots() if s.snapshot_id not in (head, r1)]
tbl.maintenance.expire_snapshots().by_ids(untagged).commit()
try:
    cat.load_table(f"{ns}.chunk_embeddings").maintenance.expire_snapshots().by_id(r1).commit()
    tag_protected = False
except ValueError as e:
    tag_protected = True
    print("expire snapshot của tag bị chặn:", e)
tbl = cat.load_table(f"{ns}.chunk_embeddings")
print(f"snapshots còn lại: {len(tbl.snapshots())}  refs: {sorted(tbl.metadata.refs)}")

# %% [markdown]
# ## 3. Replay 50 câu trích dẫn từ tag R1 và so với `main` hiện tại

# %%
r1_now = tbl.metadata.refs["rel-2026-10-v1"].snapshot_id
replayed = sum(search(tbl, r1_now, encode(c["qid"], c["model"]), c["model"]) == c["topk"] for c in citation_log)
main_v1_rows = tbl.scan(row_filter="model_version == 'emb-v1'").to_arrow().num_rows
withdrawn_main = tbl.scan(row_filter=f"doc_id == {WITHDRAWN}").to_arrow().num_rows
withdrawn_r1 = tbl.scan(snapshot_id=r1_now, row_filter=f"doc_id == {WITHDRAWN}").to_arrow().num_rows
# Lỗi trộn không gian vector: dùng query encode bằng v1 để tìm trên embedding v2 của main
mixed = np.mean([len(set(search(tbl, head, encode(c["qid"], "emb-v1"), "emb-v2")) & set(c["topk"])) / K
                 for c in citation_log])
v2_ok = np.mean([len(set(search(tbl, head, encode(c["qid"], "emb-v2"), "emb-v2")) & set(c["topk"])) / K
                 for c in citation_log])
print(f"replay từ tag R1 khớp đúng top-{K}: {replayed}/{len(citation_log)}")
print(f"main: rows emb-v1 = {main_v1_rows}; doc {WITHDRAWN} rút khỏi main = {withdrawn_main} rows, tag R1 vẫn giữ {withdrawn_r1} rows")
print(f"overlap top-{K} khi query v1 trên index v2 (trộn không gian): {mixed:.2f}")
print(f"overlap top-{K} khi query v2 trên index v2 (đúng cặp model):  {v2_ok:.2f}")

# %%
checks = {
    "50/50 trích dẫn replay đúng từ tag": replayed == len(citation_log),
    "tag được bảo vệ khỏi expire": tag_protected and "rel-2026-10-v1" in tbl.metadata.refs,
    "main không còn emb-v1": main_v1_rows == 0,
    "văn bản rút khỏi main, tag còn giữ (legal hold)": withdrawn_main == 0 and withdrawn_r1 > 0,
    "trộn không gian vector làm hỏng retrieval": mixed < 0.2 < v2_ok,
}
for k_, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k_}")
assert all(checks.values())
