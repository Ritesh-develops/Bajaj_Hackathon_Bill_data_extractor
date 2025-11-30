# Bill Data Extractor API

High-performance solution for extracting line item details from bill/invoice images using AI with advanced accuracy validation and confidence scoring.

## Features

- **Vision LLM Extraction**: Uses Google Gemini 2.0 Flash for intelligent bill parsing
- **Multi-Format Support**: Images, PDFs (single/multi-page), and Google Drive links
- **Handwritten Bill Support**: Optimized extraction for handwritten invoices and bills
- **Advanced Accuracy Validation**: Multi-level validation with confidence scoring and outlier detection
- **Outlier Detection**: IQR-based statistical analysis to flag suspicious quantities and amounts
- **Concurrent Processing**: 50 parallel workers for fast multi-page PDF processing
- **Double-Counting Prevention**: Intelligent filtering to exclude totals, taxes, and fees
- **Optimized Preprocessing**: High DPI (400) for better OCR, resolution optimization
- **High-Performance**: ~1.5-2.5s per page with concurrent processing
- **Deterministic Results**: Temperature=0.0 for 100% consistent extractions
- **Production Ready**: Docker support, comprehensive error handling, detailed logging

## Current Configuration (Phase 35)

**Optimizations Applied:**
- Model: `gemini-2.0-flash` (best accuracy/speed balance)
- DPI: 400 (increased from 300 for better OCR)
- Max Tokens: 3000 (increased from 2048 for richer extraction)
- Concurrency: 50 ThreadPoolExecutor workers (true parallelism)
- Outlier Detection: IQR-based statistical flagging
- Confidence Scoring: Per-item scores (0.4-0.95)
- Timeout: 120s keep-alive for long-running requests

## Architecture

The solution follows workflow with accuracy-first approach:

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Ingestion & Pre-processing                        │
│ - Validate URL and download document                       │
│ - Detect format (Image/PDF)                                │
│ - Optimize resolution to 400 DPI for OCR clarity           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Concurrent Extraction (50 workers)                │
│ - Send to Gemini 2.0 Flash with 3000 max tokens            │
│ - Extract all line items with confidence scoring           │
│ - Track per-page extraction metrics                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Multi-Level Validation & Outlier Detection        │
│ - IQR-based statistical analysis for outliers              │
│ - Flag quantities >50x median or >500 as suspicious        │
│ - Flag amounts exceeding IQR threshold                     │
│ - Verify math: quantity × rate = amount (5% tolerance)    │
│ - Assign confidence scores (0.4-0.95)                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Response Formatting & Logging                     │
│ - Return validated data with confidence scores             │
│ - Log outliers with warnings for review                 │
│ - Include accuracy metrics and token usage                 │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
bill-extractor/
├── app/
│   ├── api/
│   │   ├── routes.py              # API endpoints + concurrent processing
│   │   └── __init__.py
│   │
│   ├── core/
│   │   ├── image_processing.py    # Image preprocessing
│   │   ├── extractor.py           # Gemini Vision + validation + outlier detection
│   │   ├── logic.py               # Reconciliation & validation
│   │   └── __init__.py
│   │
│   ├── models/
│   │   ├── schemas.py             # Pydantic data models with confidence
│   │   ├── prompts.py             # Optimized LLM prompts (35-40% token reduction)
│   │   └── __init__.py
│   │
│   ├── main.py                    # FastAPI app with extended timeouts
│   ├── config.py                  # Configuration (DPI:400, Tokens:3000)
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

## Quick Start

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

5. **Start API server**
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Cloudflare Tunnel Deployment

For public access without exposing local IP:

```bash
# In separate terminal, start Cloudflare tunnel
cloudflared tunnel --url http://localhost:8000
```

This provides a public HTTPS URL for your API.

## API Usage

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
  "token_usage": {
    "total_tokens": 208111,
    "input_tokens": 136435,
    "output_tokens": 71676
  },
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "page_type": "Bill Detail",
        "bill_items": [
          {
            "item_name": "COMPLETE BLOOD COUNT (CBC)",
            "item_quantity": "1.0",
            "item_rate": "500.0",
            "item_amount": "500.0",
            "confidence": 0.95
          },
          {
            "item_name": "LIVER FUNCTION TEST (LFT)",
            "item_quantity": "1.0",
            "item_rate": "1100.0",
            "item_amount": "1100.0",
            "confidence": 0.95
          }
        ]
      }
    ],
    "total_item_count": 2
  },
  "error": null
}
```

**Response Fields:**
- `is_success`: Boolean indicating extraction success
- `token_usage`: Gemini API token consumption
- `data.pagewise_line_items`: Items extracted per page
- `confidence`: Per-item confidence score (0.4-0.95):
  - `0.95`: Normal, high-confidence items
  - `0.75`: Suspicious (math mismatch, etc.)
  - `0.40-0.50`: Outliers (qty >50x median, etc.)
- `error`: Error message if extraction failed

## Configuration

Edit `.env` file to customize:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# LLM Configuration (REQUIRED)
GEMINI_API_KEY=your_key_here
LLM_MODEL=gemini-2.0-flash

# Image Processing
TARGET_DPI=400               # Increased for better OCR
MIN_RESOLUTION=800
MAX_IMAGE_SIZE=20971520      # 20MB in bytes

# Token Budget
# max_output_tokens: 3000 (configured in app/core/extractor.py)

# Reconciliation & Optimization
RECONCILIATION_THRESHOLD=0.01
MAX_RETRY_ATTEMPTS=3
MIN_DISCREPANCY_FOR_RETRY=0.02

# Logging
LOG_LEVEL=INFO
```

## Accuracy & Performance

### Performance Metrics (Current Phase 35)

- **Per-page**: 1.5-2.5 seconds (with Gemini 2.0 Flash)
- **Multi-page**: 50 concurrent workers
- **5 pages**: ~7-10 seconds
- **10 pages**: ~15-20 seconds
- **Timeout**: 120-second keep-alive for long operations

### Accuracy Features

**Confidence Scoring:**
- Normal items: 0.95 (reliable extraction)
- Suspicious items: 0.75 (math mismatch detected)
- Outlier items: 0.40-0.50 (IQR-based statistical flagging)

**Outlier Detection:**
- Quantity outliers: >50x median quantity OR >500 units
- Amount outliers: Values >1.5× IQR beyond Q3
- Example: Item with qty=2001 (likely OCR error of qty=2) flagged as 0.4 confidence

**Math Verification:**
- Validates: quantity × rate = amount (5% tolerance)
- Flags mismatches with confidence 0.75


### Optimization Techniques

1. **Concurrency**: ThreadPoolExecutor(50) processes pages in parallel
2. **DPI Optimization**: 400 DPI for clearer OCR vs 300 (better accuracy with minimal speed impact)
3. **Token Budget**: 3000 max tokens for richer extraction responses
4. **Prompt Engineering**: 35-40% token reduction while maintaining accuracy
5. **Timeout Management**: 120s keep-alive prevents premature disconnections

## How It Works

### Phase 1: Image Preprocessing
```python
# Resolution Optimization: Upscale to 400 DPI if below threshold
# Format Optimization: Convert to PNG for vision clarity
# Resolution Check: Ensure minimum 800px resolution
```

### Phase 2: Concurrent Extraction (50 workers)
```python
# ThreadPoolExecutor processes multiple pages in parallel
# Each page sent to Gemini 2.0 Flash with:
#   - 3000 max output tokens
#   - Temperature 0.0 (deterministic results)
#   - Optimized prompts (40% token reduction)
# Returns: Items with basic validation
```

### Phase 3: Multi-Level Validation
```python
# Statistical Analysis:
#   - Calculate Q1, Q3, IQR for amounts
#   - Calculate median for quantities
#   - Determine outlier thresholds

# Per-Item Validation:
#   - Check quantity outliers (>50x median or >500)
#   - Check amount outliers (>1.5× IQR)
#   - Verify math: qty × rate = amount
#   - Assign confidence score (0.4-0.95)

# Accuracy Metrics:
#   - Count valid, invalid, suspicious, outlier items
#   - Calculate accuracy score with penalties:
#     - Outlier penalty: -30% per item
#     - Suspicious penalty: -15% per item
```

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

## Key Improvements (Phase 35)

 **Outlier Detection**: IQR-based statistical flagging catches OCR errors
 **Confidence Scoring**: Per-item scores (0.4-0.95) indicate reliability
 **DPI Optimization**: 400 DPI improves OCR accuracy
 **Token Expansion**: 3000 max tokens for richer extraction
 **Concurrent Processing**: 50 workers for 3.3x faster multi-page PDFs
 **Accuracy Metrics**: Detailed validation reports with penalty system
 **Timeout Management**: 120s keep-alive prevents request cancellation

## Dependencies

Core:
- `fastapi`: Web framework
- `pydantic`: Data validation
- `google-generativeai`: Gemini Vision API
- `opencv-python`: Image processing
- `pillow`: Image handling
- `aiohttp`: Async HTTP client
- `PyMuPDF`: PDF conversion (pure Python, no external deps)

See `requirements.txt` for complete list.

## Future Enhancements

- Deduplication of similar items across pages
- OCR error pattern learning
- Batch processing API
- Performance metrics dashboard
- Multi-currency support
- Item-level metadata extraction (dates, vendor info)

---

**Version**: 1.2.0
**Last Updated**: November 30, 2025
**Status**: Production Ready

**final Phase Updates (v1.2.0):**
- IQR-based outlier detection with confidence scoring
- DPI increased to 400 for better OCR
- Max tokens increased to 3000
- Concurrent processing with 50 workers
- Comprehensive accuracy validation with warnings
- Timeout management for long-running requests
- All metrics included in response
