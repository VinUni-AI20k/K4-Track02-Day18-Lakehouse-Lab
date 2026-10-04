"""Preserve the current package and emit reviewable patches; never rerun lab data operations."""
import copy
import difflib
import json
import subprocess
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"


def checked(path):
    resolved = path.resolve()
    assert resolved.is_relative_to(ROOT) and resolved != ROOT
    assert resolved == path.absolute(), f"Unexpected link: {path}"
    return resolved


def main():
    subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True)
    results = json.loads(checked(SUB / "validation_20261004/results.json").read_text(encoding="utf-8"))
    assert [results[k] for k in ("smoke", "pytest", "runner", "jupyter")] == ["9/9", "24/24", "8/8", "8/8 sequential"]
    changes = {}
    for name in ("01_delta_basics", "02_optimize_zorder", "03_time_travel", "04_medallion", "05_iceberg_catalog", "06_maintenance", "07_vectors_multimodal", "08_agents_provenance"):
        target = checked(SUB / "notebooks" / (name + ".ipynb"))
        prior = nbformat.read(target, as_version=4)
        fresh = nbformat.read(checked(SUB / "validation_20261004/notebooks" / target.name), as_version=4)
        counts = [c.execution_count for c in fresh.cells if c.cell_type == "code"]
        assert counts == list(range(1, len(counts) + 1))
        assert not any(o.output_type == "error" for c in fresh.cells if c.cell_type == "code" for o in c.outputs)
        fresh.cells.insert(1, nbformat.v4.new_markdown_cell(
            "### Bản nộp chính — Jupyter tuần tự ngày 04/10/2026\n\n"
            "Các code cell/output bên dưới giữ nguyên từ lượt chạy Jupyter từ đầu đến cuối, "
            "trong môi trường dữ liệu giả riêng `validation_ready_20261004/notebooks`. "
            "Không sửa execution_count hoặc output. Log: `../validation_20261004/jupyter_sequential.txt`. "
            "Các phần giải thích cuối notebook được giữ từ lần đo trước và có nhãn lịch sử; "
            "số đo của lượt cuối nằm trong output bên dưới. Bản trước đồng bộ giữ tại "
            "`../history_presync_20261004/`."))
        retained = [copy.deepcopy(c) for c in prior.cells if c.cell_type == "markdown" and "### " in c.source and not any(c.source == n.source for n in fresh.cells)]
        fresh.cells.append(nbformat.v4.new_markdown_cell(
            "## Giải thích và trả lời thử thách — lịch sử lần đo trước\n\n"
            "Giữ nguyên nội dung để đối chiếu với notebook/log/ảnh trước đồng bộ. Các thời gian, "
            "byte và đường dẫn trong phần này thuộc lần đo trước, có thể khác output tuần tự "
            "ở trên. Kết quả hiện tại: smoke 9/9, pytest 24/24, runner 8/8, Jupyter tuần tự 8/8 PASS."))
        fresh.cells.extend(retained)
        nbformat.validate(fresh)
        changes[target] = nbformat.writes(fresh) + "\n"

    def update(name, transform):
        path = checked(SUB / name)
        changes[path] = transform(path.read_text(encoding="utf-8"))

    current = (
        "**Trạng thái cuối ngày 04/10/2026: phần kỹ thuật và gói notebook đã hoàn tất.** "
        "Smoke **9/9**, pytest **24/24** (không deselect), runner **8/8**, Jupyter tuần tự **8/8** đều PASS. "
        "[Kết quả](validation_20261004/results.json), [smoke](validation_20261004/smoke_full.txt), "
        "[pytest](validation_20261004/pytest_full.xml), [runner](validation_20261004/runner_full.txt), "
        "[Jupyter](validation_20261004/jupyter_sequential.txt).\n\n"
        "Tám notebook trong `notebooks/` đã nhận code/output tuần tự thật và giữ giải thích/câu trả lời "
        "với nhãn lịch sử. Bản trước đồng bộ giữ nguyên tại `history_presync_20261004/`; "
        "bản Jupyter gốc tại `validation_20261004/notebooks/`. 14 PNG cùng log/HTML cũ được giữ "
        "như bằng chứng các lần đo trước. [Kiểm tra bảo toàn](validation_20261004/preservation_verified.json) "
        "xác nhận 2.838 file có hash không đổi trong lượt validation. Không còn kiểm tra kỹ thuật thiếu.\n\n"
        "Bước bàn giao: commit/push, xác minh trên GitHub, mở PR upstream và gửi repo URL + PR URL + "
        "commit SHA qua kênh lớp. Trạng thái bàn giao thực tế được báo cùng liên kết sau khi thực hiện.\n\n")
    update("RUN_STATUS.md", lambda old: "# Trạng thái thực thi\n\n" + current + "## Lịch sử trước validation đầy đủ — giữ nguyên để đối chiếu\n\n" + old.split("\n", 1)[1].lstrip())
    update("AI_USAGE.md", lambda old: "# Phạm vi hỗ trợ AI\n\nCodex thực hiện đồng bộ gói nộp, bảo toàn bản cũ, cập nhật báo cáo và chuẩn bị commit/push/PR theo yêu cầu người học. Bộ kiểm tra gốc và Jupyter tuần tự đã PASS đầy đủ trong môi trường riêng; không thay assertion, không giả output. Người học chịu trách nhiệm đọc, hiểu và khai báo hỗ trợ AI.\n\n" + current + "## Lịch sử hỗ trợ trước khi chốt\n\n" + old.split("\n", 1)[1].lstrip())
    update("REMAINING_ACTIONS.md", lambda old: "# Việc bàn giao còn lại\n\n" + current + "## Lịch sử trước validation — các yêu cầu test dưới đây đã hoàn tất\n\n" + old)
    update("EXPLANATIONS.md", lambda old: old.replace("Kiểm tra tổng hợp chưa đầy đủ; những hành vi chưa đo được ghi rõ bên dưới.", "Smoke 9/9, pytest 24/24, runner 8/8 và Jupyter tuần tự 8/8 đã PASS. Các số đo chi tiết dưới đây thuộc lần đo trước, đối chiếu với lịch sử và ảnh; output tuần tự cuối trong notebook chính là nguồn số đo mới nhất.").replace("20/24 pytest đã chạy và PASS; bốn test còn lại chưa chạy. Smoke gốc 8/9 checks PASS, runner gốc chưa hoàn tất.", "Pytest gốc 24/24, smoke gốc 9/9, runner gốc 8/8 và Jupyter tuần tự 8/8 đều PASS; xem validation_20261004/results.json và các log cùng thư mục.").replace("Không tuyên bố toàn bộ bài PASS vì kiểm tra tổng hợp chưa đủ.", "Gói notebook đã đồng bộ output tuần tự và giữ giải thích/lịch sử."))
    update("PR_DRAFT.md", lambda old: "# Nội dung PR\n\nTiêu đề: `[K4-Track02-Day18] DuongXuanVinh - 2A202602622 - Lakehouse Lab`\n\nHọ tên: Dương Xuân Vinh. MSSV: 2A202602622. Đường chạy: lightweight, Python 3.14.7 trên Windows 11.\n\nBài nộp gồm tám notebook đã chạy Jupyter tuần tự từ đầu đến cuối, output thật và giải thích/câu trả lời 3.1–3.8. Giữ 14 ảnh bằng chứng, reflection dưới 200 từ, khai AI và các bản lịch sử. Sửa hai lỗi đường dẫn Windows trong NB6: tính byte VACUUM từ path tương đối và giải mã URI có dấu cách khi kiểm tra orphan.\n\nValidation ngày 04/10/2026 trong môi trường dữ liệu giả riêng: smoke 9/9, pytest 24/24 không deselect, runner 8/8 và Jupyter tuần tự 8/8 đều PASS. Không thay assertion hoặc ngưỡng.\n\nLiên kết bản nộp trên fork: [notebooks](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab/tree/main/submission/notebooks), [ảnh](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab/tree/main/submission/screenshots), [reflection](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab/blob/main/submission/REFLECTION.md), [khai AI](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab/blob/main/submission/AI_USAGE.md), [validation](https://github.com/DngVinh/K4-Track02-Day18-DuongXuanVinh-2A202602622-Lakehouse-Lab/tree/main/submission/validation_20261004).\n\nBonus tùy chọn chưa thực hiện. Notebook/log/ảnh trước được giữ để đối chiếu; giải thích lịch sử có nhãn phân biệt với số đo tuần tự mới.\n")
    review = "# Kiểm định trước khi nộp — 04/10/2026\n\n**Kết luận: kỹ thuật và gói notebook sẵn sàng để nộp.** Không còn bài kiểm tra kỹ thuật thiếu. Việc gửi kênh lớp chỉ hoàn tất khi có xác nhận gửi thực tế.\n\n" + current + "## Đối chiếu yêu cầu cuối\n\n| Yêu cầu | Kết quả |\n|---|---|\n| Smoke gốc | 9/9 PASS |\n| Pytest gốc | 24/24 PASS, không deselect |\n| Runner gốc từ môi trường riêng | 8/8 PASS |\n| Jupyter từ đầu đến cuối | 8/8 PASS; execution_count tuần tự thật, không error output |\n| Notebook chính | Đã đồng bộ code/output từ validation và giữ giải thích 3.1–3.8 |\n| Bảo toàn lịch sử | Bản trước đồng bộ và báo cáo cũ tại history_presync_20261004/; các history/revisions/log/ảnh trước vẫn giữ |\n| INFO, reflection, khai AI | Có; reflection dưới 200 từ |\n| Screenshots | 14 PNG phủ 8 NB; số đo thuộc các lần chạy trước, không phải ảnh Jupyter |\n| NB6 source | Đã sửa đường dẫn tương đối VACUUM và URL-encoded URI Windows |\n| Commit/push/PR/kênh lớp | Hoàn tất theo bước bàn giao; đối chiếu liên kết và SHA được báo sau thực hiện |\n\nRubric nội dung và số đo lần trước giữ trong [review lịch sử](history_presync_20261004/READINESS_REVIEW_20261004.md). Part C đã có log pytest/runner đầy đủ; không suy diễn điểm chính thức từ PASS. Bonus tùy chọn, chưa thực hiện.\n"
    update("READINESS_REVIEW_20261004.md", lambda old: review)

    # Exclusive byte-for-byte archives, checked destinations; no overwrites.
    history = checked(SUB / "history_presync_20261004")
    assert not history.exists(), "Archive already exists; review before retrying"
    originals = {path: path.read_bytes() for path in changes}
    history.mkdir()
    for path, data in originals.items():
        destination = checked(history / path.name)
        with destination.open("xb") as handle:
            handle.write(data)
        assert destination.read_bytes() == data
    patches = ["*** Begin Patch"]
    for path, new in changes.items():
        old = path.read_text(encoding="utf-8")
        lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), n=3))[2:]
        if lines:
            patches.append("*** Update File: " + path.relative_to(ROOT).as_posix())
            patches.extend("@@\n" if line.startswith("@@") else line for line in lines)
    patches.append("*** End Patch")
    print(json.dumps({"patch": "\n".join(p.rstrip("\n") for p in patches)}))


if __name__ == "__main__":
    main()
