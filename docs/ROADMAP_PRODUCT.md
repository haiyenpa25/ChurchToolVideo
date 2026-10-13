# Cải tiến sản phẩm ChurchToolVideo

Ứng dụng phục vụ một người biên tập trên một máy. Preset mặc định mang tên **Hội thánh Tin lành Thạnh Mỹ Lợi**. Roadmap an toàn dữ liệu và ổn định kỹ thuật trước đó nằm trong [ROADMAP_HARDENING.md](ROADMAP_HARDENING.md).

## Đợt 1 — Biên tập dễ dùng và kiểm soát nội dung

- [x] Giao diện mặc định có ba bước: **Bài giảng → Duyệt clip → Xuất video**. Trong bước duyệt có kiểm tra phụ đề và chọn clip; chế độ nâng cao giữ các tùy chọn chi tiết.
- [x] Preset Hội Thánh lưu tên, màu nhấn phụ đề, mẫu chữ, font, logo PNG và câu kết. Có thể tạo nhiều preset, sửa preset hoặc áp dụng cho danh sách clip. Áp dụng giữ nguyên lời giảng và mốc cắt.
- [x] Hoàn tác/làm lại tối đa 100 thay đổi trong phiên biên tập; phím Ctrl+Z/Ctrl+Y ngoài ô nhập liệu. Lịch sử trên SQLite giữ tối đa 50 phiên bản mỗi dự án, tồn tại qua lần khởi động lại. Khôi phục giữ video gốc, xóa liên kết kết quả render cũ và vẫn giữ các phiên bản trước.
- [x] Nghe 15 hoặc 30 giây trước/sau đoạn cắt từ bài giảng gốc; ghi chú và xác nhận duyệt từng clip. Thay đổi tiêu đề, lời hoặc mốc cắt hủy xác nhận cũ. Giao diện yêu cầu duyệt trước khi xuất; có lựa chọn rõ ràng **Xuất bản nháp**.
- [x] Kiểm thử API, lưu trữ, dựng phụ đề và luồng trình duyệt với render FFmpeg thực; kiểm tra bố cục desktop và điện thoại.

### Cách dùng

1. Mở hoặc tải bài giảng, bóc băng và kiểm tra phụ đề.
2. Tạo danh sách clip. Chọn preset Hội Thánh, nhấn **Áp dụng cho các clip**; nghe ngữ cảnh, sửa nội dung và tick xác nhận duyệt.
3. Xuất từng clip hoặc cả danh sách. Muốn chỉnh thêm encoder, âm thanh, khung hình hoặc kiểu chữ, mở các nhóm tùy chọn hoặc bật **Chế độ nâng cao**.

Preset ban đầu dùng màu vàng `#F5C542`, font Noto và mẫu phụ đề nổi bật. Đây là giá trị mẫu có thể sửa; chưa gán logo hoặc câu kết vì chưa có tài sản/nội dung được cung cấp. Câu kết chỉ là chữ hiện ở cuối clip, không thêm lời nói hoặc kéo dài video. Sửa preset không tự thay đổi các clip đã có: cần áp dụng lại.

Hoàn tác trong phiên và lịch sử đã lưu chỉ giữ nội dung biên tập; không phải bản sao lưu video. Xung đột phiên bản được báo lỗi để tránh một tab cũ ghi đè tab mới. Cổng API render vẫn hỗ trợ khách cũ với `require_review=false`; giao diện mới gửi `require_review=true`, trừ khi người dùng chọn xuất bản nháp.

## Đợt 2 — Biên tập nhanh hơn

- [ ] Chọn đoạn trực tiếp trên transcript, đồng bộ phát video và waveform.
- [ ] AI đề xuất clip theo mục tiêu, độ dài và phong cách; hiển thị lý do chọn để biên tập viên duyệt.
- [ ] Từ điển tên riêng, thuật ngữ Hội Thánh và cách viết Kinh Thánh dùng chung khi soát phụ đề.
- [ ] Kiểm tra trước khi render: dung lượng, font/logo, thời lượng, vùng an toàn phụ đề và encoder.
- [ ] Hủy tác vụ và phục hồi luồng làm việc khi tác vụ bị gián đoạn.

## Đợt 3 — Quản lý và phát hành

- [ ] Sao lưu/khôi phục dự án kèm tài sản, chính sách lưu trữ và dung lượng.
- [ ] Theo dõi trạng thái clip: đề xuất, đang chỉnh, đã duyệt, đã xuất, đã đăng.
- [ ] Gói xuất theo nền tảng: video, SRT, tiêu đề, mô tả và ảnh bìa.
- [ ] Thống kê thời gian biên tập, lỗi render và hiệu quả các preset để ưu tiên cải tiến tiếp.

Các mục đợt 2–3 là backlog, chưa được triển khai trong đợt 1. Tích hợp dịch vụ AI hoặc đăng bài sẽ cần cấu hình tài khoản tương ứng.

## Kiểm chứng đợt 1

Ngày 13/10/2026: `.venv\Scripts\python -m pytest -q` đạt **180 test**. Test trình duyệt dùng dữ liệu mẫu và render FFmpeg thực, không gọi dịch vụ LLM hoặc tải mô hình Whisper. Sau chỉnh bố cục điện thoại, test trình duyệt liên quan cũng đã chạy lại và đạt.
