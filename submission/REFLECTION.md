# Reflection — K4-Track02-Day18 Lakehouse Lab

Lựa chọn anti-pattern: Vector Lifecycle Bug (tách rời Vector DB khỏi Lakehouse).

Khi xử lý dữ liệu multimodal và phản hồi LLM, kiến trúc thường lưu embeddings ở Vector DB độc lập và metadata ở Lakehouse. Do thiếu cơ chế đồng bộ transaction, khi người dùng yêu cầu xóa dữ liệu hoặc tài liệu được cập nhật ở Lakehouse, hệ thống thường bỏ quên sự kiện xóa trên Vector DB. Hậu quả là external index vẫn trả về vector cũ, khiến mô hình sinh phản hồi chứa thông tin vi phạm quyền riêng tư hoặc sai lệch, tương tự như lỗi tái hiện ở NB7 khi bảng đã xóa nhưng index vẫn tìm thấy kết quả.

Cách phòng tránh: Sử dụng Lakehouse làm nguồn chân lý duy nhất (Single Source of Truth), lưu embeddings trực tiếp trong bảng Delta hoặc Iceberg và kích hoạt Change Data Feed (CDF) để đồng bộ hóa có kiểm soát phiên bản sang vector index phái sinh khi cần mở rộng quy mô.

Khai báo AI: Hỗ trợ tổng hợp thông tin từ các ý chính, chỉnh lại ngôn từ cho các câu hỏi của bài lab.