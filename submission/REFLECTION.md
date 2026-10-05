# Reflection: Lakehouse Anti-Patterns & AI Systems

Trong các hệ thống RAG và LLM Observability tôi quan tâm, anti-pattern dễ vướng phải nhất là **Stale external indexes / uncoordinated deletes**.

Khi triển khai RAG quy mô lớn, dữ liệu tài liệu và hội thoại thường được lưu trên Lakehouse (System-of-Record), sau đó định kỳ trích xuất embedding nạp vào vector database ngoại vi (như Milvus, Pinecone, Qdrant). Khi người dùng thực thi quyền xóa dữ liệu cá nhân (Right-to-be-Forgotten theo GDPR / Nghị định 13/2023) hoặc tài liệu bị thu hồi, thao tác `DELETE` chỉ diễn ra trên bảng Delta/Iceberg. Do các sync pipeline thường chỉ cấu hình append/upsert một chiều và bỏ sót delete events, vector index bên ngoài vẫn tiếp tục trả về chunk đã xóa vào context của LLM — gây rủi ro pháp lý nghiêm trọng và ô nhiễm thông tin.

Để ngăn chặn, hệ thống bắt buộc phải: (1) kích hoạt Delta Change Data Feed (CDF) để đồng bộ mọi sự kiện `_change_type = 'delete'` sang vector store; hoặc (2) lưu vector và metadata chung một bảng Lakehouse để quản lý vòng đời nhất thể (như bài học ở NB7).

*(Phạm vi sử dụng AI: Chi tiết kê khai tại [AI_USAGE.md](AI_USAGE.md))*

