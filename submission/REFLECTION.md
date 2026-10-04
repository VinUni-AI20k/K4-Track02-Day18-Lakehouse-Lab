# Reflection

**Anti-pattern: small files và snapshot không được dọn.** Trong NB6, 200 commit nhỏ tạo 200 file (~51 KB/file); compaction giảm còn 11 file (18×). Expire snapshot 20→3 không giải phóng file nào (avro vẫn 40) cho tới khi quét orphan xóa 17 manifest list mồ côi. Tôi quan tâm pipeline log LLM observability: ghi streaming từng micro-batch sẽ tạo đúng tình huống này, chi phí tăng theo số file chứ không theo dung lượng.

**Phòng tránh:** tăng trigger interval/batch size ở writer, lập lịch compaction + clustering theo khóa truy vấn (user_id), chạy expiry và orphan removal thành một cặp có age guard, và giám sát số file, kích thước trung bình, số snapshot.

**Khai báo AI:** tôi dùng Claude Code để dựng môi trường, chạy notebook, đối chiếu số đo với ngưỡng và soạn nháp các Markdown cell. Số liệu lấy từ output thật trên máy tôi; tôi chịu trách nhiệm kiểm tra và hiểu nội dung nộp.
