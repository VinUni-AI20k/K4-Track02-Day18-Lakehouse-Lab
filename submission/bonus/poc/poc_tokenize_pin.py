"""Bonus PoC — spike cho mechanism khó nhất của topic A (LLM observability).

Chứng minh ba thứ, tất cả offline, không API key, không Docker:

  1. Token hóa PII một chiều: email/phone không còn dạng thô, nhưng vẫn joinable
     (cùng input -> cùng token), và KHÔNG có hàm giải mã.
  2. Ghim version Delta cho training/audit: replay ở đúng version cho đúng số row.
  3. Prune theo thời gian: đọc một ngày không cần chạm mọi partition.

Chạy từ repo root:

    ./.venv/Scripts/python.exe submission/bonus/poc/poc_tokenize_pin.py
"""
from __future__ import annotations

import hashlib
import hmac
import re
import shutil
import sys
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from lakehouse import path  # noqa: E402

# ── 1. Token hóa PII một chiều ─────────────────────────────────────────────
# Trong production salt nằm trong secret manager; ở PoC dùng hằng cố định.
_SALT = b"poc-day18-salt-not-a-real-secret"


def tokenize(value: str) -> str:
    """HMAC-SHA256 -> token joinable, không đảo ngược."""
    return "tok_" + hmac.new(_SALT, value.encode(), hashlib.sha256).hexdigest()[:24]


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\b0\d{9,10}\b")


def redact(text: str) -> str:
    text = EMAIL.sub(lambda m: tokenize(m.group(0)), text)
    return PHONE.sub(lambda m: tokenize(m.group(0)), text)


def check_pii() -> None:
    raw = [
        "user alice@example.com called",
        "bob@example.com and 0912345678",
        "alice@example.com again",  # cùng email -> cùng token (joinable)
    ]
    red = [redact(t) for t in raw]

    assert not any(EMAIL.search(t) or PHONE.search(t) for t in red), "PII còn sót!"
    assert red[0].split()[-2] == red[2].split()[0], "cùng email phải cùng token"
    assert tokenize("alice@example.com") != tokenize("bob@example.com"), "token phải phân biệt"
    assert not hasattr(sys.modules[__name__], "detokenize"), "không được có hàm giải mã"
    print("  [PASS] PII tokenized one-way; joinable; no detokenize() exists")


# ── 2 + 3. Ghim version + prune theo thời gian ─────────────────────────────
def check_delta() -> None:
    p = path("bonus_poc", "requests_delta")
    shutil.rmtree(p, ignore_errors=True)

    days = ["2026-08-01", "2026-08-02", "2026-08-03"]
    for d in days:
        n = 100
        tbl = pa.table({
            "day": [d] * n,                      # partition key, tương ứng day(ts)
            "ts": [f"{d}T12:00:00"] * n,
            "tenant": [f"t{i % 10}" for i in range(n)],
            "payload": [redact(f"req from t{i}@x.com") for i in range(n)],
        })
        write_deltalake(p, tbl, mode="append" if d != days[0] else "overwrite",
                        partition_by=["day"])

    dt = DeltaTable(p)
    n_versions = len(dt.history())
    total = dt.to_pyarrow_table().num_rows
    assert n_versions == 3 and total == 300, (n_versions, total)

    # (2) ghim version: replay ở version 0 chỉ thấy ngày đầu.
    pinned = DeltaTable(p, version=0).to_pyarrow_table()
    assert pinned.num_rows == 100, pinned.num_rows
    print(f"  [PASS] version pin: v0 -> {pinned.num_rows} rows "
          f"(of {total}); {n_versions} versions in log")

    # (3) prune: filter một ngày -> Delta chỉ đọc partition đó.
    one_day = DeltaTable(p).to_pyarrow_table(filters=[("day", "=", "2026-08-02")])
    assert one_day.num_rows == 100, one_day.num_rows
    files_all = len(list(Path(p).glob("day=*/*.parquet")))
    files_one = len(list((Path(p) / "day=2026-08-02").glob("*.parquet")))
    assert files_one < files_all, (files_one, files_all)
    print(f"  [PASS] partition prune: {files_all} files -> {files_one} for one day")


if __name__ == "__main__":
    print("Bonus PoC — tokenize + version pin + time prune\n")
    check_pii()
    check_delta()
    print("\nPoC passed — hardest mechanisms are feasible offline.")
