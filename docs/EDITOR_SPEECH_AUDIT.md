# Rà soát biên tập và nhận dạng — 14/10/2026

## Biên tập

- Bố cục dùng cột clip gọn, khung video lớn ở giữa và bảng công cụ 370–400 px bên phải. Trên màn hình nhỏ, các vùng xếp dọc. Chỉ hiện công cụ của clip đang chọn.
- **Chỉnh khung nguồn** hiển thị toàn bộ video gốc và khung crop có thể kéo. **Bản mô phỏng** vẽ vùng crop/zoom hoặc nền mờ theo tỷ lệ clip lên canvas; phụ đề dùng dữ liệu và mẫu của clip.
- Mô phỏng không thay thế render: tự căn khuôn mặt, logo, cắt khoảng lặng, nhạc nền và một số hiệu ứng cần kiểm tra bằng **Render thử 12 giây**. Bản thử dùng cùng renderer FFmpeg với xuất video, giữ cài đặt hiện tại, lấy tối đa 12 giây đầu qua các đoạn ghép.
- Bản thử không đổi revision dự án hoặc thêm vào thư viện. File được chuyển vào `workspace/tmp/previews`, có thể hủy qua hàng đợi tác vụ và được dọn theo cơ chế file tạm.
- Soát phụ đề có video riêng, nghe từng câu, nút Sửa và nút cập nhật transcript vào các clip. Việc cập nhật có xác nhận vì thay thế chữ chỉnh riêng trong clip; có thể Hoàn tác và cần duyệt lại clip.

## Nhận dạng giọng nói

Các vấn đề đã xác nhận trong mã nguồn:

1. Mặc định cài mới là `base` mặc dù HTML chọn turbo; trạng thái server có thể ghi đè HTML. Đã đồng bộ mặc định thành `large-v3-turbo`. Riêng `.env` trên máy kiểm tra đã dùng turbo từ trước, nên đây không phải nguyên nhân duy nhất của lỗi đang gặp.
2. Từ điển riêng được nối cuối prompt và dễ bị cắt mất. Đã ưu tiên tên riêng trước từ vựng chung, giới hạn prompt theo tokenizer thực tế thay vì giả định 65 từ tương đương một số token cố định.
3. Cấm lặp cụm ba token và phạt lặp có thể làm mất các danh xưng lặp trong lời giảng. Đã bỏ cấm lặp cứng, dùng nhiệt độ 0 và beam search.
4. Chế độ mặc định **Ưu tiên chất lượng lời giảng** dùng giải mã tuần tự với ngữ cảnh cửa sổ trước. Chế độ nhanh vẫn dùng batching trên GPU; CPU fallback giữ chế độ đã chọn.
5. Lựa chọn tự nhận diện ngôn ngữ trước đây bị đổi ngầm thành `vi`. Đã truyền đúng chế độ tự nhận diện; giao diện vẫn mặc định tiếng Việt.
6. Lưu `original_text` cạnh chữ đã chuẩn hóa trong transcript mới để còn đối chiếu. Transcript và clip cũ không bị tự động viết lại.

Đối chiếu triển khai với [mã nguồn chính thức faster-whisper](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py), cùng mã thư viện đang cài trong `.venv`.

## Thử nghiệm âm thanh thật

Đã chạy Whisper CUDA trên 60 giây đầu của video có sẵn trong dự án, lưu kết quả riêng dưới `workspace/tmp/speech_audit/`; không ghi đè phụ đề đang dùng.

- Cấu hình cũ có các lỗi như “Đất Chúa trời”, “chúng кон”, “nhân dân Chúa…”.
- Cấu hình giữ ngữ cảnh trên cùng đoạn âm thanh cho ra “Đức Chúa Trời”, “chúng con”, “Nhân danh Chúa…”.
- Vẫn còn lỗi như “Chúa cha tự ai”, “đồng an toàn”. Chạy lại cả bước lọc âm hiện tại cũng chưa giải quyết hết các câu này. Không dùng thay thế toàn cục để đoán nội dung người nói.

Đây là kiểm tra trên một đoạn âm thanh, không phải điểm WER hay cam kết độ chính xác toàn bài. Muốn đo chất lượng đầy đủ cần bản chép tay đã nghe kiểm chứng, nhiều giọng nói và điều kiện thu âm. Người dùng cần bóc lại bằng cấu hình mới để có transcript mới; chuẩn hóa chính tả đơn thuần không thể phục hồi mọi từ đã nghe sai.
