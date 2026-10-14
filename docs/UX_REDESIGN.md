# Rà soát giao diện và quản lý dự án — 13/10/2026

## Đã triển khai

- Trang dự án có ảnh xem trước, tìm kiếm không phân biệt dấu, tên dễ đọc, số clip, trạng thái video gốc, đổi tên, Thùng rác và khôi phục.
- Tạo dự án mở trong hộp thoại riêng, nút tạo luôn ở đầu trang.
- Biên tập gồm danh sách clip, video xem trước và thuộc tính của một clip đang chọn; danh sách clip khác không còn kéo dài trang.
- Xuất video mở riêng, hỗ trợ xuất một clip hoặc cả dự án; vẫn kiểm tra duyệt nội dung trước khi xuất.
- Preset Hội Thánh, cấu hình xuất, sao lưu và thông tin phần cứng nằm trong Thiết lập/Tùy chọn.
- Giao diện sáng, tăng độ tương phản, bố cục điện thoại không tràn ngang.
- Xóa là chuyển vào Thùng rác: không xóa video gốc, clip trong thư viện hay bản sao lưu. API yêu cầu revision, chặn ghi dữ liệu vào dự án đã xóa và chặn quản lý khi tác vụ đang chạy.
- Ảnh kiểm tra giao diện mới: `workspace/tmp/ux_redesign`. Kiểm tra dự án thật chỉ đọc; kiểm tra sửa/xóa/khôi phục dùng dữ liệu cô lập trong tests.

Các ghi nhận dưới đây mô tả giao diện trước khi thiết kế lại.

## Kết quả kiểm tra bản mới

- `python -m pytest -q --tb=short`: 359 bài kiểm thử đạt.
- Kiểm thử trình duyệt có tải video, transcript, sửa phụ đề, chọn đoạn, undo/redo, preset Hội Thánh, duyệt clip, render nhiều tỷ lệ và một clip, tải kết quả, sao lưu/khôi phục, quản lý thư viện, đổi tên/Thùng rác/khôi phục.
- Kiểm tra trực tiếp 7 dự án hiện có trên cổng 8006 bằng request chỉ đọc: tìm kiếm không dấu, chọn clip thứ hai, hộp thoại xuất một clip, tạo dự án, desktop 1440×900 và điện thoại 390×844. Không có lỗi JavaScript hay tràn ngang.
- Dữ liệu dự án thật không bị đổi tên hoặc xóa trong kiểm thử. Các thao tác quản lý dùng database/tệp tạm cô lập.

## Kết luận

Ứng dụng có nhiều chức năng nhưng cấu trúc giao diện đang là một biểu mẫu kỹ thuật dài. Các đợt bổ sung tính năng chưa tạo thành một không gian biên tập thống nhất. Cần thiết kế lại cách tổ chức công việc, vị trí preview và quản lý dự án trước khi tiếp tục thêm tính năng.

## Kiểm tra thực tế

Kiểm tra bản đang chạy trên cổng 8004 ở desktop 1440×900 và điện thoại 390×844. Các request thay đổi dữ liệu được chặn trong phiên rà soát. Ảnh chụp ở `workspace/tmp/ux_audit`.

- Trang đầu có 7 dự án; khu vực tải video bắt đầu khoảng y=890, phải cuộn trên màn hình laptop.
- 6 dự án có video gốc; 1 dự án thiếu video. Hiện giao diện báo “Video gốc đã được dọn dẹp”, trong khi API chỉ kiểm tra tệp có tồn tại, không chứng minh nguyên nhân bị dọn.
- Với một dự án có một clip, trang biên tập dài khoảng 2.853 px trên desktop, có 33 nút hiện và 6 nhóm mở rộng. Trên điện thoại dài khoảng 4.288 px.
- Danh sách dự án chỉ có tên file và “Tiếp tục”. Không có nút/API xóa dự án, đổi tên, thumbnail, trạng thái hoặc ngày chỉnh gần nhất.
- `openWorkflowStage('export')` đưa về bước 4 giống luồng duyệt; không có màn hình xuất riêng tương ứng với nhãn điều hướng.

## Các vấn đề cần xử lý

| Vấn đề | Ảnh hưởng | Thiết kế thay thế |
|---|---|---|
| Dự án và vùng tải video nối thành một trang dài | Tạo mới khó tìm; số lượng dự án quyết định độ dài trang | Trang Dự án riêng, nút “Tạo dự án” cố định trên đầu |
| Tên file rất dài, nhiều file trùng tên | Khó biết dự án nào đang chỉnh hoặc đã hoàn tất | Tên dự án chỉnh được; tên file gốc là thông tin phụ; thêm ngày, thời lượng, số clip và trạng thái |
| Ba bước, thêm điều hướng phụ, thêm năm bước ở chế độ nâng cao | Người dùng khó hiểu vị trí hiện tại và bước tiếp theo | Một tuyến Dự án → Biên tập → Xuất; giữ chỉ một hệ điều hướng công việc |
| Video không luôn hiện cạnh phần đang chỉnh | Người dùng phải tìm hoặc bật xem thử; khó quan sát hiệu quả thao tác | Player cố định trong vùng biên tập, transcript/clip nằm cạnh |
| Import kết quả LLM và hướng dẫn cú pháp đứng trước các clip | Luồng kỹ thuật chiếm vị trí đầu; clip hiện tại xuống quá sâu | Nhóm “Thêm clip” có chọn transcript / đề xuất AI / nhập thủ công; mở nhập thủ công khi cần |
| Tiêu đề/kiểu chữ đứng trước việc kiểm tra lời và mốc cắt | Ưu tiên hình thức trước kiểm duyệt nội dung | Nội dung và mốc cắt → hình thức → duyệt → xuất |
| Nút render nằm trước checkbox duyệt trong thẻ clip | Thao tác không theo thứ tự công việc | Duyệt cạnh video; “Xuất video” là hành động chính sau khi đạt điều kiện |
| Nhiều thẻ lồng nhau, viền, khung và nút cùng độ nổi bật | Mọi nhóm tranh sự chú ý, khó nhận ra hành động chính | Một vùng làm việc; khối phẳng; một màu nhấn và một nút chính ở mỗi ngữ cảnh |
| GPU/dung lượng tạm chiếm nhiều chỗ ở đầu trang | Thông tin máy nổi hơn tên dự án và nội dung đang làm | Đưa trạng thái hệ thống vào menu thông tin/cài đặt; chỉ nổi cảnh báo cần xử lý |
| Trộn Clip, Part, Hook, Preset, Render, Waveform | Người biên tập phải hiểu thuật ngữ phần mềm trước | Dùng “Clip”, “Đoạn ghép”, “Câu mở đầu”, “Mẫu Hội Thánh”, “Xuất video”; thuật ngữ kỹ thuật ở cài đặt nâng cao |

## Cấu trúc đề xuất

### 1. Dự án

Đầu trang: tiêu đề “Dự án”, tìm kiếm, bộ lọc trạng thái và nút “Tạo dự án”. Danh sách dạng bảng/thẻ gọn: thumbnail, tên dễ đọc, ngày chỉnh, thời lượng nguồn, số clip, trạng thái. Mỗi dự án có “Tiếp tục” và menu “Đổi tên / Sao lưu / Chuyển vào thùng rác”. Tìm kiếm, phân trang hoặc tải thêm để danh sách không đẩy hành động chính xuống dưới.

Các mục toàn ứng dụng: Dự án, Thư viện video đã xuất và Cài đặt. Mẫu Hội Thánh/từ điển mặc định nằm trong Cài đặt; biên tập chỉ cần chọn mẫu để áp dụng.

### 2. Biên tập

Bố cục desktop ba vùng: bên trái danh sách clip/transcript; giữa là video và mốc cắt; bên phải là thuộc tính của clip đang chọn. Thanh trên có tên dự án, trạng thái tự lưu, hoàn tác và “Xuất video”. Video và hành động chính vẫn thấy khi chỉnh lời/crop.

Chỉ hiển thị chi tiết của một clip đang chọn. Thuộc tính chia thành Nội dung, Khung hình và Phụ đề; logo, font và hiệu ứng mở khi chọn nhóm tương ứng. Không tạo lại toàn bộ biểu mẫu cho mỗi clip trong danh sách. Duyệt nội dung gắn với clip đang xem và có trạng thái rõ trong danh sách.

Điện thoại: player ở trên, các tab “Clip / Nội dung / Kiểu” ở dưới; không ép ba cột hoặc xếp toàn bộ biểu mẫu desktop thành trang dài.

### 3. Xuất

Một màn hình hoặc hộp thoại riêng: chọn clip, chọn nền tảng/tỉ lệ, xem các cảnh báo cần xử lý, rồi “Xuất video”. Encoder, thread và tùy chọn chuyên sâu nằm trong một nhóm nhỏ. Kết quả có preview, tải video/SRT/ZIP và mở thư viện. Người dùng hiểu rõ đây là bước xuất, không quay lại biểu mẫu duyệt.

## Thiết kế xóa dự án

Đề xuất mặc định **xóa mềm**, có Thùng rác và Khôi phục. Thao tác này bỏ dự án khỏi danh sách đang làm; video gốc và nội dung biên tập còn phục hồi được. Video đã xuất trong thư viện và các ZIP sao lưu được giữ. Xóa vĩnh viễn là thao tác riêng, cần trình bày rõ các tài sản bị xóa và dung lượng được giải phóng.

Khi triển khai: chặn xóa lúc dự án đang chạy tác vụ; dừng tự lưu và bỏ phiên đang mở sau khi chuyển vào thùng rác; tăng revision để tab cũ không khôi phục lại dữ liệu bằng autosave. API phải quản lý trạng thái thùng rác, không chỉ thêm một nút frontend hoặc xóa một hàng SQLite rồi để tab khác tạo lại.

Hiện trạng: xóa trong thư viện, xóa backup và dọn tệp tạm là ba chức năng khác; không thay thế xóa dự án.

## Thứ tự thực hiện và tiêu chí nghiệm thu

1. Quản lý dự án: tên dễ đọc, trạng thái, tìm kiếm, xóa mềm và khôi phục. Nút Tạo dự án luôn thấy trong khung laptop.
2. Biên tập: player cố định, danh sách clip gọn, một clip đang chỉnh, một hệ điều hướng. Không phải cuộn qua các cài đặt khác để nghe/xem hoặc duyệt clip hiện tại.
3. Xuất và cài đặt: màn hình xuất đúng chức năng; đưa cấu hình máy/mẫu/từ điển ra khỏi luồng chính.
4. Kiểm tra với người dùng: tạo dự án, tìm dự án đã làm, đổi tên/xóa/khôi phục, chọn đoạn, sửa lời, duyệt và xuất. Theo dõi chỗ người dùng phải hỏi, số lần quay lại và thao tác bị nhầm.

Bộ kiểm thử chức năng đã chạy trước đó kiểm tra tính đúng của luồng/API/render. Đợt thiết kế lại cần thêm nghiệm thu về mức dễ tìm, dễ hiểu và số thao tác để hoàn tất công việc.
