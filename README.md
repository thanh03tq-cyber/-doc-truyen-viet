# Đọc Truyện Việt (bản thử nghiệm)

## Triển khai trên Render
1. Tải toàn bộ nội dung repository GitHub.
2. Trên Render, tạo Web Service và kết nối repository này.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Sau khi deploy, mở URL Render được cấp.

## Giới hạn
- Bản này thử nghiệm trích xuất văn bản từ website được cho phép; mặc định chỉ cho phép zongheng.com.
- Không vượt đăng nhập, paywall, CAPTCHA hoặc biện pháp bảo vệ.
- Website dùng JavaScript hoặc cấu trúc riêng có thể cần bộ trích xuất riêng.
- Chưa tích hợp dịch AI tự động. Giao diện đọc thử hiện cho phép dán văn bản và dùng giọng đọc sẵn có của Safari.
