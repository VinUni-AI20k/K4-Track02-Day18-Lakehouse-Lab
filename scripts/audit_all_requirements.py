"""Read-only live validation for the rubric; prints results, writes no data."""
import ast
import json
from pathlib import Path
import sqlite3

import duckdb
import nbformat
import pyarrow as pa
from deltalake import DeltaTable
from pyiceberg.table import StaticTable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_lakehouse"


def delta(relative, version=None):
    return DeltaTable(str(DATA / relative), version=version)


def iceberg(catalog, name):
    db = DATA / "iceberg" / catalog / "catalog.db"
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
        metadata = con.execute("SELECT metadata_location FROM iceberg_tables WHERE table_name=?", (name,)).fetchone()[0]
    return StaticTable.from_metadata(metadata)


def main():
    results = {}
    users = delta("scratch/users_delta").to_pyarrow_table().to_pylist()
    results["NB1"] = {"rows": len(users), "tier_groups": sorted({str(r["tier"]) for r in users}),
                      "json_commits": len(list((DATA / "scratch/users_delta/_delta_log").glob("*.json")))}
    assert len(users) == 4 and results["NB1"]["json_commits"] >= 2
    assert {r["tier"] for r in users} == {None, "premium"}
    events = delta("scratch/events_smallfiles")
    actions = pa.table(events.get_add_actions(flatten=True)).to_pylist()
    touched = sum(r["min.user_id"] <= 4242 <= r["max.user_id"] for r in actions)
    results["NB2"] = {"current_files": len(events.file_uris()), "files_containing_target": touched,
                      "pruning_ratio": len(events.file_uris()) / touched}
    assert results["NB2"]["pruning_ratio"] >= 10
    customers = delta("scratch/customers_tt")
    results["NB3"] = {"history": [(r["version"], r["operation"]) for r in customers.history()],
                      "negative_scores": sum(r["score"] < 0 for r in customers.to_pyarrow_table().to_pylist())}
    assert len(results["NB3"]["history"]) >= 5 and results["NB3"]["negative_scores"] == 0
    assert {"MERGE", "RESTORE"}.issubset({op for _, op in results["NB3"]["history"]})
    con = duckdb.connect()
    con.register("gold", delta("gold/llm_daily_metrics").to_pyarrow_table())
    con.register("silver", delta("silver/llm_calls").to_pyarrow_table())
    metrics = con.sql("SELECT count(*),count(DISTINCT date),count(DISTINCT model),bool_and(p50_latency_ms<=p95_latency_ms AND cost_usd>0 AND error_rate BETWEEN 0 AND 1) FROM gold").fetchone()
    nb4_source = (ROOT / "notebooks/04_medallion.py").read_text(encoding="utf-8")
    tree = ast.parse(nb4_source)
    cost = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COST_TABLE" for t in n.targets)))
    query_ast = next(n.args[0] for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "sql" and n.args and isinstance(n.args[0], ast.JoinedStr) and "WITH cost" in ast.get_source_segment(nb4_source, n.args[0]))
    query = eval(compile(ast.Expression(query_ast), "<gold SQL string>", "eval"), {"COST_TABLE": cost})
    recomputed = con.sql(query).fetchall()
    stored = con.sql("SELECT * FROM gold ORDER BY date,model").fetchall()
    assert len(recomputed) == len(stored) == 24
    for expected, actual in zip(recomputed, stored):
        assert expected[:2] == actual[:2]
        assert all(abs(float(x) - float(y)) < 1e-8 for x, y in zip(expected[2:], actual[2:]))
    results["NB4"] = {"bronze_rows": delta("bronze/llm_calls_raw").count(),
                      "silver_rows": delta("silver/llm_calls").count(),
                      "gold_rows": metrics[0], "dates": metrics[1], "models": metrics[2],
                      "metric_ranges_valid": metrics[3], "all_gold_metrics_recomputed_match": True,
                      "silver_request_ids_unique": con.sql("SELECT count(*)=count(DISTINCT request_id) FROM silver").fetchone()[0],
                      "every_date_has_three_models": con.sql("SELECT bool_and(n=3) FROM (SELECT date,count(DISTINCT model) n FROM gold GROUP BY date)").fetchone()[0]}
    assert metrics[1] >= 7 and metrics[2] == 3 and metrics[3]
    assert results["NB4"]["silver_rows"] < results["NB4"]["bronze_rows"]
    assert results["NB4"]["silver_request_ids_unique"] and results["NB4"]["every_date_has_three_models"]
    table = iceberg("nb5", "llm_events")
    full = len(list(table.scan().plan_files()))
    one = len(list(table.scan(row_filter="ts >= '2026-08-05T00:00:00' and ts < '2026-08-06T00:00:00'").plan_files()))
    results["NB5"] = {"rows": table.scan().to_arrow().num_rows,
                      "latency_field_id": table.schema().find_field("latency_millis").field_id,
                      "specs_in_use": sorted(set(table.inspect.files()["spec_id"].to_pylist())),
                      "current_full_scan_files": full, "current_one_day_files": one,
                      "current_pruning_ratio": full / one}
    assert results["NB5"]["rows"] == 5500 and results["NB5"]["latency_field_id"] == 4
    assert len(results["NB5"]["specs_in_use"]) >= 2 and full / one >= 5
    maintenance = iceberg("nb6", "maint")
    results["NB6"] = {"delta_rows": delta("scratch/maint_events").count(), "snapshots": len(maintenance.snapshots()), "iceberg_rows": maintenance.scan().to_arrow().num_rows}
    assert results["NB6"] == {"delta_rows": 100000, "snapshots": 3, "iceberg_rows": 2000}
    for relative, subject in [("scratch/docs_intable", "user_042"), ("silver/training_corpus_governed", "user_007")]:
        current = sum(r["subject_id"] == subject for r in delta(relative).to_pyarrow_table().to_pylist())
        old = sum(r["subject_id"] == subject for r in delta(relative, 0).to_pyarrow_table().to_pylist())
        assert current == 0 and old == 8
        results[relative] = {"current_subject_rows": current, "version_0_subject_rows": old}
    results["NB8"] = {"pinned_steps": delta("silver/agent_trajectories", 0).count(),
                      "current_steps": delta("silver/agent_trajectories").count(),
                      "gold_policies": delta("gold/agent_performance").count(),
                      "silver_partitions": sorted(p.name for p in (DATA / "silver/agent_trajectories").glob("agent_version=*")),
                      "provenance_partitions": sorted(p.name for p in (DATA / "silver/training_corpus_governed").glob("provenance_bucket=*"))}
    assert results["NB8"]["pinned_steps"] == 1578 and results["NB8"]["gold_policies"] == 2
    assert len(results["NB8"]["silver_partitions"]) == 2 and len(results["NB8"]["provenance_partitions"]) == 5
    results["notebook_execution"] = []
    for path in sorted((ROOT / "submission/notebooks").glob("*.ipynb")):
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        code = [c for c in nb.cells if c.cell_type == "code"]
        assert not any(o.output_type == "error" for c in code for o in c.outputs)
        unexecuted = sum(c.execution_count is None for c in code)
        counts = [c.execution_count for c in code if c.execution_count is not None]
        results["notebook_execution"].append({"name": path.name, "unexecuted_code_cells": unexecuted,
                                              "counts_increasing_in_cell_order": all(a < b for a, b in zip(counts, counts[1:])),
                                              "status": nb.metadata["lab_execution_status"]})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
