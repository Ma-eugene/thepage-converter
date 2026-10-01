@echo off
chcp 65001 > nul
title 더페이지 3D 변환기 원클릭 통합 설치

echo ===================================================================
echo   더페이지 3D 변환기 원클릭 설치를 진행합니다...
echo ===================================================================
echo.

:: 1. 윈도우 11 '추가 옵션 표시' 없애고 1번에 뜨도록 레지스트리 적용
echo [1/2] 윈도우 11 우클릭을 원클릭 즉시 메뉴로 설정 중...
reg add "HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32" /f /ve >nul 2>nul

:: 2. 3D 변환기 우클릭 메뉴 등록
echo [2/2] 3D 초경량 변환 메뉴 등록 중...
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%register_context_menu.py" install >nul 2>nul

:: 3. 윈도우 탐색기 즉시 새로고침 (재부팅 없이 1초 반영)
taskkill /f /im explorer.exe >nul 2>nul
start explorer.exe

echo.
echo ===================================================================
echo   🎉 축하합니다! 모든 설정이 단 1초 만에 완료되었습니다!
echo   이제 파일이나 폴더를 우클릭하면 첫 화면에 바로 메뉴가 뜹니다.
echo ===================================================================
echo.
pause
