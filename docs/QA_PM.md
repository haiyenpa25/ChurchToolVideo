# Kiểm thử theo góc nhìn quản lý dự án — 13/10/2026

Mục tiêu phát hành: người biên tập hoàn tất một bài giảng, kiểm tra đúng lời, xuất clip và mở lại dữ liệu mà không mất công sức. Bản ghi này phân biệt kiểm thử chức năng với độ chính xác nhận dạng giọng nói.

## Ma trận luồng đã chạy

| Luồng | Điều kiện chấp nhận | Kiểm chứng |
|---|---|---|
| Tải video → trích âm → phụ đề | Nhận video hợp lệ, từ chối tệp lỗi, tạo transcript có ID và timestamp | `test_pm_flows.py`, `test_shorts_ui.py`, `test_validation.py`; nhận dạng trong test luồng dùng fixture, trích âm FFmpeg thật |
| Chuẩn hóa thuật ngữ | Không thêm “phép” vào “Lễ Báp-têm”; không mất Christ, danh xưng, số chương/câu hoặc timestamp | `test_protestant_vocabulary.py`, `test_transcript.py` |
| Chọn clip → nghe ngữ cảnh | Chọn đúng đầu/cuối câu, giữ từ và thời gian, kiểm tra trước/sau | `test_workflow_tools.py`, `test_product_browser.py` |
| Sửa → hoàn tác/làm lại → mở lịch sử | Nội dung quay lại đúng phiên bản; video gốc còn nguyên | `test_editor_versions.py`, `test_product_browser.py` |
| Duyệt → sửa tiếp → render | Chưa duyệt thì chặn; sửa tiêu đề/lời/mốc cắt hủy duyệt cũ | `test_pm_flows.py`, `test_product_api.py` |
| Render từng clip và nhiều tỉ lệ | Có video thật, SRT khớp clip, ZIP tải được, giữ các clip còn lại | `test_pm_flows.py`, `test_single_clip_render.py`, `test_clip_formats.py` |
| Mở hai tab / dự án đổi trong lúc kiểm tra | Bản cũ nhận 409 trước khi xếp hàng; không ghi đè bản mới | `test_render_revision.py`, `test_product_editor_ui.py` |
| Hủy / lỗi render / khởi động lại | Dừng FFmpeg, dọn đầu ra dở; giữ clip xong trong thư viện; task gián đoạn có trạng thái rõ | `test_media_cancellation.py`, `test_task_cancellation.py`, `test_partial_render.py`, `test_phase6.py` |
| Sao lưu → nhập lại | Tạo ID mới, giữ nguồn cũ, yêu cầu duyệt lại; ZIP lỗi bị từ chối trước khi ghi tài sản | `test_pm_flows.py`, `test_portable_backup.py` |
| Phát hành → quản lý thư viện | Gói chứa video/SRT/JPEG/metadata, lưu trạng thái/link, giới hạn dung lượng và đóng gói đồng thời | `test_pm_flows.py`, `test_publication_package.py`, `test_library.py` |
| Desktop, điện thoại và đăng nhập | Luồng trình duyệt chạy, bố cục không tràn; API/media được bảo vệ khi bật mật khẩu | `test_product_browser.py`, `test_shorts_ui.py`, `test_auth_hardening.py` |

## Từ điển và chính sách biên tập

Danh mục tham khảo có **183 mục duy nhất**, gồm đủ 66 tên sách, tên nhân vật/địa danh, danh xưng và thuật ngữ giáo lý/mục vụ. Từ điển mặc định mới có danh mục này; từ điển người dùng đã lưu được giữ nguyên. Prompt soát phụ đề bổ sung danh mục nền bên cạnh từ điển riêng. Whisper sử dụng prompt lõi ngắn trong giới hạn 65 từ; không nhét toàn bộ 183 mục vào một prompt nhận dạng.

Đối chiếu chính tả và cách dùng tại [Kinh Thánh trực tuyến HTTLVN](https://kinhthanh.httlvn.org/?v=RVV11), [Tín lý HTTL Việt Nam miền Bắc](https://tinlanhmienbac.org/chuong-ix-tin-ly/), và [bài sinh hoạt có Báp-têm/Tiệc Thánh của HTTLVN](https://httlvn.org/hiep-nguyen-giao-pham-tinh-long-an-thang-10-2024.html). Đây là quy ước phụ đề của dự án; tên gọi, viết hoa và gạch nối có khác nhau giữa các bản dịch và Hội Thánh.

Có **125 test từ ngữ**: tên 66 sách trong ngữ cảnh đọc sách, biến thể gạch nối Unicode, chữ Unicode tổ hợp, lỗi phiên âm phổ biến, tính ổn định khi chuẩn hóa lại, không sửa từ thông thường, và giữ nguyên timestamp của từ/câu. Các quy tắc mới ưu tiên cụm dài và chỉ chạy một lượt, không sửa lại chính kết quả vừa thay. Bộ đếm chỉ tính thay đổi thật. Không tự đổi “ca đoàn” thành “Ban Hát”, “tái sinh tế bào” thành “tái sanh tế bào” hoặc thay bí tích bằng nghi lễ khác. Tên sách thông dụng như Mác/Tít/Truyền Đạo cần ngữ cảnh sách hoặc số chương để tránh sửa từ đời thường.

## Bóc băng thực tế

Chạy `large-v3-turbo` trên CUDA, không mock suy luận, với hai đoạn âm thanh công khai dài 90 giây:

| Mẫu | Thời gian bóc băng | Số đoạn nhận dạng | Thuật ngữ tìm thấy | Timestamp sau chuẩn hóa |
|---|---:|---:|---|---|
| [Những Lời Cảnh Báo — 30/3/2021](https://httlvn.org/nhung-loi-canh-bao-30-3-2021.html) | 30,88 giây | 10 | Chúa Giê-xu, Phi-e-rơ | Giữ nguyên |
| [Vì Sao Tôi Thuộc Về Hội Thánh? — 10/6/2019](https://httlvn.org/vi-sao-toi-thuoc-ve-hoi-thanh-10-6-2019.html) | 7,00 giây | 11 | Phao-lô, Đức Thánh Linh, Báp-têm | Giữ nguyên |

Thời gian gồm nạp model khi cần; không dùng hai số này để so sánh tốc độ giữa bài giảng. Tìm thấy từ không phải điểm độ chính xác: chưa có bản chép tay theo từng giây để tính WER. Một ví dụ vẫn cần người nghe duyệt là cách nhận dạng số thứ tự sách trong mẫu Cô-rinh-tô. Không tự suy diễn hoặc thay số chương/câu từ âm thanh chưa chắc chắn.

Tệp kết quả và phụ đề ở `workspace/tmp/qa_protestant`; lệnh chạy lại: `.venv\Scripts\python.exe scripts/benchmark_protestant_audio.py`. Đây là công cụ kiểm chứng có truy cập mạng và chạy AI thật, tách khỏi bộ pytest chạy thường xuyên. Một link âm thanh cũ cho ngày 7/6/2019 trả 404; đã chọn mẫu công khai còn tải được thay thế.

## Quyết định nghiệm thu

Kết quả cuối: **342/342 test đạt trong 60,42 giây**, trong đó có 125 test từ ngữ. Kiểm tra `compileall` cho ứng dụng/công cụ kiểm chứng và `git diff --check` đạt.

Luồng chức năng có thể kiểm chứng tự động. Phụ đề vẫn cần nghe duyệt trước khi phát hành. Phần còn cần nghiệm thu người dùng: bài giảng thật dài 30–60 phút, giọng miền Nam/miền Bắc, mic vang/tạp âm và tên riêng của Hội Thánh. LLM trực tiếp chưa được gọi trong đợt này; tích hợp được kiểm tra bằng mock để không phát sinh phí API.
