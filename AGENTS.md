# Nguyên Tắc Phát Triển & Quy Chuẩn Code Sạch (ChurchToolVideo)

Tài liệu này quy định các nguyên tắc bắt buộc khi viết code, sửa lỗi và mở rộng tính năng cho **ChurchToolVideo**. Mọi thay đổi trong dự án phải tuân thủ nghiêm ngặt các nguyên tắc dưới đây.

---

## 1. Nguyên Tắc Cốt Lõi: Chống Trùng Lặp (DRY) & Kiến Trúc Sạch

1. **Không tạo hàm hoặc file chồng chéo (No Monkey-Patching / Shadowing)**:
   - Trên Frontend (`app/static/js/*.js`), tất cả 14 file JS đều chạy chung trong phạm vi toàn cục (`window`). **Tuyệt đối không** định nghĩa lại cùng một tên hàm ở nhiều file JS khác nhau (ví dụ: không viết hàm mới ở `sacred.js` để ghi đè ngầm hàm cùng tên trong `app.js`, `studio.js` hay `product.js`). Sửa trực tiếp tại nơi hàm đó được định nghĩa duy nhất.
   - Trên CSS (`app/static/css/*.css`), chỉ sử dụng 6 file đang được nạp trong `index.html`: `tailwind.css` (build từ `tailwind.input.css`), `shorts.css`, `sacred.css`, `captions.css`, `subfix.css`, `editor.css`. Không tạo thêm file CSS rời rạc hoặc để lại file CSS mồ côi không được liên kết.
2. **Tái sử dụng các hàm dùng chung (Shared Utilities)**:
   - **Định dạng thời gian**: Dùng `format_seconds_to_srt` / `format_seconds_to_display` (`app/services/ffmpeg_service.py`) và `format_seconds_to_vtt` (`app/services/whisper_service.py`). Không tự viết lại phép chia `3600000` / `60000` ở các service khác.
   - **Nội suy từ phụ đề (Word-timing alignment)**: Luôn đi qua `caption_words(sentence)` và `realign_words(old_words, new_text)` trong `app/services/captions_service.py`.
   - **Truy tìm video gốc & Kiểm tra ID**: Luôn dùng `find_video(video_id)` và `validate_video_id(video_id)` trong `app/services/transcript_service.py` (hoặc kiểu `VideoId` của Pydantic ở tầng Router).
   - **Kết nối SQLite**: Luôn dùng `with connect(self.db_path) as conn:` từ `app/services/sqlite_service.py` để đảm bảo `conn.close()` được gọi ngay cả khi có ngoại lệ và kích hoạt `PRAGMA journal_mode=WAL`.
3. **Tổ chức Tài liệu (`docs/`)**:
   - Giữ hệ thống tài liệu gọn trong 4 file chuẩn: `README.md`, `docs/INSTALL_AND_HARDWARE.md`, `docs/USER_GUIDE.md`, `docs/ARCHITECTURE.md`.
   - Không tạo thêm các file `.md` nhật ký kiểm thử rời rạc theo từng ngày hoặc lưu các prompt nháp vào `docs/`.

---

## 2. Nguyên Tắc An Toàn & Bảo Mật (Security & Safety)

1. **Chống Path Traversal**:
   - Mọi tham số nhận từ client (`video_id`, `logo_id`, `music_id`, `brand_id`, tên file tải xuống) bắt buộc dùng kiểu `VideoId` (`^[A-Za-z0-9_-]{1,80}$`) hoặc kiểm tra `path.resolve().parent == EXPECTED_DIR.resolve()`.
2. **An toàn khi gọi FFmpeg / FFprobe**:
   - Luôn truyền danh sách tham số (`[FFMPEG_BIN, "-y", ...]`) với `shell=False`.
   - Mọi tác vụ chạy trong background worker phải đi qua `run_media_command` / `run_ffmpeg` có hỗ trợ `checkpoint()` và hủy tiến trình (`cancel_requested`) để người dùng có thể bấm **Hủy tác vụ** bất kỳ lúc nào.
   - Đường dẫn đưa vào bộ lọc `ass=` của FFmpeg trên Windows phải được chuẩn hóa dấu gạch chéo (`/`) và thoát dấu hai chấm (`\:`): `path.as_posix().replace(":", r"\:")`.
3. **Chống XSS trên Frontend**:
   - Khi tạo giao diện từ dữ liệu người dùng hoặc từ tên file/phụ đề, ưu tiên dùng `document.createElement` + `textContent` hoặc bắt buộc bọc qua `shortsEscape(...)` / `escapeHtml(...)` nếu dùng template string.

---

## 3. Nguyên Tắc Độ Tin Cậy cho GPU, Whisper & Từ Điển Tin Lành

1. **Điều phối GPU (`serialized_gpu_job`)**:
   - Các tác vụ nặng dùng GPU/CPU (như `transcribe_audio` và `render_short`) phải được bảo vệ bởi `serialized_gpu_job` và `BoundedTaskQueue`.
   - Nếu `TaskCancelled` được ném ra trong lúc chạy trên GPU, phải dừng ngay lập tức — **không** tự động fallback sang CPU khi người dùng chủ động hủy tác vụ.
2. **Bảo toàn dữ liệu phụ đề & Từ điển Tin Lành**:
   - Không bao giờ ghi đè làm mất `original_text` của Whisper.
   - Khi thêm từ vựng vào `app/services/protestant_vocabulary.py` hoặc quy tắc vào `app/services/protestant_normalizer.py`, phải đảm bảo không gây dương tính giả (false positive) lên các từ tiếng Việt thông dụng (ví dụ: *sáng thế giới*, *truyền thông*, *mác áo*) và phải chạy `pytest tests/test_protestant_vocabulary.py`.

---

## 4. Quy Trình Kiểm Tra Chất Lượng Bắt Buộc (Definition of Done)

Trước khi kết thúc bất kỳ phiên chỉnh sửa code nào:
1. Nếu có sửa class Tailwind trong `app/static/index.html` hoặc `app/static/js/*.js`, chạy:
   ```bash
   npm run build:css
   ```
2. Chạy bộ kiểm thử tự động và đảm bảo 100% bài test vượt qua:
   ```bash
   .\.venv\Scripts\python.exe -m pytest -q
   ```
3. Không để lại file rác trong `workspace/tmp/`, `workspace/audio/`, `workspace/packages/`, hoặc file nháp ở thư mục gốc.
