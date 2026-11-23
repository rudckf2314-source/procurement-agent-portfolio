@echo off
chcp 65001 > nul
cls

echo ========================================
echo 구매계획안 분석 시스템 시작
echo ========================================
echo.

REM 현재 디렉토리 저장
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [1/3] 환경 확인 중...
echo.

REM Python 설치 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되어 있지 않습니다.
    echo Python을 설치한 후 다시 실행하세요.
    pause
    exit /b 1
)

echo ✅ Python 환경 확인 완료
echo.

echo [2/3] 필수 패키지 확인 중...
echo.

REM FastAPI가 설치되어 있는지 확인
python -c "import fastapi" > nul 2>&1
if errorlevel 1 (
    echo 📦 필수 패키지를 설치합니다...
    echo.
    pip install -q fastapi uvicorn[standard] python-multipart
    if errorlevel 1 (
        echo ❌ 패키지 설치 실패
        pause
        exit /b 1
    )
    echo ✅ 패키지 설치 완료
) else (
    echo ✅ 필수 패키지 확인 완료
)

echo.
echo [3/3] 서버 실행 중...
echo.
echo 🚀 FastAPI 서버가 시작됩니다...
echo 📍 주소: http://localhost:8000
echo 📚 API 문서: http://localhost:8000/docs
echo.
echo ⚠️  이 창을 닫으면 서버가 종료됩니다!
echo 🌐 브라우저가 자동으로 열립니다...
echo.
echo ========================================
echo.

REM 브라우저 열기 (2초 후)
timeout /t 2 > nul
start "" "file:///%SCRIPT_DIR%frontend\index.html"

REM 서버 실행
python api_server.py

REM 서버 종료 시 메시지
echo.
echo 서버가 종료되었습니다.
pause
