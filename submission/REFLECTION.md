### Lakehouse Anti-Pattern: Lifecycle Skew trong Vector Search
Một anti-pattern phổ biến em học được là việc sử dụng Vector DB độc lập, tách rời khỏi Lakehouse chính để phục vụ hệ thống AI/RAG.
- **Vấn đề:** Các đường ống đồng bộ (sync pipeline) thường chỉ biết thêm mới (upsert) mà bỏ qua các sự kiện xóa (delete). Khi người dùng yêu cầu xóa dữ liệu cá nhân (Right to erasure), dữ liệu trong Lakehouse bị xóa nhưng Vector DB vẫn ngầm giữ lại. Điều này dẫn đến rò rỉ dữ liệu nhạy cảm và vi phạm nghiêm trọng tính tuân thủ pháp lý (Compliance Bug).
- **Cách phòng tránh:** Lưu trữ trực tiếp cột vector embeddings ngay trong bảng Delta Lakehouse và sử dụng các công cụ SQL (như DuckDB) để truy vấn. Nếu bắt buộc phải dùng External Vector DB, phải thiết lập Change Data Feed (CDF) để đồng bộ cả các sự kiện DELETE.
- **AI Usage:** Em có sử dụng AI Assistant (Gemini) trong quá trình gỡ lỗi và tóm tắt các khái niệm phức tạp về kiến trúc Lakehouse.
