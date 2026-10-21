---
name: ffmpeg-shorts-debugger
description: >-
  Use this skill when modifying, debugging, or benchmarking the FFmpeg video
  rendering pipeline, ASS subtitle styling/positioning, audio loudness
  normalization, background music mixing, or NVIDIA NVENC / CPU encoding in
  ChurchVideo.
---

# FFmpeg Shorts Pipeline & ASS Captions Skill

Sổ tay kỹ thuật cho pipeline xuất video ngắn (`app/services/shorts_render_service.py` & `app/services/captions_service.py`).

## Các Điểm Kỹ Thuật Quan Trọng

1. **Single-Pass Filter Complex (`shorts_render_service.py`)**:
   - Toàn bộ quá trình cắt các `parts`, nối (`concat`/`xfade`), cắt khung (`crop`/`blur_pad`/`fit`), vẽ dải che (`drawbox`/`boxblur`), đốt phụ đề `ass`, chèn logo và trộn nhạc nền (`amix`) được thực hiện trong **một lần gọi FFmpeg duy nhất** để giữ chất lượng hình ảnh và tránh lệch tiếng.
   - Kích thước chiều rộng/chiều cao sau khi `crop` hoặc `scale` luôn phải làmẵn (`even(x)`) vì bộ mã hóa H.264 (`yuv420p`) không chấp nhận kích thước lẻ.
2. **Đốt Phụ Đề `.ass` (`captions_service.py`)**:
   - Tọa độ `PlayResX` và `PlayResY` trong file `.ass` phải khớp với kích thước đầu ra của khung hình (`1080x1920`, `1920x1080`, `1080x1080`, `1080x1350`).
   - Mọi văn bản lời thoại đưa vào dòng `Dialogue:` của `.ass` phải được làm sạch ký tự xuống dòng và thoát `{`, `}`, `\` qua `clean_ass_text()`.
   - Màu trong định dạng ASS dùng thứ tự **`&HAABBGGRR`** (Blue-Green-Red, ngược với mã Hex `#RRGGBB` trên web).
3. **Tương Thích NVENC & Tối Ưu Hóa Phần Cứng**:
   - `nvenc_status()` kiểm tra thực tế khả năng khởi tạo `h264_nvenc` trên một khung hình nháp và lưu cache kết quả.
   - Trên laptop NVIDIA, giữ `FFMPEG_HWACCEL=none` (giải mã bằng CPU + chạy filter `ass` trên RAM + mã hóa đầu ra bằng `h264_nvenc`) giúp tránh nghẽn cổ chai truyền dữ liệu qua lại giữa VRAM và RAM.

## Kiểm Thử Pipeline Render & Phụ Đề
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_shorts_render.py tests/test_captions.py tests/test_ffmpeg_safety.py tests/test_pacing.py tests/test_music.py
```
