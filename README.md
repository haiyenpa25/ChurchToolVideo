# ChurchToolVideo — Hệ Thống Bóc Băng Bài Giảng & Dựng Video Ngắn Hội Thánh

**ChurchToolVideo** là ứng dụng web chạy cục bộ (Local-first Studio) hỗ trợ Ban Truyền Thông Hội Thánh Tin Lành tự động chuyển giọng nói bài giảng thành phụ đề tiếng Việt chuẩn xác, chuẩn hóa thuật ngữ Kinh Thánh, biên tập video ngắn đa khung hình (`9:16`, `16:9`, `1:1`, `4:5`, `source`) và đóng gói xuất bản lên mạng xã hội.

---

## Tài Liệu Dự Án (`docs/`)

Toàn bộ tài liệu kỹ thuật và hướng dẫn đã được gộp và tổ chức gọn thành 3 tài liệu chuyên biệt:

1. **[Hướng Dẫn Cài Đặt & Cấu Hình Phần Cứng (`docs/INSTALL_AND_HARDWARE.md`)](docs/INSTALL_AND_HARDWARE.md)**
   - Cài đặt và chạy trên Windows (NVIDIA CUDA/NVENC hoặc CPU) và MacBook (Apple Silicon / Intel).
   - Bảng cấu hình máy xử lý (`Auto`, `Windows NVIDIA`, `Windows CPU`, `MacBook`), tương thích driver NVIDIA NVENC & FFmpeg, và các biến `.env` tinh chỉnh luồng CPU/GPU.
2. **[Hướng Dẫn Sử Dụng & Biên Tập (`docs/USER_GUIDE.md`)](docs/USER_GUIDE.md)**
   - Giao diện **Sacred Studio**: Quản lý dự án, Thùng rác (Soft-delete), Bàn dựng 3 cột & 5 tab (`Nội dung`, `Phụ đề`, `Đề tựa`, `Khung`, `Âm thanh`).
   - Nhận diện giọng nói (`faster-whisper`), Từ điển Tin Lành (183 mục từ & 66 sách Kinh Thánh), hiệu đính AI (`S0001`), Render thử 12 giây, Preset Hội Thánh, Lịch sử phiên bản (Undo/Redo & SQLite Revisions), Thư viện Clip & Sao lưu di động (`.zip`).
3. **[Kiến Trúc Kỹ Thuật & Lịch Sử Phát Triển (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)**
   - Kiến trúc Backend (FastAPI, BoundedTaskQueue, SQLite WAL, GPU Semaphore), Pipeline FFmpeg Single-Pass & Phụ đề ASS, Cơ chế bảo mật và tóm tắt các giai đoạn phát triển.

---

## Tính Năng Cốt Lõi

- **Bóc băng Bài Giảng Tiếng Việt (`faster-whisper`)**:
  - Mặc định sử dụng mô hình `large-v3-turbo` với `word_timestamps=True`, lọc khoảng lặng (`vad_filter`) và chống lặp câu rác cuối video.
  - Hỗ trợ 2 chế độ giải mã: **Chất lượng cao (`quality`)** giữ ngữ cảnh liền mạch của bài giảng (`condition_on_previous_text=True`, `beam_size=5`) và **Nhanh (`fast`)** gom đoạn theo lô (`BatchedInferencePipeline`).
- **Chuẩn Hóa Thuật Ngữ Tin Lành & Kinh Thánh**:
  - Tự động chuẩn hóa **183 mục từ Tin Lành** (*Đức Chúa Trời*, *Đức Chúa Giê-xu Christ*, *Đức Thánh Linh*, *Ha-lê-lu-gia*, *A-men*, v.v.) và tên **66 sách Kinh Thánh** theo chuẩn Hội Thánh Tin Lành Việt Nam (Bản Truyền Thống 1925).
  - Lưu trữ song song văn bản gốc Whisper (`original_text`) và văn bản đã chuẩn hóa/biên tập (`text`).
  - Hỗ trợ hiệu đính chính tả bằng AI theo từng phần (batch 80 câu theo mã `S0001`) kèm giao diện duyệt từng câu (word-diff).
- **Bàn Dựng Video Ngắn Sacred Studio (3 Cột)**:
  - **Chọn đoạn trực tiếp từ Transcript & Sóng âm (Waveform)** hoặc nhờ AI đề xuất clip ~90s theo mục tiêu (*Chứng đạo*, *Khích lệ*, *Dạy đạo*, *Cầu nguyện*, *Thông báo*).
  - **5 Tab công cụ**: `Nội dung` (sửa chữ, gắn ★ Hook, nghe trước/sau 15s–30s), `Phụ đề` (15 mẫu phụ đề minh họa, hoạt họa, nền chữ, dải che chữ cũ), `Đề tựa` (tiêu đề mở đầu, câu kết, logo PNG), `Khung` (kéo khung cắt 9:16/1:1/4:5/16:9, zoom `1×–3×`, làm mờ hai bên), `Âm thanh` (nhạc nền dự án, cắt khoảng lặng, lọc tạp âm + chuẩn hóa âm lượng `-16 LUFS`).
  - **Render thử 12 giây**: Kiểm tra thực tế video xuất từ FFmpeg (font chữ ASS, vị trí dải che, nhạc nền, âm lượng) ngay trong trình duyệt trước khi xuất hàng loạt.
- **Quản Lý Dự Án, Thư Viện & Sao Lưu**:
  - Lưu tự động vào SQLite (`workspace/projects.sqlite3`) kèm bản nháp dự phòng `localStorage`, hỗ trợ **Undo/Redo 100 bước** và **50 phiên bản lịch sử dự án**.
  - **Thư viện Clip (`workspace/library`)**: Tìm kiếm không dấu, gắn thẻ, đánh dấu ★, tải gói đăng bài theo nền tảng (`YouTube Shorts`, `Reels`, `TikTok`).
  - **Gói sao lưu di động (`workspace/backups`)**: Đóng gói/khôi phục toàn bộ dự án (`.zip` kèm kiểm tra toàn vẹn `SHA-256`).

---

## Khởi Chạy Nhanh (Quick Start)

### 1. Chạy trực tiếp trên Windows / MacBook (Khuyến nghị)

- **Windows**: Nhấp đúp `run_local.bat` hoặc chạy trong PowerShell:
  ```powershell
  .\run_local.bat
  ```
- **macOS (MacBook)**: Nhấp đúp `run_local.command` hoặc chạy trong Terminal:
  ```bash
  ./run_local.sh
  ```
- **Kiểm tra môi trường (không bật server)**:
  ```bash
  python run_local.py --check
  ```
- Sau khi khởi động, mở trình duyệt tại: **`http://localhost:8000`**.

> Xem chi tiết cách cài Python 3.11/3.12, FFmpeg (`libass`) và cấu hình GPU/CPU tại [`docs/INSTALL_AND_HARDWARE.md`](docs/INSTALL_AND_HARDWARE.md).

### 2. Chạy bằng Docker

- **Chế độ mặc định (CPU)**:
  ```bash
  docker-compose up --build -d
  ```
- **Chế độ GPU NVIDIA**:
  ```bash
  docker-compose -f docker-compose.gpu.yml up --build -d
  ```

---

## Cấu Hình Biến Môi Trường (`.env`)

Sao chép `.env.example` thành `.env` để tùy chỉnh:

| Nhóm cấu hình | Biến môi trường | Mặc định | Mô tả |
|---|---|---|---|
| **Bảo mật** | `CHURCH_PASSWORD` | *(trống)* | Mật khẩu đăng nhập. Bắt buộc đặt nếu bind ra mạng LAN (`CHURCH_BIND_ADDRESS != 127.0.0.1`). |
| **Whisper STT** | `DEFAULT_WHISPER_MODEL` | `large-v3-turbo` | Mô hình Whisper mặc định (`tiny`, `base`, `small`, `medium`, `large-v3-turbo`). |
| **Hiệu năng** | `WHISPER_CPU_THREADS` | `6` | Số luồng CPU cho CTranslate2 (`1..32`). |
| **Hiệu năng** | `FFMPEG_THREADS` / `FFMPEG_FILTER_THREADS` | `6` / `4` | Giới hạn luồng giải mã và filter của FFmpeg giúp máy mát, ổn định. |
| **Hiệu năng** | `FFMPEG_HWACCEL` | `none` | Giải mã phần cứng FFmpeg (`none` hoặc `auto`). |
| **Hàng đợi** | `RENDER_WORKERS` / `TRIM_WORKERS` | `1` / `2` | Số tác vụ render / cắt chạy song song (tối đa 10 tác vụ chờ). |
| **AI (Tùy chọn)** | `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | *(trống)* | API key để dùng nút đề xuất clip hoặc sửa phụ đề tự động bằng AI. |

---

## Cấu Trúc Thư Mục Dự Án

```text
ChurchVideo/
├── AGENTS.md                        # Nguyên tắc Clean Code & Quy chuẩn kỹ thuật cho AI / Developer
├── GEMINI.md                        # Liên kết quy chuẩn cho hệ thống Antigravity / Gemini
├── .agents/skills/                  # Bộ kỹ năng (Skills) hỗ trợ kiểm thử, từ vựng Tin Lành & FFmpeg
├── app/
│   ├── main.py                      # FastAPI Entrypoint, Upload, Transcribe, Trim, System & Project API
│   ├── shorts_api.py                # API phân tích kịch bản, đề xuất AI, render thử & render Short
│   ├── product_api.py               # API quản lý dự án, phiên bản, preset, từ điển, sao lưu & thống kê
│   ├── library_api.py               # API thư viện clip hoàn chỉnh & xuất gói đăng mạng xã hội
│   ├── auth.py                      # Xác thực phiên (Cookie HMAC) & vòng đời bảo trì định kỳ
│   ├── config.py                    # Cấu hình đường dẫn, phát hiện FFmpeg/FFprobe & giới hạn luồng
│   ├── assets/fonts/                # Bộ 9 font chữ tiếng Việt (Noto Sans, Be Vietnam Pro, Anton, v.v.)
│   ├── models/schemas.py            # Các mô hình dữ liệu Pydantic & kiểm tra an toàn đầu vào
│   ├── services/                    # Tầng xử lý nghiệp vụ (Whisper, FFmpeg, Captions ASS, Normalizer, SQLite...)
│   └── static/                      # Giao diện Sacred Studio
│       ├── index.html               # Giao diện chính (SPA)
│       ├── css/                     # Stylesheets (tailwind.css, sacred.css, editor.css, captions.css, shorts.css, subfix.css)
│       └── js/                      # Các mô-đun JS (common, app, shorts, projects, library, subfix, captions, clipeditor, product, workflow, studio, sacred, editor-preview, machine-settings)
├── docs/                            # Tài liệu hướng dẫn cài đặt, sử dụng & kiến trúc
├── scripts/                         # Các script kiểm tra môi trường, cài đặt FFmpeg & benchmark
├── tests/                           # Bộ kiểm thử tự động (pytest + Playwright UI E2E)
├── workspace/                       # Dữ liệu người dùng & SQLite (được .gitignore bảo vệ)
├── Dockerfile & docker-compose*.yml # Cấu hình đóng gói Docker (CPU & GPU)
└── run_local.py / .bat / .sh        # Trình khởi chạy tự động đa nền tảng (Windows & macOS)
```

---

## Kiểm Thử & Phát Triển

```bash
# 1. Chạy toàn bộ bộ kiểm thử đơn vị (Unit & API tests)
pytest -q

# 2. Chạy kiểm thử giao diện trình duyệt (Playwright E2E)
pytest -m integration

# 3. Biên dịch lại Tailwind CSS khi chỉnh sửa giao diện (index.html / app/static/js/*.js)
npm run build:css
```
