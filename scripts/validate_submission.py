"""Validate preserved outputs and the original rubric thresholds offline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import nbformat
import jupytext

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"


def main() -> None:
    metrics = json.loads((OUT / "evidence/metrics.json").read_text(encoding="utf-8"))
    notebooks = sorted((OUT / "notebooks").glob("[0-9]*.ipynb"))
    assert len(notebooks) == len(metrics) == 8
    manifest = {}
    report = []
    for source in sorted((ROOT / "notebooks").glob("[0-9]*.py")):
        file = OUT / "notebooks" / (source.stem + ".ipynb")
        nb = nbformat.read(file, as_version=4)
        nbformat.validate(nb)
        code_cells = [c for c in nb.cells if c.cell_type == "code" and c.source.strip()]
        source_cells = [c.source for c in jupytext.read(source).cells if c.cell_type == "code" and c.source.strip()]
        assert [c.source for c in code_cells[1:-1]] == source_cells, f"Source/output mismatch: {file.name}"
        assert [c.execution_count for c in code_cells] == list(range(1, len(code_cells) + 1)), file.name
        assert not any(o.output_type == "error" for c in code_cells for o in c.outputs), file.name
        stdout = "\n".join(o.get("text", "") for c in code_cells for o in c.outputs if o.output_type == "stream")
        assert "[FAIL]" not in stdout, file.name
        assert "Giải thích kết quả" in nb.cells[-1].source
        encoded = next(line.split("=", 1)[1] for line in stdout.splitlines() if line.startswith("LAB_METRICS_JSON="))
        assert json.loads(encoded) == metrics[source.name[:2]]
        # Code cells contain execution timestamps supplied by nbclient.
        assert all("iopub.status.idle" in c.metadata.get("execution", {}) for c in code_cells)
        picture = OUT / "screenshots" / (source.stem + ".png")
        content = picture.read_bytes()
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", content[16:24])
        assert width >= 1000 and height > 150
        for artifact in (file, picture):
            manifest[str(artifact.relative_to(OUT))] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        report.append(f"PASS {file.name}: {len(code_cells)} executed cells, no error outputs; PNG {width}x{height}")

    a, b, c, d, e, f, g, h = (metrics[f"{i:02d}"] for i in range(1, 9))
    assert a["json_commits"] >= 2 and a["schema_enforcement_blocked"] and a["failed_write_version_unchanged"] and a["tier_present"] and a["tier_groups"] == 2
    assert b["files_before"] >= 100 and b["files_after"] < b["files_before"] and (b["speedup"] >= 3 or b["pruning_ratio"] >= 10)
    assert c["history_versions"] >= 5 and "RESTORE" in c["history_operations"] and c["merge_source_rows"] == 100000 and c["bad_rows_after_restore"] == 0
    assert d["silver_rows"] < d["bronze_rows"] and d["gold_dates"] >= 7 and d["gold_models"] == 3 and d["gold_rows"] == d["gold_dates"] * 3 and d["gold_values_correct"]
    assert e["pruning_ratio"] >= 5 and e["latency_field_id"] == 4 and len(e["spec_ids"]) >= 2 and e["rows_readable"] == 5500
    assert f["compaction_ratio"] >= 10 and f["cluster_skip_rate"] >= 0.5 and f["vacuum_reclaimed_bytes"] > 0 and f["delta_orphans_removed"] == 3
    assert f["iceberg_snapshots_after"] == 3 and f["iceberg_manifest_lists_swept"] > 0 and f["checkpoint_written"] and f["delta_rows"] == 100000 and f["iceberg_rows"] == 2000
    assert g["amplification"] >= 5 and g["storage_ratio"] >= 3 and g["recall_at_10"] >= 0.8 and g["topic_fidelity"] >= 0.95
    assert g["top5_topics"].count(g["query_topic"]) >= 3 and g["deleted_in_table_hits"] == 0 and g["stale_external_hits"] > 0 and g["cdf_deletes"] == g["stale_external_hits"]
    assert len(h["agent_partitions"]) == 2 and h["gold_policies"] == 2 and h["recorded_steps"] == h["replayed_steps"]
    assert h["catalog_reads_for_5_turns"] == 1 and h["unconfirmed_result"] == "input_required" and h["task_status"] == "completed"
    assert len(h["provenance_partitions"]) == 5 and h["trainable_rows"] == h["corpus_rows"] - h["unclassified_rows"] and h["subject_rows_before"] > 0 and h["subject_rows_after"] == 0
    reflection = (OUT / "REFLECTION.md").read_text(encoding="utf-8")
    words = len(reflection.split())
    assert words <= 200, words
    report.extend(["PASS all numeric rubric thresholds", f"PASS reflection: {words} whitespace-separated words (<= 200)"])
    (OUT / "evidence/artifact-sha256.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = "\n".join(report) + "\n"
    (OUT / "evidence/submission-validation.log").write_text(result, encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
