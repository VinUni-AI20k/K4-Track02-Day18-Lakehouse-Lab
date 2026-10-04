"""Prepare isolated validation; execute destructive lab checks only after approval.

Original smoke, all pytest tests, original runner, then real Jupyter execution.
No existing lab data is reset. Each phase has a separate new data root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "_lakehouse" / "validation_ready_20261004"
OUTPUT = REPO / "submission" / "validation_20261004"
REVIEW = REPO / "submission" / "VALIDATION_REVIEW_20261004.json"


def scoped(value):
    p = Path(value)
    resolved = p.resolve()
    if not resolved.is_relative_to(REPO) or resolved == REPO:
        raise RuntimeError(f"Outside workspace: {p}")
    for ancestor in [p, *p.parents]:
        if ancestor == REPO.parent:
            break
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise RuntimeError(f"Reparse point: {ancestor}")
    return resolved


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_new(p, data):
    p = scoped(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as handle:
        handle.write(data)


def environment(root):
    return dict(os.environ, LAKEHOUSE_ROOT=str(scoped(root)), PYTHONUTF8="1",
                PYTHONDONTWRITEBYTECODE="1", IPYTHONDIR=str(BASE / "runtime" / "ipython"),
                JUPYTER_RUNTIME_DIR=str(BASE / "runtime" / "jupyter"),
                JUPYTER_CONFIG_DIR=str(BASE / "runtime" / "config"),
                JUPYTER_DATA_DIR=str(BASE / "runtime" / "data"),
                JUPYTER_PATH=str(BASE / "runtime" / "data"),
                TEMP=str(BASE / "runtime" / "temp"), TMP=str(BASE / "runtime" / "temp"))


def command(label, args, root):
    print(f"START {label}", flush=True)
    proc = subprocess.run([sys.executable, *args], cwd=REPO,
                          env=environment(root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    write_new(OUTPUT / f"{label}.txt", proc.stdout + "\n" + proc.stderr)
    print(f"END {label}: exit={proc.returncode}", flush=True)
    if proc.returncode:
        raise RuntimeError(f"{label} failed; see {OUTPUT / (label + '.txt')}")
    return proc.stdout


def prepare():
    for target in (BASE, OUTPUT, REVIEW):
        if scoped(target).exists():
            raise RuntimeError(f"Preserving existing path: {target}")
    for target in (BASE / "runner", BASE / "notebooks", BASE / "smoke",
                   *[BASE / "runtime" / p for p in ("temp", "jupyter", "config", "data", "ipython")]):
        scoped(target).mkdir(parents=True, exist_ok=False)
    OUTPUT.mkdir()
    # All generator targets are absent; their reset() calls are no-ops.
    for phase in ("runner", "notebooks"):
        command(f"prepare_{phase}_data", ["scripts/generate_data_lite.py"], BASE / phase)
        command(f"prepare_{phase}_ai", ["scripts/generate_ai_data.py"], BASE / phase)
    kernel = BASE / "runtime" / "data" / "kernels" / "lab-venv" / "kernel.json"
    write_new(kernel, json.dumps({"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                                 "display_name": "Lakehouse lab .venv", "language": "python"}, indent=2))
    sources = [*sorted((REPO / "notebooks").glob("*.py")),
               *[REPO / "scripts" / p for p in ("lakehouse.py", "run_all.py", "verify_lite.py",
                                                 "generate_data_lite.py", "generate_ai_data.py")],
               REPO / "tests" / "test_lab18.py", REPO / "pytest.ini", Path(__file__).resolve()]
    review = {
        "scope": "ONLY newly generated synthetic validation data; preserve all existing lab/evidence",
        "workspace": str(REPO),
        "required_explicit_protection_exception": "Allow recursive reset/cleanup, permanent deletion of ignored/untracked synthetic files, snapshot expiry, VACUUM and scoped replacement of generated metadata ONLY inside the four exact directory targets below, including synthetic files created during this validation. Never delete these parent targets wholesale.",
        "directory_targets": [{"canonical_path": str(scoped(BASE / p)), "tracked": False,
                                "ignored": True, "preexisting_user_data": False,
                                "effect": effect} for p, effect in (
            ("smoke", "Original verify_lite: delete id<5, reset smoke catalog, remove _smoke_delta/_smoke_cdf"),
            ("pytest", "All 24 original tests: id<3 deletion, expiry to 2 snapshots, reset nb6/drop catalog; fresh --basetemp; no test deselection"),
            ("runner", "Original run_all: table/catalog resets if present; NB6 VACUUM, 3 orphan removals, expiry to 3 snapshots, manifest sweep, checkpoint; NB7 user_042 and NB8 user_007 deletes"),
            ("notebooks", "Real Jupyter sequential execution of all 8 source notebooks with identical lab mutations; save new outputs separately"))],
        "initial_file_targets": [{"canonical_path": str(scoped(p)), "sha256": digest(p),
                                  "bytes": p.stat().st_size, "tracked": False, "ignored": True,
                                  "recovery": "Synthetic, reproducible from original generators; old _lakehouse remains unchanged"}
                                 for phase in ("runner", "notebooks", "smoke")
                                 for p in sorted((BASE / phase).rglob("*")) if p.is_file()],
        "source_hashes": {str(p.relative_to(REPO)): digest(p) for p in sources},
        "non_destructive_alternative": "Keep current partial 8/9 smoke, 20/24 pytest and separate assertion evidence; does not satisfy full reproducibility rubric.",
        "preserved": [str(REPO / "_lakehouse" / p) for p in ("bronze", "silver", "gold", "scratch", "iceberg")]
                     + [str(REPO / "submission" / p) for p in ("notebooks", "logs", "screenshots")],
        "authorization_status": "PENDING direct user confirmation; prepare does not run destructive checks",
    }
    write_new(REVIEW, json.dumps(review, ensure_ascii=False, indent=2))
    print(f"Prepared {len(review['initial_file_targets'])} files. Review SHA256: {digest(REVIEW)}", flush=True)


def execute(review_sha):
    if digest(REVIEW) != review_sha:
        raise RuntimeError("Approved review changed")
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    for source, sha in review["source_hashes"].items():
        if digest(scoped(REPO / source)) != sha:
            raise RuntimeError(f"Source changed: {source}")
    for entry in review["initial_file_targets"]:
        if digest(scoped(entry["canonical_path"])) != entry["sha256"]:
            raise RuntimeError(f"Prepared data changed: {entry['canonical_path']}")
    for phase in ("runner", "notebooks", "smoke"):
        expected = {e["canonical_path"] for e in review["initial_file_targets"]
                    if Path(e["canonical_path"]).is_relative_to(BASE / phase)}
        actual = {str(scoped(p)) for p in (BASE / phase).rglob("*") if p.is_file()}
        if actual != expected:
            raise RuntimeError(f"Target set changed: {phase}")
    if (BASE / "pytest").exists():
        raise RuntimeError("Pytest basetemp must be new; refusing pytest's existing-directory cleanup")
    smoke = command("smoke_full", ["scripts/verify_lite.py"], BASE / "smoke")
    assert smoke.count("✓") == 9
    command("pytest_full", ["-m", "pytest", "--basetemp", str(BASE / "pytest"),
                            "-p", "no:cacheprovider", "--junitxml", str(OUTPUT / "pytest_full.xml")], BASE / "pytest")
    import xml.etree.ElementTree as ET
    suite = ET.parse(OUTPUT / "pytest_full.xml").getroot().find("testsuite")
    assert suite is not None and int(suite.attrib["tests"]) == 24
    assert all(int(suite.attrib[k]) == 0 for k in ("failures", "errors", "skipped"))
    runner = command("runner_full", ["scripts/run_all.py"], BASE / "runner")
    assert "8/8 passed" in runner
    command("jupyter_sequential", [str(Path(__file__).resolve()), "--jupyter-child"], BASE / "notebooks")
    write_new(OUTPUT / "results.json", json.dumps({"smoke": "9/9", "pytest": "24/24",
                "runner": "8/8", "jupyter": "8/8 sequential", "review_sha256": review_sha,
                "data_scope": review["directory_targets"]}, ensure_ascii=False, indent=2))


def jupyter():
    import jupytext
    import nbformat
    from nbclient import NotebookClient
    sys.path.insert(0, str(REPO / "notebooks"))
    for source in sorted((REPO / "notebooks").glob("[0-9]*.py")):
        destination = scoped(OUTPUT / "notebooks" / (source.stem + ".ipynb"))
        if destination.exists():
            raise RuntimeError(f"Preserving output: {destination}")
        print(f"JUPYTER START {source.name}", flush=True)
        nb = jupytext.read(source)
        nb.metadata.pop("jupytext", None)
        nb.metadata.kernelspec = {"name": "lab-venv", "display_name": "Lakehouse lab .venv", "language": "python"}
        NotebookClient(nb, timeout=600, kernel_name="lab-venv",
                       resources={"metadata": {"path": str(REPO / "notebooks")}}).execute(env=os.environ.copy())
        code = [c for c in nb.cells if c.cell_type == "code"]
        assert all(c.execution_count is not None for c in code)
        assert [c.execution_count for c in code] == sorted(c.execution_count for c in code)
        assert not any(o.output_type == "error" for c in code for o in c.outputs)
        nb.metadata["lab_execution_status"] = "complete"
        nb.metadata["validation_data_root"] = str(BASE / "notebooks")
        write_new(destination, nbformat.writes(nb))
        print(f"JUPYTER PASS {source.name}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--execute-review-sha256")
    action.add_argument("--jupyter-child", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.jupyter_child:
        jupyter()
    else:
        execute(args.execute_review_sha256)
