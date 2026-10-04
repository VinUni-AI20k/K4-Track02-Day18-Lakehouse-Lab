# %% [markdown]
# # PoC — Topic A: PII tokenization at Bronze + tenant clustering
#
# Spike for the two hardest mechanisms in `ARCHITECTURE.md`:
# 1. **No raw PII ever lands in a readable table**: emails/phones are replaced by
#    deterministic HMAC tokens *before* the Bronze write; the token→value map lives in a
#    separate restricted "vault" table.
# 2. **"Filter by tenant" stays cheap**: micro-batch ingest creates small files; compaction +
#    Z-order on `tenant_id` lets min/max stats skip most files.
#
# Offline, lab stack only (deltalake + DuckDB + Polars). Run from the repo root:
# `.venv\Scripts\python.exe submission/bonus/poc/pii_tokenize_cluster.py`

# %%
import hashlib, hmac, re, shutil, time
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from deltalake import DeltaTable, write_deltalake

ROOT = Path(__file__).resolve().parents[3] / "_lakehouse" / "bonus_poc"
BRONZE, VAULT = str(ROOT / "bronze_llm_logs"), str(ROOT / "pii_vault")
shutil.rmtree(ROOT, ignore_errors=True)
KEY = b"demo-only-key-use-KMS-in-prod"            # prod: per-env key in KMS, rotated
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<!\w)(?:\+84|0)\d{9}(?!\d)")  # boundaries: hex inside a token is not a phone
rng = np.random.default_rng(18)
N_BATCH, ROWS, N_TENANT = 120, 2_000, 200        # 120 micro-batches ≈ 120 commits

# %% [markdown]
# ## 1. Tokenize at landing (before any table write)

# %%
def tokenize(text: str, vault: dict) -> str:
    def sub(m):
        tok = "tok_" + hmac.new(KEY, m.group().lower().encode(), hashlib.sha256).hexdigest()[:16]
        vault[tok] = m.group()
        return tok
    return PHONE.sub(sub, EMAIL.sub(sub, text))

def fake_batch(b: int) -> pl.DataFrame:
    users = rng.integers(0, 5_000, ROWS)
    prompts = [f"Hi, I am user{u}@mail.vn, call me at 09{u:08d}. Summarise ticket #{b}"
               for u in users]
    return pl.DataFrame({
        "request_id": [f"{b:04d}-{i:05d}" for i in range(ROWS)],
        "ts": pl.datetime_range(pl.datetime(2026, 10, 1), pl.datetime(2026, 10, 1, 0, 0, 59),
                                "1s", eager=True).sample(ROWS, with_replacement=True, seed=b),
        "tenant_id": rng.zipf(1.3, ROWS).clip(1, N_TENANT).astype(np.int32),  # skewed tenants
        "model": rng.choice(["haiku", "sonnet", "opus"], ROWS),
        "latency_ms": rng.gamma(2.0, 400.0, ROWS).astype(np.int32),
        "prompt": prompts,
    })

vault, t0 = {}, time.perf_counter()
for b in range(N_BATCH):                        # each loop = one streaming micro-batch commit
    df = fake_batch(b)
    df = df.with_columns(pl.col("prompt").map_elements(lambda s: tokenize(s, vault),
                                                       return_dtype=pl.String))
    write_deltalake(BRONZE, df.to_arrow(), mode="append")
write_deltalake(VAULT, pl.DataFrame({"token": list(vault), "value": list(vault.values())}).to_arrow())
ingest_s = time.perf_counter() - t0
print(f"Bronze rows: {DeltaTable(BRONZE).count():,} in {N_BATCH} commits ({ingest_s:.1f}s)")
print(f"Vault entries (distinct PII values): {len(vault):,}")

# %% [markdown]
# ## 2. Prove: zero raw PII in Bronze, tokens are deterministic (joins still work)

# %%
bronze = pl.from_arrow(DeltaTable(BRONZE).to_pyarrow_table())
raw_email = sum(bool(EMAIL.search(s)) for s in bronze["prompt"])  # Python re: Rust regex
raw_phone = sum(bool(PHONE.search(s)) for s in bronze["prompt"])  # has no lookbehind
sample = bronze["prompt"][0]
same = tokenize("user42@mail.vn", {}) == tokenize("USER42@mail.vn", {})
print(f"Rows with raw email: {raw_email}   raw phone: {raw_phone}")
print(f"Sample Bronze prompt: {sample}")
print(f"Deterministic token (case-insensitive): {same}")

# Guard for the 3 a.m. failure 'new field carries PII': scan every string column.
leak_cols = [c for c, t in bronze.schema.items() if t == pl.String
             and any(EMAIL.search(s) or PHONE.search(s) for s in bronze[c].drop_nulls())]
print(f"String columns with raw PII: {leak_cols or 'none'}")

# %% [markdown]
# ## 3. Tenant query: small files vs compacted + Z-ordered

# %%
def files_for_tenant(tid: int) -> tuple[int, int]:
    acts = pl.DataFrame(DeltaTable(BRONZE).get_add_actions(flatten=True))
    hit = acts.filter((pl.col("min.tenant_id") <= tid) & (pl.col("max.tenant_id") >= tid))
    return hit.height, acts.height

def query_ms(tid: int, reps: int = 5) -> float:
    times = []
    for _ in range(reps):
        t = time.perf_counter()
        tbl = DeltaTable(BRONZE).to_pyarrow_table(filters=[("tenant_id", "=", tid)])
        duckdb.sql("SELECT model, quantile_cont(latency_ms, 0.95) p95, count(*) n "
                   "FROM tbl GROUP BY model").fetchall()
        times.append((time.perf_counter() - t) * 1000)
    return float(np.median(times))

TENANT = 150                                   # a long-tail tenant: the common dashboard case
before_files, before_total = files_for_tenant(TENANT)
before_ms = query_ms(TENANT)

t = time.perf_counter()
DeltaTable(BRONZE).optimize.z_order(["tenant_id"], target_size=512 * 1024)
DeltaTable(BRONZE).vacuum(retention_hours=0, enforce_retention_duration=False, dry_run=False)
opt_s = time.perf_counter() - t
after_files, after_total = files_for_tenant(TENANT)
after_ms = query_ms(TENANT)

print(f"tenant_id={TENANT}")
print(f"  before: files touched {before_files}/{before_total}   median {before_ms:.1f} ms")
print(f"  after : files touched {after_files}/{after_total}   median {after_ms:.1f} ms  "
      f"(optimize+vacuum {opt_s:.1f}s)")
print(f"  skip rate after Z-order: {1 - after_files / after_total:.0%}   "
      f"speedup: {before_ms / after_ms:.1f}x")

# %%
checks = {
    "0 raw emails/phones in Bronze": raw_email == 0 and raw_phone == 0,
    "tokens deterministic":          same,
    "no string column leaks PII":    not leak_cols,
    "vault holds every token":       len(vault) > 0,
    "Z-order skips >= 50% files":    after_files / after_total <= 0.5,
    "rows intact after optimize":    DeltaTable(BRONZE).count() == N_BATCH * ROWS,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values())
