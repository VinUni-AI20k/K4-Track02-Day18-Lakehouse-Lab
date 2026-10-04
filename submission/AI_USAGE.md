# Khai báo sử dụng AI — Lò Văn Long (2A202602541)

**Công cụ:** Claude Code (model Claude Opus 5.5 của Anthropic), chạy trong VS Code trên máy của mình.

## AI đã hỗ trợ những gì
| Việc | Phạm vi |
|---|---|
| Cài môi trường | AI hỗ trợ lên kế hoạch và hướng dẫn các bước tạo `.venv`, cài `requirements.txt`, chạy smoke test, `pytest`, `run_all.py` theo hướng dẫn PowerShell của README; đồng hành khi học viên gặp vấn đề trong quá trình thực hiện |
| Thực thi notebook | AI hỗ trợ lên kế hoạch và hướng dẫn quy trình chuyển `.py` → `.ipynb` (jupytext), thực thi bằng Jupyter kernel (`nbconvert --execute`) từ dữ liệu sạch và kiểm tra kết quả; học viên tự thực hiện các bước |
| Đọc code và output | AI hướng dẫn cách đọc 8 notebook và script sinh dữ liệu, xác định các điểm cần kiểm tra và cách đối chiếu output với RUBRIC/CHECKPOINTS; học viên tự đọc, kiểm tra và đưa ra kết luận |
| Điều tra số liệu bất thường | AI hỗ trợ lên kế hoạch và hướng dẫn cách thiết kế các bước kiểm chứng đối với các vấn đề như vacuum lite vs `full=True`, đường dẫn tương đối trả về từ `vacuum()`, checkpoint tự động mỗi 100 commit, enforcement kiểu "cast" của delta-rs và múi giờ DuckDB ở NB4; học viên tự thực hiện và phân tích kết quả |
| Cell bằng chứng bổ sung | AI hướng dẫn cách xác định khi nào cần bổ sung các cell "🔎 Bằng chứng bổ sung", gợi ý hướng kiểm tra và cách thiết kế cell; học viên tự viết và chạy các cell cần thiết |
| Giải thích kết quả | AI hỗ trợ lên kế hoạch và hướng dẫn cách phân tích output, xây dựng nội dung cho cell "📝 Giải thích kết quả" bằng tiếng Việt dựa trên output thật của lần chạy nộp bài; học viên tự viết và chịu trách nhiệm về nội dung |
| Screenshots | AI hướng dẫn quy trình render các cell từ `.ipynb` đã chạy sang HTML (`nbconvert`) và chụp bằng Chrome headless; học viên tự thực hiện và lựa chọn screenshots cần nộp |
| Tài liệu nộp | AI hỗ trợ lên kế hoạch, hướng dẫn cấu trúc và đồng hành trong quá trình hoàn thiện `INFO.md`, `REFLECTION.md` và file này; học viên tự viết nội dung, tự chọn chủ đề reflection và topic bonus |
| Bonus (topic D) | AI hỗ trợ lên kế hoạch và hướng dẫn từng bước để học viên tự xây dựng `bonus/ARCHITECTURE.md` (quyết định, failure mode, phép tính chi phí, MVP) và PoC trong `bonus/poc/`; học viên tự triển khai, chạy và ghi nhận output thật. Đơn giá cloud, throughput GPU và quy mô nếu chưa được đo thực tế phải được ghi rõ là **giả định** |
## AI không làm những việc sau

- Không tạo hay sửa số liệu và output. Mọi con số trong phần giải thích lấy từ output thực thi trên máy mình.
- Không xóa hay sửa assertion, không hạ ngưỡng. `git diff` của `notebooks/*.py` chỉ có dòng thêm.
- Không dùng API key hay dữ liệu thật; lab chạy offline với dữ liệu giả.

Mình đã đọc lại các phần giải thích và reflection, và chịu trách nhiệm giải thích được mã nguồn cùng kết quả khi được hỏi.
