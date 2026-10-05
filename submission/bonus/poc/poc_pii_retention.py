# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # Bonus PoC — PII never at rest + 7-day *physical* retention, Gold survives
#
# Spike for topic A (LLM observability). Two mechanisms are proven at 1/500 000 scale:
# 1. Prompts are tokenized (keyed HMAC) **before** the first write — no Parquet file holds raw PII.
# 2. Retention drops payloads older than 7 UTC days *physically* (delete → expire → orphan sweep)
#    while 5-minute Gold rollups for every day are kept.
#
# Stack = the lab's lightweight path: pyiceberg (SQLite catalog) + DuckDB. Offline. Fake data only.

# %%
import hmac, os, random, re, sys, datetime as dt
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "scripts" / "lakehouse.py").exists())
sys.path.insert(0, str(ROOT / "scripts"))
import duckdb, pyarrow as pa, pyarrow.parquet as pq
from pyiceberg.expressions import LessThan
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import DayTransform
from pyiceberg.types import IntegerType, NestedField, StringType, TimestamptzType
from lakehouse import catalog, du, human, namespace, reset_catalog

CAT = "bonus_poc"
reset_catalog(CAT); cat = catalog(CAT); ns = namespace(cat, "obs")
WAREHOUSE = ROOT / "_lakehouse" / "iceberg" / CAT / "warehouse"

# %% [markdown]
# ## 1. Tokenizer — runs inside the ingest job, before Bronze
# Deterministic HMAC: the same e-mail always maps to the same token, so incident review can still
# count "distinct users affected" without seeing PII. The key lives in KMS in production.

# %%
KEY = os.environ.get("PII_HMAC_KEY", "demo-key-not-a-secret").encode()
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+84|0)(?:[\s.-]?\d){9}")

def _tok(kind: str, value: str) -> str:
    return f"<{kind}:{hmac.new(KEY, value.encode(), 'sha256').hexdigest()[:12]}>"

def redact(text: str) -> str:
    text = EMAIL.sub(lambda m: _tok("EMAIL", m.group().lower()), text)
    return PHONE.sub(lambda m: _tok("PHONE", re.sub(r"\D", "", m.group())[-9:]), text)

CANARIES = ["canary.long@example.com", "0912 000 777"]   # injected every day; must never land on disk
print(redact(f"Mail {CANARIES[0]} or call {CANARIES[1]} about invoice 42"))

# %% [markdown]
# ## 2. Ingest 9 UTC days → payload (7-day TTL) and metrics tables, both `day(ts)`

# %%
random.seed(18)
DAYS, PER_DAY, TENANTS, MODELS = 9, 2_000, 50, ["haiku", "sonnet", "opus"]
START = dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc)
TEMPLATES = ["Summarise ticket {n} for {pii}", "Draft a reply to {pii} about order {n}",
             "Classify log line {n}", "Translate FAQ {n} to Vietnamese"]

def raw_batch(day: int) -> list[dict]:
    rows = []
    for i in range(PER_DAY):
        pii = CANARIES[i % 2] if i < 4 else random.choice([f"user{random.randint(1, 900)}@example.com",
                                                          f"09{random.randint(10**7, 10**8 - 1)}"])
        rows.append({"request_id": f"r{day:02d}-{i:05d}", "tenant_id": f"t{random.randint(1, TENANTS):03d}",
                     "model": random.choice(MODELS),
                     "ts": START + dt.timedelta(days=day, seconds=random.randint(0, 86_399)),
                     "prompt": random.choice(TEMPLATES).format(n=i, pii=pii),
                     "latency_ms": random.randint(200, 6_000), "tokens": random.randint(50, 4_000)})
    return rows

f = lambda i, n, t, req=False: NestedField(i, n, t, required=req)
PAYLOAD = Schema(f(1, "request_id", StringType(), True), f(2, "tenant_id", StringType()),
                 f(3, "ts", TimestamptzType(), True), f(4, "prompt_redacted", StringType()))
METRICS = Schema(f(1, "request_id", StringType(), True), f(2, "tenant_id", StringType()),
                 f(3, "ts", TimestamptzType(), True), f(4, "model", StringType()),
                 f(5, "latency_ms", IntegerType()), f(6, "tokens", IntegerType()))
by_day = PartitionSpec(PartitionField(source_id=3, field_id=1000, transform=DayTransform(), name="ts_day"))
payload = cat.create_table(f"{ns}.payload", schema=PAYLOAD, partition_spec=by_day)
metrics = cat.create_table(f"{ns}.metrics", schema=METRICS, partition_spec=by_day)

for d in range(DAYS):
    rows = sorted(raw_batch(d), key=lambda r: (r["tenant_id"], r["ts"]))     # cluster by tenant
    payload.append(pa.Table.from_pylist([{"request_id": r["request_id"], "tenant_id": r["tenant_id"],
        "ts": r["ts"], "prompt_redacted": redact(r["prompt"])} for r in rows], schema=PAYLOAD.as_arrow()))
    metrics.append(pa.Table.from_pylist([{k: r[k] for k in METRICS.as_arrow().names} for r in rows],
                                        schema=METRICS.as_arrow()))
print(f"payload rows={payload.scan().to_arrow().num_rows:,}  metrics rows={metrics.scan().to_arrow().num_rows:,}")

# %% [markdown]
# ## 3. Gold — 5-minute rollups per tenant × model, kept 1 year (here: all 9 days)

# %%
con = duckdb.connect(); con.sql("SET TimeZone = 'UTC'")   # NB4 lesson: day boundaries are UTC
con.register("m", metrics.scan().to_arrow())
gold = con.sql("""SELECT time_bucket(INTERVAL 5 MINUTE, ts) AS bucket, tenant_id, model, count(*) AS calls,
                  quantile_cont(latency_ms, 0.95) AS p95_ms, sum(tokens) AS tokens
                  FROM m GROUP BY ALL ORDER BY bucket""").arrow()
gold = gold.read_all() if hasattr(gold, "read_all") else gold
gold_tbl = cat.create_table(f"{ns}.gold_5min", schema=gold.schema); gold_tbl.append(gold)
print(f"gold rows={gold.num_rows:,}  days covered={len({b.date() for b in gold.column('bucket').to_pylist()})}")

# %% [markdown]
# ## 4. Verify mechanism 1: scan every decompressed Parquet value on disk for PII

# %%
def pii_hits(files) -> int:
    hits = 0
    for fp in files:
        for col in pq.read_table(fp).columns:
            if pa.types.is_string(col.type):
                for v in col.to_pylist():
                    hits += bool(v) and (any(c in v for c in CANARIES) or bool(EMAIL.search(v) or PHONE.search(v)))
    return hits

all_parquet = lambda: sorted(WAREHOUSE.rglob("*.parquet"))
control = ROOT / "_lakehouse" / "scratch" / "unredacted_control.parquet"; control.parent.mkdir(parents=True, exist_ok=True)
pq.write_table(pa.Table.from_pylist([{"prompt": r["prompt"]} for r in raw_batch(0)[:10]]), control)
print(f"negative control (unredacted file): {pii_hits([control])} hits  ← detector works")
print(f"lakehouse files scanned: {len(all_parquet())}  PII hits: {pii_hits(all_parquet())}")

# %% [markdown]
# ## 5. Verify mechanism 2: retention = delete → expire snapshots → orphan sweep
# "Today" is 2026-04-10 00:00 UTC; keep 7 days ⇒ cutoff 2026-04-03. Because the cutoff is a UTC
# midnight and files are partitioned by `day(ts)`, the delete drops whole files — nothing is rewritten.

# %%
CUTOFF = (START + dt.timedelta(days=DAYS - 7)).isoformat()
old_files = lambda: [fp for fp in all_parquet() if "ts_day=" in str(fp) and
                     min(pq.read_table(fp, columns=["ts"]).column("ts").to_pylist()).isoformat() < CUTOFF]
print(f"files holding payload/metrics older than {CUTOFF[:10]}: {len(old_files())}")
rewritten, before_delete = {}, payload.current_snapshot().snapshot_id
for t in (payload, metrics):
    t.delete(delete_filter=LessThan("ts", CUTOFF))
    s = t.current_snapshot().summary
    rewritten[t.name()[-1]] = int(s.get("added-data-files") or 0)
    print(f"{t.name()[-1]:8s} delete: removed files={s.get('deleted-data-files')}  rewritten files={rewritten[t.name()[-1]]}")
print(f"current payload rows: {payload.scan().to_arrow().num_rows:,}   "
      f"time travel to pre-delete snapshot: {payload.scan(snapshot_id=before_delete).to_arrow().num_rows:,} rows")
print(f"files still on disk with rows older than cutoff: {len(old_files())}  ← delete alone is not erasure")

for t in (payload, metrics):
    t = cat.load_table(t.name())
    old = [s.snapshot_id for s in t.snapshots() if s.snapshot_id != t.current_snapshot().snapshot_id]
    t.maintenance.expire_snapshots().by_ids(old).commit()
    t = cat.load_table(t.name())
    live = {Path(p).name for p in t.inspect.files().column("file_path").to_pylist()}
    live |= {Path(p).name for p in t.inspect.manifests().column("path").to_pylist()}
    live |= {Path(s.manifest_list).name for s in t.snapshots()}
    root = Path(t.location().replace("file://", ""))
    swept = [fp for fp in [*root.rglob("*.parquet"), *root.rglob("*.avro")] if fp.name not in live]
    print(f"{t.name()[-1]:8s} expired {len(old)} snapshots, swept {len(swept)} files ({human(sum(du(x) for x in swept))})")
    for fp in swept:
        fp.unlink()

# %% [markdown]
# ## 6. Acceptance checks

# %%
payload, metrics = cat.load_table(f"{ns}.payload"), cat.load_table(f"{ns}.metrics")
gold_days = {b.date() for b in cat.load_table(f"{ns}.gold_5min").scan().to_arrow().column("bucket").to_pylist()}
checks = {
    "0 PII values in any lakehouse Parquet file": pii_hits(all_parquet()) == 0,
    "negative control is detected": pii_hits([control]) > 0,
    "payload keeps exactly 7 UTC days": payload.scan().to_arrow().num_rows == 7 * PER_DAY,
    "0 physical files with rows older than cutoff": len(old_files()) == 0,
    "retention rewrote 0 data files (whole-file drop)": sum(rewritten.values()) == 0,
    "pre-delete snapshot no longer exists": before_delete not in {s.snapshot_id for s in payload.snapshots()},
    "Gold still covers all 9 days": len(gold_days) == DAYS,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values()), "PoC acceptance failed"
print("\nPoC complete.")
