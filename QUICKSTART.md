# Bill Data Extractor

This is a production-grade solution for extracting line items from bills using AI vision and intelligent reconciliation.

## Quick Links
- [README](README.md) - Full documentation
- [Architecture](#architecture) - System design
- [Quick Start](#quick-start) - Get up and running

## Key Features
✅ AI-powered bill extraction using Gemini Vision
✅ Automatic reconciliation and validation  
✅ Double-counting prevention
✅ Image preprocessing (de-skew, denoise)
✅ Agentic retry for accuracy
✅ Production-ready API with Docker support

## Architecture
**Phase 1** → Image preprocessing  
**Phase 2** → Gemini Vision extraction with chain-of-thought  
**Phase 3** → Logic layer (cleaning, validation, reconciliation)  
**Phase 4** → Agentic retry if needed  
**Phase 5** → Formatted response  

## Quick Start
```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add GEMINI_API_KEY to .env

# Run
python -m uvicorn app.main:app --reload

# API at http://localhost:8000/docs
```

## API Usage
```bash
curl -X POST http://localhost:8000/api/extract-bill-data \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/bill.png"}'
```

See [README.md](README.md) for complete documentation.
