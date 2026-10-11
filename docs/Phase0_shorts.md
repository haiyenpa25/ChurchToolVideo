# Phase 0: Nền tảng Ghép Short

## Thay đổi

- Đưa `app/models/` vào các file được Git theo dõi; giữ các dependency NVIDIA cho Windows và rule `/models/` đã có trong working tree.
- Cắt frame-accurate bằng `-ss` trước input, `-t` theo thời lượng, video x264 và âm thanh AAC 160k.
- Sửa mô tả Stream Copy trong service và giao diện để nêu khả năng đứng hình/đen ở đầu clip do keyframe.
- Tách `_consume_segments` dùng chung cho GPU/CPU. Nếu generator GPU lỗi sau khi đã trả một phần dữ liệu, CPU chạy lại từ đầu, không trộn kết quả cũ.
- Dùng semaphore chung giới hạn một job bóc băng tại một thời điểm; service render ở Phase 3 phải dùng cùng `serialized_gpu_job`. Bảo vệ cache model bằng khóa.
- Thêm pytest, chuyển script kiểm tra sang entry point tương thích. Các file media kiểm thử nằm trong thư mục tạm.

## Kết quả kiểm tra

- `python -m pytest -q -s`: **14 passed**.
- FFmpeg thực: tạo video mẫu, probe metadata, trích WAV, cắt Stream Copy, cắt frame-accurate và kiểm tra ZIP.
- Cắt tại phút 40, thời lượng 2,5 giây, trên input tổng hợp 1 giờ (640×360): **0,18 giây**, output H.264/AAC và thời lượng trong sai số 0,1 giây.
- Xuất toàn bộ file staged sang thư mục tạm độc lập bằng `git checkout-index`; chạy `uvicorn app.main:app`, `/openapi.json` trả **HTTP 200**. Không sử dụng source từ working directory gốc.
- `git diff --cached --check`: không lỗi whitespace.

## Phạm vi nghiệm thu còn lại

- Chưa đo hiệu năng bằng video bài giảng thực tế có độ phân giải cao. Mốc 0,18 giây chỉ áp dụng cho input tổng hợp trên.
- Clone sạch nhánh remote `codex/shorts-phase-0`: 14 test pass; `uvicorn app.main:app` khởi động không lỗi import và OpenAPI trả HTTP 200. Dependencies dùng môi trường Python đã cài trên máy.
- Nhánh triển khai Phase 0: `codex/shorts-phase-0`.
- Theo yêu cầu mỗi Phase một PR và nghiệm thu trước Phase tiếp theo trong `Roadmap_shorts.md`, chưa triển khai Phase 1–6.

## Nội dung PR dự kiến

**Tiêu đề:** `fix: prepare shorts phase 0 with accurate cuts and serialized inference`

Khi cắt một đoạn gần cuối bài giảng, FFmpeg seek tới điểm bắt đầu trước khi decode và mã hóa lại AAC để đồng bộ âm thanh. Bóc băng dùng cùng logic tiêu thụ segment trên GPU/CPU, bảo vệ cache model và giới hạn một tác vụ để tránh cạnh tranh VRAM. Thêm các schema còn thiếu trong Git và bộ kiểm thử pytest.

Validation: 14 pytest tests pass; FFmpeg integration checks H.264/AAC output and late seek on a synthetic one-hour input; a clean staged source snapshot starts uvicorn and serves OpenAPI with HTTP 200. Clean remote clone verification also passes with 14 tests and uvicorn HTTP 200. Real sermon performance remains pending.
