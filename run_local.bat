@echo off
chcp 65001 > nul
echo =======================================================
echo   Khởi chạy ChurchToolVideo trên Windows (Local Dev)
echo =======================================================

IF NOT EXIST ".venv" (
    echo [1/3] Đang khởi tạo môi trường ảo Python .venv...
    python -m venv .venv
    echo [2/3] Đang cài đặt thư viện cần thiết...
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
) ELSE (
    echo [OK] Môi trường ảo .venv đã sẵn sàng.
)

echo [3/3] Đang khởi động máy chủ FastAPI tại http://localhost:8000 ...
echo Nhấn Ctrl+C để dừng máy chủ.
echo.

set CHURCH_ENV_ARGS=
IF EXIST ".env" set CHURCH_ENV_ARGS=--env-file .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload %CHURCH_ENV_ARGS%
pause
