"""
Diagnostic script to check PDF conversion dependencies
"""
import sys

def check_pdf_dependencies():
    """Check if all required PDF dependencies are installed"""
    print("Checking PDF conversion dependencies...")
    print("=" * 70)
    
    # Check pdf2image
    print("\n1. Checking pdf2image...")
    try:
        import pdf2image
        print("   ✓ pdf2image is installed")
        print(f"   Version: {pdf2image.__version__ if hasattr(pdf2image, '__version__') else 'Unknown'}")
    except ImportError:
        print("   ✗ pdf2image is NOT installed")
        print("   Install with: pip install pdf2image")
        return False
    
    # Check Pillow
    print("\n2. Checking Pillow (PIL)...")
    try:
        from PIL import Image
        print("   ✓ Pillow is installed")
        print(f"   Version: {Image.__version__ if hasattr(Image, '__version__') else 'Unknown'}")
    except ImportError:
        print("   ✗ Pillow is NOT installed")
        print("   Install with: pip install Pillow")
        return False
    
    # Check Poppler (the external dependency)
    print("\n3. Checking Poppler (system dependency)...")
    try:
        import pdf2image
        # Try to use pdf2image to see if Poppler is available
        test_pdf = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/Resources<<>>>>endobj xref 0 4 0000000000 65535 f 0000000009 00000 n 0000000058 00000 n 0000000115 00000 n trailer<</Size 4/Root 1 0 R>>startxref 175 %%EOF'
        
        # Check if we can import the conversion function
        from pdf2image.pdf2image import convert_from_bytes
        
        # Try a minimal conversion to check if Poppler is available
        try:
            # This will fail if Poppler is not installed
            images = convert_from_bytes(test_pdf, first_page=1, last_page=1)
            print("   ✓ Poppler is installed and working")
        except Exception as e:
            if "poppler" in str(e).lower():
                print("   ✗ Poppler is NOT installed")
                print("   ")
                print("   Windows:")
                print("     1. Install via pip: pip install poppler-for-windows")
                print("     OR")
                print("     2. Manual installation:")
                print("        - Download from: https://github.com/oschwartz10612/poppler-windows/releases/")
                print("        - Extract to: C:\\Program Files\\poppler")
                print("        - Add to PATH: C:\\Program Files\\poppler\\Library\\bin")
                print("   ")
                print("   Linux (Ubuntu/Debian):")
                print("     sudo apt-get install poppler-utils")
                print("   ")
                print("   Mac:")
                print("     brew install poppler")
                return False
            else:
                print(f"   ? Poppler check inconclusive: {e}")
                return False
    
    except Exception as e:
        print(f"   ? Error checking Poppler: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ All PDF dependencies are installed and working!")
    print("\nYou can now:")
    print("  - Upload PDF files to /api/extract-bill-data")
    print("  - Use Google Drive PDF links")
    print("  - Process multi-page PDFs with pagewise extraction")
    return True


def check_all_dependencies():
    """Check all project dependencies"""
    print("\nChecking all project dependencies...")
    print("=" * 70)
    
    required = {
        'fastapi': 'FastAPI web framework',
        'uvicorn': 'ASGI server',
        'aiohttp': 'Async HTTP client',
        'pydantic': 'Data validation',
        'google-generativeai': 'Google Gemini API',
        'opencv-python': 'Image processing',
        'numpy': 'Numerical computing',
        'Pillow': 'Image library',
        'pytest': 'Testing framework',
    }
    
    optional = {
        'pdf2image': 'PDF to image conversion',
        'python-json-logger': 'JSON logging',
    }
    
    all_good = True
    
    print("\nRequired dependencies:")
    for package, description in required.items():
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✓ {package:25} - {description}")
        except ImportError:
            print(f"  ✗ {package:25} - {description} (MISSING)")
            all_good = False
    
    print("\nOptional dependencies:")
    for package, description in optional.items():
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✓ {package:25} - {description}")
        except ImportError:
            print(f"  ⚠ {package:25} - {description} (MISSING)")
    
    return all_good


if __name__ == "__main__":
    print("PDF CONVERSION DIAGNOSTIC TOOL")
    print("=" * 70)
    
    # Check all dependencies
    all_deps_ok = check_all_dependencies()
    
    # Check PDF dependencies specifically
    pdf_ok = check_pdf_dependencies()
    
    print("\n" + "=" * 70)
    if all_deps_ok and pdf_ok:
        print("Status: ✓ READY - All systems operational")
        sys.exit(0)
    elif pdf_ok:
        print("Status: ⚠ WARNING - Some optional dependencies missing, but PDF works")
        sys.exit(0)
    else:
        print("Status: ✗ ERROR - PDF conversion will not work")
        print("\nTo fix, run:")
        print("  pip install -r requirements.txt")
        print("  pip install poppler-for-windows  # Windows only")
        sys.exit(1)
