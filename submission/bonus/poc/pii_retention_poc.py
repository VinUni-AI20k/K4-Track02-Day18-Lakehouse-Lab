"""Bonus PoC — PII tokenization at Bronze + physical retention on Iceberg.

Proves the two hardest mechanisms of ARCHITECTURE.md (topic A):
  1. No raw PII ever lands in a Bronze file (tokenized before the first write),
     with per-tenant HMAC tokens so incident review can still correlate.
  2. "Delete prompts after 7 days" really removes bytes: partition delete →
     snapshot expiry → orphan sweep, while 1-year Gold aggregates survive.

Run from the repo root:  .venv\\Scripts\\python.exe submission/bonus/poc/pii_retention_poc.py
"""
import hashlib, hmac, random, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pyiceberg.expressions import LessThan
from pyiceberg.transforms import DayTransform

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lakehouse import catalog, namespace, reset_catalog  # noqa: E402

# ── 1. Redactor: runs in the stream, before the first durable write ─────────
REDACTOR_VERSION = "v1"
MASTER_KEY = b"poc-only-master-key"          # production: KMS, one data key per tenant
PATTERNS = {                                   # order matters: longest/most specific first
    "APIKEY": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "EMAIL":  re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "CCCD":   re.compile(r"\b\d{12}\b"),                       # VN citizen ID
    "PHONE":  re.compile(r"(?<!\d)(?:\+84|0)(?:3|5|7|8|9)\d{8}(?!\d)"),
}


def tenant_key(tenant: str) -> bytes:
    return hmac.new(MASTER_KEY, tenant.encode(), hashlib.sha256).digest()


def token(key: bytes, value: str) -> str:
    # Letters only: a hex token like "175507201981" is itself a valid CCCD/phone
    # shape, which made the first version of this PoC fail its own leak scan.
    digest = hmac.new(key, value.encode(), hashlib.sha256).digest()
    return "".join(chr(97 + b % 26) for b in digest[:12])


def redact(text: str, tenant: str) -> str:
    k = tenant_key(tenant)
    for kind, rx in PATTERNS.items():
        text = rx.sub(lambda m: f"<{kind}:{token(k, m.group())}>", text)
    return text


# ── 2. Synthetic traffic: 3 days, PII-laden prompts, injected canaries ──────
CANARIES = ["canary.pii@example.com", "0912345678", "079203001234", "sk-CANARYcanaryCANARY1234"]
random.seed(18)
T0 = datetime(2026, 4, 1, tzinfo=timezone.utc)
rows = []
for i in range(30_000):
    tenant = f"t{random.randrange(50):03d}"
    pii = random.choice([f"user{i}@mail.vn", f"09{random.randrange(10**8):08d}",
                         f"{random.randrange(10**12):012d}", "no pii here"])
    if i % 1000 == 0:
        pii = CANARIES[(i // 1000) % 4]
    rows.append({
        "request_id": f"r{i:07d}", "tenant_id": tenant,
        "model": random.choice(["haiku", "sonnet", "opus"]),
        "ts": T0 + timedelta(seconds=i * 8.64),           # 30K rows spread over 3 days
        "latency_ms": random.randint(200, 6000), "cost_usd": round(random.random() / 100, 6),
        "prompt": f"Please summarize the ticket from {pii} about billing.",
    })

redacted = [{**r, "prompt": redact(r["prompt"], r["tenant_id"]), "redactor_version": REDACTOR_VERSION}
            for r in rows]
bronze_arrow = pa.Table.from_pylist(redacted)

# ── 3. Bronze on Iceberg, hidden partition day(ts) ──────────────────────────
reset_catalog("bonus_poc")
cat = catalog("bonus_poc")
ns = namespace(cat, "obs")
bronze = cat.create_table(f"{ns}.bronze_llm_requests", schema=bronze_arrow.schema)
with bronze.update_spec() as spec:
    spec.add_field("ts", DayTransform(), "ts_day")
bronze.append(bronze_arrow)
loc = Path(bronze.location().replace("file://", ""))

# Leak check on the BYTES on disk, not on a query result.
on_disk = "\n".join(t for f in loc.rglob("*.parquet") for t in pq.read_table(f).column("prompt").to_pylist())
leaks = {k: len(rx.findall(on_disk)) for k, rx in PATTERNS.items()}
canary_hits = sum(c in on_disk for c in CANARIES)
print(f"Bronze rows: {bronze_arrow.num_rows:,}  files: {len(list(loc.rglob('*.parquet')))}")
print(f"Raw PII matches in Bronze files: {leaks}   canaries found raw: {canary_hits}/4")

same = redact("x a@b.vn", "t001") == redact("x a@b.vn", "t001")
cross = redact("x a@b.vn", "t001") != redact("x a@b.vn", "t002")
print(f"Token deterministic within tenant: {same};  differs across tenants: {cross}")

# ── 4. Gold: 5-minute aggregates per tenant × model (kept 1 year) ───────────
duckdb.sql("SET TimeZone = 'UTC'")            # Iceberg timestamptz must be UTC
gold_arrow = duckdb.sql("""
    SELECT tenant_id, model, time_bucket(INTERVAL 5 MINUTE, ts) AS bucket_5m,
           count(*) AS requests, quantile_cont(latency_ms, 0.95) AS p95_ms, sum(cost_usd) AS cost_usd
    FROM bronze_arrow GROUP BY ALL""").arrow()
if isinstance(gold_arrow, pa.RecordBatchReader):
    gold_arrow = gold_arrow.read_all()
gold = cat.create_table(f"{ns}.gold_tenant_5m", schema=gold_arrow.schema)
gold.append(gold_arrow)

# ── 5. Retention: drop day 1 → expire snapshots → sweep unreferenced files ──
def disk_bytes() -> int:
    return sum(f.stat().st_size for f in loc.rglob("*") if f.is_file())

cutoff = T0 + timedelta(days=1)
before = disk_bytes()
bronze.delete(delete_filter=LessThan("ts", cutoff.isoformat()))          # whole partition → file drop
bronze = cat.load_table(f"{ns}.bronze_llm_requests")
after_delete = disk_bytes()
bronze.maintenance.expire_snapshots().by_ids([s.snapshot_id for s in bronze.snapshots()[:-1]]).commit()
bronze = cat.load_table(f"{ns}.bronze_llm_requests")
after_expire = disk_bytes()

live_data = {Path(t.file.file_path.replace("file://", "")).name for t in bronze.scan().plan_files()}
live_lists = {Path(s.manifest_list).name for s in bronze.snapshots()}
stale = [f for f in loc.rglob("*.parquet") if f.name not in live_data]
stale += [f for f in (loc / "metadata").glob("snap-*.avro") if f.name not in live_lists]
for f in stale:
    f.unlink()                       # production: only files older than the longest-running writer
after_sweep = disk_bytes()

oldest = min(pq.read_table(f, columns=["ts"]).column("ts").to_pylist()[0] for f in loc.rglob("*.parquet"))
print(f"\nTable bytes: {before/1e3:.0f} KB → delete {after_delete/1e3:.0f} KB → expire {after_expire/1e3:.0f} KB"
      f" → sweep {after_sweep/1e3:.0f} KB   (swept {len(stale)} files)")
print(f"Oldest ts left on disk: {oldest}   cutoff: {cutoff}")
print(f"Bronze rows now: {bronze.scan().to_arrow().num_rows:,}   Gold rows kept: "
      f"{cat.load_table(f'{ns}.gold_tenant_5m').scan().to_arrow().num_rows:,}")

checks = {
    "0 raw PII in Bronze files": sum(leaks.values()) == 0 and canary_hits == 0,
    "tokens per-tenant deterministic": same and cross,
    "expiry alone does not free bytes": after_expire >= after_delete,
    "sweep frees bytes": after_sweep < after_expire,
    "no expired-day data on disk": oldest >= cutoff,
    "gold survives retention": cat.load_table(f"{ns}.gold_tenant_5m").scan().to_arrow().num_rows == gold_arrow.num_rows,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
assert all(checks.values())
