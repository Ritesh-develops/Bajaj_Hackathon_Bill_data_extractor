# Google Drive Link Support

## ✅ Now Supports Google Drive Links!

The unified `/api/extract-bill-data` endpoint now automatically handles Google Drive sharing links.

### How It Works

1. **Google Drive Link** → Automatically converts to direct download URL
2. **Direct download URL** → Downloads the file
3. **Auto-detects format** → PDF or Image
4. **Processes accordingly** → Handles both formats seamlessly

### Supported Google Drive Link Formats

#### Format 1: Sharing Link with view?usp=
```json
{
    "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
}
```

#### Format 2: Sharing Link with open?usp=
```json
{
    "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/open?usp=sharing"
}
```

#### Format 3: Direct Download URL (also works)
```json
{
    "document": "https://drive.google.com/uc?export=download&id=1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA"
}
```

### Test with curl

```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{
  "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
}'
```

### Test with Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/extract-bill-data",
    json={
        "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
    },
    timeout=120  # Google Drive can be slow
)
print(response.json())
```

### Important Notes

⚠️ **Sharing Settings**: The file must be shared publicly or with appropriate access:
- ✅ "Anyone with the link can view" - Works
- ✅ "Specific people" with your Google account - Works if authenticated
- ❌ "Private" - Will fail with access denied

⚠️ **File Size**: Google Drive has rate limiting for large files
- Recommended: < 50 MB
- Maximum: Depends on Google Drive's throttling

⚠️ **Timeout**: Google Drive can be slow, so timeout is set to 120 seconds

### What Gets Converted

The endpoint automatically converts:
```
https://drive.google.com/file/d/{FILE_ID}/view?usp=drive_link
        ↓
https://drive.google.com/uc?export=download&id={FILE_ID}
```

### Link Extraction

The function extracts the file ID and converts to direct download format:

- Extracts: `FILE_ID` from the URL
- Creates: `https://drive.google.com/uc?export=download&id={FILE_ID}`
- This bypasses the sharing page and directly downloads the file

### Error Handling

If you get an error like:
```
"error": "URL returned HTML instead of file content"
```

This means:
1. ❌ File is not shared publicly
2. ❌ File ID is invalid
3. ❌ File has been deleted
4. ❌ Google Drive is blocking the download (too many requests)

### Testing the Conversion

Run the test script:
```bash
python test_google_drive.py
```

This will test the Google Drive link conversion and show the actual converted URL.

### Supported Input Types (All in One Endpoint)

```json
{
    "document": "any_of_these"
}
```

- `https://drive.google.com/file/d/...` - Google Drive sharing link ✅ NEW
- `https://example.com/bill.pdf` - Remote PDF URL
- `https://example.com/invoice.jpg` - Remote image URL
- `C:\Users\Name\bill.pdf` - Local PDF path
- `D:\invoices\image.jpg` - Local image path
- `/home/user/bill.pdf` - Unix local path
- `file://C:/Users/Name/bill.pdf` - File URL

### Response Format

Same as always:
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

---

**Everything works seamlessly in one endpoint! 🎉**
