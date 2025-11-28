#!/bin/bash
# Setup and run Bill Data Extractor

set -e

echo "================================"
echo "Bill Data Extractor - Setup"
echo "================================"

# Check Python version
echo -e "\n✓ Checking Python version..."
python --version || python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
    echo -e "\n✓ Creating virtual environment..."
    python -m venv venv || python3 -m venv venv
fi

# Activate virtual environment
echo -e "\n✓ Activating virtual environment..."
source venv/bin/activate || source venv/Scripts/activate

# Install dependencies
echo -e "\n✓ Installing dependencies..."
pip install -r requirements.txt --quiet

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "\n✓ Creating .env file from template..."
    cp .env.example .env
    echo -e "\n⚠️  WARNING: Please edit .env and add your GEMINI_API_KEY"
else
    echo -e "\n✓ .env file exists"
fi

# Run tests
echo -e "\n✓ Running tests..."
pytest tests/ -v --tb=short || true

# Start server
echo -e "\n================================"
echo "Starting API Server"
echo "================================"
echo -e "\n✅ Server starting..."
echo "📚 Docs: http://localhost:8000/docs"
echo "🔍 ReDoc: http://localhost:8000/redoc"
echo "💚 Health: http://localhost:8000/health"
echo -e "\nPress Ctrl+C to stop\n"

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
