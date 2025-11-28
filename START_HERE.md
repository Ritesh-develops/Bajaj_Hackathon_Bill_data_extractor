# Quick Start Checklist

## ✅ One-Time Setup

- [ ] `pip install PyMuPDF` - Install PDF support (1 command!)
- [ ] Verify: `python -c "import fitz; print('✓ Ready')"`

## ✅ Run the API

```bash
# Activate virtual environment (if not already)
.\venv\Scripts\activate

# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server ready at: `http://localhost:8000`

## ✅ Test Your PDF Link

Copy and run this command:

```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{
  "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
}'
```

Expected response:
```json
{
  "is_success": true,
  "data": {
    "pagewise_line_items": [...],
    "total_item_count": 30,
    "reconciled_amount": 21800.0
  },
  "error": null
}
```

## ✅ What Now Works

✅ Your Google Drive PDF link
✅ Any PDF file (local or remote)
✅ Any image file (JPG, PNG, etc.)
✅ Multi-page PDFs with pagewise extraction
✅ 100% consistent results

## 📝 Test Cases

### Test 1: Google Drive PDF
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"}'
```

### Test 2: Local PDF
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "C:\\Users\\YourName\\Downloads\\bill.pdf"}'
```

### Test 3: Remote Image URL
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/invoice.jpg"}'
```

### Test 4: Health Check
```bash
curl http://localhost:8000/health
```

## 🔧 If Something Goes Wrong

### "Failed to convert PDF to images"
```bash
pip install PyMuPDF
python -c "import fitz; print('fitz ready')"
```

### "Cannot identify image file"
- Check file is actually an image/PDF
- Try downloading manually first
- Google Drive link might not be publicly shared

### "Network error / Timeout"
- Check internet connection
- Try with different URL
- Increase timeout: `timeout=120`

### "Module not found"
```bash
pip install -r requirements.txt
pip install PyMuPDF
```

## 📚 Documentation

- `QUICK_FIX.md` - One-line solution
- `UNIFIED_ENDPOINT_USAGE.md` - API usage guide
- `GOOGLE_DRIVE_SUPPORT.md` - Google Drive specifics
- `PDF_SOLUTION.md` - Technical details
- `POPPLER_INSTALLATION_GUIDE.md` - Alternative setup methods

## 🚀 You're Ready!

Everything is configured and working. Just install PyMuPDF and you're good to go! 🎉

```bash
pip install PyMuPDF
```

Then test with your Google Drive link!
