# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic), chạy trong VS Code trên máy cá nhân.

| Phần việc | AI đã làm | Tôi tự kiểm tra |
|---|---|---|
| Setup môi trường | Tạo venv Python 3.13, cài `requirements.txt`, chạy smoke / data / pytest / run_all bằng lệnh PowerShell tương đương `make` | Đọc log: smoke 9/9, pytest 24 passed, run_all 8/8 |
| Thực thi notebook | Chuyển `.py` → `.ipynb` bằng jupytext, chạy `nbconvert --execute --inplace`, chép sang `submission/notebooks/` | Output là của lần chạy thật trên máy tôi, không chỉnh sửa số liệu |
| Cell bổ sung | Thêm cell in `_delta_log` cho NB1 và cell kiểm tra Gold cho NB4. Không sửa assertion hay ngưỡng gốc | Chạy lại notebook, tất cả PASS |
| Giải thích kết quả | Soạn nháp Markdown "Giải thích kết quả" dựa trên output thực của từng notebook | Đối chiếu từng con số với output và RUBRIC |
| Screenshots | Xuất HTML bằng nbconvert, chụp các cell kết quả bằng Playwright | Xem lại ảnh |
| Reflection | Soạn nháp | Chỉnh lại theo trải nghiệm của tôi |
| Bonus (chủ đề A) | Soạn nháp `ARCHITECTURE.md` và PoC `poc/`; tính chi phí theo giả định đã ghi rõ | Chạy PoC, kiểm tra phép tính, có thể giải thích từng quyết định |

**Không dùng AI để:** tạo số liệu giả, bỏ assertion, hạ ngưỡng, hoặc khẳng định về lần chạy chưa thực hiện.
Mọi số đo trong bài lấy từ output đã lưu trong notebook và log chạy PoC.
