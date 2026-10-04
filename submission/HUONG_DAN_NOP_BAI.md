# Hướng dẫn nộp bài Đỗ Quốc An - 2A202602892

## 1. Đọc và tự chạy lại

Bộ bài đã được Codex chuẩn bị và thực thi trên máy với output thật. Theo docs/RULES.md, bạn cần tự kiểm tra và giải thích được bài trước khi nộp. Đọc CHECKPOINT_REPORT.md, các Markdown giải thích trong 8 notebook và REFLECTION.md; sửa reflection nếu chưa đúng hiểu biết của bạn. Giữ AI_USAGE.md để khai báo phạm vi hỗ trợ.

Mở PowerShell trong thư mục repo rồi chạy:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/verify_lite.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp
.\.venv\Scripts\python.exe scripts/run_all.py
```

Mở bản có output bằng VS Code/Jupyter, đọc kết quả và thử Run All. Để tái tạo cả bộ output và log bằng kernel Python riêng:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_submission.py
```

Script chạy lại các bảng lab, không dùng cho dữ liệu production. Nếu muốn tạo lại ảnh/PDF, cài `requirements-submission.txt` rồi chạy `scripts/render_submission.py`.

## 2. Kiểm tra những gì sẽ đưa lên GitHub

`origin` phải là `https://github.com/an1-tech/K4-Track02-Day18-DoQuocAn-2A202602892-Lakehouse-Lab.git`.

```powershell
git remote -v
git status --short
git diff --check
git add README.md notebooks/01_delta_basics.py notebooks/04_medallion.py scripts/prepare_submission.py scripts/render_submission.py scripts/audit_submission.py requirements-lock.txt requirements-submission.txt .gitignore submission
git diff --cached --stat
```

Phải có 8 ipynb trong submission/notebooks và 8 PNG trong submission/screenshots; INFO, REFLECTION, AI_USAGE, report và bonus hiện trong staged files. Không đưa .venv, _lakehouse, cache, blobs, .env hay token vào commit. Chạy `.\.venv\Scripts\python.exe scripts/audit_submission.py` để kiểm bộ nộp.

## 3. Commit và push

```powershell
git commit -m "Complete Day18 lakehouse checkpoints and architecture bonus"
git push origin HEAD
git rev-parse HEAD
```

Sao chép SHA cuối. Mở repo trên GitHub và kiểm tra notebook có output, ảnh, reflection, bonus; chỉ file local chưa đủ để nộp. Tên repo phải đúng họ tên/MSSV, đây là fork của repo đề bài.

## 4. Mở PR về repo đề bài

Trên fork GitHub chọn Contribute -> Open pull request. Base repository: VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab; base branch dùng nhánh mặc định của upstream. Head repository: an1-tech/K4-Track02-Day18-DoQuocAn-2A202602892-Lakehouse-Lab; chọn nhánh vừa push.

Tiêu đề:

```text
[K4-Track02-Day18] DoQuocAn - 2A202602892 - Lakehouse Lab [+bonus]
```

Dùng PR_BODY.md làm mô tả; thay dòng Commit SHA bằng SHA thực tế và xác nhận bước tự đọc/chạy đã hoàn thành nếu bạn đã làm. Không tự merge PR vào repo lớp.

## 5. Gửi bài qua kênh của lớp

Gửi **cả link repo + link PR + commit SHA** qua kênh thu bài coach công bố. Chỉ push hoặc tạo PR chưa đồng nghĩa gửi qua kênh lớp.

Mẫu:

```text
Đỗ Quốc An - 2A202602892
K4-Track02-Day18 - Lakehouse Lab [+bonus]
Repo: https://github.com/an1-tech/K4-Track02-Day18-DoQuocAn-2A202602892-Lakehouse-Lab
PR: [dán link PR thực tế]
Commit: [dán SHA thực tế]
Lightweight; smoke 9/9, pytest 24/24, notebooks 8/8.
```

Deadline mặc định trong đề là 23:59 ngày tổ chức lab, UTC+7. Ngày cụ thể và kênh lớp không có trong repo; đối chiếu thông báo coach. Không tự coi hôm nay là deadline hoặc cộng 48 giờ. Sau deadline giữ commit đã nộp, bổ sung bằng commit mới nếu coach cho phép; không force-push/xóa bằng chứng cũ.
