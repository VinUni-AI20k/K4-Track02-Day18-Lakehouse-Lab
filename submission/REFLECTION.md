# Reflection

Trong pipeline quan sát LLM, các request thường đến liên tục theo micro-batch. Mỗi batch tạo một file riêng; output thực tế của NB6 bắt đầu với 200 file cho 100.000 dòng, trung bình chỉ khoảng 51,5 KB/file. Kiểu small-file này làm tăng chi phí lập kế hoạch và số object-storage GET, dù tổng lượng dữ liệu không đổi. Cách phòng tránh là gom batch phù hợp, theo dõi số file và kích thước file, rồi lập lịch compaction/clustering có xét cửa sổ reader và retention; không vacuum quá sớm vì có thể làm mất time travel hoặc ảnh hưởng reader cũ.

AI được dùng để đối chiếu output notebook với ngưỡng rubric và hỗ trợ soạn phần giải thích. Các số liệu trong phần nộp được lấy từ output đã lưu, không tạo output giả.
