# Unified Endpoint Documentation

## Endpoint: `/api/extract-bill-data`

**Yes, it works! ✅** The endpoint now handles both images and PDFs automatically.

### Single Endpoint, Any Format

You pass any document (image or PDF) via URL or local path in a single request:

```json
{
    "document": "url_or_path_here"
}
```

### Supported Input Formats

1. **Remote Image URL**
   ```json
   {
       "document": "https://example.com/invoice.jpg"
   }
   ```

2. **Remote PDF URL**
   ```json
   {
       "document": "https://example.com/bill.pdf"
   }
   ```

3. **Local Image Path (Windows)**
   ```json
   {
       "document": "C:\\Users\\YourName\\Downloads\\invoice.jpg"
   }
   ```

4. **Local PDF Path (Windows)**
   ```json
   {
       "document": "C:\\Users\\YourName\\Documents\\bill.pdf"
   }
   ```

5. **Local Image Path (Unix/Linux)**
   ```json
   {
       "document": "/home/user/invoice.jpg"
   }
   ```

6. **File URL Format**
   ```json
   {
       "document": "file://C:/Users/YourName/bill.pdf"
   }
   ```

### How It Works

1. **Auto-Detection**: The endpoint automatically detects if the input is:
   - A remote URL (http://, https://)
   - A local file path (C:, D:, /path, etc.)
   - A file:// URL

2. **Format Detection**: After downloading/reading, it detects:
   - PDF files (checks magic bytes `%PDF`)
   - Image files (JPG, PNG, GIF, BMP, TIFF)

3. **Processing**:
   - **If Image**: Preprocesses and extracts directly
   - **If PDF**: Converts each page to image, then processes all pages

4. **Output**: Returns pagewise line items across all pages

### API Examples

#### Using curl (Local PDF)
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d "{\"document\": \"C:\\Users\\YourName\\bill.pdf\"}"
```

#### Using curl (Remote Image)
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d "{\"document\": \"https://example.com/invoice.jpg\"}"
```

#### Using Python
```python
import requests

response = requests.post(
    "http://localhost:8000/api/extract-bill-data",
    json={"document": "C:\\path\\to\\bill.pdf"}
)
print(response.json())
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

### Features

✅ Single endpoint for all document types
✅ Automatic format detection
✅ Remote URL support
✅ Local file path support (Windows/Unix)
✅ Multi-page PDF support with pagewise breakdown
✅ Deterministic results (100% consistent)
✅ Comprehensive error handling and logging

### Testing

Run the test script to verify:
```bash
python test_unified_endpoint.py
```

Then test with your actual URLs/paths by uncommenting and modifying test cases.

### Additional Endpoints (For specific needs)

- `/api/extract-bill-data-debug`: Same as above but with detailed logging
- `/api/extract-bill-data-raw`: Same processing but without image preprocessing

All endpoints support the same unified format!
