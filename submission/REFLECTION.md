# Phản tư: Lakehouse Anti-Patterns & Phòng tránh

**Anti-pattern: Stale External Vector Index (Lifecycle Bug)**

Trong các hệ thống RAG và Agentic AI xử lý dữ liệu người dùng, vector embeddings thường được sync ra external vector database (như Pinecone/Milvus) để phục vụ ANN search. Anti-pattern xuất hiện khi hệ thống chỉ thực hiện đồng bộ một chiều (one-way upsert) mà bỏ qua luồng xoá (deletions).

Khi người dùng thực thi quyền riêng tư (Right to be Forgotten theo GDPR/Luật Dữ liệu cá nhân), dữ liệu gốc trong Lakehouse được xoá qua `DELETE`/`MERGE`, nhưng external index vẫn giữ vector cũ và tiếp tục trả văn bản đã xoá vào prompt của LLM. Điều này dẫn tới rò rỉ dữ liệu nghiêm trọng và vi phạm tuân thủ pháp lý.

**Cách phòng tránh:**
1. **Kiến trúc đồng bộ hướng sự kiện (Event-driven Sync):** Bắt buộc external index phải subscribe luồng Change Data Feed (Delta CDF hoặc Iceberg Change Log) để nhận kịp thời các `delete` event và evict vector ngay lập tức.
2. **In-table Vector Search:** Với quy mô vừa và nhỏ (dưới 100K–1M vectors), lưu vector trực tiếp trong Parquet và truy vấn SQL/DuckDB cục bộ (như NB7) để đồng nhất lifecycle dữ liệu.

*(Phạm vi AI: Xem chi tiết tại [AI_USAGE.md](AI_USAGE.md))*
