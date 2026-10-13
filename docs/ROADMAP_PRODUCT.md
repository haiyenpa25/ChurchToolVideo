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

- [x] Chọn đoạn trực tiếp trên transcript, đồng bộ phát video và waveform.
- [x] AI đề xuất clip theo mục tiêu, độ dài và phong cách; hiển thị lý do chọn để biên tập viên duyệt.
- [x] Từ điển tên riêng, thuật ngữ Hội Thánh và cách viết Kinh Thánh dùng chung khi soát phụ đề.
- [x] Kiểm tra trước khi render: dung lượng, font/logo, thời lượng, vùng an toàn phụ đề và encoder.
- [x] Hủy tác vụ và phục hồi luồng làm việc khi tác vụ bị gián đoạn.

## Đợt 3 — Quản lý và phát hành

- [x] Sao lưu/khôi phục dự án kèm tài sản, chính sách lưu trữ và dung lượng.
- [x] Theo dõi trạng thái clip: đề xuất, đang chỉnh, đã duyệt, đã xuất, đã đăng.
- [x] Gói xuất theo nền tảng: video, SRT, tiêu đề, mô tả và ảnh bìa.
- [x] Thống kê thời gian biên tập, lỗi render và hiệu quả các preset để ưu tiên cải tiến tiếp.

### Dùng các phần mới

- **Transcript và waveform:** mở nhóm tương ứng trong bước Duyệt clip. Tải transcript, chọn Bắt đầu/Kết thúc ở từng câu và thêm clip. Nhấn nút phát ở câu hoặc waveform để chuyển vị trí; câu đang phát và con trỏ waveform đồng bộ với video. Waveform được tính khi bạn yêu cầu, giới hạn số điểm hiển thị và đọc âm thanh theo từng khối.
- **AI và từ điển:** mở nhóm Mục tiêu AI và từ điển Hội Thánh. Chọn mục tiêu, phong cách, 60/75/90 giây và 3–5 clip. Các tùy chọn dùng cho cả Copy Prompt và gọi API. AI trả lý do chọn để bạn đọc khi duyệt. Từ điển lưu trên SQLite, bổ sung vào prompt Whisper và yêu cầu soát phụ đề; không tự thay lời giảng. API trực tiếp vẫn cần key/model trong `.env` theo hướng dẫn README; không có key thì dùng Copy Prompt.
- **Kiểm tra trước render:** nút kiểm tra cho biết số video, dung lượng ước lượng/trống và lỗi tài sản/encoder. Giao diện tự kiểm tra lại trước khi xuất. Ước lượng dung lượng có phần dự phòng, không phải dự báo chính xác kích thước file. Cảnh báo vùng phụ đề và thời lượng cần người biên tập xem lại.
- **Hủy tác vụ:** nút Hủy xuất hiện khi theo dõi tác vụ. Tác vụ còn chờ được bỏ qua; FFmpeg render đang chạy được dừng; Whisper và yêu cầu mạng dừng ở lần kiểm tra tiến độ tiếp theo. Có thể cần chờ bước tải model, nhận dạng hoặc yêu cầu API hiện tại kết thúc. Những clip đã render xong vẫn ở thư viện. Dự án được giữ để mở lại và chạy lại sau gián đoạn; không tiếp tục giữa một lần suy luận hoặc encode.
- **Sao lưu:** trong bước Duyệt clip, chọn Sao lưu dự án và video gốc. ZIP chứa phiên bản biên tập hiện tại, video gốc, JSON/SRT/VTT hiện có và logo của dự án, kèm SHA-256. Giới hạn 20 GB tài sản và 5 MB manifest. Thư viện video đã xuất và toàn bộ lịch sử cũ không nằm trong gói này; video có thể render lại, thư viện có ZIP tải riêng. Nhập ZIP trong Bài giảng → Sao lưu và thống kê tạo ID mới, giữ dữ liệu cũ và yêu cầu duyệt lại các clip. Các preset/từ điển dùng chung không bị ghi đè khi nhập.
- **Lưu trữ:** bản sao nằm trong `workspace/backups`, được giữ đến khi bạn xóa bằng nút Xóa bản sao. Dọn dẹp tệp tạm không xóa bản sao, video gốc hoặc thư viện. Bảng thống kê hiển thị dung lượng các bản sao. Nên tải một bản sang ổ đĩa khác; sao lưu trên cùng ổ đĩa chưa bảo vệ khỏi hỏng ổ.
- **Phát hành:** trạng thái Đề xuất/Đang chỉnh/Đã duyệt hiện trong trình biên tập; Đã xuất/Chờ đăng/Đã đăng và link bài đăng lưu trong thư viện, có bộ lọc. Gói phát hành theo nền tảng dùng video đã render đúng tỉ lệ, kèm SRT nếu có, mô tả, metadata và ảnh bìa JPEG lấy từ video. Gói không tự đăng lên tài khoản mạng xã hội.
- **Thống kê:** số dự án/clip đã duyệt, thời gian biên tập ước lượng, thời gian tác vụ (gồm hàng đợi), lỗi/hủy và mức dùng preset. So sánh preset theo số clip duyệt, thời gian chỉnh và lỗi render còn lưu; đây là chỉ số vận hành, chưa đo lượt xem hoặc chất lượng nội dung. Phạm vi là 100 dự án gần nhất và các tác vụ còn lưu, nên việc dọn lịch sử tác vụ ảnh hưởng thống kê.


## Kiểm chứng đợt 1

Ngày 13/10/2026: `.venv\Scripts\python -m pytest -q` đạt **180 test**. Test trình duyệt dùng dữ liệu mẫu và render FFmpeg thực, không gọi dịch vụ LLM hoặc tải mô hình Whisper. Sau chỉnh bố cục điện thoại, test trình duyệt liên quan cũng đã chạy lại và đạt.

## Kiểm chứng đợt 2–3

Bộ test mở rộng kiểm tra chọn transcript, từ điển, cấu hình prompt, hủy hàng đợi và FFmpeg thật, ZIP an toàn/checksum, khôi phục không ghi đè và gói phát hành có JPEG thật. Test trình duyệt chạy xuyên suốt từ chọn câu tới sao lưu, nhập lại và tải gói phát hành. Ngày 13/10/2026: `.venv\Scripts\python -m pytest -q` đạt **195 test** trong 335,26 giây; `python -m compileall -q app` và `git diff --check` cũng đạt. Bản chạy thử đầy đủ tại `http://127.0.0.1:8002` đã được kiểm tra HTTP 200 cho trang chính, preset, từ điển, thống kê và danh sách sao lưu. Chưa gọi LLM thật vì máy chưa có API key/model; các tích hợp LLM được kiểm thử bằng mock.
