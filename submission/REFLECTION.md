# Reflection

Anti-pattern tôi chọn phân tích là tách embeddings khỏi dữ liệu nguồn nhưng
chỉ đồng bộ upsert, bỏ qua delete. Với hệ thống RAG có tài liệu thường xuyên
được sửa hoặc thu hồi, index sẽ chứa vector cũ và retrieval có thể trả về
tài liệu không còn trong version hiện tại của lakehouse.

NB7 tái hiện trực tiếp sự lệch vòng đời này: xóa theo subject trong bảng
không cập nhật bản sao external index. Việc index vẫn trả ID đã xóa cho thấy
đồng bộ thành công lúc ingest chưa đủ để bảo đảm tính đúng đắn lâu dài.

Cách phòng tránh là coi lakehouse là nguồn dữ liệu chuẩn, index là cấu trúc
dẫn xuất có thể xây dựng lại. Consumer phải nhận insert/update/delete qua CDF,
lưu watermark và xử lý idempotent; cần theo dõi độ trễ, đối chiếu ID và phiên
bản embedding model. Version pin giúp tái lập tập dữ liệu, còn retention và
vacuum quyết định thời gian tồn tại bản cũ.

AI: Codex hỗ trợ thực thi, kiểm tra và soạn bản reflection này; xem
[AI_USAGE.md](AI_USAGE.md). Người nộp cần rà soát và điều chỉnh theo góc nhìn cá nhân.
