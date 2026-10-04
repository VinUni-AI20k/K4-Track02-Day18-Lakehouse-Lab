"""Run the accepted review with temporary runtime files inside approved scope."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import complete_submission_validation as validation


def inventory(root):
    result = {}
    if root.exists():
        for item in root.rglob("*"):
            validation.scoped(item)
            if item.is_file():
                result[str(item)] = validation.digest(item)
    return result


def main():
    review = json.loads(validation.REVIEW.read_text(encoding="utf-8"))
    allowed = [validation.scoped(validation.BASE / phase)
               for phase in ("smoke", "pytest", "runner", "notebooks")]
    assert [str(p) for p in allowed] == [e["canonical_path"] for e in review["directory_targets"]]
    for target in allowed:
        validation.scoped(target)
        inventory(target)
    for item in validation.OUTPUT.rglob("*"):
        validation.scoped(item)
    for name in ("smoke_full.txt", "pytest_full.txt", "pytest_full.xml",
                 "runner_full.txt", "jupyter_sequential.txt", "results.json",
                 "preservation_verified.json", "notebooks"):
        assert not validation.scoped(validation.OUTPUT / name).exists(), name

    # Preserve old lab data, shared runtime, and every existing evidence file.
    protected = {}
    lake = validation.REPO / "_lakehouse"
    for item in lake.rglob("*"):
        validation.scoped(item)
        if item.is_file() and not any(item.is_relative_to(p) for p in allowed):
            protected[str(item)] = validation.digest(item)
    protected.update(inventory(validation.REPO / "submission"))
    status = __import__("subprocess").check_output(
        ["git", "status", "--porcelain"], cwd=validation.REPO, text=True)
    original_environment = validation.environment

    def contained_environment(root):
        env = original_environment(root)
        root = validation.scoped(root)
        # Keep pytest basetemp absent until pytest creates it itself.
        runtime = ((allowed[0] / "_validation_runtime" / "pytest")
                   if root == allowed[1] else root / "_validation_runtime")
        for key, leaf in (("IPYTHONDIR", "ipython"), ("JUPYTER_RUNTIME_DIR", "jupyter"),
                          ("JUPYTER_CONFIG_DIR", "config"), ("JUPYTER_DATA_DIR", "data"),
                          ("TEMP", "temp"), ("TMP", "temp")):
            target = validation.scoped(runtime / leaf)
            assert any(target.is_relative_to(p) for p in allowed)
            target.mkdir(parents=True, exist_ok=True)
            env[key] = str(target)
        # The prepared kernel specification is read only.
        env["JUPYTER_PATH"] = str(validation.BASE / "runtime" / "data")
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        return env

    validation.environment = contained_environment
    print(f"Review SHA256: {validation.digest(validation.REVIEW)}", flush=True)
    print(f"Preserving {len(protected)} existing files", flush=True)
    try:
        validation.execute(validation.digest(validation.REVIEW))
    finally:
        changed = [p for p, sha in protected.items()
                   if not Path(p).is_file() or validation.digest(p) != sha]
        if changed:
            raise RuntimeError(f"Protected files changed: {changed}")
        final_status = __import__("subprocess").check_output(
            ["git", "status", "--porcelain"], cwd=validation.REPO, text=True)
        assert final_status == status, "Git state changed during validation"
        validation.write_new(validation.OUTPUT / "preservation_verified.json", json.dumps({
            "preserved_file_count": len(protected), "all_existing_hashes_unchanged": True,
            "git_status_unchanged_during_execution": True,
            "runtime_scope": [str(p) for p in allowed],
        }, indent=2))
        print("Preservation verified: existing hashes and Git state unchanged", flush=True)


if __name__ == "__main__":
    main()
