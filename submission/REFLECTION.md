# Reflection — Anti-pattern: small files

Hệ thống mình quan tâm — log quan sát LLM (request, token, latency như NB4) — dễ vướng **small files**
nhất. Log đến liên tục nên job streaming commit mỗi vài giây: từng commit đều đúng, nhưng tích lũy thành
hàng nghìn file vài chục KB.

Lab đo được cái giá: NB6 có 200 file trung bình 51.5 KB; point query phải mở 11/11 file vì min/max chồng
lấn. Sau compaction còn 11 file (18×), sau Z-order chỉ mở 1/10. NB5 cho thấy small files phạt hai lần:
metadata lớn gấp ~2.9 lần data. Bẫy thứ hai: với deltalake 1.6.6, VACUUM không dọn file từ writer crash,
và PyIceberg expire snapshot không xóa manifest list.

Cách phòng tránh: gom batch ở writer (tăng trigger interval); chạy maintenance định kỳ theo thứ tự
compaction → Z-order theo cột lọc chính (`model`, `date`) → vacuum/expiry với retention ≥ 7 ngày →
orphan sweep có age guard; theo dõi số file và kích thước trung bình mỗi partition như một metric.

**Sử dụng AI:** xem [AI_USAGE.md](AI_USAGE.md).
