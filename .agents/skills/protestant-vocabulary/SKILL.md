---
name: protestant-vocabulary
description: >-
  Use this skill when adding, editing, or debugging Protestant Christian
  terminology, Bible book names (1925 Traditional Vietnamese Bible), Whisper
  initial prompts, or subtitle normalization rules in protestant_vocabulary.py
  and protestant_normalizer.py.
---

# Protestant Vocabulary & Subtitle Normalizer Skill

Hướng dẫn chuẩn hóa và mở rộng từ điển Tin Lành Việt Nam (Bản Truyền Thống 1925) cho **ChurchToolVideo**.

## Cấu Trúc Tệp Liên Quan
- `app/services/protestant_vocabulary.py`: Chứa danh sách từ vựng chuẩn (`PROTESTANT_TERMS_DICT`), 66 sách Kinh Thánh (`BIBLE_BOOKS`), và từ mồi cho Whisper (`CORE_WHISPER_PROMPT_TERMS`).
- `app/services/protestant_normalizer.py`: Chứa bộ máy chuẩn hóa regex theo ngữ cảnh (`normalize_protestant_text`, `get_core_hotwords_prompt`).
- `tests/test_protestant_vocabulary.py`: Bộ kiểm thử 125+ trường hợp chuẩn hóa và chống nhận diện nhầm (false-positive).

## Nguyên Tắc Khi Thêm / Sửa Từ Vựng

1. **Phân biệt từ đơn nghĩa và từ đa nghĩa**:
   - **Từ chuyên biệt** (ví dụ: `giê-xu`, `ha-lê-lu-gia`, `báp-têm`, `ma-thi-ơ`, `cô-rinh-tô`): Đặt trong `PROTESTANT_TERMS_DICT` để luôn chuẩn hóa dấu gạch nối và viết hoa.
   - **Từ đa nghĩa / xuất hiện trong giao tiếp đời thường** (ví dụ: `sáng thế`, `truyền đạo`, `sứ đồ`, `tiên tri`, `mục sư`, `thánh linh`, `tin lành`, `hội thánh`): **Không** thay thế mù quáng mọi vị trí. Phải đặt trong các quy tắc ngữ cảnh của `protestant_normalizer.py` (chỉ viết hoa khi đi kèm tên riêng, từ chỉ định thần học hoặc từ `Sách`/`Kinh Thánh`).
2. **Giới hạn Token của Whisper Prompt**:
   - Whisper chỉ nhận tối đa 224 token cho `initial_prompt`. Hàm `transcription_prompt()` trong `app/services/whisper_service.py` giới hạn ở 180 token và ưu tiên tên riêng người dùng nhập trước khi nối `CORE_WHISPER_PROMPT_TERMS`. Chỉ đưa các thuật ngữ quan trọng nhất, dễ bị Whisper nghe sai nhất vào `CORE_WHISPER_PROMPT_TERMS`.

## Kiểm Chứng Bắt Buộc
Sau mọi chỉnh sửa, chạy lệnh:
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_protestant_vocabulary.py tests/test_subtitle_fix.py
```
