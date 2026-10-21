---
name: churchvideo-quality-gate
description: >-
  Use this skill when validating code changes, checking for code duplication or
  temporary workspace clutter, rebuilding Tailwind CSS, or running the pytest
  and Playwright test suites in ChurchVideo.
---

# ChurchVideo Quality Gate & Verification Skill

Quy trình chuẩn để kiểm tra chất lượng code, dọn dẹp file tạm và xác minh toàn bộ hệ thống **ChurchToolVideo** hoạt động ổn định.

##Các Bước Thực Hiện

### 1. Kiểm tra môi trường & Phụ thuộc
Chạy lệnh kiểm tra nhanh môi trường (Python, FFmpeg, FFprobe, Whisper):
```powershell
.\.venv\Scripts\python.exe scripts\check_environment.py
```

### 2. Biên dịch lại Tailwind CSS (Nếu có sửa HTML/JS)
Nếu thay đổi có liên quan đến `app/static/index.html` hoặc `app/static/js/*.js`:
```powershell
npm run build:css
```

### 3. Chạy Bộ Kiểm Thử Nhanh (Unit, API & Node VM JS Tests)
Chạy tất cả các bài kiểm thử đơn vị (bỏ qua bài test trình duyệt Playwright nặng nếu cần kiểm tra nhanh):
```powershell
.\.venv\Scripts\python.exe -m pytest -q -m "not integration"
```

### 4. Chạy Kiểm Thử Trình Duyệt Đầy Đủ (Playwright E2E)
Khi thay đổi giao diện `index.html`, CSS hoặc luồng tương tác JS:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 5. Kiểm Tra & Dọn Dẹp File Tạm Trong `workspace/`
Đảm bảo không để sót dữ liệu test hoặc file tạm trong `workspace/tmp`, `workspace/audio`, `workspace/packages`, `workspace/segments`:
```powershell
foreach ($dir in @("workspace\tmp", "workspace\audio", "workspace\packages", "workspace\segments")) {
    if (Test-Path $dir) {
        Get-ChildItem $dir -Force | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Recurse -Force
    }
}
```
