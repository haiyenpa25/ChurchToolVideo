@echo off
chcp 65001 > nul
echo =======================================================
echo   Kích hoạt WSL 2 cho Docker Desktop (Windows 11 Home)
echo =======================================================
echo.
echo Đang yêu cầu quyền Administrator để cài đặt WSL 2...
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoExit', '-Command', 'Write-Host \"Đang tiến hành cài đặt WSL 2 cho Docker Desktop...\" -ForegroundColor Cyan; wsl.exe --install --no-distribution; Write-Host \"`n=======================================================\" -ForegroundColor Green; Write-Host \"  CÀI ĐẶT WSL 2 HOÀN TẤT!\" -ForegroundColor Green; Write-Host \"  Nếu Windows yêu cầu restart, vui lòng KHỞI ĐỘNG LẠI MÁY TÍNH.\" -ForegroundColor Yellow; Write-Host \"=======================================================\" -ForegroundColor Green; pause'"
