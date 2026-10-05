"""PoC for the two hardest mechanisms in ARCHITECTURE.md (topic A, LLM observability).

  Spike 1  PII redactor: regex + Luhn + HMAC tokens. Measures recall/precision on a SYNTHETIC
           labelled corpus and single-core MB/s (the number that sizes the compute fleet).
  Spike 2  7-day TTL on an Iceberg table: delete -> expire snapshots -> orphan sweep, then prove
           the bytes are physically gone (positive-control byte grep) and time travel cannot
           bring them back. Also replays the NB7 lifecycle bug on a derived search index.

Run from the repo root:  .venv/Scripts/python.exe submission/bonus/poc/retention_and_redaction_poc.py
"""
import datetime as dtm, hashlib, hmac, random, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import pyarrow as pa
from pyiceberg.expressions import LessThan
from pyiceberg.transforms import DayTransform
from lakehouse import catalog, du, human, namespace, reset_catalog

random.seed(7)
KEY = b"poc-only-key"  # prod: KMS-held key, rotated; never in code

# ───────────── Spike 1: redactor ─────────────
PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"(?<!\d)(?:\+84|0)(?:3|5|7|8|9)\d{8}(?!\d)"),   # VN mobile
    "CARD":  re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)"),
    "APIKEY": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
}


def luhn(s: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", s)][::-1]
    return (sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])) % 10 == 0


def redact(text: str) -> str:
    def tok(kind):
        def f(m):
            if kind == "CARD" and not luhn(m.group()):
                return m.group()                      # order ids etc. are NOT cards
            return f"<{kind}:{hmac.new(KEY, m.group().encode(), hashlib.sha256).hexdigest()[:10]}>"
        return f
    for kind, rx in PATTERNS.items():
        text = rx.sub(tok(kind), text)
    return text


def make_corpus(n=20_000):
    filler = "Summarise the incident timeline and list the follow-up actions for the platform team. " * 4
    docs, planted = [], []
    for i in range(n):
        t, secrets = filler, []
        if i % 5 == 0:
            e = f"user{i}@example.com"; t += f" contact {e}"; secrets.append(e)
        if i % 7 == 0:
            p = f"09{random.randint(10**7, 10**8 - 1)}"; t += f" call {p}"; secrets.append(p)
        if i % 11 == 0:
            body = "".join(random.choice("0123456789") for _ in range(15))
            c = next(body + str(d) for d in range(10) if luhn(body + str(d)))
            t += f" card {c}"; secrets.append(c)
        if i % 13 == 0:
            k = "sk-" + "".join(random.choices("abcdefABCDEF0123456789", k=32)); t += f" key {k}"; secrets.append(k)
        if i % 17 == 0:
            t += " order 1234567890123456"             # 16 digits, fails Luhn: must survive
        docs.append(t); planted.append(secrets)
    return docs, planted


docs, planted = make_corpus()
t0 = time.perf_counter(); out = [redact(d) for d in docs]; dt = time.perf_counter() - t0
mb = sum(len(d) for d in docs) / 1e6
n_sec = sum(len(s) for s in planted); leaked = sum(s in o for ss, o in zip(planted, out) for s in ss)
false_pos = sum("order 1234567890123456" not in o for d, o in zip(docs, out) if "order 1234567890123456" in d)
print("== Spike 1: redactor (synthetic corpus, planted PII only) ==")
print(f"planted secrets: {n_sec:,}  leaked after redaction: {leaked}  recall: {1 - leaked / n_sec:.4f}")
print(f"Luhn false positives on 16-digit non-card ids: {false_pos}")
print(f"throughput: {mb / dt:.1f} MB/s on 1 core  ({mb:.1f} MB in {dt:.2f}s)")
print("NOT covered: person names / street addresses / free-text identifiers (regex cannot see them).")

# ───────────── Spike 2: TTL really deletes ─────────────
CAT, TTL_DAYS, N_DAYS = "poc_ttl", 7, 9
reset_catalog(CAT); cat = catalog(CAT); ns = namespace(cat, "lake")
schema = pa.schema([pa.field("request_id", pa.int64(), nullable=False),
                    pa.field("ts", pa.timestamp("us"), nullable=False), pa.field("prompt", pa.string())])
tbl = cat.create_table(f"{ns}.llm_silver", schema=schema,
                       properties={"write.parquet.compression-codec": "uncompressed"})  # so byte-grep is meaningful
with tbl.update_spec() as s:
    s.add_field("ts", DayTransform(), "ts_day")
tbl = cat.load_table(f"{ns}.llm_silver")

today = dtm.datetime(2026, 10, 5)
for d in range(N_DAYS):                                    # day 0 = oldest; days 0,1 are past the 7-day TTL
    day = today - dtm.timedelta(days=N_DAYS - 1 - d)
    ids = list(range(d * 100, d * 100 + 100))
    tbl.append(pa.table({"request_id": ids, "ts": [day + dtm.timedelta(minutes=i) for i in range(100)],
                         "prompt": [f"SENTINEL-DAY{d}-{i}" for i in ids]}, schema=schema))
tbl = cat.load_table(f"{ns}.llm_silver")
root = Path(tbl.location().replace("file://", ""))
old_snapshot = tbl.snapshots()[0].snapshot_id


def grep_bytes(needle: bytes) -> int:
    return sum(needle in f.read_bytes() for f in root.rglob("*.parquet"))


expired_ids = [r for r in tbl.scan().to_arrow()["request_id"].to_pylist() if r < 200]  # keep list for index eviction
index = {i: "stale-index-entry" for i in expired_ids}          # derived search index (NB7 lesson)
print("\n== Spike 2: 7-day TTL on Iceberg ==")
print(f"before: snapshots={len(tbl.snapshots())}  parquet files with SENTINEL-DAY0 (positive control): {grep_bytes(b'SENTINEL-DAY0')}")

cutoff = today - dtm.timedelta(days=TTL_DAYS - 1)
tbl.delete(delete_filter=LessThan("ts", cutoff.isoformat()))                      # step 1: logical delete
tbl = cat.load_table(f"{ns}.llm_silver")
print(f"after delete only: current rows={tbl.scan().to_arrow().num_rows}  "
      f"bytes still on disk for DAY0: {grep_bytes(b'SENTINEL-DAY0')}  (time travel still works: "
      f"old snapshot rows={tbl.scan(snapshot_id=old_snapshot).to_arrow().num_rows})")

keep = [tbl.current_snapshot().snapshot_id]                                         # step 2: expire every old snapshot
tbl.maintenance.expire_snapshots().by_ids([s.snapshot_id for s in tbl.snapshots() if s.snapshot_id not in keep]).commit()
tbl = cat.load_table(f"{ns}.llm_silver")

live = {Path(p.replace("file://", "")).resolve() for p in tbl.inspect.files()["file_path"].to_pylist()}
live |= {Path(s.manifest_list.replace("file://", "")).resolve() for s in tbl.snapshots()}
for m in tbl.current_snapshot().manifests(tbl.io):
    live.add(Path(m.manifest_path.replace("file://", "")).resolve())
orphans = [f for f in root.rglob("*") if f.is_file() and f.suffix in {".parquet", ".avro"} and f.resolve() not in live
           and time.time() - f.stat().st_mtime >= 0]                                # prod: older_than >= 3 days (age guard!)
freed = sum(f.stat().st_size for f in orphans)
for f in orphans:
    f.unlink()                                                                        # step 3: orphan sweep
tbl = cat.load_table(f"{ns}.llm_silver")
print(f"after expire + sweep: freed {human(freed)} in {len(orphans)} files; snapshots={len(tbl.snapshots())}; "
      f"current rows={tbl.scan().to_arrow().num_rows}")
print(f"bytes on disk for DAY0/DAY1 sentinels: {grep_bytes(b'SENTINEL-DAY0') + grep_bytes(b'SENTINEL-DAY1')} files (want 0); "
      f"DAY8 still present: {grep_bytes(b'SENTINEL-DAY8')} file(s)")
try:
    tbl.scan(snapshot_id=old_snapshot).to_arrow(); print("time travel to expired snapshot: STILL WORKS (bad)")
except Exception as e:
    print(f"time travel to expired snapshot: {type(e).__name__} (good)")

hits = sum(1 for i in expired_ids if i in index)
print(f"derived index still serving expired docs: {hits}  <- NB7 lifecycle bug")
for i in expired_ids:                                                                 # evict from the delete list
    index.pop(i, None)
print(f"after eviction driven by the delete list: {sum(1 for i in expired_ids if i in index)}")
assert leaked == 0 and false_pos == 0
assert grep_bytes(b"SENTINEL-DAY0") == 0 and grep_bytes(b"SENTINEL-DAY1") == 0 and grep_bytes(b"SENTINEL-DAY8") >= 1
print("\nPOC OK")
