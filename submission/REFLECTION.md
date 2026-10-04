# Reflection — Lò Văn Long (2A202602541)

**Anti-pattern:** vector index tách rời khỏi system-of-record (lệch vòng đời embedding).

Mình quan tâm dữ liệu train/RAG. Tài liệu được thêm, sửa, xóa liên tục, và embedding được tính lại mỗi
khi đổi model. Cách làm phổ biến là mỗi đêm upsert sang một vector DB riêng, và đó chính là anti-pattern
này. NB7 đo được: xóa 8 doc của `user_042` thì lakehouse trả 0 hit nhưng index ngoài vẫn trả 8. Nếu sync
chỉ upsert thì index giữ các doc đó mãi. Với RAG, như vậy là trả lời bằng dữ liệu đã bị yêu cầu xóa: lỗi
tuân thủ chứ không chỉ lỗi kỹ thuật. Khi đổi model, vector cũ và mới còn bị trộn lẫn.

Cách phòng tránh:
(1) Lưu embedding cùng dòng với `doc_id`, license, consent và `embedding_model_version`.
(2) Coi index ngoài là bản dẫn xuất, cập nhật từ Change Data Feed (kể cả `delete`) và dựng lại được từ
version bảng đã pin.
(3) Định kỳ đối soát `doc_id` giữa bảng và index.
(4) VACUUM sau retention để xóa thật cả version cũ.

**Sử dụng AI:** xem [AI_USAGE.md](AI_USAGE.md).
