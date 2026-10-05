# %% [markdown]
# # Replay an Iceberg commit without losing a late correction
# One Silver writer; SQLite is a local stand-in for Glue, not a concurrency test.
# A real process crash is modelled by raising after the durable upsert.
# %%
import json
import os
import tempfile
from pathlib import Path

import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog

repo = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
scratch = repo / "_lakehouse"
scratch.mkdir(exist_ok=True)
work = tempfile.TemporaryDirectory(prefix="bonus-replay-", dir=scratch)
base = Path(work.name)
warehouse = f"file://{base}" if os.name == "nt" else base.as_uri()
catalog = SqlCatalog("local", uri="sqlite:///" + (base / "catalog.db").as_posix(), warehouse=warehouse)
catalog.create_namespace("lab")
schema = pa.schema([("event_id", pa.string()), ("revision", pa.int64()),
                    ("tenant", pa.string()), ("window", pa.int64()), ("cost_micro_usd", pa.int64())])
silver = catalog.create_table("lab.silver", schema=schema)
gold_schema = pa.schema([("tenant", pa.string()), ("window", pa.int64()),
                        ("request_count", pa.int64()), ("cost_micro_usd", pa.int64())])
gold = catalog.create_table("lab.gold", schema=gold_schema)
checkpoints = set()

# %%
def ingest(batch_id, rows, crash=False):
    # Source checkpoint is deliberately outside the Iceberg commit.
    if batch_id in checkpoints:
        return 0
    current = {r["event_id"]: r for r in silver.scan().to_arrow().to_pylist()}
    for row in rows:
        old = current.get(row["event_id"])
        if old is None or row["revision"] > old["revision"]:
            current[row["event_id"]] = row
        elif row["revision"] == old["revision"] and row != old:
            raise ValueError("Conflicting contents at the same event revision")
    before = {r["event_id"]: r for r in silver.scan().to_arrow().to_pylist()}
    changes = [r for k, r in current.items() if before.get(k) != r]
    if changes:
        silver.upsert(pa.Table.from_pylist(changes, schema=schema), join_cols=["event_id"])
    if crash:
        raise RuntimeError("Injected crash: commit succeeded, checkpoint not saved")
    checkpoints.add(batch_id)
    return len(changes)


def publish_gold():
    silver_id = silver.current_snapshot().snapshot_id
    sums = {}
    for row in silver.scan(snapshot_id=silver_id).to_arrow().to_pylist():
        key = row["tenant"], row["window"]
        count, cost = sums.get(key, (0, 0))
        sums[key] = count + 1, cost + row["cost_micro_usd"]
    rows = [dict(tenant=t, window=w, request_count=n, cost_micro_usd=c)
            for (t, w), (n, c) in sorted(sums.items())]
    gold.overwrite(pa.Table.from_pylist(rows, schema=gold_schema),
                   snapshot_properties={"silver_snapshot_id": str(silver_id)})
    return gold.scan().to_arrow().to_pylist()


def event(key, rev, cost):
    return dict(event_id=key, revision=rev, tenant="tenant-A", window=123, cost_micro_usd=cost)

# %%
first = [event("r1:attempt1", 1, 100), event("r2:attempt1", 1, 200)]
crash_seen = False
try:
    ingest("batch-1", first, crash=True)
except RuntimeError as error:
    crash_seen = True
    print(error)
assert crash_seen
assert "batch-1" not in checkpoints
snapshot_after_crash = silver.current_snapshot().snapshot_id
# Reload through catalog to demonstrate persistence, not just a Python cache.
silver = catalog.load_table("lab.silver")
assert len(silver.scan().to_arrow()) == 2
replay_changes = ingest("batch-1", first)
assert replay_changes == 0
assert silver.current_snapshot().snapshot_id == snapshot_after_crash
assert publish_gold()[0]["cost_micro_usd"] == 300
old_gold = gold.current_snapshot().snapshot_id
assert ingest("late-correction", [event("r1:attempt1", 2, 150)]) == 1
stale_changes = ingest("stale-replay", [event("r1:attempt1", 1, 100)])
assert stale_changes == 0
assert len(silver.scan().to_arrow()) == 2
assert publish_gold()[0] == dict(tenant="tenant-A", window=123, request_count=2, cost_micro_usd=350)
assert gold.scan(snapshot_id=old_gold).to_arrow().to_pylist()[0]["cost_micro_usd"] == 300
stable_gold = publish_gold()
assert stable_gold[0]["request_count"] == 2 and stable_gold[0]["cost_micro_usd"] == 350
conflict_blocked = False
try:
    ingest("conflict", [event("r1:attempt1", 2, 999)])
except ValueError:
    conflict_blocked = True
assert conflict_blocked
assert gold.current_snapshot().summary.additional_properties["silver_snapshot_id"] == str(silver.current_snapshot().snapshot_id)
result = dict(crash_after_commit=crash_seen, replay_added_rows=replay_changes,
              stale_revision_ignored=stale_changes == 0,
              conflicting_revision_blocked=conflict_blocked, request_count=stable_gold[0]["request_count"],
              final_cost_micro_usd=stable_gold[0]["cost_micro_usd"],
              old_snapshot_cost_micro_usd=gold.scan(snapshot_id=old_gold).to_arrow().to_pylist()[0]["cost_micro_usd"],
              repeated_gold_equal=publish_gold() == stable_gold)
print(json.dumps(result, indent=2))
print("BONUS_RESULT_JSON=" + json.dumps(result))
catalog.engine.dispose()
work.cleanup()
