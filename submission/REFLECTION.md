# Reflection — K4-Track02-Day18 Lakehouse Lab

Trong các hệ thống RAG và LLM Observability hiện đại, anti-pattern **Decoupled External Vector Store Desynchronization** (sự phân rã vòng đời giữa Vector Store ngoại vi và Lakehouse) là nguy cơ dễ vướng nhất. 

Khi thực hiện yêu cầu bảo mật/GDPR hoặc dọn dữ liệu rác trong Lakehouse qua `DELETE`/`MERGE`, dữ liệu biến mất trong bảng nhưng external index không nhận được sự kiện xóa nếu pipeline streaming chỉ lắng nghe thao tác insert/append. Hậu quả là semantic search vẫn trả về các "ghost chunks" đã bị xóa, dẫn đến rò rỉ dữ liệu cá nhân hoặc tạo ra câu trả lời sai lệch (như đã tái hiện thực tế tại NB7). 

**Giải pháp:** Quản lý vector trực tiếp trong Lakehouse với kiểu mảng/int8 trên định dạng mở (Delta/Iceberg + DuckDB), hoặc bắt buộc sử dụng Change Data Feed (CDF) từ transaction log để đồng bộ nghiêm ngặt cả thao tác `delete` sang external index.

*(Khai báo AI: Sử dụng AI để đối chiếu tiêu chí rubric và soát lỗi kiểm thử).*
