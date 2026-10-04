# Khai báo sử dụng AI — Lò Văn Long (2A202602541)

**Công cụ:** Claude Code (model Claude Opus 5.5 của Anthropic), chạy trong VS Code trên máy của mình.

## AI đã hỗ trợ những gì

| Việc | Phạm vi |
|---|---|
| Cài môi trường | Tạo `.venv`, cài `requirements.txt`, chạy smoke test, pytest, `run_all.py` theo hướng dẫn PowerShell của README |
| Thực thi notebook | Chuyển `.py` → `.ipynb` (jupytext), thực thi bằng Jupyter kernel (`nbconvert --execute`) từ dữ liệu sạch, chép vào `submission/notebooks/` |
| Đọc code và output | Đọc 8 notebook và script sinh dữ liệu, đối chiếu output với RUBRIC/CHECKPOINTS |
| Điều tra số liệu bất thường | Viết thí nghiệm nhỏ ngoài repo để kiểm chứng: vacuum lite vs `full=True`, đường dẫn tương đối trả về từ `vacuum()`, checkpoint tự động mỗi 100 commit, enforcement kiểu "cast" của delta-rs, múi giờ DuckDB ở NB4 |
| Cell bằng chứng bổ sung | Đề xuất và thêm các cell "🔎 Bằng chứng bổ sung" (chỉ đọc, hoặc chạy trên bảng scratch riêng) |
| Giải thích kết quả | Soạn nháp cell "📝 Giải thích kết quả" (tiếng Việt) cho từng notebook, dựa trên output thật của lần chạy nộp bài |
| Screenshots | Render các cell từ `.ipynb` đã chạy sang HTML (nbconvert) và chụp bằng Chrome headless |
| Tài liệu nộp | Soạn nháp `INFO.md`, `REFLECTION.md`, file này; chủ đề reflection và topic bonus do mình chọn |

## AI không làm những việc sau

- Không tạo hay sửa số liệu và output. Mọi con số trong phần giải thích lấy từ output thực thi trên máy mình.
- Không xóa hay sửa assertion, không hạ ngưỡng. `git diff` của `notebooks/*.py` chỉ có dòng thêm.
- Không dùng API key hay dữ liệu thật; lab chạy offline với dữ liệu giả.

Mình đã đọc lại các phần giải thích và reflection, và chịu trách nhiệm giải thích được mã nguồn cùng kết quả khi được hỏi.
