"""Prepare additive NB6/NB7 baselines and an exact review; never delete/reset.

Run once. Refuses existing destinations, preserves previous notebook outputs,
and does not execute expiry, row deletes, VACUUM or file moves. All generated
artifacts remain in the workspace. The review is not deletion authorization.
"""
from __future__ import annotations

import datetime as dtm
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import DeltaTable, write_deltalake

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "_lakehouse"
DEST = REPO / "submission"


def scoped(value):
    p = Path(value).resolve()
    if not p.is_relative_to(REPO) or p == REPO:
        raise RuntimeError(f"Outside workspace: {p}")
    return p


def fresh(value):
    p = scoped(value)
    if p.exists():
        raise RuntimeError(f"Preserving existing destination: {p}")
    return p


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def file_record(value, category):
    p = scoped(value)
    if not p.is_file():
        raise RuntimeError(f"Missing file: {p}")
    rel = p.relative_to(REPO).as_posix()
    tracked = bool(git("ls-files", "--", rel))
    return {
        "path": str(p), "bytes": p.stat().st_size,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "tracked": tracked,
        "git_status": git("status", "--porcelain=v1", "--ignored", "--", rel),
        "category": category,
        "proposed_quarantine": str(fresh(DATA / "review_quarantine" / p.relative_to(DATA))),
        "recovery": "No move performed. If explicitly authorized later, move this exact file back from quarantine; verify SHA256.",
    }


def write_new(value, content):
    p = fresh(value)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f:
        f.write(content)


def main():
    initial_status = git("status", "--porcelain=v1", "--untracked-files=all")
    report_path = fresh(DEST / "REVIEW_20261004.json")
    log_path = fresh(DEST / "logs" / "preparation_20261004.json")
    os.environ["LAKEHOUSE_ROOT"] = str(scoped(DATA))
    import lakehouse as lh

    table = scoped(DATA / "scratch" / "maint_events")
    dt = DeltaTable(str(table))
    vacuum = [file_record(table / f, "pre-existing ignored tombstoned Delta data")
              for f in dt.vacuum(retention_hours=0, dry_run=True,
                                 enforce_retention_duration=False)]
    live = {scoped(unquote(p.replace("file://", ""))) for p in dt.file_uris()}
    assert all(Path(f["path"]) not in live for f in vacuum)
    orphan_paths = [fresh(table / f"part-9999{i}-crashed-writer-c000.snappy.parquet")
                    for i in range(3)]
    catalog_dir = fresh(DATA / "iceberg" / "nb6")
    cdf_path = fresh(DATA / "scratch" / "docs_cdf")
    docs = DeltaTable(str(scoped(DATA / "bronze" / "docs_multimodal"))).to_pyarrow_table()
    # Resolve every additive destination before any data writes.
    fresh(DATA / "review_quarantine")
    rows_before = dt.count()
    for orphan in orphan_paths:
        pq.write_table(pa.table({
            "event_id": list(range(1000)), "user_id": [0] * 1000,
            "ts": [dtm.datetime(2026, 8, 1)] * 1000,
            "latency_ms": [1] * 1000, "payload": ["x" * 80] * 1000,
        }), orphan)
        old = time.time() - 30 * 86400
        os.utime(orphan, (old, old))
    orphans = [file_record(p, "new synthetic orphan created by this script") for p in orphan_paths]
    assert DeltaTable(str(table)).count() == rows_before == 100000
    assert all(p not in live for p in orphan_paths)
    cutoff = time.time() - 24 * 3600
    aged_unreferenced = [scoped(p) for p in table.rglob("*.parquet")
                        if "_delta_log" not in p.parts and scoped(p) not in live
                        and p.stat().st_mtime < cutoff]
    # Older tombstones may also meet the age guard: report rather than deleting.
    vacuum_after = dt.vacuum(retention_hours=0, dry_run=True,
                            enforce_retention_duration=False)
    assert not any(scoped(table / p) in orphan_paths for p in vacuum_after)

    assert lh._catalog_dir("nb6").resolve() == catalog_dir
    cat = lh.catalog("nb6")  # fresh catalog; never call reset_catalog
    lh.namespace(cat, "lake")
    schema = pa.schema([pa.field("event_id", pa.int64(), nullable=False),
                        pa.field("user_id", pa.int64())])
    ice = cat.create_table("lake.maint", schema=schema)
    scoped(ice.location().replace("file://", ""))
    for b in range(20):
        ice.append(pa.table({"event_id": list(range(b * 100, (b + 1) * 100)),
                             "user_id": [(b * 31 + i) % 5000 for i in range(100)]},
                            schema=schema))
    ice = cat.load_table("lake.maint")
    assert len(ice.snapshots()) == 20 and ice.scan().to_arrow().num_rows == 2000
    expired = ice.snapshots()[:-3]
    manifest_lists = [file_record(s.manifest_list.replace("file://", ""),
                                 "new manifest list; CURRENTLY REFERENCED, not an orphan")
                      for s in expired]
    metadata = file_record(ice.metadata_location.replace("file://", ""),
                           "retain this original metadata for recovery; DO NOT move")
    metadata.pop("proposed_quarantine")

    write_deltalake(str(cdf_path), docs.select(["doc_id", "subject_id"]),
                    mode="error", configuration={"delta.enableChangeDataFeed": "true"})
    assert DeltaTable(str(cdf_path)).count() == docs.num_rows
    row_reviews = []
    for relative, subject in [("scratch/docs_intable", "user_042"),
                              ("scratch/docs_cdf", "user_042"),
                              ("silver/training_corpus_governed", "user_007")]:
        p = scoped(DATA / relative)
        t = DeltaTable(str(p))
        rows = t.to_pyarrow_table(filters=[("subject_id", "=", subject)])
        assert rows.num_rows > 0
        row_reviews.append({"table": str(p), "version": t.version(),
                            "predicate": f"subject_id = '{subject}'",
                            "count": rows.num_rows, "doc_ids": rows.column("doc_id").to_pylist(),
                            "tracked": False, "git_status": git("status", "--porcelain=v1", "--ignored", "--", p.relative_to(REPO).as_posix()),
                            "recovery": f"Keep physical files; restore Delta version {t.version()} through a new commit if needed. No VACUUM on this table.",
                            "effect": "Proposed row delete creates a new current version; older data remains. NOT EXECUTED."})
    log_dir = scoped(table / "_delta_log")
    checkpoint = json.loads((log_dir / "_last_checkpoint").read_text(encoding="utf-8"))
    checkpoint_files = sorted(p.name for p in log_dir.glob("*.checkpoint.parquet"))
    assert checkpoint_files
    evidence = {
        "date": "2026-10-04", "delta_rows_unchanged": rows_before,
        "vacuum_candidates": len(vacuum), "vacuum_candidate_bytes": sum(f["bytes"] for f in vacuum),
        "vacuum_reclaimed_bytes": 0, "vacuum_executed": False,
        "planted_orphans": len(orphans), "planted_orphan_bytes": sum(f["bytes"] for f in orphans),
        "aged_unreferenced_count_including_tombstones": len(aged_unreferenced),
        "vacuum_dry_run_detected_planted_orphans": False,
        "iceberg_snapshots": 20, "iceberg_rows": 2000, "expiry_executed": False,
        "cdf_baseline_rows": docs.num_rows, "cdf_delete_executed": False,
        "subject_rows_before_delete": [{"table": r["table"], "count": r["count"]} for r in row_reviews],
        "automatic_checkpoint": checkpoint, "checkpoint_files": checkpoint_files,
        "manual_checkpoint_executed": False,
        "ready_to_submit": False,
    }
    review = {
        "workspace": str(REPO), "status": "PREPARATION ONLY; NO DESTRUCTIVE ACTION AUTHORIZED OR EXECUTED",
        "initial_git_status": initial_status,
        "vacuum": {"table": str(table), "version": dt.version(), "files": vacuum,
                   "candidate_bytes": evidence["vacuum_candidate_bytes"],
                   "effect": "VACUUM would permanently delete ignored data and invalidate older versions. Agent will not permanently delete these files.",
                   "alternative": "Review exact quarantine pairs; reversible relocation requires separate explicit authorization. It is NOT a real VACUUM result."},
        "delta_orphans": orphans,
        "iceberg": {"catalog": str(catalog_dir), "table": "lake.maint",
                    "metadata_to_retain": metadata,
                    "expire_snapshot_ids": [s.snapshot_id for s in expired],
                    "keep_snapshot_ids": [s.snapshot_id for s in ice.snapshots()[-3:]],
                    "manifest_lists_after_proposed_expiry": manifest_lists,
                    "effect": "Proposed expiry removes 17 references from current metadata. Old metadata/files must remain recoverable. No expiry/sweep executed.",
                    "alternative": "Keep 20 snapshots; or explicitly authorize reversible metadata expiry and later quarantines. Do not permanently delete untracked files."},
        "row_deletions": row_reviews,
        "evidence": evidence,
        "verification_requirement": "Recheck versions, doc_ids, SHA256s, Git state, and canonical quarantine paths immediately before any separately authorized operation. Stop on drift.",
        "permanent_deletion": "PROHIBITED for untracked/dirty data by user policy; user must perform permanent removal manually if truly required.",
    }
    write_new(report_path, json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    write_new(log_path, json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
