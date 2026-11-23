@echo off
chcp 65001 > nul
cls

echo ========================================
echo 구매계획안 분석 시스템 - 초기 설정
echo ========================================
echo.

REM 현재 디렉토리로 이동
cd /d "%~dp0"

echo [1/2] Python 패키지 설치 중...
echo.

REM requirements.txt의 모든 패키지 설치
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ❌ 패키지 설치 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ 모든 패키지 설치 완료!
echo.

echo [2/2] 환경 변수 설정 확인...
echo.

if not exist .env (
    echo ⚠️  .env 파일이 없습니다.
    echo 📝 .env 파일을 생성합니다...
    echo.
    echo # OpenAI API Key > .env
    echo OPENAI_API_KEY=your_api_key_here >> .env
    echo.
    echo ✅ .env 파일이 생성되었습니다.
    echo ⚠️  .env 파일을 열어서 OPENAI_API_KEY를 설정하세요!
    echo.
    notepad .env
) else (
    echo ✅ .env 파일이 이미 존재합니다.
)

echo.
echo ========================================
echo 설치 완료!
echo ========================================
echo.
echo 이제 'run.bat'을 실행하여 시스템을 사용하세요.
echo.
pause
