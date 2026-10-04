# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic, model Claude Opus 5.5).

**Phạm vi hỗ trợ:**

- Đọc output, phát hiện các chỗ in số liệu gây hiểu nhầm trong NB6 (checkpoint tự động bị đếm là orphan,
  dry-run báo `0 B`, in sai tên checkpoint) và chỉnh lại phần in; thay check hardcode ở NB1 bằng cờ thật;
- Soạn nháp phần "📝 Phân tích kết quả" cuối mỗi notebook, `INFO.md`, `REFLECTION.md`
  dựa trên output thực tế của lần chạy đã lưu.

**Không dùng AI để:** tạo số liệu/output giả, sửa output bằng tay, hay hạ ngưỡng để báo PASS.
Mọi con số trong notebook và screenshots là output thật từ máy này.

