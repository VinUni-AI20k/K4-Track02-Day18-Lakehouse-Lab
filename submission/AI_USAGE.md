# Khai báo phạm vi sử dụng AI

Bài lab cho phép dùng AI kèm khai báo ([`docs/RULES.md`](../docs/RULES.md)). Dưới đây là
phạm vi sử dụng thực tế trong bài nộp này.

## AI đã được dùng để

- **Đọc và tóm tắt tài liệu lab** (`README.md`, `docs/CHECKPOINTS.md`, `docs/RUBRIC.md`,
  `docs/SUBMISSION.md`) và lập checklist theo yêu cầu/ngưỡng.
- **Chạy môi trường và các lệnh kiểm tra** thay cho `make` (không có trên Windows):
  `scripts/verify_lite.py`, `pytest`, `scripts/run_all.py`, sinh dữ liệu bằng
  `scripts/generate_data_lite.py` và `scripts/generate_ai_data.py`.
- **Thực thi 8 notebook** (`notebooks/0*.py` → `.ipynb`) bằng `nbconvert` để giữ output,
  rồi chép bản đã chạy vào `submission/notebooks/`.
- **Viết script tạo ảnh chụp** `submission/_make_screenshots.py` (render output notebook
  ra PNG terminal-style) — không thuộc runtime của lab.
- **Soạn các tài liệu bài nộp**: `INFO.md`, `REFLECTION.md`, `AI_USAGE.md`, và
  `bonus/ARCHITECTURE.md`.

## AI KHÔNG được dùng để

- **Bịa hoặc sửa output** của notebook. Mọi số liệu (số file, speedup, pruning ratio,
  recall, fidelity…) đều do notebook tự sinh khi chạy thật.
- **Hạ ngưỡng hay bỏ kiểm tra** để báo PASS. Các ngưỡng giữ nguyên theo `RUBRIC.md`.
- **Tạo bằng chứng giả**: ảnh trong `submission/screenshots/` render trực tiếp từ output
  đã lưu của notebook, không vẽ tay số liệu.

## Nguồn

- Mã notebook, script và helper dùng nguyên bản từ repo đề bài
  [K4-Track02-Day18-Lakehouse-Lab](https://github.com/VinUni-AI20k/K4-Track02-Day18-Lakehouse-Lab).
- Phần suy luận reflection, lựa chọn anti-pattern và các quyết định kiến trúc trong bonus
  là của tác giả; AI hỗ trợ diễn đạt và kiểm tra tính nhất quán với số liệu.

Trợ lý AI: Claude Code (Anthropic), dùng trong phiên làm bài ngày 2026-10-04.
