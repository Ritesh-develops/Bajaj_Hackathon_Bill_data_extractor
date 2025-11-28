@echo off
REM Setup and run Bill Data Extractor (Windows)

echo.
echo ================================
echo Bill Data Extractor - Setup
echo ================================

REM Check Python version
echo.
echo [*] Checking Python version...
python --version

REM Create virtual environment
if not exist "venv" (
    echo.
    echo [*] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo.
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo [*] Installing dependencies...
pip install -r requirements.txt --quiet

REM Check for .env file
if not exist ".env" (
    echo.
    echo [*] Creating .env file from template...
    copy .env.example .env
    echo.
    echo [!] WARNING: Please edit .env and add your GEMINI_API_KEY
) else (
    echo.
    echo [*] .env file exists
)

REM Run tests
echo.
echo [*] Running tests...
pytest tests/ -v --tb=short || true

REM Start server
echo.
echo ================================
echo Starting API Server
echo ================================
echo.
echo [+] Server starting...
echo Docs: http://localhost:8000/docs
echo ReDoc: http://localhost:8000/redoc
echo Health: http://localhost:8000/health
echo.
echo Press Ctrl+C to stop
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
