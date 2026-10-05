"""Kiểm tra bộ bài nộp trước khi commit. Không cần dependency ngoài stdlib.

    python3 scripts/check_submission.py

Kiểm những lỗi khiến mất điểm oan theo docs/RUBRIC.md và docs/SUBMISSION.md:

  1. submission/notebooks/ đủ 8 file 01…08 (không có _setup.ipynb).
  2. Mỗi notebook THỰC SỰ có output đã lưu (đây là lỗi phổ biến nhất:
     `run_all.py` chạy mã nhưng không ghi output vào .ipynb).
  3. Cell lỗi chưa xử lý (output type = error) được cảnh báo kèm tên notebook.
  4. Có ít nhất 1 ảnh bằng chứng cho mỗi notebook trong submission/screenshots/.
  5. INFO.md tồn tại, không còn placeholder; REFLECTION.md ≤ 200 từ.

Script chỉ ĐỌC, không sửa gì. Exit code 1 nếu có lỗi chặn (FAIL).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"
NB_DIR = SUB / "notebooks"
SHOTS = SUB / "screenshots"
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
EXPECTED = [
    "01_delta_basics",
    "02_optimize_zorder",
    "03_time_travel",
    "04_medallion",
    "05_iceberg_catalog",
    "06_maintenance",
    "07_vectors_multimodal",
    "08_agents_provenance",
]
PLACEHOLDERS = ("<điền", "<fill", "TODO", "XXX", "HoVaTen", "MSSV-CUA-BAN")

fails: list[str] = []
warns: list[str] = []


def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    fails.append(msg)


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")
    warns.append(msg)


def check_notebooks() -> None:
    print("\n1) submission/notebooks/")
    if not NB_DIR.is_dir():
        fail(f"thiếu thư mục {NB_DIR.relative_to(ROOT)}")
        return
    found = sorted(p for p in NB_DIR.glob("*.ipynb") if not p.name.startswith("_"))
    names = [p.stem for p in found]
    if len(found) == 8:
        ok(f"đủ 8 notebook: {', '.join(n[:2] for n in names)}")
    else:
        fail(f"cần 8 notebook, đang có {len(found)}: {', '.join(names) or '(trống)'}")
    for stem in EXPECTED:
        if not any(n.startswith(stem[:2]) for n in names):
            fail(f"thiếu notebook {stem}.ipynb")
    if (NB_DIR / "_setup.ipynb").exists():
        warn("_setup.ipynb không thuộc bài nộp — xoá khỏi submission/notebooks/")

    print("\n2) output đã lưu trong notebook")
    for nb_path in found:
        try:
            nb = json.loads(nb_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            fail(f"{nb_path.name}: không đọc được JSON ({exc})")
            continue
        cells = nb.get("cells", [])
        code = [c for c in cells if c.get("cell_type") == "code"]
        with_out = [c for c in code if c.get("outputs")]
        md = [c for c in cells if c.get("cell_type") == "markdown"]
        errors = [
            c
            for c in code
            for o in c.get("outputs", [])
            if o.get("output_type") == "error"
        ]
        label = f"{nb_path.name}: {len(with_out)}/{len(code)} code cell có output, {len(md)} markdown"
        if not code:
            fail(f"{nb_path.name}: không có code cell nào")
        elif not with_out:
            fail(f"{nb_path.name}: KHÔNG có output nào được lưu — mở lại trong Jupyter, Run All rồi Save")
        elif len(with_out) < max(3, len(code) // 3):
            warn(label + "  (ít output bất thường — chắc chắn đã Run All chưa?)")
        else:
            ok(label)
        if errors:
            warn(f"{nb_path.name}: có {len(errors)} cell báo lỗi — lỗi cố ý (schema enforcement) thì giải thích trong Markdown")


def check_screenshots() -> None:
    print("\n3) submission/screenshots/")
    if not SHOTS.is_dir():
        fail("thiếu thư mục submission/screenshots/")
        return
    imgs = [p for p in SHOTS.iterdir() if p.suffix.lower() in IMG_EXT]
    if not imgs:
        fail("chưa có ảnh bằng chứng nào")
        return
    ok(f"{len(imgs)} ảnh")
    for stem in EXPECTED:
        num = stem[:2]
        if not any(num in p.name for p in imgs):
            warn(f"chưa thấy ảnh cho NB{num} (đặt tên dạng nb{num}_*.png cho dễ chấm)")


def check_docs() -> None:
    print("\n4) INFO.md / REFLECTION.md")
    info = SUB / "INFO.md"
    if not info.exists():
        fail("thiếu submission/INFO.md")
    else:
        text = info.read_text(encoding="utf-8")
        left = [p for p in PLACEHOLDERS if p.lower() in text.lower()]
        if left:
            fail(f"INFO.md còn placeholder chưa điền: {', '.join(left)}")
        else:
            ok("INFO.md đã điền")

    refl = SUB / "REFLECTION.md"
    if not refl.exists():
        fail("thiếu submission/REFLECTION.md")
        return
    text = refl.read_text(encoding="utf-8")
    body = re.sub(r"```.*?```", " ", text, flags=re.S)
    body = re.sub(r"[#>*_`\-\[\]()]", " ", body)
    words = [w for w in body.split() if any(ch.isalnum() for ch in w)]
    if any(p.lower() in text.lower() for p in PLACEHOLDERS):
        fail("REFLECTION.md còn placeholder chưa điền")
    elif len(words) > 200:
        fail(f"REFLECTION.md dài {len(words)} từ (giới hạn 200)")
    else:
        ok(f"REFLECTION.md {len(words)} từ (≤ 200)")
    if not re.search(r"\bAI\b|Claude|ChatGPT|Copilot|Gemini|Arena", text, re.I) and not (
        SUB / "AI_USAGE.md"
    ).exists():
        warn("RULES.md yêu cầu khai phạm vi dùng AI trong reflection hoặc AI_USAGE.md")


def main() -> int:
    print(f"Kiểm tra bài nộp tại {SUB}")
    if not SUB.is_dir():
        print("  [FAIL] chưa có thư mục submission/")
        return 1
    check_notebooks()
    check_screenshots()
    check_docs()
    print("\n" + "─" * 64)
    print(f"  {len(fails)} FAIL · {len(warns)} WARN")
    if fails:
        print("  Sửa các mục FAIL trước khi commit.")
        return 1
    print("  Bộ bài nộp đạt các kiểm tra cơ bản. Vẫn tự đối chiếu docs/RUBRIC.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())