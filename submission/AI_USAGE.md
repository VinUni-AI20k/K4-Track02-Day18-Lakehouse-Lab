# Khai báo sử dụng AI

- Công cụ: OpenAI Codex, sau đó Claude Code (Anthropic) tiếp tục phần thực
  thi notebook, render ảnh/PDF và kiểm tra cuối, trong workspace của bài lab.
- Phạm vi: đọc đề/rubric và mã nguồn; cài môi trường; bổ sung kiểm chứng NB1,
  NB4; thực thi smoke, pytest và notebook; lưu output, tạo trang bằng chứng
  từ output thật; chụp ảnh; soạn giải thích, reflection và architecture brief.
- Mã nền và generator lấy từ repo đề bài của VinUniversity AICB, commit
  `f5d65ee`. Không nhận mã hoặc output từ bài của học viên khác.
- Output do Python/Jupyter chạy trên máy này tạo ra, không phải số do AI tự
  đặt. Các giả định capacity/chi phí trong bonus được ghi riêng, không coi là
  số benchmark. Log thực thi và phiên bản dependency được giữ trong bài nộp.
- NB1 thay cờ hardcode bằng kết quả exception và xác nhận version/row count
  không đổi. NB4 bổ sung kiểm tra toàn bộ Gold và sửa mô tả malformed JSON cho
  đúng hành vi hiện có. NB4 cố định ngày Gold theo UTC (`AT TIME ZONE 'UTC'`)
  vì trên máy UTC+7 DuckDB gom thành 8 ngày, hai ngày đầu/cuối thiếu giờ; có
  thêm assertion đối chiếu cột `date` với ngày UTC của `ts`. Không xóa
  assertion hoặc hạ ngưỡng rubric.
- Các notebook nộp có cell bootstrap để mở từ thư mục submission, cell bằng
  chứng bổ sung và Markdown giải thích. `scripts/build_submission.py` tái tạo
  chúng từ nguồn; không thay output bằng văn bản soạn tay.
- Các thao tác được Codex thực thi theo yêu cầu người dùng, không khai là
  học viên đã tự thao tác từng lệnh. Người nộp cần tự đọc, chạy lại và giải thích
  bài trước khi nộp theo `docs/RULES.md`; reflection là bản được AI hỗ trợ soạn.
- Spark/Docker, Apple container và bộ mô phỏng Unix 12 kịch bản không thuộc
  đường thực thi của bài nộp này. Không tuyên bố các đường đó đã PASS.
