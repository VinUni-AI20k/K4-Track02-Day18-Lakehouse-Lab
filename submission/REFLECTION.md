# Reflection — Anti-pattern dễ vướng nhất: small-file problem

Hệ thống tôi quan tâm là pipeline ghi log LLM-observability (như NB4/NB6): request đến liên tục và writer
thường commit mỗi vài giây để dữ liệu "tươi", nên đây là chỗ dễ sinh nhiều file nhỏ nhất. Trong NB6, 100K dòng
qua 200 commit tạo 200 file, trung bình 51.5 KB; compaction đưa về 11 file (18× ít hơn). NB2 cho thấy sau
OPTIMIZE + Z-ORDER truy vấn điểm nhanh khoảng 10× và chỉ phải mở 1/55 file. Hại không chỉ ở tốc độ: mỗi file là
một request GET và một dòng metadata (NB5: metadata gấp ~2.9 lần dữ liệu ở 10 dòng/file), và chi phí object
store tăng theo số file chứ không theo dung lượng.

Cách phòng tránh: tăng trigger interval/batch ở writer thay vì dọn về sau; lập lịch compaction + clustering theo
khóa hay lọc (`user_id`, `ts`) cùng checkpoint log; ghép expiry/vacuum với quét orphan có age guard (NB6 cho
thấy `VACUUM` của `deltalake` bỏ sót 3 file mồ côi chưa từng commit); theo dõi số file và kích thước file trung
bình như một SLO.

*AI: Claude Code hỗ trợ chạy lab, thêm cell bằng chứng và soạn nháp văn bản; chi tiết ở [AI_USAGE.md](AI_USAGE.md).*
