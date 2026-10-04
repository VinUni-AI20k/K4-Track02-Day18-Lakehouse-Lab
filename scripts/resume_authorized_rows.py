"""Resume only the three reviewed Delta row deletes; preserve physical files.

Requires direct user authorization in the conversation, plus the exact review
digest and confirmation phrase supplied at invocation. No reset, VACUUM,
expiry, file deletion or cleanup. Original notebooks are backed up; proposed
notebook updates are emitted as a targeted patch for review/application.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

import nbformat
from deltalake import DeltaTable

from prepare_remaining_review import REPO, DATA, DEST, fresh, git, scoped, write_new


def execute(shell, cell, count):
    from IPython.utils.capture import capture_output
    with capture_output() as captured:
        result = shell.run_cell(cell.source, store_history=False)
    cell.execution_count = count
    cell.outputs = []
    if captured.stdout:
        cell.outputs.append(nbformat.v4.new_output("stream", name="stdout", text=captured.stdout))
        print(captured.stdout, end="", flush=True)
    if captured.stderr:
        cell.outputs.append(nbformat.v4.new_output("stream", name="stderr", text=captured.stderr))
    for output in captured.outputs:
        cell.outputs.append(nbformat.v4.new_output("display_data", data=output.data, metadata=output.metadata))
    error = result.error_before_exec or result.error_in_exec
    if error:
        raise error


def resume(name, context, indices, replace=None):
    from IPython.core.interactiveshell import InteractiveShell
    target = scoped(DEST / "notebooks" / f"{name}.ipynb")
    original = target.read_text(encoding="utf-8")
    notebook = nbformat.reads(original, as_version=4)
    # Keep a byte-for-byte copy of all previous cells and outputs.
    backup = fresh(DEST / "history_20261004" / target.name)
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb") as f:
        f.write(target.read_bytes())
    shell = InteractiveShell()
    shell.user_ns.update({"__name__": "__main__"})
    count = max(c.execution_count or 0 for c in notebook.cells if c.cell_type == "code")
    setup_cell = nbformat.v4.new_code_cell(context)
    count += 1
    execute(shell, setup_cell, count)
    # Execute original assertions and deletion tails; no original PASS weakened.
    for index in indices:
        cell = notebook.cells[index]
        assert cell.cell_type == "code" and cell.execution_count is None
        if replace and index in replace:
            cell.source = replace[index](cell.source)
        count += 1
        execute(shell, cell, count)
    note = nbformat.v4.new_markdown_cell(
        "### Tiếp tục ngày 04/10/2026 sau xác nhận trực tiếp\n\n"
        "Đã kiểm tra lại danh sách row_deletions/version/doc_id. Chỉ xóa dòng trong version hiện tại; "
        "giữ file vật lý và version cũ. Cell sau phục hồi biến bằng cách đọc dữ liệu hiện có, "
        "không chạy lại reset hay ghi đè baseline. Output gốc được giữ trong history_20261004/. "
        "Kết quả mới và assertion gốc nằm trong các cell tiếp theo."
    )
    notebook.cells[indices[0]:indices[0]] = [note, setup_cell]
    # Supersede the old stop marker explicitly, retaining its historical text.
    for cell in notebook.cells:
        if cell.cell_type == "markdown" and cell.source.startswith("**DỪNG THEO CHÍNH SÁCH"):
            cell.source += "\n\n**Cập nhật 04/10/2026:** đã nhận xác nhận trực tiếp cho row_deletions; phần xóa dòng bên dưới đã chạy. Không bao gồm xóa file/expiry/VACUUM."
    notebook.metadata["lab_execution_status"] = "complete"
    notebook.metadata["lab_resume_date"] = "2026-10-04"
    nbformat.validate(notebook)
    revised = nbformat.writes(notebook)
    write_new(DEST / "revisions_20261004" / target.name, revised)
    changes = list(difflib.unified_diff(original.splitlines(), revised.splitlines(), n=3))[2:]
    # apply_patch accepts contextual hunks without numeric line offsets.
    changes = ["@@" if line.startswith("@@") else line for line in changes]
    patch = "*** Update File: " + str(target) + "\n" + "\n".join(changes) + "\n"
    write_new(DEST / "logs" / f"{name}_resumed_20261004.txt", "\n\n".join(
        o.get("text", "") for c in notebook.cells if c.cell_type == "code"
        for o in c.outputs if o.output_type == "stream"))
    return patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != "TÔI XÁC NHẬN THAO TÁC PHÁ HỦY NÀY":
        raise RuntimeError("Exact confirmation phrase required")
    review_path = scoped(DEST / "REVIEW_20261004.json")
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == args.review_sha256
    review = json.loads(review_path.read_text(encoding="utf-8"))
    expected = [(DATA / "scratch" / "docs_intable", "user_042"),
                (DATA / "scratch" / "docs_cdf", "user_042"),
                (DATA / "silver" / "training_corpus_governed", "user_007")]
    physical_before = {}
    initial_status = git("status", "--porcelain=v1", "--untracked-files=all")
    for record, (p, subject) in zip(review["row_deletions"], expected, strict=True):
        assert scoped(record["table"]) == scoped(p)
        assert record["predicate"] == f"subject_id = '{subject}'"
        t = DeltaTable(str(p))
        assert t.version() == record["version"] == 0
        rows = t.to_pyarrow_table(filters=[("subject_id", "=", subject)])
        assert rows.num_rows == record["count"] == 8
        assert sorted(rows.column("doc_id").to_pylist()) == sorted(record["doc_ids"])
        physical_before[str(p)] = {str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                                   for f in p.rglob("*.parquet")}
    runtime = fresh(DATA / "resume_rows_20261004")
    for name in ("07_vectors_multimodal", "08_agents_provenance"):
        fresh(DEST / "history_20261004" / f"{name}.ipynb")
        fresh(DEST / "revisions_20261004" / f"{name}.ipynb")
        fresh(DEST / "logs" / f"{name}_resumed_20261004.txt")
    fresh(DEST / "logs" / "row_deletions_20261004.json")
    runtime.mkdir()
    write_new(runtime / "physical_preflight.json", json.dumps(physical_before, indent=2) + "\n")
    os.environ["IPYTHONDIR"] = str(runtime / "ipython")
    os.environ["LAKEHOUSE_ROOT"] = str(DATA)
    sys.path.insert(0, str(REPO / "scripts"))
    nb7 = nbformat.read(DEST / "notebooks" / "07_vectors_multimodal.ipynb", as_version=4)
    context7 = '''import time
from pathlib import Path
import duckdb
import numpy as np
import pyarrow.parquet as pq
from deltalake import DeltaTable
from lakehouse import ROOT, du, human
DOCS = str(ROOT / "bronze" / "docs_multimodal")
docs = DeltaTable(DOCS).to_pyarrow_table()
emb = np.array(docs.column("emb").to_pylist(), dtype="float32")
n, dim = emb.shape
SCALE = 127.0
emb_i8 = np.clip(np.round(emb * SCALE), -127, 127).astype("int8")
INLINE = str(ROOT / "scratch" / "media_inline")
F32 = str(ROOT / "scratch" / "emb_f32")
I8 = str(ROOT / "scratch" / "emb_int8")
EXTERNAL = str(ROOT / "scratch" / "vector_index_external")
INTABLE = str(ROOT / "scratch" / "docs_intable")
blobs = [next((ROOT / "blobs").glob("*.bin")).read_bytes()]
SUBJECT = "user_042"
dt = DeltaTable(INTABLE)
victim_ids = docs.filter(__import__("pyarrow.compute", fromlist=["equal"]).equal(docs["subject_id"], SUBJECT))["doc_id"].to_pylist()
'''
    context7 += "\n" + "\n\n".join(nb7.cells[i].source for i in [8, 12, 18])
    def cdf_tail(source):
        marker = 'DeltaTable(CDF_TABLE).delete('
        assert source.count(marker) == 1
        return ('# Baseline CDF was created by prepare_remaining_review.py; preserve it.\n'
                'CDF_TABLE = str(ROOT / "scratch" / "docs_cdf")\n' + source[source.index(marker):])
    patch7 = resume("07_vectors_multimodal", context7, [24, 26, 28, 30], {28: cdf_tail})
    nb8 = nbformat.read(DEST / "notebooks" / "08_agents_provenance.ipynb", as_version=4)
    pin_output = "".join(o.get("text", "") for o in nb8.cells[7].outputs if o.output_type == "stream")
    training_run, _ = json.JSONDecoder().raw_decode(pin_output.lstrip())
    context8 = '''import json
import time
from pathlib import Path
import duckdb
import polars as pl
from deltalake import DeltaTable
from lakehouse import ROOT, catalog, to_arrow
SILVER = str(ROOT / "silver" / "agent_trajectories")
GOLD = str(ROOT / "gold" / "agent_performance")
DOCS = str(ROOT / "bronze" / "docs_multimodal")
GOVERNED = str(ROOT / "silver" / "training_corpus_governed")
gold = DeltaTable(GOLD).to_pyarrow_table()
con = duckdb.connect()
cat = catalog("nb8")
ns = "lake"
'''
    context8 += "\ntraining_run = " + repr(training_run) + "\n"
    context8 += 'pinned = DeltaTable(SILVER, version=training_run["table_version"])\n'
    context8 += "\n\n".join(nb8.cells[i].source for i in [10, 12, 14, 16, 18, 20])
    context8 += '''
parts = sorted(p.name for p in Path(GOVERNED).glob("provenance_bucket=*"))
corpus_version = DeltaTable(GOVERNED).version()
con.register("governed", DeltaTable(GOVERNED).to_pyarrow_table())
SUBJECT = "user_007"
before = con.sql("SELECT count(*) FROM governed WHERE subject_id = 'user_007'").fetchone()[0]
dt = DeltaTable(GOVERNED)
'''
    patch8 = resume("08_agents_provenance", context8, [28, 30])
    final = []
    for record in review["row_deletions"]:
        p = Path(record["table"])
        t = DeltaTable(str(p))
        subject = record["predicate"].split("'")[1]
        after = sum(row["subject_id"] == subject for row in t.to_pyarrow_table().to_pylist())
        assert after == 0 and t.version() == record["version"] + 1
        old_count = sum(row["subject_id"] == subject for row in
                        DeltaTable(str(p), version=record["version"]).to_pyarrow_table().to_pylist())
        assert old_count == record["count"]
        for file_path, digest in physical_before[str(p)].items():
            assert hashlib.sha256(Path(file_path).read_bytes()).hexdigest() == digest
        final.append({"table": str(p), "predicate": record["predicate"],
                      "before": record["count"], "after": after,
                      "before_version": record["version"], "after_version": t.version(),
                      "old_version_subject_rows": old_count, "original_parquet_files_preserved": True})
    write_new(runtime / "notebook_updates.patch", "*** Begin Patch\n" + patch7 + patch8 + "*** End Patch\n")
    write_new(DEST / "logs" / "row_deletions_20261004.json", json.dumps(
        {"review_sha256": args.review_sha256, "authorization_scope": "row_deletions ONLY",
         "initial_git_status": initial_status, "results": final,
         "NB7_original_assertions": "PASS", "NB8_original_assertions": "PASS",
         "physical_file_deletion": False, "vacuum": False, "expiry": False}, ensure_ascii=False, indent=2) + "\n")
    print("Original NB7/NB8 assertions passed; physical files and prior versions preserved.")


if __name__ == "__main__":
    main()
