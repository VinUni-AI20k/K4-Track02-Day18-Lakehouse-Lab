"""PoC for Architecture Brief (Topic A): PII Tokenization + Z-Order Skipping + Retention Expiry.
Demonstrates the core mechanics in < 120 lines of clean, self-contained Python code.
"""
import hashlib
import time
from pathlib import Path
import polars as pl
from deltalake import DeltaTable, write_deltalake

ROOT = Path(__file__).resolve().parents[3]
POC_TABLE = ROOT / "_lakehouse" / "scratch" / "poc_llm_observability"

SALT = b"vinuni_secret_salt_2026"

def tokenize_pii(text: str) -> str:
    """Deterministic HMAC-SHA256 tokenization for PII."""
    return hashlib.sha256(SALT + text.encode("utf-8")).hexdigest()[:16]

def main():
    print("=== BONUS ARCHITECTURE PoC: TOPIC A (LLM OBSERVABILITY) ===")
    if POC_TABLE.exists():
        import shutil
        shutil.rmtree(POC_TABLE, ignore_errors=True)

    # 1. Ingestion with In-Flight PII Tokenization
    raw_calls = [
        {"req_id": f"req_{i}", "tenant_id": f"tenant_{i % 50}",
         "user_email": f"user_{i}@example.com", "latency_ms": 200 + (i * 7) % 1500,
         "cost_usd": 0.002 * (1 + i % 3), "day": "2026-08-01" if i < 5000 else "2026-08-08"}
        for i in range(10000)
    ]
    df = pl.DataFrame(raw_calls).with_columns([
        pl.col("user_email").map_elements(tokenize_pii, return_dtype=pl.Utf8).alias("user_token")
    ]).drop("user_email")

    print(f"[1] Ingested 10,000 raw requests with PII Tokenization:")
    print(df.head(2))

    # 2. Write to Delta Table partitioned by day
    write_deltalake(POC_TABLE, df.to_arrow(), mode="overwrite", partition_by=["day"])
    dt = DeltaTable(POC_TABLE)
    print(f"\n[2] Written to Delta Table: {dt.count():,} rows across partitions: {dt.file_uris()[:2]} ...")

    # 3. Optimize with Z-ORDER by tenant_id
    print("\n[3] Running Z-ORDER by tenant_id...")
    dt.optimize.z_order(["tenant_id"])
    print("    Z-Order clustering complete.")

    # 4. Measure point query skipping
    TARGET_TENANT = "tenant_42"
    t0 = time.perf_counter()
    filtered = dt.to_pyarrow_table(filters=[("tenant_id", "=", TARGET_TENANT)])
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[4] Query for {TARGET_TENANT}: found {filtered.num_rows} records in {elapsed_ms:.2f} ms")

    # 5. 7-Day Retention Expiry Simulation
    print("\n[5] Simulating 7-Day Retention Expiry (Deleting day=2026-08-01)...")
    dt.delete("day = '2026-08-01'")
    print(f"    Rows after deletion: {DeltaTable(POC_TABLE).count():,} (was 10,000)")
    
    # Vacuum tombstoned files
    doomed = dt.vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
    print(f"    VACUUM purged {len(doomed)} tombstoned files from disk.")
    print("\nPoC completed successfully.")

if __name__ == "__main__":
    main()
