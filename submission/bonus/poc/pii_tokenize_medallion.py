"""PoC: PII tokenization at Bronze landing + schema contract + "no PII anywhere on disk".

Bonus topic A (LLM observability). Proves the hardest mechanism of the design:
raw PII must never be readable, including in time-travel history.

Steps:
  1. Tokenize email/phone/user_id with deterministic HMAC before the write.
  2. Schema contract: a batch with a column outside the allowlist is rejected.
  3. Gold: 5-minute p50/p95/cost per tenant, computed on tokenized data.
  4. Failure drill F1: a buggy writer bypasses the contract and commits raw PII.
     Detect it → rollback → expire the bad snapshot → sweep unreferenced files
     → re-scan the bytes on disk and require 0 matches.

Run from the repo root:  .venv\\Scripts\\python.exe submission/bonus/poc/pii_tokenize_medallion.py
"""
from __future__ import annotations

import datetime as dtm
import hashlib
import hmac
import os
import random
import re
import sys
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lakehouse import catalog, namespace, reset_catalog  # noqa: E402

KEY = os.environ.get("PII_HMAC_KEY", "lab-only-key-use-KMS-in-prod").encode()
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Vietnamese mobile numbers. The boundaries matter: without them an all-digit
# HMAC token like <USER:010560272435> is a false positive (seen on first run).
PHONE = re.compile(r"(?<![\w:])(?:\+84|0)(?:3|5|7|8|9)\d{8}(?!\w)")

SCHEMA = pa.schema([
    pa.field("request_id", pa.string(), nullable=False),
    pa.field("ts", pa.timestamp("us"), nullable=False),
    pa.field("tenant_id", pa.string()),
    pa.field("user_token", pa.string()),
    pa.field("model", pa.string()),
    pa.field("prompt", pa.string()),
    pa.field("latency_ms", pa.int64()),
    pa.field("cost_usd", pa.float64()),
])
ALLOWED = set(SCHEMA.names)


def tok(value: str, kind: str) -> str:
    """Deterministic token: same input → same token, so GROUP BY/join still work."""
    return f"<{kind}:{hmac.new(KEY, value.encode(), hashlib.sha256).hexdigest()[:12]}>"


def redact(text: str) -> str:
    text = EMAIL.sub(lambda m: tok(m.group(), "EMAIL"), text)
    return PHONE.sub(lambda m: tok(m.group(), "PHONE"), text)


def raw_events(n: int, seed: int) -> list[dict]:
    """Synthetic gateway log: prompts contain emails and phone numbers."""
    rnd = random.Random(seed)
    base = dtm.datetime(2026, 10, 4, 3, 0)
    out = []
    for i in range(n):
        uid = f"user{rnd.randint(1, 500)}"
        out.append({
            "request_id": f"req-{seed}-{i}",
            "ts": base + dtm.timedelta(seconds=rnd.randint(0, 3599)),
            "tenant_id": rnd.choice(["acme", "globex", "initech"]),
            "user_email": f"{uid}@example.com",
            "model": rnd.choice(["haiku", "sonnet", "opus"]),
            "prompt": f"Call me at 09{rnd.randint(10**7, 10**8 - 1)} or mail {uid}@example.com about order {i}",
            "latency_ms": int(rnd.lognormvariate(6.5, 0.5)),
            "cost_usd": round(rnd.uniform(0.0001, 0.02), 6),
        })
    return out


def tokenizing_writer(events: list[dict]) -> pa.Table:
    """The ONLY sanctioned path into Bronze: tokenize, then enforce the contract."""
    rows = [{
        "request_id": e["request_id"], "ts": e["ts"], "tenant_id": e["tenant_id"],
        "user_token": tok(e["user_email"], "USER"), "model": e["model"],
        "prompt": redact(e["prompt"]), "latency_ms": e["latency_ms"], "cost_usd": e["cost_usd"],
    } for e in events]
    return enforce_contract(pa.Table.from_pylist(rows, schema=SCHEMA))


def enforce_contract(batch: pa.Table) -> pa.Table:
    extra = set(batch.column_names) - ALLOWED
    if extra:
        raise ValueError(f"schema contract violation, unknown columns {sorted(extra)} → DLQ")
    return batch


def pii_hits_on_disk(table) -> int:
    """Read every Parquet file under the table directory (bypassing the catalog,
    which only exposes the current snapshot) and count PII regex matches."""
    hits = 0
    root = Path(table.location().replace("file://", ""))
    for f in root.rglob("*.parquet"):
        t = pq.read_table(f)
        for name in t.column_names:
            if pa.types.is_string(t.schema.field(name).type):
                for v in t.column(name).to_pylist():
                    hits += bool(v and (EMAIL.search(v) or PHONE.search(v)))
    return hits


# ── 1. Tokenized ingest into Bronze ─────────────────────────────────────────
reset_catalog("poc_bonus")
cat = catalog("poc_bonus")
ns = namespace(cat, "obs")
bronze = cat.create_table(f"{ns}.llm_calls_bronze", schema=SCHEMA)
for seed in range(5):                       # 5 micro-batch commits
    batch = tokenizing_writer(raw_events(2_000, seed))
    bronze.append(batch.sort_by([("tenant_id", "ascending"), ("ts", "ascending")]))
bronze = cat.load_table(f"{ns}.llm_calls_bronze")
print(f"[1] Bronze rows={bronze.scan().to_arrow().num_rows:,}  snapshots={len(bronze.snapshots())}")
print(f"    sample prompt: {bronze.scan(limit=1).to_arrow().column('prompt')[0]}")
clean_hits = pii_hits_on_disk(bronze)
print(f"    PII regex hits in Parquet on disk: {clean_hits}")
assert clean_hits == 0

# ── 2. Schema contract rejects an unknown column ────────────────────────────
snaps_before = len(cat.load_table(f"{ns}.llm_calls_bronze").snapshots())
bad = pa.Table.from_pylist([{**raw_events(1, 99)[0]}])   # still has raw user_email
try:
    bronze.append(enforce_contract(bad))
    raise AssertionError("contract should have rejected the batch")
except ValueError as e:
    print(f"[2] REJECTED: {e}")
assert len(cat.load_table(f"{ns}.llm_calls_bronze").snapshots()) == snaps_before

# ── 3. Gold: 5-minute metrics per tenant ────────────────────────────────────
con = duckdb.connect()
con.register("bronze", bronze.scan().to_arrow())
gold = con.sql("""
    SELECT time_bucket(INTERVAL 5 MINUTE, ts) AS bucket_5m, tenant_id,
           count(*) AS calls,
           quantile_cont(latency_ms, 0.5)  AS p50_ms,
           quantile_cont(latency_ms, 0.95) AS p95_ms,
           round(sum(cost_usd), 4)         AS cost_usd,
           count(DISTINCT user_token)      AS users
    FROM bronze GROUP BY 1, 2 ORDER BY 1, 2
""").fetchall()
print(f"[3] Gold rows={len(gold)}  (12 buckets × 3 tenants expected)")
for r in gold[:3]:
    print(f"    {r}")
assert len(gold) == 36 and all(r[3] <= r[4] for r in gold)

# ── 4. Failure drill F1: a buggy writer commits raw PII ─────────────────────
bronze = cat.load_table(f"{ns}.llm_calls_bronze")
last_clean = bronze.current_snapshot().snapshot_id
leak = pa.Table.from_pylist([{
    "request_id": e["request_id"], "ts": e["ts"], "tenant_id": e["tenant_id"],
    "user_token": e["user_email"],                      # BUG: raw email, not a token
    "model": e["model"], "prompt": e["prompt"],          # BUG: not redacted
    "latency_ms": e["latency_ms"], "cost_usd": e["cost_usd"],
} for e in raw_events(500, 7)], schema=SCHEMA)
bronze.append(leak)
bronze = cat.load_table(f"{ns}.llm_calls_bronze")
bad_snap = bronze.current_snapshot().snapshot_id
detected = pii_hits_on_disk(bronze)
print(f"[4] leak committed (snapshot {bad_snap}); detector finds {detected} PII hits")
assert detected > 0

# 4a. rollback: current state goes back to the last clean snapshot
bronze.manage_snapshots().rollback_to_snapshot(last_clean).commit()
bronze = cat.load_table(f"{ns}.llm_calls_bronze")
print(f"    after rollback: current={bronze.current_snapshot().snapshot_id} rows={bronze.scan().to_arrow().num_rows:,}")
print(f"    but on disk (time-travel history) still: {pii_hits_on_disk(bronze)} hits  ← rollback alone is NOT enough")

# 4b. expire the bad snapshot, then sweep files no live snapshot references
bronze.maintenance.expire_snapshots().by_id(bad_snap).commit()
bronze = cat.load_table(f"{ns}.llm_calls_bronze")
live_data, live_meta = set(), set()
for s in bronze.snapshots():
    live_meta.add(Path(s.manifest_list).name)
    for m in s.manifests(bronze.io):
        live_meta.add(Path(m.manifest_path).name)
        for entry in m.fetch_manifest_entry(bronze.io):
            live_data.add(Path(entry.data_file.file_path).name)
root = Path(bronze.location().replace("file://", ""))
swept = [f for f in root.rglob("*.parquet") if f.name not in live_data]
swept += [f for f in root.rglob("*.avro") if f.name not in live_meta]
for f in swept:
    f.unlink()
final_hits = pii_hits_on_disk(bronze)
print(f"    expired snapshot {bad_snap}; swept {len(swept)} unreferenced files")
print(f"    PII regex hits on disk after sweep: {final_hits}")
assert final_hits == 0
assert bronze.scan().to_arrow().num_rows == 10_000
print("\nPoC PASS: tokenized ingest, contract rejection, Gold 5m, leak → rollback → expire → sweep → 0 PII on disk.")
