# ROADMAP — Ổn định & an toàn hệ thống ChurchVideo Shorts

> Nguồn: rà soát ngày 2026-10-12 (backend, render pipeline, frontend). Test hiện tại: 87/87 pass.
> Cách dùng: làm **theo thứ tự**. Mỗi task có 1 prompt riêng — dán **Prompt ngữ cảnh chung** trước, rồi dán prompt của task. Xong task nào chạy test, commit, rồi mới sang task tiếp.

## Tổng quan

| Giai đoạn | Mục tiêu | Ước lượng | Task |
|---|---|---|---|
| 0 | Chốt code đang làm | 15 phút | 0.1 |
| 1 | An toàn dữ liệu & bảo mật | ~0,5 ngày | 1.1 – 1.4 |
| 2 | Trải nghiệm luồng clip | ~1 ngày | 2.1 – 2.5 |
| 3 | Render ổn định & nhanh | ~1 ngày | 3.1 – 3.4 |
| 4 | Nâng cấp (tuỳ chọn) | — | 4.1 – 4.3 |

### Checklist

- [x] 0.1 Commit phần đang làm
- [x] 1.1 Sửa nút Dọn dẹp (không xoá dữ liệu gốc)
- [x] 1.2 Validate `video_id`, `model_size`, giới hạn input
- [x] 1.3 Chặn XSS trong `app.js`
- [x] 1.4 Bắt buộc mật khẩu khi bind ngoài localhost + session secret
- [ ] 2.1 Polling dừng khi lỗi, render lỗi quay về bước 4
- [ ] 2.2 Autosave project + cảnh báo rời trang
- [ ] 2.3 Phân tích lại: xác nhận + khoá nút; `shortsRequest` chịu lỗi non-JSON
- [ ] 2.4 Preview cập nhật khi sửa part; chọn clip tự seek
- [ ] 2.5 Parser: cảnh báo gộp dòng, pad điểm cuối, id chữ thường
- [ ] 3.1 Video xoay & kích thước lẻ
- [ ] 3.2 Tối ưu ffmpeg (hwaccel, NVENC, bỏ copy thừa, kill process)
- [ ] 3.3 Hàng đợi tác vụ + bỏ blocking trong async
- [ ] 3.4 SQLite đóng kết nối, ẩn lỗi nội bộ, sửa thứ tự library add/delete
- [ ] 4.x Nâng cấp tuỳ chọn

---

## Prompt ngữ cảnh chung (dán đầu mỗi phiên ChatGPT)

```text
Bạn là kỹ sư Python/FastAPI + vanilla JS, đang sửa dự án "ChurchVideo" — app cắt video bài giảng thành video short dọc có phụ đề tiếng Việt (ASS), dùng faster-whisper, LLM, ffmpeg (NVENC). Chạy trên Windows, single worker.

Cấu trúc chính:
- Backend: app/main.py, app/shorts_api.py, app/library_api.py, app/auth.py, app/config.py, app/models/schemas.py
- Services: app/services/ (shorts_parser.py, shorts_render_service.py, captions_service.py, ffmpeg_service.py, task_manager.py, project_service.py, library_service.py, whisper_service.py, pacing_service.py, transcript_service.py có find_video())
- Frontend: app/static/index.html, app/static/js/{app.js, shorts.js, captions.js, clipeditor.js, projects.js, library.js, subfix.js}
- Tests: tests/ (pytest). Lệnh test: .venv\Scripts\python -m pytest -q

Quy tắc bắt buộc:
1. Thay đổi tối thiểu, đúng phạm vi task; giữ style code hiện có (tên biến, mật độ comment, thông báo UI bằng tiếng Việt).
2. Không đổi API/hành vi ngoài phạm vi task; không refactor lan man.
3. Mỗi lỗi sửa phải có test mới (pytest) chứng minh — viết test fail trước, rồi sửa cho pass.
4. Toàn bộ test cũ phải vẫn pass.
5. Nếu bạn không xem được file, hãy yêu cầu tôi dán nội dung file đó — KHÔNG đoán code.
6. Kết quả trả về: danh sách file đổi + diff hoặc code đầy đủ từng hàm đã sửa + test mới + lệnh kiểm tra.
```

---

## Giai đoạn 0 — Chốt phần đang làm

### 0.1 Commit (tự chạy, không cần ChatGPT)

```powershell
git add app tests docs
git commit -m "feat: per-clip editor, caption templates and Vietnamese fonts"
```

---

## Giai đoạn 1 — An toàn dữ liệu & bảo mật

### 1.1 Sửa nút Dọn dẹp

**Vấn đề:** `POST /api/system/cleanup` (app/main.py ~618-656) xoá cả `UPLOADS_DIR`, `SUBTITLES_DIR`, `LOGOS_DIR`, `SHORTS_DIR`; frontend (app/static/js/app.js:167) gọi `clear_all=true` → mất video gốc, phụ đề, logo, project (do `project_store.remove_missing`). Mặc định cũng xoá upload > 2 giờ.

```text
TASK 1.1 — Sửa endpoint dọn dẹp để không bao giờ xoá dữ liệu gốc.

File: app/main.py (hàm cleanup_storage, ~dòng 618-656), app/static/js/app.js (~dòng 160-175).

Yêu cầu:
- Chỉ dọn các thư mục tạm: AUDIO_DIR, TMP_DIR, PACKAGES_DIR, SEGMENTS_DIR. KHÔNG xoá UPLOADS_DIR, SUBTITLES_DIR, LOGOS_DIR, SHORTS_DIR và thư mục library.
- Bỏ lời gọi project_store.remove_missing(UPLOADS_DIR) khỏi cleanup.
- Giữ kiểm tra has_active_tasks (trả 409).
- Không nuốt lỗi im lặng: đếm số file xoá lỗi và trả về trong response ("failed_files").
- Frontend: hộp confirm trước khi dọn ghi rõ "Chỉ xoá file tạm (audio, gói zip, file trung gian). Video gốc, phụ đề, project và thư viện được giữ nguyên."
- Test mới trong tests/: tạo file giả trong UPLOADS_DIR, SUBTITLES_DIR, SHORTS_DIR và AUDIO_DIR/TMP_DIR (monkeypatch các DIR sang tmp_path), gọi endpoint với clear_all=true, assert chỉ file tạm bị xoá và project vẫn còn.

Tiêu chí xong: test mới pass, toàn bộ test pass.
```

### 1.2 Validate input

```text
TASK 1.2 — Validate input ở app/models/schemas.py.

Vấn đề:
- video_id ở các schema TranscribeRequest, TrimPreviewRequest, TrimExecuteRequest (và mọi schema khác có video_id không có pattern; schemas.py dòng ~39, 52, 70, 75, 83, 99, 201) không được validate → dùng trong UPLOADS_DIR.glob(f"{video_id}.*") và tên file output (main.py ~256, 419, 439, 478, 562) → path traversal / glob injection ("../x", "*").
- model_size (schemas.py ~53) là chuỗi tự do → WhisperModel tải repo tuỳ ý. language, initial_prompt không giới hạn độ dài.
- TrimSegment/TrimExecuteRequest: start_sec/end_sec không có ge=0, không kiểm end>start, không chặn inf/nan; segments không max_length; title không max_length; trim_mode là str tự do.

Yêu cầu:
- Mọi video_id: Field(pattern=r"^[A-Za-z0-9_-]{1,80}$") (định nghĩa 1 type alias VideoId dùng chung).
- model_size: chỉ nhận giá trị trong SUPPORTED_MODELS (app/config.py:58) — dùng Literal hoặc field_validator.
- language: max_length=10; initial_prompt: max_length=2000.
- TrimSegment: start_sec ge=0, end_sec > start_sec (model_validator), allow_inf_nan=False; title max_length=200; segments max_length=50; trim_mode Literal theo các giá trị đang dùng trong ffmpeg_service.py (đọc code để lấy đúng giá trị).
- Ở main.py, thay các chỗ glob thủ công bằng find_video() từ app/services/transcript_service.py nếu tương đương.
- Test: request với video_id "../x", "a*", model_size "evil/repo", end<start → 422.
```

### 1.3 Chặn XSS trong app.js

```text
TASK 1.3 — Chặn XSS trong app/static/js/app.js (chế độ cắt đoạn cũ).

Vấn đề: dữ liệu từ LLM/transcript/người dùng chèn vào innerHTML không escape:
- app.js ~581: ignored_lines chèn thẳng vào <li>
- app.js ~700: value="${seg.title}" → thoát khỏi thuộc tính
- app.js ~792-796: seg.title, seg.filename trong title, div và thuộc tính download

Yêu cầu:
- Dùng hàm escapeHtml có sẵn (app.js ~1021) cho mọi giá trị động đưa vào template HTML (cả nội dung và thuộc tính). Đảm bảo escapeHtml escape cả & < > " '.
- Rà toàn bộ app.js, projects.js, library.js, subfix.js tìm innerHTML/insertAdjacentHTML với biến chưa escape và sửa luôn; liệt kê từng vị trí đã sửa.
- projects.js ~34: selector option[value=${provider.id}] → dùng CSS.escape và kiểm tra null.
- Thêm test trong tests/test_shorts_ui.py (kiểu test đọc file JS hiện có) assert các vị trí trên dùng escapeHtml.
```

### 1.4 Bắt buộc mật khẩu khi mở ra mạng

```text
TASK 1.4 — Siết xác thực ở app/auth.py và app/config.py.

Vấn đề:
- auth.py ~41: CHURCH_PASSWORD rỗng (mặc định) → tắt toàn bộ auth.
- auth.py ~23: không có CHURCH_SESSION_SECRET thì khoá ký = sha256(":" + password) → lộ cookie là brute-force được mật khẩu offline.

Yêu cầu:
- Khi khởi động: nếu host bind không phải loopback (127.0.0.1/localhost/::1) và CHURCH_PASSWORD rỗng → log lỗi rõ ràng bằng tiếng Việt và không khởi động (hoặc ép bind 127.0.0.1). Đọc run_local.bat, docker-compose.yml, Dockerfile để biết host được truyền thế nào; với Docker (0.0.0.0) cần hướng dẫn đặt biến trong .env/README.
- Nếu thiếu CHURCH_SESSION_SECRET: sinh ngẫu nhiên secrets.token_hex(32), lưu vào file trong workspace (vd workspace/.session_secret) và tái sử dụng lần sau.
- Dọn _attempts định kỳ (xoá IP hết hạn) để không phình bộ nhớ.
- Cập nhật README phần cấu hình.
- Test: secret được sinh và tái dùng; logic kiểm tra loopback.
```

---

## Giai đoạn 2 — Trải nghiệm luồng clip

### 2.1 Polling & điều hướng khi lỗi

```text
TASK 2.1 — Sửa vòng polling tác vụ trong app/static/js/app.js (~dòng 418-478).

Vấn đề: response lỗi hoặc lỗi mạng (kể cả 404 sau khi server restart) chỉ gọi scheduleNext() mãi mãi → state.pollTimer không bao giờ null → projects.js ~73 từ chối mở project ("Đợi tác vụ..."), shortsBusy kẹt true → nút render bị khoá (shorts.js ~83, 206). Ngoài ra render thất bại gọi navigateToStep(1) (~461) thay vì quay về bước chỉnh clip.

Yêu cầu:
- 404 → dừng ngay, chạy nhánh thất bại với thông báo "Tác vụ không còn tồn tại (server có thể đã khởi động lại)".
- Lỗi khác: dừng sau 5 lần liên tiếp, có backoff (5s → 10s → 20s, tối đa 30s).
- Nhánh thất bại luôn: clear pollTimer, reset shortsBusy, bật lại nút.
- Tác vụ loại Shorts thất bại → navigateToStep(4) và giữ nguyên state.shortClips; loại khác giữ hành vi cũ.
- Khôi phục lại tiêu đề "#step2 h2" mà shorts.js ~214 đã đổi sau khi tác vụ kết thúc.
```

### 2.2 Autosave

```text
TASK 2.2 — Tự lưu project Shorts.

Bối cảnh: clip, style từng clip, chữ đã sửa chỉ nằm trong state.shortClips; chỉ lưu khi bấm "Lưu project" (projects.js ~58). Reload là mất.

Yêu cầu:
- Debounce 2 giây sau mỗi thay đổi trong editor clip (shorts.js, clipeditor.js, captions.js — tìm các điểm thay đổi state.shortClips, có thể gom vào một hàm markDirty()) → gọi cùng API lưu project mà projects.js đang dùng. Nếu chưa có project thì tạo mới tự động với tên = tên video.
- Hiển thị trạng thái nhỏ: "Đã lưu lúc HH:MM" / "Đang lưu..." / "Lưu thất bại — thử lại".
- Đồng thời lưu bản nháp vào localStorage (bọc try/catch) để khôi phục nếu server lỗi; khi mở lại cùng video, hỏi "Khôi phục bản nháp chưa lưu?".
- beforeunload cảnh báo nếu còn thay đổi chưa lưu.
- Không gửi lưu khi đang có request lưu khác (tránh ghi đè lộn xộn).
```

### 2.3 Phân tích lại an toàn

```text
TASK 2.3 — An toàn cho nút "Phân tích" và shortsRequest.

File: app/static/js/shorts.js, captions.js.
- parseShorts (~31-42) ghi đè state.shortClips không hỏi → nếu đã có clip có chỉnh sửa, confirm("Phân tích lại sẽ thay toàn bộ clip và chỉnh sửa hiện tại. Tiếp tục?"). Tốt hơn: giữ lại style/title đã sửa cho clip có cùng số thứ tự và cùng khoảng thời gian.
- Khoá nút Phân tích + hiện "Đang phân tích..." trong lúc request, tránh double-click.
- shortsRequest (~17-21) gọi response.json() vô điều kiện → nếu content-type không phải JSON, ném lỗi "Máy chủ lỗi (HTTP <status>)" thay vì "Unexpected token <".
- captions.js ~68: catch(e){return;} khi tải /caption-templates, /caption-fonts → hiện toast lỗi + nút thử lại.
- captions.js ~73-86: setInterval 450ms chạy mãi → chỉ chạy khi bước 4 đang hiển thị (dừng khi rời bước), hoặc chuyển sang CSS animation.
```

### 2.4 Preview đúng thực tế

```text
TASK 2.4 — Preview cập nhật đúng.

File: app/static/js/shorts.js, captions.js, clipeditor.js, projects.js.
- moveShortPart (~95), removeShortPart (~93) và nhánh không hợp lệ của editShortPart (~88) không gọi bumpCaptions() → previewLines cache theo version (captions.js ~129) hiển thị dòng cũ. Thêm bumpCaptions().
- Các hàm đó render lại toàn bộ thẻ → textarea "✎ Sửa chữ" đang mở bị mất nội dung. Áp dụng cùng guard như editShortPart (~86) hoặc giữ nội dung đang soạn.
- setActiveClip: seek video tới thời điểm bắt đầu part đầu tiên của clip được chọn.
- Video chưa phiên âm: fillMissingClipWords hiện "Đang tải lời..." mãi → hiện "Video chưa có phiên âm — hãy chạy Phiên âm trước để có phụ đề".
- Bỏ code chết: projects.js ~82 (selectCaptionTemplate không tồn tại), ~83 (state.captionWords không ai đọc); shorts.js ~73 bỏ markCaptionGallery() trong oninput của tiêu đề.
```

### 2.5 Parser danh sách clip

```text
TASK 2.5 — Sửa app/services/shorts_parser.py.

Vấn đề:
- ~34-64: các dòng S-id liền nhau không có tiêu đề giờ bị gộp thành 1 clip; >10 part bị bỏ (~75); chỉ báo khi gộp >4 dòng (~105).
- ~96-100: part theo timestamp snap điểm cuối về word end gần nhất, không pad → cụt chữ; end có thể <= start rồi bị bỏ.
- ~83: id chữ thường trong JSON ("s5") không khớp, trong khi đường text có upper() (~48).

Yêu cầu:
- Định dạng chuẩn "HH:MM:SS - HH:MM:SS: Clip N - Tiêu đề": nhiều dòng cùng "Clip N" = 1 clip nhiều part (giữ nguyên hành vi này, đã có test).
- Dòng không có "Clip N" và không có tiêu đề: mỗi dòng 1 clip (hành vi cũ), KHÔNG tự gộp.
- Mọi lần gộp hoặc cắt bỏ part (>10) đều phải thêm note cảnh báo rõ ràng.
- Snap: start → word start gần nhất <= start (nếu có), end → word end nhỏ nhất >= end nhưng chỉ chọn word end > start; sau đó áp dụng pad giống nhánh S-id.
- JSON id: str(id).upper().
- Test cho từng trường hợp trong tests/test_shorts_parser.py.
```

---

## Giai đoạn 3 — Render ổn định & nhanh

### 3.1 Video xoay & kích thước lẻ

```text
TASK 3.1 — Sửa kích thước khung khi render.

- app/services/ffmpeg_service.py get_media_info: đọc rotation (tag "rotate" hoặc side_data_list displaymatrix "rotation"); nếu 90/-90/270 thì đổi chỗ width/height. ffmpeg tự xoay khi decode nên crop phải tính theo kích thước sau xoay.
- app/services/shorts_render_service.py (~78, 110, 140, 213): ở aspect "source", output_size trả kích thước gốc có thể lẻ → video_filter làm tròn chẵn nhưng ASS PlayRes và crop của band dùng giá trị lẻ → ffmpeg lỗi. Làm tròn chẵn ngay sau output_size và dùng thống nhất ở mọi nơi.
- Test: mock ffprobe JSON có rotation=90 → width/height bị đổi; source 1081x1921 → mọi kích thước dùng 1080x1920.
```

### 3.2 Tối ưu ffmpeg & sửa timing phụ đề

```text
TASK 3.2 — Tối ưu lệnh ffmpeg và sửa timing phụ đề.

- app/services/shorts_render_service.py ~231-236: khi dùng NVENC, thêm "-rc vbr -b:v 0" cạnh -cq để thiết lập chất lượng có hiệu lực.
- Thêm "-hwaccel auto" vào input args (chỉ khi có GPU; fallback CPU vẫn chạy được). Filter chain vẫn trên CPU — đảm bảo không cần hwdownload.
- ~251: shutil.copyfile(final.mp4 → output) → shutil.move.
- ~38-48: nếu progress_cb ném lỗi thì Popen bị bỏ rơi; process.wait() không timeout → bọc try/finally, kill process khi lỗi, wait có timeout hợp lý.
- app/services/pacing_service.py ~31: spans[0] IndexError khi spans rỗng → if not spans: return [part].
- app/services/captions_service.py ~19-22: opcode "insert" gán thời gian của words[a] → chồng thời gian với từ kế tiếp; khi b == a hãy chia khoảng trống trước words[a]["start"] (như realign_words đang làm).
- captions_service.py ~365-370: karaoke/fill có intro thì từ đầu mất 0.15s fill → bỏ tách intro khi highlight == "fill" hoặc karaoke.
- Test cho pacing rỗng, insert timing, cờ NVENC trong lệnh build.
```

### 3.3 Hàng đợi & không chặn event loop

```text
TASK 3.3 — Hàng đợi tác vụ và bỏ blocking trong async handler.

- Blocking trong async def: app/main.py ~138-184 (upload: get_media_info subprocess, buffer.write), ~417 (/trim/preview ffprobe), ~586 (/system/storage duyệt thư mục), ~98 (/system/status nvidia-smi), app/shorts_api.py ~80. → chuyển thành def thường hoặc bọc run_in_threadpool.
- Upload (~169): get_media_info lỗi → xoá file vừa ghi, trả 400 "Không phải file video hợp lệ"; client ngắt giữa chừng → xoá file dở.
- Trim/render/LLM chạy bằng BackgroundTasks không giới hạn → tạo executor giới hạn trong task_manager (render: 1 worker mặc định, cấu hình qua env RENDER_WORKERS; trim: 2). Hàng đợi đầy (vd >10 tác vụ chờ) → 429. Task ở trạng thái chờ hiện "Đang xếp hàng (vị trí N)".
- Giới hạn trong schemas: tổng số words trong 1 request render (vd 50.000), tổng thời lượng clip (vd 15 phút); /api/shorts/realign-words giảm giới hạn và chạy trong threadpool.
- Test: endpoint trả 429 khi hàng đợi đầy (mock executor).
```

### 3.4 Lưu trữ & lỗi

```text
TASK 3.4 — SQLite, library, thông báo lỗi.

- app/services/task_manager.py ~43-46, 75-97, project_service.py, library_service.py: "with sqlite3.connect()" không đóng kết nối → dùng contextlib.closing hoặc 1 connection/store (check_same_thread=False + lock). Throttle ghi tiến độ task (tối đa 1 lần/giây trừ khi đổi trạng thái).
- library_service.py ~77-82: add() move file trước get_media_info → validate trước rồi mới move. ~153 delete(): xoá file trước, xoá row sau; PermissionError trên Windows → trả lỗi rõ ràng, không để orphan.
- app/shorts_api.py ~56-72: batch lỗi giữa chừng → ghi các clip đã xong vào result của task (partial results) để người dùng vẫn tải được.
- app/main.py ~249, 553, shorts_api.py ~74: fail_task(str(e)) lộ stderr ffmpeg + đường dẫn → log chi tiết bằng logger, trả người dùng thông báo chung tiếng Việt + mã lỗi ngắn. VideoInfo.file_path (~175) không trả đường dẫn tuyệt đối.
- app/services/llm_service.py: retry có backoff cho 429/5xx (tối đa 3 lần).
- Thêm lịch dọn tự động file tạm > 24h (chỉ các thư mục tạm của Task 1.1) khi khởi động và mỗi 6 giờ; prune task history > 30 ngày.
```

---

## Giai đoạn 4 — Nâng cấp (tuỳ chọn)

```text
TASK 4.1 — Tỉ lệ khung (9:16, 1:1, 4:5, 16:9) chọn riêng từng clip trong editor clip, thay vì checkbox chung ở tuỳ chọn render. Preview và vị trí phụ đề dùng tỉ lệ của clip đang chọn. Giữ tương thích project cũ (mặc định = lựa chọn chung cũ).
```

```text
TASK 4.2 — Render từng clip riêng: nút "Render clip này" trên mỗi thẻ clip, thanh tiến độ riêng cho từng clip, sau khi xong có nút "Sửa & render lại" quay về đúng clip đó.
```

```text
TASK 4.3 — Gom helper dùng chung (shortsEscape, shortsRequest, captionTemplate, CAPTION_ANIMATIONS, CAPTION_BOXES, tính caption_y mặc định đang lặp ở captions.js ~157, 209 và clipeditor.js ~9) vào một file app/static/js/common.js nạp trước các file khác trong index.html; bỏ input ẩn shortCaptionPosition/shortCaptionStyle trong index.html (~510-512) nếu không còn dùng. Không đổi hành vi.
```

---

## Quy trình mỗi task

1. Dán **Prompt ngữ cảnh chung** + prompt task vào ChatGPT (nếu ChatGPT không đọc được repo, đính kèm các file được nêu trong task).
2. Áp dụng thay đổi.
3. Chạy `.venv\Scripts\python -m pytest -q` — phải xanh hết.
4. Mở app thử thủ công đúng luồng liên quan.
5. `git commit` với message ghi số task (vd `fix(1.1): cleanup chỉ xoá file tạm`).
6. Tick checklist ở đầu file này.
