# Giao diện ChurchVideo — 14/10/2026

Tham khảo các bản thiết kế trong `docs/giao-dien/` và bảng màu Sacred Studio: nền sáng, tím chàm, điểm nhấn cam, ba vùng biên tập trên desktop.

## Luồng sử dụng

1. Chọn video và chuyển thành văn bản có mốc thời gian.
2. Sao chép SRT hoặc SRT kèm yêu cầu sang Gemini/ChatGPT. Dán kết quả vào cùng màn hình. Các mốc liên tiếp ghép thành một clip; dòng trống bắt đầu clip mới. JSON và nhãn CLIP vẫn được hỗ trợ.
3. Xem thử bản ghép. Chỉnh một clip tại một thời điểm qua các tab Nội dung, Phụ đề, Đề tựa, Khung và Âm thanh. Nội dung có sửa chữ, chọn hook, sửa/thêm/xóa/đổi thứ tự đoạn và xác nhận duyệt.
4. Chọn tỷ lệ trên video và kéo vùng crop. Chỉnh crop mặc định lưu riêng cho clip hiện tại; vẫn có lựa chọn khung chung.
5. Xuất một clip hoặc cả dự án. Hộp thoại xuất một clip phản ánh tỷ lệ của clip đó; tỷ lệ chung dùng cho clip không đặt tỷ lệ riêng.
6. Thư viện có tìm kiếm, lọc, xem trước và panel chi tiết để chỉnh thông tin, trạng thái đăng, tải video/SRT/gói phát hành.

## Âm thanh

Nhạc nền áp dụng ở cấp dự án. Hỗ trợ tải tệp tối đa 50 MB/2 giờ, nghe riêng, chỉnh âm lượng lời nói và nhạc, lấy nhạc từ một mốc, đặt độ trễ và fade in/out. FFmpeg trộn nhạc sau khi ghép các đoạn. Video xem trước vẫn phát âm thanh gốc; nghe bản trộn hoàn chỉnh qua video đã xuất.

Nhạc lưu riêng trong `workspace/music`, không bị dọn như âm thanh trích xuất tạm. Bản sao lưu chứa nhạc nền; khôi phục tạo mã tài sản mới.

## Kiểm tra

- Bộ kiểm thử toàn ứng dụng: 364 bài đạt, gồm render FFmpeg thực và luồng trình duyệt.
- Kiểm tra desktop 1440×900 và điện thoại 390×844; không tràn ngang hoặc lỗi JavaScript trong phiên chụp kiểm tra.
- Ảnh giao diện tại `workspace/tmp/ui_sacred/`: `source.png`, `editor.png`, `export.png`, `library.png`, `mobile.png`.
- Kiểm tra chức năng dùng tệp/database tạm. Phiên xem giao diện dùng workspace mẫu tách biệt.

Khởi động lại ứng dụng để tải các API âm thanh mới và làm mới trình duyệt bằng Ctrl+F5 để tải JavaScript/CSS mới.
