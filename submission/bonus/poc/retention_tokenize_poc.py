"""PoC for ARCHITECTURE.md (Topic A): the two hardest mechanisms of the design.

1. PII is tokenized AT BRONZE LANDING (HMAC, deterministic per tenant) — nobody
   ever reads raw PII from the lake; incident review can still join on tokens.
2. Bodies are kept 7 days, aggregates 1 year: the retention job must PHYSICALLY
   remove expired body files (not just hide them), while Gold stays intact.

Also measures the JSON → Parquet(zstd) compression ratio used in the cost math.

Run from the repo root (uses the lab's .venv, offline):
    .venv/Scripts/python.exe submission/bonus/poc/retention_tokenize_poc.py
"""
from __future__ import annotations

import hashlib, hmac, json, random, re, shutil, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

random.seed(18)
ROOT = Path(tempfile.mkdtemp(prefix="poc_obs_"))
BODIES, GOLD = str(ROOT / "silver_bodies"), str(ROOT / "gold_tenant_5min")
SECRET = b"demo-key-from-kms"          # production: per-tenant key in KMS, rotated
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+84|0)\d{9}")
HEX_TO_ALPHA = str.maketrans("0123456789abcdef", "ghijklmnopqrstuv")
WORDS = "hoá đơn tháng này bị tính sai vui lòng kiểm tra lại giúp tôi đơn hàng giao chậm".split()


def tokenize(text: str, tenant: str) -> str:
    """Replace PII with a stable token: same value + tenant -> same token (joinable)."""
    def tok(m: re.Match) -> str:
        h = hmac.new(SECRET, f"{tenant}|{m.group(0)}".encode(), hashlib.sha256).hexdigest()[:12]
        # Letters-only alphabet: a hex token like '204518408044' would itself match the
        # phone detector (~0.25% of tokens did in the first run) and drown the canary.
        return f"<pii:{h.translate(HEX_TO_ALPHA)}>"
    return PHONE.sub(tok, EMAIL.sub(tok, text))


def make_requests(day: datetime, n: int) -> list[dict]:
    rows = []
    for i in range(n):
        tenant = f"t{random.randint(1, 50):03d}"
        prompt = " ".join(random.choices(WORDS, k=random.randint(40, 120)))
        if i % 5 == 0:   # 20% of prompts carry PII
            prompt += f" email nguyenvan{i}@gmail.com sđt 09{random.randint(10**7, 10**8 - 1)}"
        rows.append({
            "request_id": f"{day:%m%d}-{i:06d}", "tenant_id": tenant,
            "ts": day + timedelta(seconds=random.randint(0, 86_399)),
            "model": random.choice(["small", "medium", "large"]),
            "latency_ms": int(random.lognormvariate(6.5, 0.5)),
            "prompt": prompt, "response": " ".join(random.choices(WORDS, k=random.randint(60, 200))),
        })
    return rows


# ── Land 10 days of traffic: tokenize BEFORE anything is written ─────────────
start = datetime(2026, 4, 1, tzinfo=timezone.utc)
raw_json_bytes = 0
for d in range(10):
    day = start + timedelta(days=d)
    reqs = make_requests(day, 3_000)
    raw_json_bytes += sum(len(json.dumps(r, default=str, ensure_ascii=False).encode()) for r in reqs)
    for r in reqs:
        r["prompt"], r["response"] = tokenize(r["prompt"], r["tenant_id"]), tokenize(r["response"], r["tenant_id"])
        r["date"] = r["ts"].date().isoformat()
    write_deltalake(BODIES, pa.Table.from_pylist(reqs), mode="append", partition_by=["date"],
                    writer_properties=None)

con = duckdb.connect()
con.sql("SET TimeZone = 'UTC'")        # the NB4 lesson: day boundaries in UTC, not laptop time
con.register("bodies", DeltaTable(BODIES).to_pyarrow_table())
leaks = con.sql(rf"""SELECT count(*) FROM bodies
                    WHERE regexp_matches(prompt, '[\w.+-]+@[\w-]+\.[\w.]+')
                       OR regexp_matches(prompt, '(\+84|0)\d{{9}}')""").fetchone()[0]
tokens = con.sql("SELECT count(*) FROM bodies WHERE prompt LIKE '%<pii:%'").fetchone()[0]

parquet_bytes = sum(f.stat().st_size for f in Path(BODIES).rglob("*.parquet"))
print(f"[1] tokenization at landing: {tokens:,} prompts tokenized, raw PII left = {leaks}")
print(f"    raw JSON {raw_json_bytes/1e6:.1f} MB → Parquet {parquet_bytes/1e6:.1f} MB "
      f"(compression {raw_json_bytes/parquet_bytes:.1f}×)")

# ── Gold: 5-minute tenant aggregates, kept 1 year (no bodies, no PII) ────────
gold = con.sql("""
    SELECT tenant_id, model, time_bucket(INTERVAL 5 MINUTE, ts) AS bucket,
           count(*) AS n, quantile_cont(latency_ms, 0.95) AS p95_ms
    FROM bodies GROUP BY ALL
""").arrow()
write_deltalake(GOLD, gold, mode="overwrite")
gold_rows_before = DeltaTable(GOLD).to_pyarrow_table().num_rows

# ── Retention job: bodies older than 7 days must be PHYSICALLY gone ──────────
cutoff = (start + timedelta(days=10 - 7)).date().isoformat()   # keep the last 7 days
files_before = len(list(Path(BODIES).rglob("*.parquet")))
dt = DeltaTable(BODIES)
dt.delete(f"date < '{cutoff}'")
still_on_disk = len(list(Path(BODIES).rglob("*.parquet")))
# lab-only retention 0; production keeps ~24 h grace so a bad delete can be rolled back
DeltaTable(BODIES).vacuum(retention_hours=0, enforce_retention_duration=False, dry_run=False)
files_after = len(list(Path(BODIES).rglob("*.parquet")))
days_left = sorted({p.parent.name for p in Path(BODIES).rglob("*.parquet")})   # dirs that still hold data

print(f"[2] retention: delete date < {cutoff}")
print(f"    parquet files: {files_before} → after DELETE {still_on_disk} (still on disk!) "
      f"→ after VACUUM {files_after}")
print(f"    partitions left: {days_left[0]} … {days_left[-1]} ({len(days_left)} days)")
print(f"    Gold rows: {gold_rows_before:,} → {DeltaTable(GOLD).to_pyarrow_table().num_rows:,} (untouched)")

checks = {
    "no raw PII lands in the lake": leaks == 0 and tokens > 0,
    "DELETE alone does not free storage": still_on_disk == files_before,
    "VACUUM physically removes expired bodies": files_after < files_before,
    "exactly 7 days of bodies remain": len(days_left) == 7,
    "Gold (1-year aggregates) intact": DeltaTable(GOLD).to_pyarrow_table().num_rows == gold_rows_before,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
shutil.rmtree(ROOT, ignore_errors=True)
assert all(checks.values())
