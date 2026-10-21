# Hướng Dẫn Cài Đặt & Cấu Hình Phần Cứng (Windows & MacBook)

Tài liệu này tổng hợp hướng dẫn cài đặt, khởi chạy, chọn cấu hình phần cứng (GPU/CPU) và tinh chỉnh hiệu năng cho **ChurchToolVideo** trên cả máy Windows và MacBook.

---

## 1. Bảng Tương Thích Phần Cứng & Cấu Hình Máy Xử Lý

Trong giao diện **Thiết lập → Cấu hình máy xử lý**, bạn có thể chọn chế độ phù hợp với máy tính đang sử dụng (hoặc để **Tự động theo máy**):

| Tùy chọn trong Thiết lập | Hệ điều hành | Chuyển giọng nói (`faster-whisper`) | Xuất video (`FFmpeg`) | Ghi chú vận hành |
|---|---|---|---|---|
| **Tự động theo máy** (`auto`) | Windows / macOS | Windows thử CUDA trước, nếu lỗi tự chuyển sang CPU; macOS dùng CPU | Windows thử `h264_nvenc` trước, nếu lỗi chuyển sang `libx264`; macOS dùng `libx264` | Khuyến nghị mặc định cho hầu hết người dùng |
| **Windows có card NVIDIA** | Windows | `cuda` (`float16` / `int8_float16`), tự lùi về CPU nếu thiếu VRAM/driver | `h264_nvenc` (tự lùi về `libx264` nếu FFmpeg/driver không hỗ trợ) | Nhanh nhất khi bóc băng bài giảng dài và xuất nhiều tỷ lệ khung hình |
| **Windows dùng CPU** | Windows | `cpu` (`int8`) | `libx264` (`veryfast`) | Dành cho laptop Windows không có GPU rời hoặc khi muốn giữ GPU cho phần mềm khác |
| **MacBook (Apple Silicon / Intel)** | macOS | `cpu` (`int8` / `int8_float32` / `float32`) | `libx264` | `CTranslate2` (engine của `faster-whisper`) trên macOS chỉ hỗ trợ CPU; chọn mô hình `small` hoặc `base` để xử lý nhanh hơn |

---

## 2. Cài Đặt Trên Laptop Windows

### Yêu cầu cần cài trước
1. **Python 3.11 hoặc 3.12** (khuyến nghị Python 3.12 64-bit, bật *Add python.exe to PATH* khi cài).
2. **FFmpeg và FFprobe** (có bộ lọc phụ đề `subtitles`/`ass`). Có thể cài nhanh bằng PowerShell:
   ```powershell
   winget install Gyan.FFmpeg
   ```
3. **Nếu máy có card rời NVIDIA**: Cài NVIDIA Driver mới để dùng CUDA và `h264_nvenc`. Nếu máy không có GPU NVIDIA, ứng dụng tự động chuyển sang CPU (`int8` cho Whisper và `libx264` cho FFmpeg).

### Cách khởi chạy trên Windows
Nhấp đúp vào `run_local.bat` hoặc mở PowerShell tại thư mục dự án:
```powershell
.\run_local.bat
```
Lần đầu chạy, script sẽ tự tạo môi trường ảo `.venv` (hoặc `.venv-windows` nếu thư mục đang chứa `.venv` từ macOS), cài đặt các gói trong `requirements.txt`, kiểm tra FFmpeg/Whisper rồi mở server tại `http://localhost:8000`.

Các lệnh hỗ trợ kiểm tra và bảo trì:
```powershell
.\run_local.bat --check          # Chỉ kiểm tra Python, FFmpeg, thư mục workspace
.\run_local.bat --install        # Cài đặt / cập nhật lại thư viện Python
.\run_local.bat --port 8080      # Chạy trên cổng 8080
```

---

## 3. Cài Đặt Trên MacBook (Apple Silicon M1/M2/M3/M4 hoặc Intel)

### Yêu cầu cần cài trước (qua Homebrew)
Bản `ffmpeg` mặc định của Homebrew hiện không kèm sẵn `libass` (cần thiết để đốt phụ đề `.ass`/`.srt` lên video Short). Vì vậy hãy cài **`ffmpeg-full`**:

```bash
brew install python@3.12 ffmpeg-full
```

> Lưu ý: `app/config.py` được thiết kế để tự động ưu tiên tìm `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` (Apple Silicon) và `/usr/local/opt/ffmpeg-full/bin/ffmpeg` (Mac Intel) trước khi tìm trong `PATH`, nên bạn không cần sửa `PATH` thủ công.

### Cách khởi chạy trên MacBook
Trong Finder, nhấp đúp vào **`run_local.command`**, hoặc mở Terminal tại thư mục dự án:
```bash
chmod +x run_local.sh run_local.command
./run_local.sh
```

Nếu chép nguyên thư mục dự án từ máy Windows sang MacBook, trình khởi chạy sẽ giữ nguyên `.venv` của Windows và tự tạo môi trường riêng `.venv-macos` cho macOS (tránh xung đột file nhị phân).

---

## 4. Tương Thích NVIDIA Driver, FFmpeg NVENC & Tinh Chỉnh Hiệu Năng (`.env`)

### Lưu ý quan trọng về FFmpeg 9+ và NVIDIA Driver (NVENC API)
- Các bản **FFmpeg 8.1.2 / 9.0+** được biên dịch với **NVENC SDK 13.1**, yêu cầu NVIDIA Driver từ **610+** trở lên. Trên các laptop dùng driver nhánh R590 (ví dụ `591.91`), FFmpeg 9+ sẽ báo lỗi `Driver does not support the required nvenc API version` và ứng dụng sẽ phải lùi về CPU (`libx264`).
- **Giải pháp**: Với driver NVIDIA `< 610`, sử dụng **FFmpeg 8.0.1** (biên dịch với NVENC SDK 13.0). Bạn có thể chạy script tự động tải bản FFmpeg tương thích vào thư mục `.tools/`:
  ```powershell
  .\.venv\Scripts\python.exe scripts\install_compatible_ffmpeg.py
  ```
  Sau đó trỏ `FFMPEG_PATH` và `FFPROBE_PATH` trong `.env` vào `.tools/ffmpeg-8.0.1-essentials_build/bin/`.

### Cấu hình `.env` khuyến nghị cho Laptop có GPU NVIDIA (ví dụ Core i5 / 16 GB RAM / RTX Laptop)
```ini
DEFAULT_WHISPER_MODEL=large-v3-turbo
WHISPER_CPU_THREADS=6
WHISPER_BATCH_SIZE=4
FFMPEG_THREADS=6
FFMPEG_FILTER_THREADS=4
FFMPEG_HWACCEL=none
RENDER_WORKERS=1
TRIM_WORKERS=1
```

- **Tại sao `FFMPEG_HWACCEL=none` lại nhanh hơn khi ghép Short?**
  Khi render Short có bộ lọc phức tạp (`crop`, `scale`, đốt phụ đề `ass`), tất cả filter này chạy trên RAM CPU. Nếu bật `-hwaccel auto`, khung hình giải mã trên GPU phải chép ngược về RAM CPU để chạy filter rồi lại đẩy lên GPU để mã hóa `h264_nvenc`. Để CPU giải mã trực tiếp (`FFMPEG_HWACCEL=none`) với 6 luồng, chạy filter `ass`, rồi giao phần mã hóa cuối cùng cho `h264_nvenc` giúp giảm ~30% thời gian render.
- **Công cụ Benchmark hiệu năng thực tế**:
  - Kiểm tra tốc độ render FFmpeg/NVENC: `python scripts/benchmark_laptop_render.py`
  - Kiểm tra tốc độ và độ chính xác bóc băng bài giảng: `python scripts/benchmark_protestant_audio.py`
