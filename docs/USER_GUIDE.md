# Hướng Dẫn Sử Dụng & Biên Tập — ChurchToolVideo (Sacred Studio)

Tài liệu này hướng dẫn chi tiết quy trình làm việc trên giao diện **Sacred Studio**, từ lúc tải bài giảng gốc đến khi xuất bản các video ngắn (Shorts/Reels/TikTok) hoàn chỉnh.

---

## 1. Quản Lý Dự Án & Thùng Rác (Màn Hình `Dự án`)

- **Tạo dự án mới**: Tải video bài giảng gốc (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`) lên hệ thống.
- **Danh sách dự án đã lưu**:
  - Hiển thị ảnh đại diện trích xuất từ video gốc, tiêu đề dự án, số lượng clip, ngày cập nhật và trạng thái (*Đang biên tập*, *Chưa có clip*, *Thiếu video gốc*).
  - Hỗ trợ **Tìm kiếm không dấu** theo tên dự án hoặc tên file video gốc.
  - Menu `•••` trên mỗi thẻ dự án cho phép **Đổi tên dự án** hoặc **Chuyển vào Thùng rác**.
- **Thùng rác (Soft-delete)**:
  - Chuyển bộ lọc sang **Thùng rác** để xem các dự án đã ẩn và bấm **Khôi phục** bất cứ lúc nào.
  - Việc chuyển dự án vào Thùng rác **không xóa** file video gốc hay các clip đã xuất trong Thư viện.

---

## 2. Nhận Diện Giọng Nói (Whisper STT) & Chuẩn Hóa Phụ Đề Tin Lành

### Cấu hình nhận diện
- **Mô hình**: Mặc định `large-v3-turbo` (cân bằng tốt nhất giữa tốc độ và độ chính xác tiếng Việt có dấu).
- **Chế độ giải mã**:
  - **Chất lượng cao (`quality` - Mặc định)**: Giải mã tuần tự, giữ ngữ cảnh đoạn trước (`condition_on_previous_text=True`), dùng `beam_size=5` và không chặn lặp cụm từ 3 chữ (giúp giữ nguyên vẹn các điệp ngữ trong bài giảng như *"Đức Chúa Trời"*, *"Ha-lê-lu-gia"*).
  - **Nhanh (`fast`)**: Gom các đoạn lời thoại theo lô (`BatchedInferencePipeline`) để tăng tốc trên bài giảng rất dài.
- **Từ điển mồi (Initial Prompt)**: Tự động tính toán theo số lượng **token thực tế của Whisper** (giới hạn an toàn $\le 180$ token, tránh vượt ngưỡng 224 token của Whisper) và luôn ưu tiên giữ tên riêng do người dùng nhập trước khi ghép từ điển Tin Lành mặc định.

### Từ điển Tin Lành & Quy tắc chuẩn hóa (183 mục từ & 66 sách Kinh Thánh)
- Hệ thống tích hợp sẵn từ điển chuẩn của Hội Thánh Tin Lành Việt Nam (Bản Truyền Thống 1925):
  - **Danh xưng & Thuật ngữ**: *Đức Chúa Trời*, *Đức Chúa Giê-xu Christ*, *Đức Thánh Linh*, *Cứu Chúa*, *Ha-lê-lu-gia*, *A-men*, *Báp-têm*, *Tiệc Thánh*, *Đấng Christ*, *Phi-e-rơ*, *Phao-lô*, *Áp-ra-ham*, *Môi-se*, *Đa-vít*, v.v.
  - **66 sách Kinh Thánh** (39 Cựu Ước, 27 Tân Ước): *Sáng-thế Ký*, *Xuất Ê-díp-tô Ký*, *Thi-thiên*, *Châm-ngôn*, *Ma-thi-ơ*, *Giăng*, *Rô-ma*, *Khải-huyền*, v.v.
- **Quy tắc an toàn ngữ cảnh**:
  - Chỉ viết hoa các từ đa nghĩa (*Sứ đồ*, *Tiên tri*, *Mục sư*, *Thánh linh*, *Tin lành*, *Hội thánh*) khi đi kèm cụm danh từ riêng hoặc ngữ cảnh thần học rõ ràng.
  - Không tự ý biến từ đời thường (*truyền thông*, *sáng thế giới*, *mác áo*) thành thuật ngữ Kinh Thánh.
  - Mọi câu thoại đều lưu giữ **`original_text`** (văn bản thô từ Whisper) bên cạnh **`text`** (văn bản đã chuẩn hóa/biên tập).

### Duyệt & Hiệu đính Phụ đề (`Sửa phụ đề`)
- Nhấp vào từng dòng phụ đề để nghe đúng câu đó trên video, nhấp đúp để sửa chữ trực tiếp, hoặc bấm **Hoàn tác câu này**.
- **AI sửa chính tả**: Gửi phụ đề theo từng lô 80 câu (mã định danh cố định `S0001`, `S0002`...) hoặc dùng **Copy Prompt** để dán vào Gemini/ChatGPT miễn phí. Hệ thống hiển thị bảng đối chiếu từng từ (`<del>` / `<ins>`) và chặn các câu AI tự ý tóm tắt làm lệch quá 35% độ dài câu gốc.
- Sau khi sửa xong, bấm **Cập nhật chữ vào các clip** để đồng bộ chữ mới vào các clip đang dựng mà vẫn giữ nguyên mốc thời gian từng từ (`realign_words`).

---

## 3. Bàn Dựng Clip 3 Cột (`Biên tập`)

Giao diện biên tập được chia làm 3 khu vực rõ ràng:

1. **Cột trái — Danh sách Clip (`Danh sách clip`)**:
   - Chuyển nhanh giữa các clip trong dự án, xem thời lượng và trạng thái duyệt của từng clip.
   - Nút **`+ Thêm clip`** mở hộp thoại chọn đoạn trực tiếp từ Transcript, chọn trên biểu đồ **Sóng âm (Waveform)**, dán mốc thời gian (`00:01:10 - 00:02:05` hoặc `S0010 -> S0018`), hoặc nhờ AI đề xuất theo mục tiêu (*Chứng đạo*, *Khích lệ*, *Dạy đạo*, *Cầu nguyện*, *Thông báo*).
2. **Cột giữa — Khung Xem Trước & Timeline**:
   - Chuyển đổi giữa **Khung nguồn (Source Frame)** (kéo khung cắt trực quan trên video gốc 16:9) và **Mô phỏng xuất (Output Simulation)** (xem trước bố cục dọc 9:16, vuông 1:1, 4:5 kèm phụ đề động).
   - Nút **`Render thử 12 giây`**: Gọi FFmpeg xuất một đoạn MP4 thực tế dài tối đa 12 giây tại vị trí đang xem để kiểm tra chính xác font chữ ASS, hiệu ứng karaoke, dải che chữ và nhạc nền trước khi xuất thật.
   - Thanh công cụ **Hoàn tác / Làm lại (Undo/Redo 100 bước)** (`Ctrl+Z` / `Ctrl+Y`) và **Lịch sử 50 phiên bản dự án** lưu trong SQLite.
3. **Cột phải — Thanh Mẫu Preset Toàn Diện & 5 Tab Tinh Chỉnh Chi Tiết**:
   - **Thanh Mẫu cài đặt nhanh (Template Preset)** ngay đầu cột phải:
     - Chỉnh một lần toàn bộ cài đặt (Phụ đề, Lớp phủ Blur 1/3, Logo, Chỉnh màu, Nhạc nền, Outro) rồi bấm **`💾 Lưu đè mẫu này`** hoặc **`➕ Lưu thành mẫu mới`**.
     - Khi chọn một mẫu từ danh sách hoặc bấm **`Áp dụng mẫu`**, toàn bộ thông số đã thiết lập sẽ tự động nạp và hiển thị trên tất cả các thanh trượt và màn hình xem trước.
   - **Nội dung & Chế độ cắt chuẩn**:
     - Hỗ trợ chọn **Chế độ cắt (`#shortsCutMode`)**: **Trọn câu / Trọn ý + Chống lem sang câu sau (Khuyên dùng)**, **Chính xác tuyệt đối theo mốc đã nhập (Không cộng đệm 0.15s)**, hoặc **Mặc định (Khớp từ + đệm 0.15s)**.
     - Sửa chữ trong từng đoạn (`part`), bôi đen từ để gắn **★ Hook** (hoặc bấm **⚡ Câu đầu làm Hook**), bấm **✨ Trọn câu** để tự động nới mốc lấy trọn ý mà không lem sang câu kế tiếp, bấm **Nghe trước / Nghe sau** và đánh dấu **Đã nghe ngữ cảnh và kiểm tra nội dung clip**.
   - **Phụ đề & Lớp phủ Blur 1/3 Mờ Dần**:
     - Chọn từ 18 mẫu phụ đề minh họa riêng cho chữ thường và chữ Hook (bao gồm mẫu **Hộp thoại Tin Lành - `sacred_dialog`**), chọn font tiếng Việt, cỡ chữ, màu nhấn, hiệu ứng vào chữ (`Pop`, `Slide`, `Fade`, `Typewriter`).
     - **Lớp phủ Blur 1/3 khung có độ chuyển mất dần (Feathered Blur)**: Nút 1-click **`🌫 Lớp phủ Blur 1/3 khung (Mờ dần)`**, chọn chế độ (*Làm mờ Blur* / *Dải màu*), chọn vị trí nhanh (*1/3 Đáy*, *1/4 Đáy*, *1/3 Đỉnh*), chỉnh **Vị trí dọc**, **Chiều cao (tới 60% khung)**, **Độ nhòe Blur (`4–28px`)** và **Độ chuyển mất dần (`0–50%`)** để mép lớp phủ tan mượt vào video.
   - **Đề tựa**: Bật/tắt tiêu đề mở đầu clip, chỉnh thời lượng hiển thị, font chữ và cỡ chữ tiêu đề.
   - **Khung, Logo & Chỉnh màu cơ bản**:
     - **Khung hình**: Chọn tỷ lệ khung hình riêng cho clip hoặc dùng chung dự án, chỉnh chế độ khung (`Cắt lấy khung` / `Làm mờ hai bên`), kéo vị trí ngang/dọc và **Phóng khung (`1.0× – 3.0×`)**.
     - **Logo Hội Thánh tùy chỉnh**: Tải ảnh PNG trong suốt, chọn nhanh 5 vị trí góc, chỉnh thanh trượt **Kích thước (`4%–45%`)**, **Vị trí Ngang (X)**, **Vị trí Dọc (Y)**, **Độ đậm (Opacity)** hoặc **kéo-thả logo trực tiếp bằng chuột trên khung xem trước**.
     - **Chỉnh màu cơ bản (Color Grading)**: 4 mẫu màu 1-click (*Gốc*, *☀ Ấm áp*, *✨ Tươi sáng*, *⛪ Trang nghiêm*) và 3 thanh trượt **Độ sáng (Brightness)**, **Tương phản (Contrast)**, **Độ tươi màu (Saturation)** có xem trước thời gian thực.
   - **Âm thanh, Nhạc nền & Video Outro Hội Thánh**:
     - Bật tự động cắt khoảng lặng, lọc tạp âm giọng nói và chuẩn hóa âm lượng EBU R128.
     - **Nhạc nền chuyên sâu**: Tải file nhạc (`.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac`), chỉnh **Âm lượng lời nói**, **Âm lượng nhạc nền**, cắt đoạn nhạc (**Bắt đầu nhạc `music_start`**, **Kết thúc `music_end`**), chỉnh **Fade In (s)** / **Fade Out (s)** và nghe thử ngay trên trình duyệt.
     - **Đoạn nối Outro Hội Thánh**: Tải lên video Outro (`.mp4`, `.mov`, `.webm`), xem trước video Outro và tự động chuẩn hóa độ phân giải/FPS/âm thanh để nối mượt vào cuối mỗi clip khi xuất.

---

## 4. Kiểm Tra Trước Khi Xuất, Thư Viện Clip & Sao Lưu

- **Kiểm tra trước khi xuất (`Kiểm tra trước khi xuất`)**: Tự động rà soát thời lượng từng clip (cảnh báo nếu `< 30s` hoặc `> 120s`), kiểm tra tràn dòng phụ đề, kiểm tra file nhạc nền/logo và trạng thái duyệt clip.
- **Cổng duyệt nội dung (Review Gate)**: Ngăn việc vô tình xuất các clip chưa được kiểm tra ngữ cảnh (trừ khi bật rõ tùy chọn *Xuất bản nháp*).
- **Thư viện Clip (`Thư viện clip`)**:
  - Lưu trữ toàn bộ các video ngắn đã xuất kèm ảnh thu nhỏ, phụ đề `.srt`, siêu dữ liệu dự án và nền tảng gợi ý.
  - Hỗ trợ tải lẻ từng video, tải **Gói đăng bài theo nền tảng** (`.zip` gồm MP4 + SRT + ảnh bìa `.jpg` + file hướng dẫn tiêu đề/hashtag), hoặc chọn nhiều clip để tải gói ZIP hàng loạt.
- **Sao lưu di động (`Sao lưu / Khôi phục`)**:
  - Xuất toàn bộ cấu hình dự án, phụ đề, preset thương hiệu, từ điển và nhạc nền/logo ra một file `.zip` duy nhất (có mã băm `SHA-256` kiểm tra toàn vẹn) để lưu trữ hoặc chuyển sang máy tính khác làm việc tiếp.
