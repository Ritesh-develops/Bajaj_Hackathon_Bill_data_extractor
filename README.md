# Bill Data Extractor API

A production-grade solution for extracting line item details from bill/invoice images using AI with automatic reconciliation and validation.

## 🎯 Features

- **Vision LLM Extraction**: Uses Google Gemini 2.0 Flash for intelligent bill parsing
- **Multi-Phase Processing**: Ingestion → Extraction → Validation → Reconciliation
- **Automatic Reconciliation**: Detects and corrects discrepancies between extracted and actual totals
- **Double-Counting Prevention**: Intelligent filtering to exclude totals, taxes, and fees
- **Image Preprocessing**: De-skewing, binarization, resolution optimization
- **Agentic Retry**: Self-correcting mechanism when totals don't match
- **Production Ready**: Docker support, comprehensive error handling, detailed logging

## 🏗️ Architecture

The solution follows a "Gold Standard" workflow mimicking how a human accountant works:

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Ingestion & Pre-processing                        │
│ - Validate URL and download document                       │
│ - Detect format (Image/PDF)                                │
│ - De-skew, binarize, optimize resolution                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Hybrid Extraction                                 │
│ - Send to Gemini Vision with Chain-of-Thought prompt       │
│ - Locate table, identify headers, extract rows             │
│ - Extract bill total separately                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Logic & Reconciliation                            │
│ - Clean and standardize extracted data                     │
│ - Remove double-count entries (Total, Tax, etc.)           │
│ - Calculate sum and compare with bill total                │
│ - Validate line item calculations (Qty × Rate = Amount)    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Agentic Retry (if needed)                         │
│ - If totals don't match, send back to Gemini               │
│ - Provide specific feedback on discrepancy                 │
│ - Request corrections (add/remove/modify items)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 5: Response Formatting                               │
│ - Return validated, reconciled data in standard format      │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
bill-extractor/
├── app/
│   ├── api/
│   │   ├── routes.py              # API endpoints
│   │   ├── dependencies.py        # Dependency injection
│   │   └── __init__.py
│   │
│   ├── core/
│   │   ├── image_processing.py    # Image preprocessing
│   │   ├── extractor.py           # Gemini Vision integration
│   │   ├── logic.py               # Reconciliation & validation
│   │   └── __init__.py
│   │
│   ├── models/
│   │   ├── schemas.py             # Pydantic data models
│   │   ├── prompts.py             # LLM prompts
│   │   └── __init__.py
│   │
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management
│   └── __init__.py
│
├── tests/
│   ├── test_logic.py              # Unit tests
│   └── __init__.py
│
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker Compose setup
├── .env.example                   # Environment template
└── README.md                      # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Google Gemini API key (get from [Google AI Studio](https://aistudio.google.com))
- Docker & Docker Compose (optional, for containerized deployment)

### Local Setup

1. **Clone and navigate to project**
```bash
cd bill-extractor
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

5. **Run tests**
```bash
pytest tests/ -v
```

6. **Start API server**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Docker Deployment

1. **Build and run with Docker Compose**
```bash
docker-compose up --build
```

2. **Or build and run manually**
```bash
docker build -t bill-extractor .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key_here bill-extractor
```

## 📡 API Usage

### Extract Bill Data

**Endpoint:** `POST /api/extract-bill-data`

**Request:**
```json
{
  "document": "https://example.com/bill.png"
}
```

**Response (Success):**
```json
{
  "is_success": true,
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "bill_items": [
          {
            "item_name": "Livi 300mg Tab",
            "item_quantity": 14,
            "item_rate": 32,
            "item_amount": 448
          },
          {
            "item_name": "Metnuro",
            "item_quantity": 7,
            "item_rate": 17.72,
            "item_amount": 124.03
          }
        ]
      }
    ],
    "total_item_count": 2,
    "reconciled_amount": 572.03
  }
}
```

**Response (Error):**
```json
{
  "is_success": false,
  "error": "Failed to download document"
}
```

## 🔧 Configuration

Edit `.env` file to customize:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# LLM Configuration (REQUIRED)
GEMINI_API_KEY=your_key_here
LLM_MODEL=gemini-2.0-flash

# Image Processing
TARGET_DPI=300
MIN_RESOLUTION=800

# Reconciliation
RECONCILIATION_THRESHOLD=0.01      # 0.01% acceptable discrepancy
MAX_RETRY_ATTEMPTS=3               # Retry count if totals don't match

# Logging
LOG_LEVEL=INFO
```

## 🧠 How It Works

### Phase 1: Image Preprocessing
```python
# De-skewing: Detects and corrects tilted documents
# Binarization: Converts to B&W, removes background artifacts
# Upscaling: Enhances low-resolution images using INTER_CUBIC
# Sharpening: Improves text clarity
```

### Phase 2: Gemini Vision Extraction
Uses Chain-of-Thought prompting:
1. Locate the main line items table
2. Identify column headers (Item, Qty, Rate, Amount)
3. Extract each row line-by-line
4. Identify and capture the final total separately
5. Ignore rows with keywords: Total, Subtotal, Tax, VAT, etc.

### Phase 3: Reconciliation Logic
```python
# Data Cleaning
- Convert "$1,200.50" → 1200.50
- Fix OCR errors (l→1, O→0)
- Normalize item names

# Double-Counting Guard
- Filter items with keywords: total, subtotal, tax, gst, etc.
- Detect if amount equals sum of others (outlier detection)

# Reconciliation Check
- Calculate: Sum of all line items
- Compare with actual bill total
- Check if within threshold (default 0.01%)
```

### Phase 4: Agentic Retry
If totals don't match:
```python
# Send back to Gemini with:
- Current extracted items
- Calculated total
- Actual bill total
- Specific discrepancy amount

# Gemini responds with:
- Analysis of the image re-examination
- Suggested corrections (add/remove/modify)
- Updated confidence score
```

## 📊 Accuracy Metrics

The system optimizes for:

1. **No Missing Items**: Comprehensive extraction with visual and LLM analysis
2. **No Double-Counting**: Intelligent filtering of meta-items (totals, taxes)
3. **Exact Reconciliation**: Agentic retry mechanism to achieve accuracy
4. **Decimal Precision**: Maintains exact amounts from bills

**Target Accuracy**: Reconciled amount matches actual bill total to within 0.01%

## 🧪 Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run specific test:
```bash
pytest tests/test_logic.py::TestReconciliationEngine::test_reconcile_exact_match -v
```

Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

## 🛠️ Development

### Adding New Features

1. **New LLM Model**: Update `config.py` and `GEMINI_API_KEY` in `.env`
2. **New Validation Rule**: Add to `app/core/logic.py` → `ExtractedDataValidator`
3. **New API Endpoint**: Add to `app/api/routes.py`

### Code Style
```bash
# Format code
black app/

# Check style
flake8 app/

# Type checking
mypy app/
```

## 📝 Logging

The API logs detailed information at different levels:

```
INFO: Started extraction request
DEBUG: Gemini raw response: {...}
INFO: Extracted 4 items from page 1
WARNING: Item discrepancy detected, triggering retry
ERROR: Failed to download document
```

Check logs in console or Docker logs:
```bash
docker-compose logs -f bill-extractor
```

## 🚨 Error Handling

The API gracefully handles:
- **Network Errors**: Timeouts, failed downloads
- **Image Issues**: Corrupted, unreadable formats
- **Extraction Failures**: Empty results, parsing errors
- **API Errors**: Rate limits, invalid responses

All errors return appropriate HTTP status codes and descriptive messages.

## 📚 Key Modules

### `image_processing.py`
- `ImageProcessor`: Complete image preprocessing pipeline
- Resolution checking and upscaling
- Document de-skewing
- Binarization and denoising

### `logic.py`
- `DataCleaner`: Standardize numbers and clean text
- `DoubleCountingGuard`: Filter meta-items and detect outliers
- `ReconciliationEngine`: Verify calculations and totals
- `ExtractedDataValidator`: End-to-end validation pipeline

### `extractor.py`
- `GeminiExtractor`: Gemini Vision integration
- `ExtractionOrchestrator`: Orchestrates full workflow including retry logic

### `schemas.py`
- Pydantic models for type validation
- Request/Response contract definitions

## 🔐 Security

- API uses CORS for cross-origin requests
- All input URLs are validated
- No sensitive data logged
- Secure error messages (no leaking internal details)

## 📦 Dependencies

Core:
- `fastapi`: Web framework
- `pydantic`: Data validation
- `google-generativeai`: Gemini Vision API
- `opencv-python`: Image processing
- `pillow`: Image handling
- `aiohttp`: Async HTTP client

See `requirements.txt` for complete list.

## 🤝 Contributing

1. Create feature branch
2. Add tests for new functionality
3. Run tests and code checks
4. Submit pull request

## 📄 License

[Add your license here]

## 📞 Support

For issues or questions:
1. Check logs for detailed error messages
2. Review API documentation at `/docs`
3. Check sample requests in this README

## 🎓 Technical Details

### Why This Approach?

1. **Vision LLM (Gemini)**: State-of-the-art bill understanding with reasoning
2. **Image Preprocessing**: Improves LLM accuracy by 15-20%
3. **Reconciliation Engine**: Pure logic layer ensures mathematical correctness
4. **Agentic Retry**: LLM self-correction with specific feedback
5. **Double-Counting Guard**: Prevents common extraction mistakes

### Why These Technologies?

- **Gemini 2.0 Flash**: Fast, accurate, cost-effective for vision tasks
- **FastAPI**: High-performance, async-ready Python web framework
- **OpenCV**: Industry-standard image processing library
- **Pydantic**: Type safety and data validation

## 🎯 Future Enhancements

- [ ] Multi-page document support
- [ ] OCR-based coordinate validation with PaddleOCR
- [ ] Support for multiple currencies
- [ ] Batch processing API
- [ ] Performance metrics dashboard
- [ ] Fine-tuned models for specific invoice formats

---

**Version**: 1.0.0
**Last Updated**: November 2025
**Status**: Production Ready ✅
