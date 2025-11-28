# Installation & Setup Guide

## Quick Start (First Time Setup)

### 1. Clone Repository
```bash
git clone https://github.com/Ritesh-develops/Bajaj_Hackathon_Bill_data_extractor.git
cd Bajaj_Hackathon_Bill_data_extractor
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install PDF Support (Optional but Recommended)

**Windows:**
```bash
pip install poppler-for-windows
```

**Linux:**
```bash
sudo apt-get install poppler-utils
```

**Mac:**
```bash
brew install poppler
```

### 5. Configure Google Gemini API

Create `.env` file:
```bash
GEMINI_API_KEY=your_api_key_here
```

Get API key: https://aistudio.google.com/app/apikey

### 6. Start the Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server running at: `http://localhost:8000`

---

## API Usage

### Single Unified Endpoint

**POST** `/api/extract-bill-data`

Accepts any document type (image or PDF) via URL or local path:

```json
{
    "document": "any_of_these"
}
```

**Supported Input Types:**

1. **Google Drive Links**
   ```json
   {"document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"}
   ```

2. **Remote URLs (HTTP/HTTPS)**
   ```json
   {"document": "https://example.com/bill.pdf"}
   ```

3. **Local File Paths (Windows)**
   ```json
   {"document": "C:\\Users\\Name\\Downloads\\bill.pdf"}
   ```

4. **Local File Paths (Unix)**
   ```json
   {"document": "/home/user/bill.pdf"}
   ```

5. **File URLs**
   ```json
   {"document": "file://C:/Users/Name/bill.pdf"}
   ```

### Response Format

```json
{
    "is_success": true,
    "data": {
        "pagewise_line_items": [
            {
                "page_no": "1",
                "bill_items": [
                    {
                        "item_name": "Product Name",
                        "item_quantity": 2.0,
                        "item_rate": 100.0,
                        "item_amount": 200.0
                    }
                ]
            }
        ],
        "total_item_count": 30,
        "reconciled_amount": 21800.0
    },
    "error": null
}
```

### Error Response

```json
{
    "is_success": false,
    "data": null,
    "error": "Error message describing what went wrong"
}
```

---

## Testing

### Run Diagnostics
```bash
python check_pdf_dependencies.py
```

### Test with curl

**Image URL:**
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/bill.jpg"}'
```

**PDF URL:**
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/bill.pdf"}'
```

**Local PDF:**
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "C:\\path\\to\\bill.pdf"}'
```

**Google Drive:**
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://drive.google.com/file/d/FILE_ID/view?usp=drive_link"}'
```

### Test with Python
```python
import requests

response = requests.post(
    "http://localhost:8000/api/extract-bill-data",
    json={"document": "C:\\path\\to\\bill.pdf"},
    timeout=120
)
print(response.json())
```

---

## Endpoints Available

| Endpoint | Purpose | Input |
|----------|---------|-------|
| `/api/extract-bill-data` | Extract from images/PDFs | URL or local path |
| `/api/extract-bill-data-debug` | Same + detailed logging | URL or local path |
| `/api/extract-bill-data-raw` | Without preprocessing | URL or local path |
| `/health` | Health check | None |

---

## Features

✅ **Auto-format Detection** - Detects PDF vs Image automatically
✅ **Google Drive Support** - Converts sharing links to direct download
✅ **Multi-page PDFs** - Extracts from each page separately
✅ **Local & Remote** - Handles both local paths and URLs
✅ **Deterministic** - 100% consistent results (LLM temperature=0)
✅ **Smart Reconciliation** - Context-aware item filtering
✅ **Error Handling** - Detailed error messages for debugging
✅ **Async** - Built on FastAPI with async/await

---

## Project Structure

```
bill-extractor/
├── app/
│   ├── core/
│   │   ├── extractor.py          # Gemini Vision extraction
│   │   ├── image_processing.py   # Image preprocessing
│   │   └── logic.py              # Reconciliation logic
│   ├── api/
│   │   └── routes.py             # API endpoints
│   ├── models/
│   │   └── schemas.py            # Data models
│   └── main.py                   # FastAPI app
├── tests/                        # Unit tests
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container setup
├── docker-compose.yml            # Multi-container setup
├── .env.example                  # Environment template
└── README.md                     # Full documentation
```

---

## Troubleshooting

### PDF Conversion Fails
See: `PDF_CONVERSION_FIX.md`

### Google Drive Links Fail
1. Check file is publicly shared
2. Check file ID is correct
3. Try direct download URL: `https://drive.google.com/uc?export=download&id=FILE_ID`

### Image Not Recognized
- Ensure URL returns actual image file
- Check file format is JPG, PNG, GIF, BMP, or TIFF
- Try downloading manually to verify

### Gemini API Errors
- Verify API key in `.env`
- Check quota at: https://aistudio.google.com/app/usage
- Ensure API is enabled in Google Cloud Console

### Connection Timeout
- Increase timeout in requests: `requests.post(..., timeout=120)`
- Check network connectivity
- Verify server is running: `curl http://localhost:8000/health`

---

## Performance Tips

1. **Use smaller images** - Reduces processing time
2. **Increase timeout** - Large PDFs take longer (use `timeout=180`)
3. **Batch requests** - Process multiple bills efficiently
4. **Monitor logs** - Check logs for performance bottlenecks

---

## Environment Variables

```bash
# Required
GEMINI_API_KEY=your_api_key_here

# Optional
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
PORT=8000                   # Server port
HOST=0.0.0.0                # Server host
WORKER_THREADS=4            # Number of workers
```

---

## Need Help?

1. **Check logs** - Run server with: `python -m uvicorn app.main:app --log-level debug`
2. **Run diagnostics** - `python check_pdf_dependencies.py`
3. **Test endpoint** - Use curl or Postman
4. **Review documentation** - See detailed guides in project root

---

## Support Files

- `UNIFIED_ENDPOINT_USAGE.md` - Endpoint usage guide
- `GOOGLE_DRIVE_SUPPORT.md` - Google Drive link handling
- `PDF_CONVERSION_FIX.md` - PDF setup troubleshooting
- `00_START_HERE.md` - Project overview
