# Reflection

Anti-pattern tôi thấy dễ gặp nhất là **small-file problem**. Một pipeline streaming có thể hoàn toàn đúng về schema và dữ liệu nhưng vẫn tạo hàng triệu file nhỏ vì commit quá thường xuyên. Hệ thống khi đó tốn thời gian list/open object, metadata phình to và file statistics quá rộng để pruning hiệu quả; chi phí tăng nhanh hơn dung lượng dữ liệu.

Kết quả NB6 làm rủi ro này cụ thể hơn: 200 file được compact còn 11 file, tức giảm khoảng 18 lần, và clustering giúp bỏ qua 90% file cho point query. Cách phòng tránh của tôi là đặt target file size, theo dõi file count/average size, chạy compaction và clustering theo lịch, đồng thời điều chỉnh trigger của writer để không liên tục tạo micro-file. Snapshot expiry phải đi cùng orphan sweep và retention an toàn; chỉ giảm số snapshot chưa chắc đã giảm dung lượng vật lý.

Tôi sử dụng AI để hỗ trợ cài môi trường, chạy kiểm tra, tổng hợp số đo và rà soát cách diễn giải. Tôi đã đối chiếu lại các kết quả bằng output notebook và assertion của repo.
