"""Recover saved NB7/NB8 outputs and verify completed row deletes; no deletes."""
import difflib
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

import nbformat
import pyarrow as pa
from deltalake import DeltaTable

from prepare_remaining_review import DATA, DEST, fresh, scoped, write_new


def main():
    review_path = DEST / "REVIEW_20261004.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    patch_path = fresh(DATA / "resume_rows_20261004" / "notebook_updates.patch")
    log_path = fresh(DEST / "logs" / "row_deletions_20261004.json")
    results = []
    for record in review["row_deletions"]:
        p = scoped(record["table"])
        subject = record["predicate"].split("'")[1]
        current = DeltaTable(str(p))
        old = DeltaTable(str(p), version=record["version"])
        old_rows = old.to_pyarrow_table().to_pylist()
        rows = current.to_pyarrow_table().to_pylist()
        before_ids = sorted(r["doc_id"] for r in old_rows if r["subject_id"] == subject)
        after_ids = [r["doc_id"] for r in rows if r["subject_id"] == subject]
        assert current.version() == record["version"] + 1 == 1
        assert before_ids == sorted(record["doc_ids"]) and len(before_ids) == 8
        assert after_ids == [] and len(old_rows) == 2000 and len(rows) == 1992
        old_files = [scoped(unquote(f.replace("file://", ""))) for f in old.file_uris()]
        assert all(f.is_file() for f in old_files)
        results.append({"table": str(p), "predicate": record["predicate"],
                        "before": 8, "after": 0, "before_version": 0, "after_version": 1,
                        "prior_version_rows": len(old_rows), "current_rows": len(rows),
                        "all_prior_version_files_present": True,
                        "prior_files_current_sha256": {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in old_files}})
    cdf = DeltaTable(str(DATA / "scratch" / "docs_cdf")).load_cdf(starting_version=1).read_all()
    events = [r for r in pa.table(cdf).to_pylist() if r["_change_type"] == "delete"]
    assert len(events) == 8
    assert sorted(r["doc_id"] for r in events) == sorted(review["row_deletions"][1]["doc_ids"])
    ext = DeltaTable(str(DATA / "scratch" / "vector_index_external")).to_pyarrow_table()
    victim_ids = set(review["row_deletions"][0]["doc_ids"])
    ex_hits = sum(doc_id in victim_ids for doc_id in ext["doc_id"].to_pylist())
    assert ex_hits == 8
    patches = []
    for name, number in [("07_vectors_multimodal", 7), ("08_agents_provenance", 8)]:
        target = scoped(DEST / "notebooks" / f"{name}.ipynb")
        backup = scoped(DEST / "history_20261004" / target.name)
        revision = scoped(DEST / "revisions_20261004" / target.name)
        assert target.read_bytes() == backup.read_bytes(), "Original notebook changed; stop before patch"
        nb = nbformat.read(revision, as_version=4)
        nbformat.validate(nb)
        assert nb.metadata["lab_execution_status"] == "complete"
        assert any(f"NB{number} complete." in o.get("text", "") for c in nb.cells
                   if c.cell_type == "code" for o in c.outputs)
        assert not any(o.output_type == "error" for c in nb.cells if c.cell_type == "code" for o in c.outputs)
        changes = list(difflib.unified_diff(target.read_text(encoding="utf-8").splitlines(),
                                           revision.read_text(encoding="utf-8").splitlines(), n=3))[2:]
        changes = ["@@" if line.startswith("@@") else line for line in changes]
        patches.append("*** Update File: " + str(target) + "\n" + "\n".join(changes) + "\n")
    write_new(patch_path, "*** Begin Patch\n" + "".join(patches) + "*** End Patch\n")
    result = {"review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
              "authorization_scope": "row_deletions ONLY", "results": results,
              "NB7_original_assertions": "PASS", "NB8_original_assertions": "PASS",
              "NB7_current_table_hits": 0, "NB7_stale_external_index_hits": ex_hits,
              "cdf_delete_events": len(events), "physical_file_deletion": False,
              "vacuum": False, "expiry": False,
              "recovery_note": "Resume finished all deletions and assertions; final Arrow filter audit hit string/string_view incompatibility. This read-only recovery read whole tables and verified current/prior versions. No deletion rerun."}
    write_new(log_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Verified: NB7 0/8 hits, CDF 8 deletes; NB8 8 -> 0; original assertions PASS; prior versions have all 2000 rows.")


if __name__ == "__main__":
    main()
