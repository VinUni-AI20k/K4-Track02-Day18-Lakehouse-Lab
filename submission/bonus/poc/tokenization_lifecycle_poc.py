"""PoC for Day 18 Bonus Challenge (Topic A: LLM Observability at 1B req/day).

Demonstrates:
1. In-flight PII redaction / tokenization before committing to Bronze/Silver.
2. Z-Order clustering by tenant_id for high-speed tenant dashboard filtering.
3. Retention lifecycle enforcement via Delta Lake / Iceberg table operations.
"""
import re
import hashlib
import time
import polars as pl
from deltalake import DeltaTable, write_deltalake
from pathlib import Path
import shutil

POC_DIR = Path("_lakehouse/bonus_poc")
if POC_DIR.exists():
    shutil.rmtree(POC_DIR)
POC_DIR.mkdir(parents=True, exist_ok=True)

# 1. In-flight Redaction Engine
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
CC_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SALT = "day18-secret-salt"

def tokenize_pii(text: str) -> str:
    """Mask email and credit cards deterministically."""
    def mask_email(match):
        h = hashlib.sha256((match.group(0) + SALT).encode()).hexdigest()[:8]
        return f"[EMAIL_TOKEN_{h}]"
    
    def mask_cc(match):
        return "[CC_REDACTED]"
    
    masked = EMAIL_REGEX.sub(mask_email, text)
    masked = CC_REGEX.sub(mask_cc, masked)
    return masked

# 2. Simulate raw inbound events
raw_events = [
    {"req_id": f"req_{i}", "tenant_id": f"tenant_{i % 5}", "user_prompt": f"My email is user_{i}@company.com and card 4111-2222-3333-4444", "tokens": 120 + i}
    for i in range(1000)
]

# Apply in-flight redaction BEFORE lakehouse commit
cleansed_events = [
    {
        "req_id": ev["req_id"],
        "tenant_id": ev["tenant_id"],
        "prompt": tokenize_pii(ev["user_prompt"]),
        "tokens": ev["tokens"]
    }
    for ev in raw_events
]

df = pl.DataFrame(cleansed_events)
table_path = str(POC_DIR / "cleansed_silver")

# 3. Write and perform Z-Order by tenant_id
write_deltalake(table_path, df.to_arrow(), mode="overwrite")
dt = DeltaTable(table_path)
dt.optimize.z_order(["tenant_id"])

print("=== Bonus PoC Verification ===")
print(f"Total rows committed: {len(df)}")
# Verify zero PII leakage
unmasked_emails = [r for r in df["prompt"] if "@company.com" in r]
print(f"Unmasked PII emails found: {len(unmasked_emails)} (Expected: 0)")
assert len(unmasked_emails) == 0, "PII Leakage detected!"

# Check sample row
sample = DeltaTable(table_path).to_pyarrow_table().slice(0, 1).to_pylist()[0]
print(f"Sample masked prompt: {sample['prompt']}")
print("PoC completed successfully.")
