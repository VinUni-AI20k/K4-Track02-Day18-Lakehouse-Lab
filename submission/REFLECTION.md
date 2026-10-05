# Bài Thu Hoạch (Reflection) — K4-Track02-Day18 Lakehouse Lab

Một anti-pattern nguy hiểm trong các hệ thống AI/RAG là **"Forgotten Deletes"** (Bỏ quên sự kiện xóa khi đồng bộ Vector Index ngoài).

Khi Lakehouse xóa dữ liệu nhạy cảm theo yêu cầu bảo vệ quyền riêng tư (Nghị định 13/GDPR) hoặc thu hồi tài liệu hết hiệu lực, bảng Delta thực hiện xóa logic trong transaction log. Tuy nhiên, pipeline đồng bộ sang Vector DB (như Milvus/Pinecone) thường chỉ là batch upsert một chiều. Hậu quả là Vector DB trở thành "kho dữ liệu ma", tiếp tục truy xuất văn bản đã xóa cho LLM, gây sai lệch thông tin và vi phạm pháp lý nghiêm trọng.

**Giải pháp phòng tránh:** Bắt buộc kích hoạt Change Data Feed (CDF) trên Delta Lake. Đường ống đồng bộ phải đăng ký lắng nghe stream sự kiện `_change_type = 'delete'` để tự động thu hồi vector tương ứng, hoặc lưu trữ vector trực tiếp trong row Parquet của Lakehouse để hợp nhất vòng đời dữ liệu.

*Khai báo AI: Sử dụng Gemini 3.8 Flash hỗ trợ rà soát code và đối chiếu rubric. Chi tiết tại [AI_USAGE.md](AI_USAGE.md).*
