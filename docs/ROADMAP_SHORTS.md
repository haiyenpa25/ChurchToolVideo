# Roadmap: Tính năng "Ghép Short ~1:30 từ bài giảng"

> Tài liệu giao việc cho Codex. Làm **theo thứ tự Phase**, mỗi Phase là 1 PR riêng, phải pass tiêu chí nghiệm thu trước khi sang Phase kế.
> Ngôn ngữ UI/thông báo: tiếng Việt (giữ đúng phong cách hiện tại). Code/identifier: tiếng Anh.

## 1. Mục tiêu nghiệp vụ

```
Video bài giảng (30–90 phút)
  → Bóc băng có mốc thời gian
  → Copy transcript + prompt sang ChatGPT/Gemini
  → LLM trả về N clip, mỗi clip gồm 1..4 "part" (liền nhau HOẶC rải rác nhưng cùng 1 ý)
  → Hệ thống cắt các part, ghép lại thành 1 video ~60–90s / clip
  → Xuất dạng TikTok/Shorts: dọc 9:16, có phụ đề cháy (burn-in), âm lượng chuẩn
```

## 2. Đánh giá hệ thống hiện tại

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| Upload video | ✅ Có | `POST /api/upload`, stream 1MB chunk, ffprobe metadata |
| Bóc băng có timestamp | ✅ Có | faster-whisper, SRT/VTT, chuẩn hóa từ vựng Tin Lành. **Chỉ timestamp mức segment**, chưa có word-level |
| Prompt + copy sang LLM | ⚠️ Một phần | `copyPromptWithSrt()` trong `app/static/js/app.js` — prompt chỉ yêu cầu đoạn **liền nhau**, không có khái niệm "ghép nhiều khúc thành 1 clip", không ràng buộc thời lượng |
| Parse kết quả LLM | ⚠️ Một phần | `parse_timestamps_text()` — mỗi dòng = 1 đoạn độc lập. Không nhóm được nhiều đoạn vào 1 clip |
| Cắt video | ⚠️ Một phần | Cắt rời từng đoạn + zip. **Không ghép (concat)** |
| Dọc 9:16 / phụ đề cháy / loudnorm | ❌ Chưa có | |

**Kết luận:** hệ thống đáp ứng ~60% (bước 1–3). Thiếu phần lõi: **nhóm part → ghép thành 1 clip → xuất định dạng short**. Hiện tại người dùng phải cắt rời rồi tự ghép bằng CapCut.

### Lỗi / điểm yếu phát hiện khi review

1. **Repo clone mới sẽ crash**: `.gitignore` cũ có rule `models/` nên `app/models/schemas.py` **chưa từng được commit** (hiện đang untracked). Working tree đã sửa `.gitignore` (`/models/` + `!app/models/`) nhưng chưa commit.
2. **`trim_video_frame_accurate`** (`app/services/ffmpeg_service.py`) đặt `-ss` **sau** `-i` → ffmpeg decode từ đầu video tới điểm cắt. Với bài giảng 1 giờ, cắt đoạn phút 50 phải decode 50 phút → rất chậm. Khi đã re-encode thì `-ss` trước `-i` vẫn chính xác từng frame.
3. **`trim_video_stream_copy`**: `-c copy` luôn bắt đầu ở keyframe gần nhất → vài giây đầu bị đứng hình/đen. Docstring nói "không keyframe snap" là sai. Giữ làm chế độ "nhanh", nhưng **tính năng Short bắt buộc re-encode**.
4. `frame_accurate` dùng `-c:a copy` → audio có thể lệch vài chục ms so với video sau khi cắt chính xác. Nên encode AAC.
5. `whisper_service.transcribe_audio`: vòng lặp xử lý segment bị **lặp code 2 lần** (GPU và CPU fallback). Cần tách hàm chung.
6. **Không giới hạn đồng thời**: 2 tác vụ bóc băng chạy song song trên GPU (RTX 3050) dễ OOM; `_cached_model` global không thread-safe.
7. Model mặc định `base` cho tiếng Việt chất lượng kém; nên thử `large-v3-turbo` (`int8_float16` vừa VRAM 4GB).
8. `test_system.py`: dòng 20 dùng `shutil` nhưng không import ở đầu file. Không có test pytest thật.
9. Task state lưu RAM → restart server mất hết tiến độ (chấp nhận được cho tool nội bộ, xử lý ở Phase 6).
10. Không auth + CORS `*` — OK khi chạy localhost, **không được** expose ra LAN/Internet như hiện tại.

## 3. Quyết định thiết kế quan trọng

### 3.1 LLM trả về **ID câu**, không trả về timestamp

LLM hay "bịa"/làm tròn timestamp (sai vài giây → cắt giữa câu). Giải pháp: gán ID cho từng câu trong transcript gửi LLM, LLM chỉ trả về **khoảng ID**, hệ thống tự map sang thời gian chính xác từ dữ liệu Whisper.

Transcript gửi LLM (gọn hơn SRT ~40% token):
```
S0001 [00:00:12] Kính chào quý ông bà anh chị em...
S0002 [00:00:18] Hôm nay chúng ta cùng suy gẫm Giăng đoạn 3...
```

Vẫn **chấp nhận timestamp** làm fallback (tương thích ngược với cách dùng hiện tại).

### 3.2 Định dạng output LLM

Ưu tiên JSON (parse tin cậy nhất):
```json
{
  "clips": [
    {
      "title": "Tình yêu không điều kiện",
      "hook": "Bạn có biết Chúa yêu bạn ngay cả khi...",
      "parts": [
        {"from": "S0123", "to": "S0130"},
        {"from": "S0210", "to": "S0215"}
      ]
    }
  ]
}
```

Fallback dạng text (parser phải hỗ trợ cả hai):
```
CLIP 1: Tình yêu không điều kiện
- S0123 -> S0130
- 00:25:10 - 00:25:58

CLIP 2: ...
```
Dòng timestamp không có header `CLIP` → mỗi dòng là 1 clip 1 part (giữ hành vi cũ).

### 3.3 Pipeline render (FFmpeg)

Không dùng 1 `filter_complex` khổng lồ. Làm 3 bước, dễ debug:

1. **Mỗi part** → file tạm, re-encode cùng thông số:
   `ffmpeg -ss {start} -i input -t {dur} -vf "{reframe},{subtitles}" -af "afade=t=in:d=0.04,afade=t=out:st={dur-0.04}:d=0.04" -r 30 -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 160k -ar 48000 part_i.mp4`
2. **Ghép** bằng concat demuxer: `ffmpeg -f concat -safe 0 -i list.txt -c copy merged.mp4`
3. **Loudnorm** cuối: `-af loudnorm=I=-14:TP=-1.5:LRA=11` (chuẩn TikTok/Reels).

Reframe 9:16 (1080×1920):
- `crop`: `crop=ih*9/16:ih:(iw-ih*9/16)*{crop_x}:0,scale=1080:1920` — `crop_x` ∈ [0,1], mặc định 0.5 (người dùng chỉnh nếu mục sư đứng lệch).
- `blur_pad` (mặc định, an toàn): nền là video phóng to + blur, video gốc nằm giữa:
  `split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2`
- `source`: giữ nguyên tỉ lệ.

Encoder: dùng `h264_nvenc` nếu có GPU NVIDIA, fallback `libx264`.

**Lưu ý Windows:** filter `subtitles=`/`ass=` rất khó escape đường dẫn (`C\:/...`). Chạy ffmpeg với `cwd` = thư mục tạm và truyền tên file tương đối.

## 4. Roadmap

### Phase 0 — Dọn nền (nhỏ, làm trước)

- [x] Commit `app/models/` + `.gitignore` + `requirements.txt` đang thay đổi.
- [x] Tạo `tests/` dùng pytest; chuyển nội dung `test_system.py` thành test thật (sửa thiếu `import shutil`). Thêm `pytest` vào `requirements-dev.txt`.
- [x] `trim_video_frame_accurate`: chuyển `-ss` trước `-i`, dùng `-t duration`, audio encode `aac` thay vì copy.
- [x] Sửa docstring `trim_video_stream_copy` cho đúng (có keyframe snap); UI ghi rõ "nhanh nhưng có thể đứng hình đầu clip".
- [x] Refactor `transcribe_audio`: tách hàm `_consume_segments(segments_gen, ...)` dùng chung cho GPU và CPU fallback.
- [x] Thêm `threading.Semaphore(1)` cho job GPU (bóc băng + render) trong `task_manager` hoặc service.

**Nghiệm thu:** `pytest` pass; clone repo sạch rồi chạy `uvicorn app.main:app` không lỗi import; cắt frame-accurate đoạn ở phút 40 của video 1h chạy < 15s.

### Phase 1 — Transcript có ID + word timestamps

- [x] `whisper_service`: bật `word_timestamps=True` (kiểm tra `BatchedInferencePipeline` của version faster-whisper đang cài có hỗ trợ; nếu không thì fallback `model.transcribe`).
- [x] Lưu `workspace/subtitles/{video_id}.json`:
  ```json
  {"video_id": "...", "duration": 3600.0,
   "sentences": [{"id": "S0001", "start": 12.04, "end": 17.80, "text": "...",
                  "words": [{"w": "Kính", "start": 12.04, "end": 12.30}]}]}
  ```
  Mỗi Whisper segment = 1 sentence (đủ dùng). Chuẩn hóa Tin Lành áp dụng lên `text`; `words` giữ nguyên timestamp.
- [x] Endpoint `GET /api/subtitles/{video_id}/llm-transcript` → text dạng `S0001 [HH:MM:SS] câu...`.
- [x] Endpoint `POST /api/subtitles/{video_id}/normalize` phải cập nhật cả file `.json`.

**Nghiệm thu:** bóc băng video mẫu sinh đủ `.srt`, `.vtt`, `.json`; mọi `sentence.start < end`, ID liên tục, tăng dần.

### Phase 2 — Prompt Short + Parser nhóm clip

- [x] `app/services/prompt_service.py`: hàm `build_shorts_prompt(video_id, target_sec=90, num_clips=5)` trả về prompt + transcript ID. Endpoint `GET /api/shorts/prompt/{video_id}?target_sec=90&num_clips=5`.
  Prompt phải yêu cầu:
  - 3–5 clip, mỗi clip **tổng 60–90s**, 1–4 part.
  - Part có thể rải rác trong bài nhưng **cùng 1 ý**, nối lại phải trôi chảy, có nghĩa khi nghe độc lập.
  - Câu đầu clip là **hook** mạnh; kết thúc ở câu trọn vẹn; không cắt giữa câu.
  - Chỉ dùng ID có trong transcript. **Chỉ trả về JSON** đúng schema ở mục 3.2, không giải thích.
- [x] Frontend: nút "📋 Copy Prompt Short 1:30" ở Bước 3 gọi endpoint trên (giữ nút prompt cũ).
- [x] `app/services/shorts_parser.py`: `parse_shorts_text(raw_text, transcript) -> (clips, warnings, ignored_lines)`:
  - Thử JSON trước (tách khỏi code fence ```json nếu có), lỗi thì fallback text format.
  - Map ID → thời gian: `start = sentence[from].start - pad`, `end = sentence[to].end + pad`, `pad` mặc định 0.15s; **clamp** để không lấn sang câu bên cạnh (không vượt điểm giữa khoảng lặng giữa 2 câu).
  - Timestamp thô (fallback): snap về ranh giới word gần nhất trong `words`.
  - Cảnh báo (không chặn): tổng < 45s hoặc > 100s; part < 3s; part chồng nhau; ID không tồn tại; `from > to`.
- [x] Schemas mới trong `app/models/schemas.py`: `ClipPart{start_sec,end_sec,from_id?,to_id?,text_preview}`, `ShortClip{id,title,hook,parts,total_duration_sec,warnings}`, `ShortsPreviewRequest/Response`.
- [x] Endpoint `POST /api/shorts/preview`.

**Nghiệm thu:** unit test cho parser với: JSON chuẩn, JSON trong code fence, JSON lỗi → fallback text, format cũ 1 dòng/đoạn, ID không tồn tại, part chồng nhau, clip 3 part không liền nhau. Tổng thời lượng tính đúng.

### Phase 3 — Render Short (lõi)

- [x] `app/services/shorts_render_service.py`: `render_short(video_path, clip, options, progress_cb) -> Path` theo pipeline mục 3.3.
  - `options`: `aspect: "9:16"|"16:9"|"source"`, `reframe: "blur_pad"|"crop"`, `crop_x: float=0.5`, `burn_subtitles: bool=True`, `loudnorm: bool=True`, `encoder: "auto"|"nvenc"|"x264"`.
  - File tạm trong `workspace/tmp/{task_id}/`, xóa sau khi xong (kể cả khi lỗi).
- [x] Endpoint `POST /api/shorts/render` (background task, dùng `task_manager` + semaphore GPU) render nhiều clip, kết quả lưu `workspace/shorts/`, mount static `/workspace/shorts`, tùy chọn zip.
- [x] Thêm `SHORTS_DIR`, `TMP_DIR` vào `app/config.py`; thêm vào `/api/system/storage` và `/api/system/cleanup`.

**Nghiệm thu:** clip 3 part rải rác → 1 file MP4 1080×1920, 30fps, H.264/AAC 48kHz; thời lượng = tổng part ±0.3s; không đứng hình đầu part, không "bụp" tiếng ở chỗ nối; mở được trên điện thoại.

### Phase 4 — Phụ đề cháy kiểu TikTok

- [x] Sinh file `.ass` từ `words` cho từng part (timeline local của part): 3–6 từ/dòng, chữ to, viền đen, đặt ở ~70% chiều cao, font hỗ trợ tiếng Việt (bundle `Be Vietnam Pro` hoặc `Noto Sans` vào `app/assets/fonts/`, dùng `fontsdir=`). Tùy chọn highlight từ đang nói (karaoke `\k`).
- [x] Tùy chọn overlay tiêu đề clip 3s đầu (`drawtext`) và logo hội thánh (PNG góc trên).
- [x] Dockerfile: cài font / copy thư mục font.

**Nghiệm thu:** chữ có dấu tiếng Việt hiển thị đúng (ệ, ữ, ỡ...) trên cả Windows local và Docker; phụ đề khớp tiếng ±150ms.

### Phase 5 — UI "Ghép Short"

- [x] Bước 4: toggle chế độ **"Cắt rời từng đoạn"** (cũ) | **"Ghép Short 1:30"** (mới).
- [x] Mỗi clip hiển thị dạng card: tiêu đề (sửa được), danh sách part (start/end sửa được, nút ±0.5s, xóa part, kéo đổi thứ tự), text preview của part, badge tổng thời lượng (xanh 60–95s / vàng / đỏ), danh sách cảnh báo.
- [x] Nút **"▶ Xem thử"**: phát nối tiếp các part trên `<video>` hiện có (seek tới start part, `timeupdate` ≥ end thì nhảy part kế) — không cần render.
- [x] Panel tùy chọn render: tỉ lệ, kiểu reframe, slider `crop_x` có khung xem trước, bật/tắt phụ đề, logo.
- [x] Bước 5: player dọc cho từng short + tải từng file / zip.

**Nghiệm thu:** toàn bộ luồng chạy được bằng tay từ upload → tải short mà không cần mở công cụ khác ngoài ChatGPT/Gemini.

### Phase 6 — Tùy chọn / nâng cao (làm sau khi Phase 1–5 ổn)

- [x] Gọi API LLM trực tiếp (Gemini/OpenAI/Claude, API key qua biến môi trường) → bỏ bước copy-paste; giữ nguyên chế độ copy-paste làm fallback.
- [x] Persist task + project (SQLite) để restart không mất trạng thái; danh sách video đã xử lý.
- [x] Auto-reframe theo khuôn mặt (MediaPipe/OpenCV) thay cho `crop_x` cố định.
- [x] Auth đơn giản (1 mật khẩu) nếu muốn mở cho người khác trong mạng LAN dùng.

## 5. Quy ước chung cho Codex

- Giữ style hiện tại: FastAPI + service module trong `app/services/`, Pydantic schema trong `app/models/schemas.py`, background task qua `task_manager`, thông báo lỗi tiếng Việt.
- Mọi lệnh ffmpeg đi qua `ffmpeg_service` / `shorts_render_service`, dùng list args (không `shell=True`), bắt `CalledProcessError` và trả về message dễ hiểu.
- Không phá API cũ (`/api/trim/*`) — tính năng mới nằm dưới `/api/shorts/*`.
- Mỗi Phase: thêm/cập nhật test pytest, cập nhật README mục tính năng.


> Implementation status: Phases 0-6 are implemented in stacked PRs. See [SHORTS_IMPLEMENTATION.md](SHORTS_IMPLEMENTATION.md) for verification results and outstanding real-world validation. Checked tasks indicate implemented code, not completion of every manual acceptance scenario.
