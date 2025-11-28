import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
import aiohttp
import asyncio
from app.models.schemas import BillItemRequest, BillExtractionResponse, ExtractedBillData, PageLineItems
from app.core.image_processing import ImageProcessor
from app.core.extractor import ExtractionOrchestrator
from decimal import Decimal
import io

logger = logging.getLogger(__name__)

router = APIRouter()


image_processor = ImageProcessor()
orchestrator = ExtractionOrchestrator()


@router.post("/extract-bill-data", response_model=BillExtractionResponse)
async def extract_bill_data(request: BillItemRequest) -> BillExtractionResponse:
    """
    Extract line items and totals from a bill (image or PDF)
    
    This endpoint:
    1. Detects document type (PDF or Image)
    2. Downloads and preprocesses the document
    3. If PDF: Converts to images (one per page) and processes each page
    4. If Image: Processes directly
    5. Extracts line items using Gemini Vision
    6. Reconciles extracted totals with actual bill total
    7. Returns cleaned, validated data
    
    Args:
        request: BillItemRequest with document URL (can be image or PDF URL/local path)
        
    Returns:
        BillExtractionResponse with extracted data from all pages or error
    """
    try:
        document_url = str(request.document)
        logger.info(f"Received extraction request for: {document_url}")
        
        # Download document
        logger.info("Downloading document...")
        document_bytes = await download_document(document_url)
        
        if not document_bytes:
            raise ValueError("Failed to download document")
        
        logger.info(f"Downloaded {len(document_bytes)} bytes")
        
        # Detect if PDF or Image
        is_pdf = detect_document_type(document_bytes, document_url)
        logger.info(f"Detected document type: {'PDF' if is_pdf else 'Image'}")
        
        # Process accordingly
        if is_pdf:
            return await process_pdf_extraction(document_bytes)
        else:
            return await process_image_extraction(document_bytes)
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            error=f"Internal server error: {str(e)}"
        )


@router.post("/extract-bill-data-debug", response_model=BillExtractionResponse)
async def extract_bill_data_debug(request: BillItemRequest) -> BillExtractionResponse:
    """
    Debug version - Shows what's being extracted, filtered, etc.
    Same as extract-bill-data but with detailed logging
    """
    try:
        logger.info(f"DEBUG: Received extraction request for: {request.document}")
        
        logger.info("DEBUG: Downloading document...")
        image_bytes = await download_document(str(request.document))
        
        if not image_bytes:
            raise ValueError("Failed to download document")
        
        logger.info(f"DEBUG: Downloaded {len(image_bytes)} bytes")
        
        logger.info("DEBUG: Preprocessing image...")
        processed_image = image_processor.process_document(image_bytes)
        processed_bytes = ImageProcessor.image_to_bytes(processed_image)
        logger.info(f"DEBUG: Processed image to {len(processed_bytes)} bytes")
        
        logger.info("DEBUG: Starting extraction orchestration...")
        cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
            processed_bytes,
            page_no="1"
        )
        
        logger.info(f"DEBUG: Extraction metadata: {metadata}")
        
        if not cleaned_items:
            return BillExtractionResponse(
                is_success=False,
                token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
                error="No line items could be extracted from the document"
            )
        
        bill_items = [
            {
                "item_name": item['item_name'],
                "item_quantity": float(item['item_quantity']),
                "item_rate": float(item['item_rate']),
                "item_amount": float(item['item_amount'])
            }
            for item in cleaned_items
        ]
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=[
                PageLineItems(
                    page_no="1",
                    page_type="Bill Detail",
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items)
        )
        
        token_usage = metadata.get('token_usage', {})
        response = BillExtractionResponse(
            is_success=True,
            token_usage={
                'total_tokens': token_usage.get('total_tokens', 0),
                'input_tokens': token_usage.get('input_tokens', 0),
                'output_tokens': token_usage.get('output_tokens', 0)
            },
            data=extracted_data
        )
        
        logger.info(
            f"DEBUG: Successfully extracted {len(cleaned_items)} items. "
            f"Status: {metadata.get('reconciliation_status', 'unknown')}, "
            f"Tokens: {token_usage.get('total_tokens', 0)}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"DEBUG: Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"DEBUG: Unexpected error: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )


@router.post("/extract-bill-data-raw", response_model=BillExtractionResponse)
async def extract_bill_data_raw(request: BillItemRequest) -> BillExtractionResponse:
    """
    Test endpoint - Sends RAW image directly to LLM (NO preprocessing)
    Compare results with /extract-bill-data to see if preprocessing helps or hurts
    """
    try:
        logger.info(f"RAW: Received extraction request for: {request.document}")
        
        logger.info("RAW: Downloading document...")
        image_bytes = await download_document(str(request.document))
        
        if not image_bytes:
            raise ValueError("Failed to download document")
        
        logger.info(f"RAW: Downloaded {len(image_bytes)} bytes (NO PREPROCESSING)")
        
        logger.info("RAW: Starting extraction orchestration with RAW image...")
        cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
            image_bytes, 
            page_no="1"
        )
        
        logger.info(f"RAW: Extraction metadata: {metadata}")
        
        if not cleaned_items:
            return BillExtractionResponse(
                is_success=False,
                token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
                error="No line items could be extracted from the document"
            )
        
        bill_items = [
            {
                "item_name": item['item_name'],
                "item_quantity": float(item['item_quantity']),
                "item_rate": float(item['item_rate']),
                "item_amount": float(item['item_amount'])
            }
            for item in cleaned_items
        ]
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=[
                PageLineItems(
                    page_no="1",
                    page_type="Bill Detail",
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items)
        )
        
        token_usage = metadata.get('token_usage', {})
        response = BillExtractionResponse(
            is_success=True,
            token_usage={
                'total_tokens': token_usage.get('total_tokens', 0),
                'input_tokens': token_usage.get('input_tokens', 0),
                'output_tokens': token_usage.get('output_tokens', 0)
            },
            data=extracted_data
        )
        
        logger.info(
            f"RAW: Successfully extracted {len(cleaned_items)} items. "
            f"Status: {metadata.get('reconciliation_status', 'unknown')}, "
            f"Tokens: {token_usage.get('total_tokens', 0)}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"RAW: Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"RAW: Unexpected error: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Bill Data Extractor API",
        "version": "1.0.0"
    }


async def download_document(url_or_path: str) -> Optional[bytes]:
    """
    Download document from URL or read from local path
    
    Supports:
    - Remote URLs (http://, https://)
    - Google Drive links (automatically converts to direct download)
    - Local file paths (C:\\path\\to\\file or /path/to/file)
    - File URLs (file://C:/path/to/file)
    
    Args:
        url_or_path: Document URL or local file path
        
    Returns:
        Document bytes or None if failed
    """
    try:
        # Check if it's a local file path
        if url_or_path.startswith(('file://', 'C:', 'D:', 'E:', '/', '\\\\')):
            # Local file path
            file_path = url_or_path
            if file_path.startswith('file://'):
                file_path = file_path[7:]  # Remove 'file://' prefix
                if len(file_path) > 2 and file_path[2] == ':':  # Handle file:///C:
                    file_path = file_path[1:]
            
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                logger.info(f"Read local file: {file_path} ({len(data)} bytes)")
                return data
            except FileNotFoundError:
                logger.error(f"Local file not found: {file_path}")
                return None
            except Exception as e:
                logger.error(f"Error reading local file {file_path}: {e}")
                return None
        
        # Handle Google Drive links
        if 'drive.google.com' in url_or_path:
            url_or_path = convert_google_drive_link(url_or_path)
            logger.info(f"Converted Google Drive link to direct download URL")
        
        # Download from URL
        async with aiohttp.ClientSession() as session:
            # Add headers to prevent redirects and bypass restrictions
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            try:
                async with session.get(
                    url_or_path, 
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers=headers,
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        
                        # Check if we got HTML instead of the file (Google Drive redirect)
                        if data.startswith(b'<!DOCTYPE') or data.startswith(b'<html'):
                            logger.warning("Got HTML response, likely a redirect. Checking if it's a Google Drive link...")
                            raise ValueError("URL returned HTML instead of file content. This may be due to access restrictions.")
                        
                        logger.info(f"Downloaded {len(data)} bytes from URL")
                        return data
                    else:
                        logger.error(f"Failed to download: HTTP {response.status}")
                        # Try to read response text for debugging
                        try:
                            text = await response.text()
                            if len(text) < 500:
                                logger.error(f"Response: {text}")
                        except:
                            pass
                        return None
            except asyncio.TimeoutError:
                logger.error(f"Timeout downloading from {url_or_path}")
                return None
            except Exception as e:
                logger.error(f"Error downloading from {url_or_path}: {e}")
                return None
    except Exception as e:
        logger.error(f"Error downloading from {url_or_path}: {e}")
        return None


def convert_google_drive_link(drive_link: str) -> str:
    """
    Convert Google Drive sharing link to direct download URL
    
    Args:
        drive_link: Google Drive sharing link (view?usp=sharing or open?usp=sharing)
        
    Returns:
        Direct download URL
    """
    try:
        # Extract file ID from Google Drive link
        # Format: https://drive.google.com/file/d/{FILE_ID}/view?usp=...
        if '/file/d/' in drive_link:
            file_id = drive_link.split('/file/d/')[1].split('/')[0]
            # Convert to direct download URL
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            logger.info(f"Extracted Google Drive file ID: {file_id}")
            return direct_url
        
        # Handle folder links (not supported, return original)
        if '/folders/' in drive_link:
            logger.warning("Google Drive folder links are not supported, trying original URL")
            return drive_link
        
        # If format is not recognized, return original
        logger.warning("Could not parse Google Drive link format, trying original URL")
        return drive_link
    except Exception as e:
        logger.error(f"Error converting Google Drive link: {e}")
        return drive_link




def detect_document_type(document_bytes: bytes, url: str = "") -> bool:
    """
    Detect if document is PDF or Image
    
    Args:
        document_bytes: Document file bytes
        url: Original URL for additional detection hints
        
    Returns:
        True if PDF, False if Image
    """
    try:
        # Check PDF magic number
        if document_bytes.startswith(b'%PDF'):
            return True
        
        # Check URL extension
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return True
        
        # Check for image magic numbers
        image_signatures = [
            (b'\xff\xd8\xff', 'JPEG'),
            (b'\x89\x50\x4e\x47', 'PNG'),
            (b'\x47\x49\x46', 'GIF'),
            (b'\x42\x4d', 'BMP'),
            (b'\x49\x49\x2a\x00', 'TIFF'),
            (b'\x4d\x4d\x00\x2a', 'TIFF'),
        ]
        
        for sig, fmt in image_signatures:
            if document_bytes.startswith(sig):
                return False
        
        # Default to image if unsure
        return False
        
    except Exception as e:
        logger.warning(f"Error detecting document type: {e}, assuming image")
        return False


async def process_image_extraction(image_bytes: bytes) -> BillExtractionResponse:
    """
    Process single image extraction
    
    Args:
        image_bytes: Image file bytes
        
    Returns:
        BillExtractionResponse with extracted data
    """
    try:
        logger.info("Processing image...")
        
        # Preprocess image
        logger.info("Preprocessing image with OCR enhancements...")
        processed_image = image_processor.process_document(image_bytes)
        processed_bytes = ImageProcessor.image_to_bytes(processed_image)
        logger.info(f"Processed image to {len(processed_bytes)} bytes")
        
        # Extract from image
        logger.info("Starting extraction orchestration...")
        cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
            processed_bytes,
            page_no="1"
        )
        
        if not cleaned_items:
            return BillExtractionResponse(
                is_success=False,
                token_usage={
                    'total_tokens': metadata.get('token_usage', {}).get('total_tokens', 0),
                    'input_tokens': metadata.get('token_usage', {}).get('input_tokens', 0),
                    'output_tokens': metadata.get('token_usage', {}).get('output_tokens', 0)
                },
                error="No line items could be extracted from the document"
            )
        
        bill_items = [
            {
                "item_name": item['item_name'],
                "item_quantity": float(item['item_quantity']),
                "item_rate": float(item['item_rate']),
                "item_amount": float(item['item_amount'])
            }
            for item in cleaned_items
        ]
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=[
                PageLineItems(
                    page_no="1",
                    page_type="Bill Detail",
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            token_usage={
                'total_tokens': metadata.get('token_usage', {}).get('total_tokens', 0),
                'input_tokens': metadata.get('token_usage', {}).get('input_tokens', 0),
                'output_tokens': metadata.get('token_usage', {}).get('output_tokens', 0)
            },
            data=extracted_data
        )
        
        logger.info(
            f"Successfully extracted {len(cleaned_items)} items. "
            f"Status: {metadata['reconciliation_status']}, Tokens: {metadata.get('token_usage', {}).get('total_tokens', 0)}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in image processing: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )


async def process_pdf_extraction(pdf_bytes: bytes) -> BillExtractionResponse:
    """
    Process PDF extraction (multiple pages)
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        BillExtractionResponse with extracted data from all pages
    """
    try:
        # Convert PDF to images (one per page)
        logger.info("Converting PDF to images...")
        image_list = convert_pdf_to_images(pdf_bytes)
        
        logger.info(f"Converted PDF to {len(image_list)} page(s)")
        
        # Process each page
        all_items = []
        pagewise_items = []
        total_token_usage = {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
        
        for page_no, image_bytes in enumerate(image_list, start=1):
            logger.info(f"Processing page {page_no}...")
            
            # Preprocess image
            processed_image = image_processor.process_document(image_bytes)
            processed_bytes = ImageProcessor.image_to_bytes(processed_image)
            
            # Extract from image
            cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
                processed_bytes,
                page_no=str(page_no)
            )
            
            # Accumulate token usage
            page_token_usage = metadata.get('token_usage', {})
            total_token_usage['total_tokens'] += page_token_usage.get('total_tokens', 0)
            total_token_usage['input_tokens'] += page_token_usage.get('input_tokens', 0)
            total_token_usage['output_tokens'] += page_token_usage.get('output_tokens', 0)
            
            if cleaned_items:
                logger.info(f"Page {page_no}: Extracted {len(cleaned_items)} items")
                
                bill_items = [
                    {
                        "item_name": item['item_name'],
                        "item_quantity": float(item['item_quantity']),
                        "item_rate": float(item['item_rate']),
                        "item_amount": float(item['item_amount'])
                    }
                    for item in cleaned_items
                ]
                
                all_items.extend(cleaned_items)
                pagewise_items.append(
                    PageLineItems(
                        page_no=str(page_no),
                        page_type="Bill Detail",
                        bill_items=bill_items
                    )
                )
        
        if not all_items:
            return BillExtractionResponse(
                is_success=False,
                token_usage=total_token_usage,
                error="No line items could be extracted from the PDF"
            )
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=pagewise_items,
            total_item_count=len(all_items)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            token_usage=total_token_usage,
            data=extracted_data
        )
        
        logger.info(
            f"Successfully extracted {len(all_items)} total items from {len(image_list)} page(s). "
            f"Tokens: {total_token_usage.get('total_tokens', 0)}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in PDF processing: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )



def convert_pdf_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Convert PDF to list of image bytes (one per page)
    
    Tries pdf2image first, falls back to PyMuPDF if available.
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        List of image bytes (PNG format)
    """
    # Try pdf2image first
    try:
        import pdf2image
        from PIL import Image
        
        logger.info("Using pdf2image for PDF conversion...")
        images = pdf2image.convert_from_bytes(pdf_bytes, fmt='png')
        
        if not images:
            raise ValueError("No pages found in PDF or PDF is invalid/corrupted")
        
        logger.info(f"Converted {len(images)} pages from PDF using pdf2image")
        
        # Convert PIL images to bytes
        image_bytes_list = []
        for idx, img in enumerate(images):
            try:
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                image_bytes_list.append(img_bytes.getvalue())
                logger.info(f"Converted page {idx + 1} to PNG ({len(img_bytes.getvalue())} bytes)")
            except Exception as e:
                logger.error(f"Error converting page {idx + 1} to PNG: {e}")
                raise ValueError(f"Failed to convert page {idx + 1} to PNG: {e}")
        
        logger.info(f"Successfully converted {len(image_bytes_list)} PDF pages to images")
        return image_bytes_list
        
    except ImportError:
        logger.info("pdf2image not available, trying PyMuPDF...")
        # Fall back to PyMuPDF
        try:
            import fitz
            from PIL import Image
            
            logger.info("Using PyMuPDF for PDF conversion...")
            pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if len(pdf) == 0:
                raise ValueError("No pages found in PDF or PDF is invalid/corrupted")
            
            logger.info(f"PDF has {len(pdf)} pages")
            
            image_bytes_list = []
            for page_num in range(len(pdf)):
                try:
                    page = pdf[page_num]
                    # Render at 2x zoom for better quality
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    
                    # Convert pixmap to PIL Image
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    
                    # Convert to PNG bytes
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    image_bytes_list.append(img_bytes.getvalue())
                    logger.info(f"Converted page {page_num + 1} to PNG ({len(img_bytes.getvalue())} bytes)")
                except Exception as e:
                    logger.error(f"Error converting page {page_num + 1}: {e}")
                    raise ValueError(f"Failed to convert page {page_num + 1}: {e}")
            
            pdf.close()
            logger.info(f"Successfully converted {len(image_bytes_list)} PDF pages using PyMuPDF")
            return image_bytes_list
            
        except ImportError:
            error_msg = (
                "PDF conversion requires either:\n"
                "  1. pdf2image + Poppler: pip install pdf2image, then download Poppler from https://github.com/oschwartz10612/poppler-windows/releases/\n"
                "  2. PyMuPDF (easiest): pip install PyMuPDF"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error converting PDF with PyMuPDF: {e}", exc_info=True)
            raise ValueError(f"Failed to convert PDF to images: {e}")
    except Exception as e:
        if "poppler" in str(e).lower() or "not found" in str(e).lower():
            error_msg = (
                "Poppler is not installed or not in PATH.\n"
                "Solutions:\n"
                "  1. Install PyMuPDF (easiest, no setup): pip install PyMuPDF\n"
                "  2. Download Poppler manually: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                "  3. See POPPLER_INSTALLATION_GUIDE.md for detailed instructions"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            logger.error(f"Unexpected error converting PDF: {e}", exc_info=True)
            raise ValueError(f"Failed to convert PDF to images: {e}")
