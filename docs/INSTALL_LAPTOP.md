# Chạy ChurchToolVideo trên Windows và MacBook

Ứng dụng dùng cùng mã nguồn và mở trong trình duyệt tại `http://localhost:8000`. Không cần XAMPP. Hai hệ điều hành có môi trường Python riêng; không sao chép `.venv` giữa chúng.

| Máy | Bóc băng hiện tại | Render hiện tại | Khởi chạy |
|---|---|---|---|
| Windows có NVIDIA tương thích | CUDA, tự chuyển CPU khi cần | NVENC khi kiểm tra khả dụng; nếu không dùng x264 | `run_local.bat` |
| Windows không có NVIDIA | CPU | x264 | `run_local.bat` |
| MacBook Apple Silicon hoặc Intel | CPU, chọn kiểu tính toán được CTranslate2 hỗ trợ | x264 | `bash run_local.sh` hoặc `run_local.command` |

Backend hiện tại chưa dùng GPU Apple/Metal. [CTranslate2 hỗ trợ CPU macOS Intel và ARM64; GPU dùng CUDA NVIDIA](https://opennmt.net/CTranslate2/hardware_support.html). Model `small` là điểm bắt đầu để thử trên CPU; cần đo tốc độ/độ chính xác trên máy thật. Model lớn có thể chạy lâu hơn và cần nhiều bộ nhớ.

## Windows

1. Cài Python 3.12 hoặc 3.11 từ [Python](https://www.python.org/downloads/windows/), chọn thêm Python vào PATH. Bộ phụ thuộc media hiện tại sử dụng hai phiên bản này.
2. Cài FFmpeg đầy đủ, gồm `ffmpeg` và `ffprobe`, qua WinGet:

```powershell
winget install --id Gyan.FFmpeg -e
```

3. Mở Terminal mới hoặc nhấp đúp `run_local.bat`. Lần đầu launcher tạo môi trường và cài thư viện; các lần sau dùng lại môi trường. Nếu sửa danh sách thư viện, chạy:

```powershell
.\run_local.bat --install
```

Windows có NVIDIA cần driver phù hợp để sử dụng CUDA/NVENC. Máy không có NVIDIA vẫn chạy bằng CPU. File thư viện NVIDIA chỉ được cài trên Windows theo marker trong `requirements.txt`.

## MacBook

Cài [Homebrew](https://brew.sh/) theo hướng dẫn chính thức, rồi mở Terminal:

```bash
brew install python@3.12 ffmpeg-full
cd "/duong/dan/ChurchVideo"
bash run_local.sh
```

[FFmpeg-full của Homebrew](https://formulae.brew.sh/formula/ffmpeg-full) có `libass` cần để chèn phụ đề; bản FFmpeg thường hiện không có đủ thư viện cho luồng này. Launcher tự tìm đường dẫn Homebrew của Apple Silicon (`/opt/homebrew`) hoặc Intel (`/usr/local`), bao gồm `ffmpeg-full` dạng keg-only. Việc Homebrew có gói nhị phân sẵn phụ thuộc phiên bản macOS và kiến trúc; máy cũ có thể phải biên dịch từ nguồn hoặc cài FFmpeg tương thích từ [trang tải FFmpeg](https://ffmpeg.org/download.html).

Để nhấp đúp trong Finder, cấp quyền thực thi một lần:

```bash
chmod +x run_local.command run_local.sh
```

Sau đó mở `run_local.command`; Terminal giữ tiến trình máy chủ. Nhấn Ctrl+C để dừng. Cài lại thư viện khi cần:

```bash
bash run_local.sh --install
```

## Kiểm tra cài đặt và đổi cổng

```powershell
# Windows
.\run_local.bat --check
.\run_local.bat --port 8001
```

```bash
# MacBook
bash run_local.sh --check
bash run_local.sh --port 8001
```

`--check` kiểm tra thư viện Python, FFmpeg/FFprobe, bộ lọc phụ đề/âm lượng và encoder H.264/AAC. Lệnh này không khởi chạy thêm máy chủ. Nếu cổng 8000 đang có máy chủ, mở địa chỉ hiện có hoặc chọn cổng khác.

Các launcher đọc `.env` khi khởi động, chạy một worker và chỉ bind `127.0.0.1`. Có thể đặt `FFMPEG_PATH`, `FFPROBE_PATH` trong `.env` nếu binary nằm ở vị trí khác. Để nhập dự án từ máy kia, dùng ZIP sao lưu của ứng dụng; không sao chép môi trường Python. Nếu phát hiện `.venv` thuộc hệ điều hành khác, launcher giữ nó và tạo `.venv-macos`/`.venv-windows` riêng.

## Phạm vi kiểm chứng

Đã kiểm tra cài đặt hiện có và khởi chạy thật trên Windows; kiểm thử các nhánh chọn CPU/đường dẫn cho macOS bằng mô phỏng, cùng cú pháp Bash. Chưa chạy trên MacBook vật lý trong phiên này. Cần nghiệm thu trên máy Mac đích: upload → bóc băng → chèn phụ đề → render → sao lưu/khôi phục.

Ngày 13/10/2026: toàn bộ **352 test đạt** trong 122,75 giây; launcher Windows mở trang/API HTTP 200 trên cổng kiểm thử 8003. Kiểm tra Bash, compileall và git diff --check đạt. Server cũ trên cổng 8000 chưa khởi động lại; lệnh khởi động lại tự động bị chính sách công cụ chặn.
