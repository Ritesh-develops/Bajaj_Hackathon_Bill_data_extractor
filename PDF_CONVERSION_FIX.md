# PDF Conversion Failed - Fix Guide

## Error
```json
{
  "is_success": false,
  "data": null,
  "error": "Invalid request: Failed to convert PDF to images"
}
```

## Cause
The PDF conversion requires **Poppler**, an external system dependency that's not automatically installed.

## Solution

### Step 1: Check What's Missing
Run the diagnostic tool:
```bash
python check_pdf_dependencies.py
```

### Step 2: Install Poppler

#### **Windows**

**Option A: Via pip (Recommended)**
```bash
pip install poppler-for-windows
```

**Option B: Manual Installation**
1. Download: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extract to: `C:\Program Files\poppler`
3. Add to PATH environment variable: `C:\Program Files\poppler\Library\bin`
4. Restart your terminal

#### **Linux (Ubuntu/Debian)**
```bash
sudo apt-get install poppler-utils
```

#### **Mac**
```bash
brew install poppler
```

### Step 3: Reinstall Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation
```bash
python check_pdf_dependencies.py
```

You should see:
```
✓ pdf2image is installed
✓ Pillow is installed
✓ Poppler is installed and working
```

## After Fixing

Your Google Drive PDF link should now work:
```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{
  "document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
}'
```

## Troubleshooting

### Still Getting Error?

1. **Check Python can find Poppler:**
   ```bash
   python -c "import pdf2image; print(pdf2image.poppler_path)"
   ```

2. **Check PATH:**
   ```bash
   # Windows
   echo %PATH%
   
   # Linux/Mac
   echo $PATH
   ```

3. **Check Poppler Installation:**
   ```bash
   # Windows
   where pdftoimage
   
   # Linux/Mac
   which pdftoppm
   ```

4. **Reinstall Poppler:**
   ```bash
   pip uninstall poppler-for-windows
   pip install poppler-for-windows
   ```

## What Each Part Does

- **pdf2image**: Python library that calls Poppler
- **Poppler**: System utility that actually converts PDF to images
- **Pillow (PIL)**: Handles image format conversion (PNG, JPG, etc.)

All three are required for PDF support!

## Quick Install (All at Once)

```bash
# Install Python dependencies
pip install pdf2image Pillow aiohttp

# Install system dependency
pip install poppler-for-windows  # Windows only
# OR
sudo apt-get install poppler-utils  # Linux
# OR
brew install poppler  # Mac
```

---

After installation, test immediately and let me know if you get any errors!
