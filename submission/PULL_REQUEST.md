# [K4-Track02-Day18] HoangThaiDat - 2A202602959 - Lakehouse Lab [+bonus]

Hoang Thai Dat — MSSV 2A202602959. Hoàn thành phần bắt buộc NB1–NB8 bằng
đường lightweight trên Windows/Python 3.11.3, cài dependencies bằng uv.

Bổ sung kiểm tra schema enforcement thực tế, metrics MERGE, kiểm tra Gold
độc lập và loại UNCLASSIFIED; giữ nguyên các ngưỡng rubric. Tám notebook
đã thực thi có output và diễn giải trong [submission/notebooks](notebooks/).
Bằng chứng gồm [ảnh render output](screenshots/), [metrics](evidence/metrics.json),
[reflection](REFLECTION.md), [thông tin môi trường](INFO.md) và [khai AI](AI_USAGE.md).

Validation: smoke 9/9, pytest 24/24, headless 8/8; kiểm tra notebook không có
error output, ngưỡng số học và cấu trúc bài nộp PASS. Pytest có cảnh báo ghi
cache do sandbox, không có test thất bại.

PNG là output render có nhãn rõ nguồn, không phải screenshot giao diện.
NB8 là mô phỏng offline; replay kiểm tra số bước và provenance buckets chỉ
minh họa. Không chạy Spark. Xem [báo cáo](README.md).

Bonus A: [architecture](bonus/ARCHITECTURE.md) và PDF 6 trang, 6 decisions với
12 alternatives, 6 failure modes, cost model có nguồn official và MVP một tuần.
[PoC có output](bonus/poc/replay_safe.ipynb) kiểm tra crash/replay/late revision
và lineage snapshot; không suy rộng thành benchmark production. Storage tháng
31 ngày 4.971,56 USD gồm toàn bộ Kinesis, phụ thuộc nén detail >=4:1;
7 ngày là TTL đọc, physical purge tối đa 24h sau đó. Xem [bonus README](bonus/README.md).

Đây là nội dung PR chuẩn bị ở local; chưa tạo PR hoặc gửi bài qua kênh lớp.
