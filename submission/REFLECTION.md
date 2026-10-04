# K4-Track02-Day18 — Reflection

Trong các Lakehouse Anti-Patterns, **"Stale External Vector Index Desync"** (kiểm chứng tại NB7) là rủi ro phổ biến nhất trong hệ thống GenAI và RAG thực tế.

Khi lưu trữ embeddings trong Lakehouse nhưng lại phục vụ truy vấn qua external vector database độc lập, bài toán đồng bộ vòng đời dữ liệu rất dễ bị phá vỡ:
1. Khi có yêu cầu xoá dữ liệu người dùng (GDPR Right-to-be-Forgotten) hoặc cập nhật tài liệu trên Delta/Iceberg, nếu external index không tiêu thụ Change Data Feed (CDF), index vẫn giữ vector cũ và tiếp tục trả về thông tin đã thu hồi.
2. Reindex định kỳ tốn kém lớn về chi phí GPU/CPU và luôn tồn tại độ trễ dữ liệu.

**Giải pháp phòng tránh:** Bắt buộc đồng bộ real-time dựa trên CDC/CDF từ transaction log của Lakehouse sang vector index, hoặc truy vấn vector trực tiếp trên Lakehouse bằng Parquet/DuckDB để đảm bảo tính nhất quán ACID.

*(Khai báo AI: Sử dụng AI hỗ trợ rà soát rubric và định dạng nộp bài; toàn bộ lab thực thi cục bộ).*
