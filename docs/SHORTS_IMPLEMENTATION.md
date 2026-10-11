# Triển khai Ghép Short — Phase 1–6

## Các PR theo thứ tự

| Phase | PR | Nội dung |
|---|---|---|
| 0 | [#1](https://github.com/haiyenpa25/ChurchToolVideo/pull/1) | Dọn nền, seek chính xác, AAC, semaphore và pytest |
| 1 | [#2](https://github.com/haiyenpa25/ChurchToolVideo/pull/2) | ID câu, word timestamps, JSON và chuẩn hóa |
| 2 | [#3](https://github.com/haiyenpa25/ChurchToolVideo/pull/3) | Prompt Short và parser nhóm clip |
| 3 | [#4](https://github.com/haiyenpa25/ChurchToolVideo/pull/4) | Render nhiều part, reframe, concat, loudnorm |
| 4 | [#5](https://github.com/haiyenpa25/ChurchToolVideo/pull/5) | ASS, karaoke, font tiếng Việt, tiêu đề và logo |
| 5 | [#6](https://github.com/haiyenpa25/ChurchToolVideo/pull/6) | UI chỉnh part, xem thử và tải Short |
| 6 | [#7](https://github.com/haiyenpa25/ChurchToolVideo/pull/7) | LLM trực tiếp, SQLite, crop theo khuôn mặt và auth tùy chọn |

Các PR xếp chồng: mỗi PR lấy nhánh Phase trước làm base để chỉ hiện diff của Phase tương ứng. Review/merge theo thứ tự; cập nhật base về main khi nhánh trước đã được merge. Không tự merge trong lần triển khai này.

## Cách dùng

1. Cài `requirements.txt`, chạy server bằng `run_local.bat` hoặc Uvicorn.
2. Upload và bóc băng. Video đã bóc băng từ bản cũ dùng lại SRT được; bóc băng lại để có timestamp từng từ.
3. Copy Prompt Short để dùng ChatGPT/Gemini, hoặc cấu hình key/model trong `.env` và bấm nút gửi transcript đến API LLM đã chọn.
4. Ở Bước 4 chọn Ghép Short 1:30, dán kết quả và phân tích. Kiểm tra ý nghĩa, thời lượng và các part; chỉnh mốc, thứ tự, tiêu đề khi cần.
5. Chọn tùy chọn render, xem thử, lưu dự án hoặc xuất Short và tải MP4/ZIP.
6. Dùng Dự án đã lưu để mở lại video, clip đã chỉnh, kết quả render và theo dõi task sau khi tải lại trang.

## Kiểm tra đã thực hiện

- 42 test pytest trên Windows, gồm kiểm thử Chromium từ upload đến tải MP4 và mở lại dự án sau reload.
- Kiểm tra UI ở desktop 1400 px và điện thoại 390 px; không tràn ngang và không có lỗi JavaScript.
- FFmpeg thực: ba part rải rác ra một MP4 1080×1920, 30fps, H.264/AAC 48kHz, thời lượng trong sai số 0,3 giây; kiểm tra decode và xóa file tạm khi thành công/lỗi.
- Render tiếng Việt “ệ, ữ, ỡ”, kiểm tra ảnh có tiêu đề, karaoke và logo. Timing phụ đề dùng timeline local của part, không làm thay đổi timestamp nguồn khi chuẩn hóa chữ.
- Docker build Phase 4 thành công; 5 test ASS/render trên Linux vượt qua.
- Docker build bản Phase 6 thành công; toàn bộ 41 test backend trên Linux vượt qua (UI Chromium được kiểm tra trên Windows).
- Whisper thật với model tiny trên giọng nói tổng hợp tiếng Anh: 1 sentence và 19 word timestamps; sinh SRT/VTT/JSON.
- OpenCV thật nhận diện khuôn mặt trên mẫu ảnh thử; crop_x lệch tâm 0,216. Có test render expression crop thay đổi theo thời gian và fallback khi không thấy mặt.
- Task/dự án SQLite qua restart; task đang dở được đánh dấu gián đoạn, task hoàn tất giữ kết quả.
- Mock request/response cho OpenAI, Gemini, Claude; không phát sinh gọi API trả phí trong kiểm thử. Có test key không xuất hiện trong response/lỗi.
- Auth kiểm tra API và media cần đăng nhập, cookie HttpOnly, sai mật khẩu và yêu cầu khác origin.

## Giới hạn xác minh

Chưa đánh giá chất lượng bóc băng bằng một bài giảng tiếng Việt thực tế, cảm nhận chỗ nối âm thanh hoặc playback trên điện thoại thật. Kiểm thử UI dùng transcript fixture, còn Whisper được kiểm tra riêng bằng giọng nói tổng hợp. LLM API chưa được kiểm tra live bằng key trả phí; cần đặt key và model hợp lệ trước khi sử dụng. Tự căn khuôn mặt chọn mặt lớn nhất, có thể cần chỉnh tay nếu nhiều diễn giả hoặc khuôn mặt bị che/quay nghiêng.
