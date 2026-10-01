@echo off
chcp 65001 > nul
title 3D 변환기 메뉴 삭제 및 윈도우11 순정 복구

echo 3D 변환 메뉴 삭제 및 윈도우11 기본값 복구를 진행합니다...

:: 1. 윈도우 11 순정 메뉴 복구
reg delete "HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}" /f >nul 2>nul

:: 2. 3D 변환 메뉴 레지스트리 삭제
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%register_context_menu.py" uninstall >nul 2>nul

:: 3. 윈도우 탐색기 새로고침
taskkill /f /im explorer.exe >nul 2>nul
start explorer.exe

echo 완료되었습니다.
pause
