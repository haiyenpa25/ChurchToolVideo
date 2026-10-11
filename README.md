# 🎬 ChurchToolVideo - AI Speech-to-Text & Smart Video Trimmer

Hệ thống web app tự động bóc băng âm thanh thành phụ đề chuẩn SRT bằng mô hình AI **faster-whisper** và thực hiện cắt video hàng loạt siêu tốc bằng kỹ thuật **FFmpeg Stream Copy (`-c copy`)**.

---

## 🌟 Tính Năng Nổi Bật

1. **Tiếp nhận Video đa định dạng:** Hỗ trợ MP4, MKV, MOV, AVI, WebM (kích thước lên đến 4GB).
2. **Tách luồng âm thanh chuẩn hóa:** Tự động gọi FFmpeg trích xuất âm thanh sang 16kHz mono WAV (chuẩn tối ưu cho Whisper).
3. **Bóc băng AI (Speech-to-Text):** Tích hợp `faster-whisper` hỗ trợ tăng tốc phần cứng qua **NVIDIA GPU (CUDA float16)** hoặc CPU fallback, sinh file `.srt` và `.vtt` chính xác đến từng mili-giây.
4. **Trợ lý Prompt LLM tích hợp:** Cung cấp sẵn mẫu câu lệnh (Prompt) chuẩn hóa để copy kèm toàn bộ phụ đề SRT gửi cho ChatGPT / Gemini lọc phân đoạn hay.
5. **Bộ phân tích cú pháp linh hoạt (Smart Parser):** Dán trực tiếp kết quả từ LLM, tự động nhận diện các định dạng:
   - `00:00:15 - 00:01:30: Tiêu đề phân đoạn`
   - `[00:00:15,000] --> [00:01:30,000]`
   - `01:15 -> 02:40`
   - Kèm tiêu đề hoặc số thứ tự đoạn thoại.
6. **Cắt video hàng loạt siêu tốc (Stream Copy):** Cắt hàng loạt các phân đoạn chỉ trong vài mili-giây mà không cần re-encode, giữ nguyên 100% độ nét gốc.
7. **Đóng gói & Tải về:** Xem trước từng clip, tải riêng từng đoạn hoặc tải toàn bộ qua 1 file `.zip`.
8. **Kiến trúc Asynchronous:** Tác vụ nặng chạy dạng Background Task không nghẽn giao diện, polling tiến độ real-time.
9. **Nền tảng Ghép Short — Phase 0:** Cắt chính xác dùng seek trước input và mã hóa AAC để tránh giải mã toàn bộ phần đầu bài giảng. Bóc băng dùng chung một semaphore cho các tác vụ GPU và khóa bảo vệ cache model; tác vụ tiếp theo chờ tác vụ hiện tại hoàn tất. Stream Copy vẫn nhanh nhưng có thể đứng hình/đen ở đầu clip do phụ thuộc keyframe.

### Ghép Short: tiến độ triển khai

**Phase 6:** Dự án, clip đã chỉnh, kết quả render và task được lưu trong `workspace/projects.sqlite3`. Dùng “Lưu dự án” ở Bước 4 và “Dự án đã lưu” để mở lại; các task hoàn tất giữ kết quả qua restart, task đang dở báo gián đoạn và cần chạy lại. Chạy một worker Uvicorn.

Tự căn khuôn mặt dùng OpenCV 4, lấy mẫu theo part, chọn khuôn mặt lớn nhất và làm mượt vị trí crop theo thời gian. Chọn “Cắt khung” và bật tự căn; nếu không phát hiện khuôn mặt thì dùng slider. Khuôn mặt quay nghiêng, bị che hoặc nhiều diễn giả có thể cần chỉnh tay.

Để bật LLM trực tiếp, cấu hình cặp biến `OPENAI_API_KEY` + `OPENAI_MODEL`, `GEMINI_API_KEY` + `GEMINI_MODEL` hoặc `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`. Key không được trả về trình duyệt. Nút “Gửi transcript để AI đề xuất Short” gọi nhà cung cấp đã chọn; người dùng kiểm tra clip trước khi render. Nếu API lỗi hoặc chưa có key, giữ luồng Copy Prompt. Integration tham chiếu [OpenAI Responses](https://developers.openai.com/api/docs/guides/text), [Gemini generateContent](https://ai.google.dev/gemini-api/docs/generate-content/text-generation) và [Claude Messages](https://platform.claude.com/docs/en/api/messages/create).

Đặt `CHURCH_PASSWORD` để bật đăng nhập cho API, video gốc, Short, ZIP, dự án và task; cookie HttpOnly có hạn 12 giờ. Có thể đặt thêm `CHURCH_SESSION_SECRET`. Sao chép `.env.example` thành `.env` rồi chạy `uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env --workers 1`. Khi phục vụ qua LAN cần bật mật khẩu; khi phục vụ qua Internet dùng HTTPS qua reverse proxy.

Kiểm thử trình duyệt: cài `requirements-dev.txt` và chạy `python -m playwright install chromium` trước `pytest`. Test UI dùng transcript fixture; kiểm thử Whisper thật trên giọng nói tổng hợp được thực hiện riêng. Kiểm thử API LLM dùng mock, không gửi transcript và không phát sinh phí API trong bộ test.

**Phase 5:** Ở Bước 4 chọn “Ghép Short 1:30”, dán JSON/CLIP rồi phân tích. Sửa tiêu đề và mốc thời gian (giây), dùng ±0,5s, xóa hoặc kéo part; nút ↑/↓ hỗ trợ đổi thứ tự trên điện thoại. Xem thử phát nối tiếp trên video gốc. Panel render có phụ đề, karaoke, tiêu đề, logo, encoder, ZIP và khung crop xem trước. Bước 5 có player và tải từng Short.

**Phase 4:** Phụ đề ASS 3–6 từ một dòng, viền đen, vị trí 70% chiều cao và karaoke tùy chọn. Font Noto Sans kèm giấy phép ở `app/assets/fonts` và được cài trong Docker. Bật `show_title` để hiện tiêu đề 3 giây đầu, upload logo PNG ≤2 MB qua `/api/shorts/logo` rồi dùng `logo_id`. SRT cũ không có word timestamps sẽ dùng thời gian ước tính trong câu; bóc băng lại để đồng bộ từng từ.

**Phase 3:** `POST /api/shorts/render` chạy nền, render từng part rồi concat và loudnorm; MP4 nằm ở `workspace/shorts`, tải qua `/workspace/shorts` hoặc ZIP. Tùy chọn 9:16 / 16:9 / source, blur_pad / crop, crop_x, phụ đề và encoder auto / NVENC / x264. Auto kiểm tra NVENC thực và fallback x264; chọn NVENC rõ ràng sẽ báo lỗi nếu không khả dụng. File tạm được xóa cả khi lỗi. Dọn workspace bị chặn khi có tác vụ đang chạy.

**Phase 2:** Nút Copy Prompt Short 1:30 tạo prompt gồm ID câu và thời lượng chính xác. `/api/shorts/preview` nhóm 1–4 part thành clip, nhận JSON, code fence, header CLIP và timestamp cũ; tự map ID, giới hạn padding ở khoảng lặng, snap timestamp theo từ và cảnh báo thời lượng/chồng part.

**Phase 1:** Bóc băng sinh thêm JSON với ID câu liên tục và timestamp từng từ. `GET /api/subtitles/{video_id}/llm-transcript` xuất transcript có ID; chuẩn hóa cập nhật cả JSON, giữ timestamp từ. SRT cũ được chuyển sang JSON khi đọc (không có timestamp từng từ; bóc băng lại để có dữ liệu này).

### Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

Nếu môi trường được quản lý bằng uv, dùng `uv pip install --python .\.venv\Scripts\python.exe -r requirements-dev.txt`.
Bộ test dùng thư mục tạm cho video/audio/zip, kiểm tra parser, khởi tạo FastAPI, GPU fallback, cache model và giới hạn đồng thời mà không tải model AI. Test tích hợp cần FFmpeg/FFprobe và kiểm tra cắt tại phút 40 của video tổng hợp 1 giờ (640×360); hiệu năng video bài giảng thực tế cần đo riêng. Lệnh `python test_system.py` cũng chạy bộ pytest này.

---

## 🚀 Hướng Dẫn Sử Dụng

### 1. Chạy Trực Tiếp Trên Máy Tính Này (Windows Dev Mode)

> Máy tính của bạn đã có **Python 3.11**, **NVIDIA RTX 3050 (CUDA 12.9)** và **FFmpeg** đã được cấu hình sẵn.

#### Cách 1: Chạy bằng file batch (1 click)
Nhấp đúp vào file `run_local.bat` trong thư mục dự án.

#### Cách 2: Chạy qua dòng lệnh (PowerShell)
```powershell
# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# Khởi động server FastAPI
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Sau đó mở trình duyệt truy cập: **`http://localhost:8000`**

---

### 2. Đóng Gói Và Sử Dụng Cho Máy Khác Qua Docker (Containerized Mode)

Toàn bộ ứng dụng đã được đóng gói khép kín trong `Dockerfile` và `docker-compose.yml`. Trên máy đích, chỉ cần cài đặt **Docker Engine & Docker Compose**.

#### Bước 1: Sao chép thư mục dự án sang máy khác
Sao chép thư mục `ChurchToolVideo` sang máy mới (bỏ qua thư mục `.venv` và `workspace/uploads`).

#### Bước 2: Khởi động container
```bash
# Cách 1: Chạy file batch (nếu máy Windows có Docker)
run_docker.bat

# Cách 2: Dùng lệnh docker compose
docker compose up --build -d
```

Ứng dụng sẽ tự động tải thư viện, cấu hình FFmpeg và chạy tại cổng `8000`:
👉 Truy cập: **`http://localhost:8000`**. Docker mặc định chỉ mở cổng trên localhost. Để dùng trong LAN, đặt `CHURCH_BIND_ADDRESS=0.0.0.0` và `CHURCH_PASSWORD` trong `.env`, rồi truy cập bằng IP máy chủ. `run_local.bat` cũng đọc `.env` nếu file tồn tại.

#### Quản lý Docker:
- Xem log thời gian thực: `docker compose logs -f`
- Dừng container: `docker compose down`

---

## 📂 Cấu Trúc Dự Án

```
ChurchToolVideo/
├── app/
│   ├── config.py              # Cấu hình đường dẫn, FFmpeg binary, GPU settings
│   ├── main.py                # FastAPI endpoints & static routing
│   ├── models/
│   │   └── schemas.py         # Pydantic schemas dữ liệu
│   ├── services/
│   │   ├── ffmpeg_service.py  # Xử lý audio, stream copy & nén zip
│   │   ├── whisper_service.py # fast-whisper engine (CUDA/CPU) & SRT generator
│   │   ├── parser_service.py  # Regex parser mốc thời gian từ LLMs
│   │   └── task_manager.py    # Quản lý tiến độ tác vụ ngầm (BackgroundTasks)
│   └── static/                # Giao diện người dùng SPA
│       ├── index.html         # Giao diện chính (Stepper 5 bước)
│       ├── css/style.css      # Dark mode glassmorphism UI
│       └── js/app.js          # Xử lý logic frontend, upload & polling
├── workspace/                 # Thư mục dữ liệu (Được mount qua Docker Volume)
│   ├── uploads/               # Video gốc tải lên
│   ├── audio/                 # Âm thanh WAV 16kHz tách từ video
│   ├── subtitles/             # Tệp phụ đề .srt và .vtt
│   ├── segments/              # Các đoạn video đã cắt
│   └── packages/              # Tệp .zip đóng gói tất cả đoạn cắt
├── Dockerfile                 # Đóng gói Python 3.11 + FFmpeg OS-level
├── docker-compose.yml         # Thiết lập Docker Compose
├── requirements.txt           # Danh sách thư viện Python
├── run_local.bat              # Script chạy trên Windows
├── run_docker.bat             # Script chạy trên Docker
└── README.md
```

---

## 💡 Lưu Ý Về XAMPP

Thư mục này hiện nằm trong `C:\xampp\htdocs\ChurchToolVideo`. 
- Ứng dụng là **Python FastAPI** chạy trên cổng riêng (`8000`), không phụ thuộc vào Apache/PHP của XAMPP.
- Nếu bạn muốn cấu hình Apache trong XAMPP làm Reverse Proxy trỏ đến cổng `8000`, chỉ cần bật `mod_proxy` trong file `httpd.conf` của Apache:
  ```apache
  ProxyPass /churchtool http://127.0.0.1:8000/
  ProxyPassReverse /churchtool http://127.0.0.1:8000/
  ```
