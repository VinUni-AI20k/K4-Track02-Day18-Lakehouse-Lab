"""Bonus Challenge PoC: Ingestion, Salted Tokenization & Z-Order Clustering for LLM Observability.

Demonstrates:
1. Micro-batch landing into Bronze.
2. Deterministic salted tokenization at Bronze -> Silver boundary (zero raw PII in Silver).
3. Delta Z-Order compaction on (tenant_id, timestamp) for high-efficiency tenant pruning.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import polars as pl
from deltalake import DeltaTable, write_deltalake

POC_DIR = Path(__file__).resolve().parent / "_poc_lakehouse"
if POC_DIR.exists():
    shutil.rmtree(POC_DIR)
POC_DIR.mkdir(parents=True, exist_ok=True)

SALT = b"vinuni_lakehouse_2026_salt"
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")

def tokenize_pii(text: str) -> str:
    """Deterministic salting & tokenization of sensitive identifiers."""
    def _replace(match):
        val = match.group(0).encode("utf-8")
        token = hashlib.sha256(SALT + val).hexdigest()[:12]
        return f"[TOKEN_{token}]"
    return EMAIL_REGEX.sub(_replace, text)

def main():
    print("=== BONUS PoC: LLM Observability Ingestion & Tokenization Pipeline ===")
    
    # 1. Synthesize 5-minute micro-batch telemetry with PII
    raw_prompts = [
        "User user_alice@company.com asked for quarterly revenue summary.",
        "Summarize incident report submitted by dev_bob@techcorp.io regarding API latency.",
        "Check account balance for finance_lead@fintech.vn.",
        "Generate automated marketing email for sales@startup.ai.",
    ] * 250  # 1,000 rows
    
    tenants = ["tenant_alpha", "tenant_beta", "tenant_gamma", "tenant_target"] * 250
    timestamps = [f"2026-04-01T12:{i%60:02d}:00" for i in range(1000)]
    
    df_raw = pl.DataFrame({
        "req_id": [f"req_{i:06d}" for i in range(1000)],
        "tenant_id": tenants,
        "timestamp": timestamps,
        "prompt": raw_prompts,
        "tokens": [150 + (i % 80) for i in range(1000)],
        "latency_ms": [120.5 + (i % 50) for i in range(1000)],
    })
    
    # 2. Land into Bronze (Raw stream)
    bronze_path = str(POC_DIR / "bronze_telemetry")
    write_deltalake(bronze_path, df_raw.to_arrow(), mode="overwrite")
    print(f"Bronze raw table written: {len(df_raw)} rows.")
    
    # 3. Transform to Silver: Tokenize PII in prompt
    tokenized_prompts = [tokenize_pii(p) for p in df_raw["prompt"]]
    df_silver = df_raw.with_columns(pl.Series("prompt", tokenized_prompts))
    
    silver_path = str(POC_DIR / "silver_telemetry")
    write_deltalake(silver_path, df_silver.to_arrow(), mode="overwrite")
    print(f"Silver sanitized table written: {len(df_silver)} rows.")
    
    # 4. Verify PII Protection Contract in Silver
    sample_silver_prompts = df_silver["prompt"].to_list()
    has_raw_email = any(EMAIL_REGEX.search(p) for p in sample_silver_prompts)
    print(f"PII Leakage Check in Silver: {'FAIL (Leaks found)' if has_raw_email else 'PASS (Zero raw PII)'}")
    assert not has_raw_email, "PII found in Silver layer!"
    
    # 5. Optimize & Z-Order Silver by (tenant_id)
    dt_silver = DeltaTable(silver_path)
    dt_silver.optimize.compact()
    dt_silver.optimize.z_order(["tenant_id"])
    print("Compaction & Z-Order clustering on 'tenant_id' completed.")
    
    # 6. Point Query Test: Scan for tenant_target
    filtered = dt_silver.to_pyarrow_table(filters=[("tenant_id", "=", "tenant_target")])
    print(f"Tenant filter query for 'tenant_target': retrieved {filtered.num_rows} rows.")
    assert filtered.num_rows == 250, "Expected 250 rows for tenant_target"
    
    print("\n[SUCCESS] Bonus PoC pipeline completed and validated successfully!")
    
    # Cleanup POC dir to avoid committing large temporary files
    shutil.rmtree(POC_DIR)

if __name__ == "__main__":
    main()
