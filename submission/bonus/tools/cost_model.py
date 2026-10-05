"""Deterministic, offline estimate; no AWS account or credentials required."""
from decimal import Decimal as D
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = D(1024) ** 3
TB = D(10) ** 12
SOURCES = {
    "s3": "https://aws.amazon.com/s3/pricing/",
    "kinesis": "https://aws.amazon.com/kinesis/data-streams/pricing/",
    "fargate": "https://aws.amazon.com/fargate/pricing/",
    "glue": "https://aws.amazon.com/glue/pricing/",
    "athena": "https://aws.amazon.com/athena/pricing/",
}
evidence = json.loads((ROOT / "evidence/aws-s3-price-evidence.json").read_text())
dims = evidence["price_dimensions"]
storage_tiers = sorted(
    [d for d in dims if d["unit"] == "GB-Mo"], key=lambda d: D(d["beginRange"])
)
put_rate = D(next(d for d in dims if d["attributes"].get("group") == "S3-API-Tier1")["pricePerUnit"]["USD"])
get_rate = D(next(d for d in dims if d["attributes"].get("group") == "S3-API-Tier2")["pricePerUnit"]["USD"])


def s3_cost(byte_count):
    gib = byte_count / GIB
    total = D(0)
    for tier in storage_tiers:
        start = D(tier["beginRange"])
        end = gib if tier["endRange"] == "Inf" else D(tier["endRange"])
        total += max(D(0), min(gib, end) - start) * D(tier["pricePerUnit"]["USD"])
    return total


def model(days=30, compression=4, tenants=10_000):
    days, compression = D(days), D(compression)
    hours = days * 24
    # 7 days readable + <=24 h physical cleanup; all copies costed.
    bronze = D(5) * TB * 8 / compression
    silver = D(1) * TB * 8 / compression
    rewrites = (bronze + silver) * D("0.25")
    gold = D(tenants) * 3 * 288 * 365 * 4000 / 2
    other = TB  # audit/checkpoints/manifests/results, including log-export storage
    occupancy = bronze + silver + rewrites + gold + other
    s3 = s3_cost(occupancy)
    requests = (D(8_000_000) * put_rate + D(30_000_000) * get_rate) * days / 30
    stream = D(350) * hours * D("0.015") + D(1_000_000_000) * days / 1_000_000 * D("0.014")
    storage = s3 + requests + stream + 100  # explicitly allocated storage reserve
    cpu_s, ram_s = D("0.000011244"), D("0.000001235")
    redact = 12 * (8 * cpu_s + 16 * ram_s) * hours * 3600
    api = 2 * (2 * cpu_s + 4 * ram_s) * hours * 3600
    glue_stream = 16 * hours * D("0.44")
    glue_maintenance = 8 * 4 * days * D("0.44")
    athena = D(30) * 5 * days / 30  # 30 billed TB/month; scan guardrails
    operations = D(500) * days / 30  # explicit allowance, not a provider quote
    compute = redact + api + glue_stream + glue_maintenance + athena + operations
    return {"days": days, "compression": compression, "tenants": tenants,
            "bronze_tb": bronze / TB, "silver_tb": silver / TB,
            "rewrite_tb": rewrites / TB, "gold_tb": gold / TB,
            "other_tb": other / TB, "s3_tb": occupancy / TB,
            "s3_gib": occupancy / GIB, "s3_usd": s3,
            "s3_requests_usd": requests, "stream_usd": stream,
            "storage_reserve_usd": D(100), "storage_usd": storage,
            "storage_headroom_usd": D(5000) - storage,
            "fargate_redaction_usd": redact, "fargate_api_usd": api,
            "glue_stream_usd": glue_stream, "glue_maintenance_usd": glue_maintenance,
            "athena_usd": athena, "operations_allowance_usd": operations,
            "compute_operations_usd": compute, "total_usd": compute + storage,
            "storage_cap_pass": storage <= 5000}


avg_rps = D(1_000_000_000) / 86400
peak_bytes = avg_rps * 5 * 5000
capacity_bytes = D(350) * 1_000_000  # conservative decimal MB, including keys
assert capacity_bytes >= peak_bytes * D("1.20")
assert avg_rps * 5 < 350 * 1000
assert model(30)["storage_cap_pass"] and model(31)["storage_cap_pass"]
out = {"pricing_checked_on": "2026-10-05", "region": "us-east-1",
       "basis": "USD, on-demand Linux/x86, no tax/discount; 30-day base + 31-day stress",
       "sources": SOURCES, "s3_evidence_version": evidence["offer_version"],
       "ingress": {"average_rps": avg_rps, "five_x_peak_rps": avg_rps * 5,
                   "peak_mb_per_second": peak_bytes / 1_000_000,
                   "capacity_mb_per_second": capacity_bytes / 1_000_000,
                   "capacity_over_peak_pct": (capacity_bytes / peak_bytes - 1) * 100},
       "base": model(30), "month_31_days": model(31),
       "sensitivity": [model(31, c, t) for c, t in [(3, 10_000), (2, 10_000), (1, 10_000), (4, 20_000)]]}
# Serialize exact decimal strings to avoid hiding binary floating-point rounding.
serialized = json.dumps(out, ensure_ascii=False, indent=2, default=str)
(ROOT / "evidence/cost-model.json").write_text(serialized + "\n", encoding="utf-8")
print(serialized)
