# REFLECTION

**Anti-pattern chọn: small-file problem (quá nhiều file nhỏ)**

Trong NB6, bảng Delta ban đầu gồm 200 file nhỏ, trung bình khoảng 51 KB mỗi file, xa mức 128–512 MB thường khuyến nghị. Sau compaction còn 11 file, giảm 18 lần. Mỗi file thêm một lượt GET và một mục metadata cần đọc, nên chi phí truy vấn tăng theo số file chứ không theo lượng dữ liệu.

Dữ liệu LLM observability dễ rơi vào tình huống này vì ghi theo sự kiện: mỗi request hoặc mỗi lô nhỏ tạo một commit. Throughput càng cao, file tích lũy càng nhanh, trong khi delta-rs và Delta mã nguồn mở mặc định không tự gom file.

Cách phòng tránh: gom ghi theo micro-batch (đệm vài phút rồi flush một file lớn), lên lịch OPTIMIZE định kỳ, và theo dõi số file cùng kích thước trung bình như một chỉ số vận hành. Compaction chỉ tạo file mới, nên cần đi kèm vacuum theo retention để thu hồi dung lượng.

*Có dùng AI hỗ trợ chạy lệnh, kiểm tra ngưỡng và soạn nháp; phạm vi chi tiết trong [AI_USAGE.md](AI_USAGE.md).*