"""Verify prepared targets, URI handling and submission without changing data."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time
from urllib.parse import unquote
import xml.etree.ElementTree as ET

import nbformat
from deltalake import DeltaTable

from prepare_remaining_review import REPO, DATA, DEST, scoped


def main():
    review = json.loads((DEST / "REVIEW_20261004.json").read_text(encoding="utf-8"))
    file_records = (review["vacuum"]["files"] + review["delta_orphans"]
                    + review["iceberg"]["manifest_lists_after_proposed_expiry"]
                    + [review["iceberg"]["metadata_to_retain"]])
    nb6_done = (DEST / "logs" / "nb6_completed_20261004.json").exists()
    if nb6_done:
        completed = json.loads((DEST / "logs" / "nb6_completed_20261004.json").read_text(encoding="utf-8"))
        assert len(completed["checks"]) == 9 and all(completed["checks"].values())
        assert completed["vacuum_net_reclaimed_bytes"] > 0
        assert all(not scoped(r["path"]).exists() for r in file_records[:-1])
        preflight = json.loads((DATA / "resume_nb6_20261004" / "preflight.json").read_text(encoding="utf-8"))
        for p, sha in preflight["active_file_hashes"].items():
            assert hashlib.sha256(scoped(p).read_bytes()).hexdigest() == sha
        assert DeltaTable(review["vacuum"]["table"]).count() == 100000
    for record in (file_records[-1:] if nb6_done else file_records):
        p = scoped(record["path"])
        assert p.stat().st_size == record["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == record["sha256"], p
    for record in review["row_deletions"]:
        table = DeltaTable(str(scoped(record["table"])))
        subject = record["predicate"].split("'")[1]
        baseline = DeltaTable(record["table"], version=record["version"]).to_pyarrow_table().to_pylist()
        assert sorted(r["doc_id"] for r in baseline if r["subject_id"] == subject) == sorted(record["doc_ids"])
        if (DEST / "logs" / "row_deletions_20261004.json").exists():
            assert table.version() == record["version"] + 1
            assert not any(r["subject_id"] == subject for r in table.to_pyarrow_table().to_pylist())
        else:
            assert table.version() == record["version"]
    # Exercise the exact corrected function without executing the notebook.
    source = (REPO / "notebooks" / "06_maintenance.py").read_text(encoding="utf-8")
    function = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "find_orphans")
    context = dict(os=os, time=time, Path=Path, DeltaTable=DeltaTable, unquote=unquote)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<NB6 find_orphans>", "exec"), context)
    orphans = {scoped(p) for p in context["find_orphans"](review["vacuum"]["table"])}
    expected = set() if nb6_done else {scoped(r["path"]) for r in review["delta_orphans"]}
    assert orphans == expected, (orphans, expected)
    notebooks = []
    for p in sorted((DEST / "notebooks").glob("*.ipynb")):
        nb = nbformat.read(p, as_version=4)
        nbformat.validate(nb)
        assert not any(o.output_type == "error" for c in nb.cells
                       if c.cell_type == "code" for o in c.outputs)
        if p.name.startswith(("07_", "08_")) and (DEST / "logs" / "row_deletions_20261004.json").exists():
            original = nbformat.read(DEST / "history_20261004" / p.name, as_version=4)
            assertion_source = original.cells[30].source
            assertion = next(c for c in nb.cells if c.cell_type == "code" and c.source == assertion_source)
            output = "".join(o.get("text", "") for o in assertion.outputs)
            assert "[FAIL]" not in output
            assert output.count("[PASS]") == (7 if p.name.startswith("07_") else 10)
            assert nb.metadata["lab_execution_status"] == "complete"
        if p.name.startswith("06_") and nb6_done:
            original = nbformat.read(DEST / "history_nb6_20261004" / p.name, as_version=4)
            assertion = next(c for c in nb.cells if c.cell_type == "code" and c.source == original.cells[33].source)
            output = "".join(o.get("text", "") for o in assertion.outputs)
            assert output.count("[PASS]") == 9 and "[FAIL]" not in output
            assert nb.metadata["lab_execution_status"] == "complete"
        notebooks.append({"name": p.name, "status": nb.metadata["lab_execution_status"]})
    assert len(notebooks) == 8
    screenshots = list((DEST / "screenshots").glob("*.png"))
    for p in screenshots:
        data = p.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert all(n > 0 for n in struct.unpack(">II", data[16:24]))
    assert all(any(p.name.startswith(f"nb{i:02d}_") for p in screenshots) for i in range(1, 9))
    words = len((DEST / "REFLECTION.md").read_text(encoding="utf-8").split())
    assert words <= 200
    info = (DEST / "INFO.md").read_text(encoding="utf-8")
    assert "Dương Xuân Vinh" in info and "2A202602622" in info and "suy ra" not in info
    junit = ET.parse(DEST / "logs" / "pytest_safe_20261004.xml")
    suites = list(junit.getroot().iter("testsuite"))
    assert sum(int(s.get("tests", 0)) for s in suites) == 20
    assert all(s.get("failures") == "0" and s.get("errors") == "0" for s in suites)
    patterns = re.compile(r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}|sk-proj-[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")
    for p in DEST.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".json", ".ipynb", ".txt", ".html", ".xml"}:
            assert not patterns.search(p.read_text(encoding="utf-8")), f"Credential-like pattern in {p}"
    print(json.dumps({"target_file_hashes_verified": 1 if nb6_done else len(file_records),
                      "reviewed_deleted_files_verified_absent": 231 if nb6_done else 0,
                      "NB6_original_assertions_preserved_and_passed": nb6_done,
                      "row_target_lists_verified": len(review["row_deletions"]),
                      "corrected_find_orphans_exact_count": len(orphans),
                      "active_data_files_misidentified_as_orphan": 0,
                      "notebooks": notebooks, "screenshots": len(screenshots),
                      "reflection_words": words, "identity_confirmed": True,
                      "pytest_safe_passed": 20, "pytest_destructive_not_run": 4,
                      "NB7_NB8_original_assertions_preserved_and_passed": (DEST / "logs" / "row_deletions_20261004.json").exists(),
                      "credential_pattern_findings": [], "credential_scan_is_exhaustive": False,
                      "ready_to_submit": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
