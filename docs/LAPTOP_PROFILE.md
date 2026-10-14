# Cấu hình ChurchVideo cho laptop hiện tại — 13/10/2026

Phần cứng kiểm tra trực tiếp: Intel Core i5-13420H (8 nhân, 12 luồng), RAM dùng được khoảng 15,7 GB, NVIDIA GeForce RTX 5050 Laptop GPU (8 GB), driver 591.91. Ổ C còn khoảng 196 GB tại lúc kiểm tra.

## Cấu hình đã áp dụng

File `.env` riêng của máy đặt:

| Mục | Giá trị | Mục đích |
|---|---|---|
| Model mặc định | `large-v3-turbo` | Bóc băng tiếng Việt bằng CUDA khi khả dụng |
| `WHISPER_CPU_THREADS` | 6 | Giới hạn pool CPU của model |
| `WHISPER_BATCH_SIZE` | 8 | Giữ mức batch đã chạy được trên GPU này |
| `FFMPEG_THREADS` | 6 | Giới hạn luồng decode/encode |
| `FFMPEG_FILTER_THREADS` | 4 | Giới hạn luồng lọc crop/phụ đề |
| `FFMPEG_HWACCEL` | `none` | Decode/lọc trên CPU; NVENC vẫn encode trên GPU |
| `RENDER_WORKERS` / `TRIM_WORKERS` | 1 / 1 | Hạn chế các tác vụ nặng đồng thời trên RAM 16 GB |
| FFmpeg/FFprobe | Bản 8.0.1 trong `.tools` | Encode NVENC tương thích driver đang có |

FFmpeg 9.0.2 của hệ thống và bản 8.1.2 đã thử đều báo cần NVENC API 13.1 / driver 610+. Bản [8.0.1 từ Gyan](https://github.com/GyanD/codexffmpeg/releases/tag/8.0.1) đã được kiểm tra SHA-256 theo metadata phát hành và encode NVENC thành công trên driver 591.91. Chỉ binary riêng trong dự án được chọn; driver và bản FFmpeg hệ thống được giữ nguyên. Giới hạn driver của SDK 13.0 có trong [tài liệu NVIDIA](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/read-me/index.html).

`--hwaccel auto` làm chậm đường render có bộ lọc CPU trên mẫu kiểm tra này. Decode bằng CPU rồi encode NVENC cho kết quả tốt hơn. Cấu hình không ép GPU cho máy khác; giá trị mặc định chung vẫn giữ nguyên. Khi nâng driver hoặc chuyển máy, cần kiểm tra lại profile và đường dẫn FFmpeg trong `.env`.

## Đo thực tế

Clip tổng hợp chuyển động, đầu vào 1920×1080, đầu ra 1080×1920, 60 giây, crop và chèn phụ đề:

| Cấu hình | Render | Dung lượng | Kết quả |
|---|---:|---:|---|
| Trước: FFmpeg 9.0.2, x264, luồng tự động | 6,000 giây | 42,8 MB | Video 60 giây + SRT |
| Sau: FFmpeg 8.0.1, NVENC, decode CPU, giới hạn luồng | 4,172 giây | 68,3 MB | Video 60 giây + SRT |

Thời gian giảm khoảng **30,5%** trên một lượt đo; không phải cam kết cho mọi bài giảng. Đo render không tính tạo video nguồn và dò encoder. NVENC nhanh hơn trong mẫu này nhưng file lớn hơn; CQ của NVENC và CRF của x264 không phải cùng thang đo chất lượng. Đầu ra GPU đã được giải mã lại bằng FFmpeg không báo lỗi. Kết quả JSON/video ở `workspace/tmp/laptop_benchmark`.

Bóc băng lại mẫu âm thanh công khai 90 giây qua `large-v3-turbo` với cấu hình mới: CUDA, 8,70 giây, 11 đoạn; timestamp nguyên vẹn sau chuẩn hóa. Nhận được Phao-lô, Đức Thánh Linh, Báp-têm. Đây là kiểm tra chức năng thật; không phải số đo WER.

## Kiểm chứng và sử dụng

**357/357 test đạt** trong 50,97 giây; kiểm tra môi trường launcher, compileall và git diff --check đạt. Dữ liệu benchmark tách khỏi dự án người dùng.

Mở bản chạy cấu hình mới tại `http://localhost:8004`. Server cũ trên cổng 8000 vẫn là cấu hình trước; dùng một server cho các thao tác biên tập để tránh cập nhật đồng thời. Lần khởi chạy sau bằng `run_local.bat` sẽ đọc `.env`; nếu cổng 8000 đang dùng thì chạy `run_local.bat --port 8004`.

Gói FFmpeg 8.1.2 thử không tương thích còn trong `.tools`: lệnh dọn tự động bị chính sách công cụ chặn. Nó không được cấu hình để sử dụng.
