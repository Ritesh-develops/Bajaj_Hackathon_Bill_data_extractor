# Quick Fix - One Command

## The Simplest Solution

Just install PyMuPDF (no external dependencies, no PATH setup needed):

```bash
pip install PyMuPDF
```

That's it! 🎉

Now your PDF support works automatically with your Google Drive link:

```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{
  "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
}'
```

---

## What Changed

The code now:
1. ✅ Tries pdf2image first (if Poppler is installed)
2. ✅ Falls back to PyMuPDF if pdf2image not available
3. ✅ PyMuPDF has NO external dependencies
4. ✅ Just requires: `pip install PyMuPDF`

---

## Why PyMuPDF?

- ✅ No Poppler setup needed
- ✅ No PATH environment variables
- ✅ Faster installation (< 1 minute)
- ✅ Built-in PDF support
- ✅ Higher quality rendering (2x zoom)

---

## Test It

After installing PyMuPDF:

```bash
# Test with local PDF
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "C:\\path\\to\\bill.pdf"}'

# Test with Google Drive
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://drive.google.com/file/d/FILE_ID/view?usp=drive_link"}'
```

---

Done! That's all you need. ✅
