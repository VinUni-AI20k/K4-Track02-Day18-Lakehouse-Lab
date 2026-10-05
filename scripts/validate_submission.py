"""Check preserved notebook evidence against the numeric rubric and bundle contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def main():
    manifest = json.loads((OUT / "evidence" / "execution.json").read_text(encoding="utf-8"))
    notebooks = sorted((OUT / "notebooks").glob("*.ipynb"))
    assert len(notebooks) == len(manifest["notebooks"]) == 8
    for path in notebooks:
        record = manifest["notebooks"][path.stem]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["notebook_sha256"]
        source = ROOT / "notebooks" / (path.stem + ".py")
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record["source_sha256"]
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        code = [c for c in nb.cells if c.cell_type == "code"]
        assert [c.execution_count for c in code] == list(range(1, len(code) + 1))
        assert not any(o.output_type == "error" for c in code for o in c.outputs)
        assert any(c.outputs for c in code)
        text = "".join(o.get("text", "") for c in code for o in c.outputs)
        raw = text.split("METRICS_JSON=", 1)[1].strip()
        assert json.loads(raw) == record["metrics"], "Manifest must match actual notebook output"
        shot = OUT / "screenshots" / ("nb" + path.stem + ".png")
        assert shot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        print(f"PASS {path.name}: sequential execution, outputs, hashes, screenshot")

    m = [r["metrics"] for _, r in sorted(manifest["notebooks"].items())]
    a, b, c, d, e, f, g, h = m
    assert len(a["commits"]) >= 2 and a["schema_blocked"] and "tier" in a["columns"] and len(a["tier_groups"]) == 2
    assert b["files_before"] >= 100 and b["files_after"] < b["files_before"]
    assert b["speedup"] >= 3 or b["pruning_ratio"] >= 10
    assert len(c["history"]) >= 5 and any(r["operation"] == "RESTORE" for r in c["history"])
    assert c["merge_metrics"]["num_source_rows"] == 100_000 and c["negative_scores"] == 0
    assert d["silver_rows"] < d["bronze_rows"] and d["dates"] >= 7 and d["models"] == 3
    assert d["gold_rows"] == d["dates"] * d["models"] and d["gold_metrics_verified"]
    assert e["pruning_ratio"] >= 5 and e["renamed_field_id"] == 4 and len(e["spec_ids"]) >= 2
    assert e["rows_after_evolution"] == 5500 and e["metadata_bytes"] > 0
    assert f["compaction_ratio"] >= 10 and f["skip_rate"] >= 0.5 and f["vacuum_reclaimed_bytes"] > 0
    assert f["delta_orphans_removed"] == 3 and f["delta_orphans_remaining"] == 0
    assert f["iceberg_snapshots_after"] == 3 and f["manifest_lists_swept"] == 17
    assert f["checkpoint"] and f["last_checkpoint"] and f["delta_rows"] == 100_000 and f["iceberg_rows"] == 2000
    assert g["amplification"] >= 5 and g["storage_ratio"] >= 3
    assert g["recall_at_10"] >= 0.8 and g["topic_fidelity"] >= 0.95
    assert g["top5_topics"].count(g["query_topic"]) >= 3
    assert g["in_table_hits"] == 0 < g["stale_index_hits"] and g["cdf_deletes"] == g["deleted_subject_docs"]
    assert len(h["trajectory_partitions"]) == h["gold_policies"] == 2
    assert h["training_steps"] == h["replay_steps"] < h["current_steps"]
    assert h["catalog_reads_for_5_turns"] == 1 and h["unconfirmed_result"] == "input_required" and h["task_status"] == "completed"
    assert len(h["provenance_partitions"]) == 5 and h["unclassified_rows"] > 0
    assert h["trainable_rows"] + h["unclassified_rows"] == 2000 and h["subject_rows_before"] > 0 == h["subject_rows_after"]
    for name in ["INFO.md", "AI_USAGE.md", "RESULTS.md", "requirements-lock.txt", "bonus/ARCHITECTURE.md", "bonus/ARCHITECTURE.pdf"]:
        assert (OUT / name).is_file(), name
    words = len((OUT / "REFLECTION.md").read_text(encoding="utf-8").split())
    assert words <= 200, words
    print(f"PASS all numeric rubric gates; reflection {words}/200 whitespace-separated words.")


if __name__ == "__main__":
    main()
