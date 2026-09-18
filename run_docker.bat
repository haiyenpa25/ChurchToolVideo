@echo off
chcp 65001 > nul
echo =======================================================
echo   Khởi chạy ChurchToolVideo trên Docker Desktop
echo =======================================================
echo.

:: 1. Tự động dò tìm đường dẫn docker.exe trên máy tính
where docker >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    SET "DOCKER_BIN=docker"
) ELSE IF EXIST "%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe" (
    SET "DOCKER_BIN=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe"
    SET "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;%PATH%"
) ELSE IF EXIST "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
    SET "DOCKER_BIN=%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"
    SET "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
) ELSE (
    echo [LỖI] Không tìm thấy docker.exe trên hệ thống!
    echo Vui lòng đảm bảo bạn đã cài đặt Docker Desktop.
    pause
    exit /b 1
)

:: 2. Kiểm tra xem Docker Engine đã khởi động chưa
echo [1/2] Đang kiểm tra trạng thái Docker Engine...
%DOCKER_BIN% info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [CHÚ Ý] Docker Desktop chưa bật hoặc đang trong quá trình khởi động!
    echo Đang tự động mở Docker Desktop...
    start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe" 2>nul
    echo.
    echo Vui lòng đợi biểu tượng cá voi Docker Desktop chuyển sang màu xanh (Engine running)
    echo Sau khi Docker Desktop báo 'Engine running', hãy bấm phím bất kỳ để tiếp tục...
    pause > nul
)

:: 3. Tiến hành build và chạy container
echo.
echo [2/2] Đang build và khởi chạy container ChurchToolVideo...
docker compose up --build -d

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================
    echo   🎉 ChurchToolVideo Docker đã khởi chạy THÀNH CÔNG!
    echo   👉 Truy cập ứng dụng tại: http://localhost:8000
    echo =======================================================
    echo.
    echo * Xem nhật ký hoạt động (log):  docker compose logs -f
    echo * Dừng container:               docker compose down
    echo.
) ELSE (
    echo.
    echo [!] Quá trình khởi chạy gặp lỗi. Vui lòng kiểm tra lại Docker Desktop.
)

pause
