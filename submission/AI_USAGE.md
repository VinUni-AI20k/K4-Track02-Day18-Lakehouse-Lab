# Khai báo sử dụng AI

**Công cụ:** Claude Code (Anthropic, model Claude Opus 5.5), chạy trong terminal trên máy cá nhân.

## AI đã hỗ trợ những gì

| Phần | Mức hỗ trợ |
|---|---|
| Môi trường | Tạo venv, chuyển từ `pip` sang `uv` khi pip quá chậm, chạy smoke/pytest/run_all và lưu log vào `evidence/` |
| Thực thi notebook | Chuyển `.py` sang `.ipynb` bằng jupytext và thực thi bằng `nbconvert --execute`. Toàn bộ output là output thật của máy tôi |
| Cell bổ sung | Viết cell in `_delta_log` (NB1), kiểm tra chặn write thật (NB1), assert chất lượng Gold (NB4). Không sửa logic gốc, không hạ ngưỡng |
| Phần giải thích | Nháp các cell "Phân tích kết quả" dựa trên output thật. Tôi đã đọc lại và đối chiếu từng con số |
| Bonus | Nháp `ARCHITECTURE.md` và viết PoC. PoC đã chạy thật, log ở `evidence/poc_bonus.txt` |
| Reflection | Nháp theo chủ đề tôi chọn (hệ thống LLM/AI app) |

## Những gì đã được kiểm chứng thay vì chấp nhận ngay

- NB4 ra 8 ngày thay vì 7: đã kiểm chứng nguyên nhân là `CAST(ts AS DATE)` đổi theo múi giờ máy (UTC+7).
  Ngày đầu chỉ có ~17h dữ liệu.
- NB6 báo "5 files you pay for" dù chỉ cài 3 orphan: đã kiểm chứng 2 file còn lại là checkpoint mà deltalake tự ghi
  ở v99 và v199. Dòng "0 B" là do `vacuum()` trả về đường dẫn tương đối.
- PoC lần đầu FAIL vì 66 false positive (regex số điện thoại khớp vào token HMAC toàn chữ số), lần hai FAIL vì
  generator có lỗi biên thời gian. Cả hai được sửa ở **nguyên nhân gốc**, không nới assert.

## Trách nhiệm của tôi

Tôi đã đọc lại toàn bộ phần giải thích, reflection và bonus. Tôi chịu trách nhiệm giải thích được mã nguồn và
kết quả khi được hỏi, theo [RULES.md](../docs/RULES.md).
