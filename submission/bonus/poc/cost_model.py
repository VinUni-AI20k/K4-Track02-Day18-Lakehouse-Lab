"""Back-of-envelope cost model for Bonus topic E (click-stream, 10 TB/day, 365d, cap $8K/mo).
Run: python submission/bonus/poc/cost_model.py
All prices are ASSUMED list prices (us-east-1, USD) -- verify against the AWS pricing page before use.
"""
RAW_TB_DAY = 10.0
COMPRESSION = 5.0              # JSON -> Parquet+zstd, ASSUMPTION: validate on a 1-day sample
PQ_TB_DAY = RAW_TB_DAY / COMPRESSION
GB = 1000                      # 1 TB = 1000 GB (S3 billing uses GB-month)

PRICE = {"STD": 0.023, "IA": 0.0125, "GIR": 0.004}   # $/GB-month
HOT_D, WARM_END, RETAIN = 7, 90, 365
tb = {"STD": PQ_TB_DAY * HOT_D,
      "IA": PQ_TB_DAY * (WARM_END - HOT_D),
      "GIR": PQ_TB_DAY * (RETAIN - WARM_END)}

storage = {k: tb[k] * GB * PRICE[k] for k in tb}
# Retrieval: assumed scanned volume per month AFTER pruning (the main risk, see failure mode F3)
RETR = {"IA": (40, 0.01), "GIR": (10, 0.03)}          # (TB/month, $/GB)
retrieval = {k: v[0] * GB * v[1] for k, v in RETR.items()}
# Compute (spot/savings-blended factor 0.4 of on-demand), 730 h/month
H = 730
ingest = 6 * 0.384 * H * 0.4        # 6 x m6i.2xlarge streaming ingest
trino = 4 * 0.768 * H * 0.4         # 4 x m6i.4xlarge query workers
compact = 10 * 0.384 * 1 * 30       # daily 1h compaction/tier-down, 10 nodes, on-demand
compute = {"ingest": ingest, "trino": trino, "compaction": compact}

total = sum(storage.values()) + sum(retrieval.values()) + sum(compute.values())
print(f"Parquet volume/day: {PQ_TB_DAY:.1f} TB   steady state: {sum(tb.values()):.0f} TB")
for k in tb: print(f"  {k:3s} {tb[k]:6.0f} TB  x ${PRICE[k]*GB:6.1f}/TB-mo = ${storage[k]:8,.0f}")
print(f"STORAGE total      ${sum(storage.values()):8,.0f}")
for k in retrieval: print(f"  retrieval {k}: {RETR[k][0]} TB x ${RETR[k][1]*GB:.0f}/TB = ${retrieval[k]:,.0f}")
for k in compute: print(f"  compute {k:10s} ${compute[k]:8,.0f}")
print(f"ALL-IN total       ${total:8,.0f}   cap $8,000   headroom ${8000-total:,.0f}")

# Why not pure lifecycle Standard->IA: objects must sit >=30 days in Standard first
extra = PQ_TB_DAY * (30 - HOT_D) * GB * (PRICE["STD"] - PRICE["IA"])
print(f"Pure-lifecycle penalty (days 8-30 stuck in Standard): +${extra:,.0f}/mo")
# Guardrail: one unbounded SELECT over the cold tier
print(f"Unbounded scan of cold tier: {tb['GIR']:.0f} TB x $30/TB = ${tb['GIR']*GB*0.03:,.0f} per query")
