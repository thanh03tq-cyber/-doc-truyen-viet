# Đọc Truyện Việt 2.0 (Vercel / iPhone)

## Cập nhật repository GitHub
Sao lưu mã nguồn cũ trước. Tải lên và ghi đè các file ở thư mục gốc: `main.py`, `index.html`, `requirements.txt`, `vercel.json`, `README.md`.
Vercel sẽ tự triển khai nếu đã liên kết repository. Framework preset: FastAPI (hoặc Other với rewrite trong vercel.json).

## Environment Variables (Vercel)
- `GEMINI_API_KEY`: **Secret**, API key từ Google AI Studio. Không dán vào GitHub hay HTML.
- `GEMINI_MODEL` (tùy chọn): mặc định `gemini-2.5-flash`; phải là model tài khoản được cấp quyền, có thể thay đổi theo chính sách Google.
- `ALLOWED_DOMAINS` (tùy chọn): danh sách tên miền phân cách bằng dấu phẩy, mặc định `zongheng.com,qidian.com,17k.com,fanqienovel.com,shuqi.com`. Chỉ thêm nguồn được phép truy cập.

## Lưu ý
- Trích xuất đa nguồn là phương pháp chung, không bảo đảm tất cả website, đặc biệt trang yêu cầu JavaScript, CAPTCHA hoặc đăng nhập. Tôn trọng robots.txt; không vượt tường phí.
- Một chương dài được chia thành nhiều phần gửi lần lượt sang Gemini. Dịch dài có thể vượt giới hạn thời gian của Vercel hoặc hạn mức Gemini; người dùng có thể bấm dịch lại.
- Auto-next phụ thuộc vào liên kết chương tiếp theo trong HTML. Khi đọc cuộn tới cuối, app chuyển chương; khi TTS kết thúc, app thử chuyển và đọc tiếp. iOS Safari có thể hạn chế phát âm thanh tự động khi khóa màn hình.
- Gemini API có hạn mức và có thể tính phí nếu bật billing. Kiểm tra hạn mức tại Google AI Studio.
- Trước khi sử dụng hãy thử `/health` và thử với một chương được phép truy cập.
