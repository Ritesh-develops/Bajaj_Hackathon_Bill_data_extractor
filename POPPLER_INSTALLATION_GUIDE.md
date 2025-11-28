# Poppler Installation Guide - Alternative Methods

## Issue
`poppler-for-windows` package not found in pip

## Solution Options

### Option 1: Use pdf2image with system Poppler (Recommended for Windows)

**Step 1: Download Poppler**
- Go to: https://github.com/oschwartz10612/poppler-windows/releases/
- Download: `Release-23.11.0` or latest (file size ~150MB)
- Extract to: `C:\Program Files\poppler` (create folder if needed)

**Step 2: Add to PATH**
1. Open Environment Variables:
   - Right-click "This PC" or "My Computer"
   - Click "Properties"
   - Click "Advanced system settings"
   - Click "Environment Variables"

2. Under "System variables", click "New":
   - Variable name: `Path` (or edit existing)
   - Variable value: `C:\Program Files\poppler\Library\bin`
   - Click OK

3. Restart PowerShell/Terminal

**Step 3: Verify Installation**
```bash
# Open new PowerShell
where pdftoppm

# Should show: C:\Program Files\poppler\Library\bin\pdftoppm.exe
```

**Step 4: Install Python library only**
```bash
pip install pdf2image
```

---

### Option 2: Use WinRAR/7-Zip for Manual Extraction

If you prefer manual setup:

1. Download from GitHub (same link as Option 1)
2. Extract using WinRAR or 7-Zip
3. Copy `poppler-23.11.0\Library\bin` to `C:\Program Files\poppler\Library\bin`
4. Add to PATH as shown above

---

### Option 3: Use PyMuPDF (fitz) - No External Dependencies

**Install PyMuPDF** (no Poppler needed, built-in):
```bash
pip install PyMuPDF
```

Then use this instead of pdf2image:

```python
import fitz  # PyMuPDF
import io
from PIL import Image

def convert_pdf_to_images_fitz(pdf_bytes: bytes):
    """Convert PDF using PyMuPDF (no Poppler needed)"""
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
        img_bytes = io.BytesIO()
        Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(img_bytes, format='PNG')
        images.append(img_bytes.getvalue())
    
    return images
```

---

### Option 4: Use Docker (Includes Everything)

If you have Docker installed:

```bash
# Build image with all dependencies
docker build -t bill-extractor .

# Run container
docker run -p 8000:8000 bill-extractor
```

The Dockerfile includes Poppler automatically.

---

## Recommended: Option 1 (Download + PATH)

### Quick Setup Script

Create `install_poppler.ps1`:

```powershell
# Download Poppler
$downloadUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0/Release-23.11.0.zip"
$zipPath = "$env:TEMP\poppler.zip"
$extractPath = "C:\Program Files\poppler"

Write-Host "Downloading Poppler..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

Write-Host "Extracting..."
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

Write-Host "Adding to PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$newPath = "$extractPath\Library\bin"
if ($currentPath -notlike "*$newPath*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$newPath", "Machine")
    Write-Host "✓ Added to PATH"
}

Write-Host "Verifying installation..."
& "$extractPath\Library\bin\pdftoppm.exe" -v

Write-Host "✓ Poppler installed successfully!"
Write-Host "Restart PowerShell to apply PATH changes"
```

Run it:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install_poppler.ps1
```

---

## After Installation

### Verify it works:

```bash
# Check Poppler is accessible
pdftoppm -v

# Check Python library
python -c "import pdf2image; print('✓ pdf2image ready')"

# Run diagnostic
python check_pdf_dependencies.py
```

### Then test the endpoint:

```bash
curl -X POST "http://localhost:8000/api/extract-bill-data" \
  -H "Content-Type: application/json" \
  -d '{"document": "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"}'
```

---

## If All Else Fails: Use PyMuPDF (No Setup Needed)

Just run:
```bash
pip install PyMuPDF
```

Then I'll update the code to use PyMuPDF instead (no external dependencies needed).

---

## Which Option?

| Option | Ease | Speed | External Deps |
|--------|------|-------|---------------|
| 1. Manual Download | ⭐⭐ | Slow (download) | Yes (add to PATH) |
| 2. WinRAR Extract | ⭐⭐⭐ | Medium | Yes (if no WinRAR) |
| 3. PyMuPDF | ⭐⭐⭐⭐⭐ | Fast | No |
| 4. Docker | ⭐⭐ | Medium | Yes (Docker) |

**Best for your case: Option 3 (PyMuPDF)** - Just one pip install, no PATH setup needed!

Let me know which option you prefer and I can help guide you through it.
