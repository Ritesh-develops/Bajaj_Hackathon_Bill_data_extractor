import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
import aiohttp
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
    Extract line items and totals from a bill image
    
    This endpoint:
    1. Validates the document URL
    2. Downloads and preprocesses the image
    3. Extracts line items using Gemini Vision
    4. Reconciles extracted totals with actual bill total
    5. Returns cleaned, validated data
    
    Args:
        request: BillItemRequest with document URL
        
    Returns:
        BillExtractionResponse with extracted data or error
    """
    try:
        logger.info(f"Received extraction request for: {request.document}")
        
        logger.info("Downloading document...")
        image_bytes = await download_document(str(request.document))
        
        if not image_bytes:
            raise ValueError("Failed to download document")
        
        logger.info(f"Downloaded {len(image_bytes)} bytes")
        
        logger.info("Preprocessing image with OCR enhancements...")
        processed_image = image_processor.process_document(image_bytes)
        processed_bytes = ImageProcessor.image_to_bytes(processed_image)
        logger.info(f"Processed image to {len(processed_bytes)} bytes")
        
        logger.info("Starting extraction orchestration...")
        cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
            processed_bytes,
            page_no="1"
        )
        
        if not cleaned_items:
            return BillExtractionResponse(
                is_success=False,
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
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items),
            reconciled_amount=float(reconciled_total)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            data=extracted_data
        )
        
        logger.info(
            f"Successfully extracted {len(cleaned_items)} items. "
            f"Total: {reconciled_total}, Status: {metadata['reconciliation_status']}"
        )
        
        return response
        
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
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items),
            reconciled_amount=float(reconciled_total)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            data=extracted_data
        )
        
        logger.info(
            f"DEBUG: Successfully extracted {len(cleaned_items)} items. "
            f"Total: {reconciled_total}, Status: {metadata['reconciliation_status']}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"DEBUG: Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"DEBUG: Unexpected error: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
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
                    bill_items=bill_items
                )
            ],
            total_item_count=len(cleaned_items),
            reconciled_amount=float(reconciled_total)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            data=extracted_data
        )
        
        logger.info(
            f"RAW: Successfully extracted {len(cleaned_items)} items. "
            f"Total: {reconciled_total}, Status: {metadata['reconciliation_status']}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"RAW: Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"RAW: Unexpected error: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
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


async def download_document(url: str) -> Optional[bytes]:
    """
    Download document from URL
    
    Args:
        url: Document URL
        
    Returns:
        Document bytes or None if failed
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"Failed to download: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        return None


@router.post("/extract-bill-data-pdf", response_model=BillExtractionResponse)
async def extract_bill_data_pdf(file: UploadFile = File(...)) -> BillExtractionResponse:
    """
    Extract line items from a PDF file (file upload)
    
    Supports:
    - Single page PDFs (converted to image)
    - Multi-page PDFs (returns items for all pages)
    
    Args:
        file: PDF file upload
        
    Returns:
        BillExtractionResponse with extracted data from all pages
    """
    try:
        logger.info(f"Received PDF extraction request for: {file.filename}")
        
        # Read PDF file
        pdf_bytes = await file.read()
        
        if not pdf_bytes:
            raise ValueError("Failed to read PDF file")
        
        logger.info(f"Read PDF file: {len(pdf_bytes)} bytes")
        
        # Process PDF
        return await process_pdf_extraction(pdf_bytes)
        
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


@router.post("/extract-bill-data-pdf-url", response_model=BillExtractionResponse)
async def extract_bill_data_pdf_url(request: BillItemRequest) -> BillExtractionResponse:
    """
    Extract line items from a PDF file via URL or local path
    
    Supports:
    - Remote PDF URLs (https://...)
    - Local file paths (file:// or C:\\path\\to\\file.pdf)
    - Single and multi-page PDFs
    
    Args:
        request: BillItemRequest with PDF document URL or local path
        
    Returns:
        BillExtractionResponse with extracted data from all pages
    """
    try:
        document_path = str(request.document)
        logger.info(f"Received PDF extraction request for: {document_path}")
        
        # Check if it's a local file path or URL
        if document_path.startswith(('file://', 'C:', 'D:', '/', '\\')):
            # Local file path
            pdf_bytes = read_local_pdf(document_path)
            if not pdf_bytes:
                raise ValueError(f"Failed to read local PDF file: {document_path}")
            logger.info(f"Read local PDF file: {len(pdf_bytes)} bytes")
        else:
            # Remote URL
            pdf_bytes = await download_document(document_path)
            if not pdf_bytes:
                raise ValueError(f"Failed to download PDF from URL: {document_path}")
            logger.info(f"Downloaded PDF from URL: {len(pdf_bytes)} bytes")
        
        # Process PDF
        return await process_pdf_extraction(pdf_bytes)
        
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


async def process_pdf_extraction(pdf_bytes: bytes) -> BillExtractionResponse:
    """
    Common PDF processing logic
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        BillExtractionResponse with extracted data
    """
    try:
        # Convert PDF to images (one per page)
        logger.info("Converting PDF to images...")
        image_list = convert_pdf_to_images(pdf_bytes)
        
        if not image_list:
            raise ValueError("Failed to convert PDF to images")
        
        logger.info(f"Converted PDF to {len(image_list)} page(s)")
        
        # Process each page
        all_items = []
        pagewise_items = []
        
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
                        bill_items=bill_items
                    )
                )
        
        if not all_items:
            return BillExtractionResponse(
                is_success=False,
                error="No line items could be extracted from the PDF"
            )
        
        # Calculate total across all pages
        total_amount = sum(
            Decimal(str(item.get('item_amount', 0)))
            for item in all_items
        )
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=pagewise_items,
            total_item_count=len(all_items),
            reconciled_amount=float(total_amount)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            data=extracted_data
        )
        
        logger.info(
            f"Successfully extracted {len(all_items)} total items from {len(image_list)} page(s). "
            f"Total: {total_amount}"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return BillExtractionResponse(
            is_success=False,
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in PDF processing: {e}", exc_info=True)
        return BillExtractionResponse(
            is_success=False,
            error=f"Internal server error: {str(e)}"
        )


def read_local_pdf(file_path: str) -> Optional[bytes]:
    """
    Read a local PDF file
    
    Args:
        file_path: Local file path (C:\path\to\file.pdf or /path/to/file.pdf)
        
    Returns:
        PDF file bytes or None if failed
    """
    try:
        import pathlib
        
        # Handle file:// URLs
        if file_path.startswith('file://'):
            file_path = file_path[7:]  # Remove 'file://' prefix
            if file_path.startswith('/') and len(file_path) > 2 and file_path[2] == ':':
                file_path = file_path[1:]  # Handle file:///C: format
        
        # Read file
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        
        logger.info(f"Successfully read local PDF: {file_path} ({len(pdf_bytes)} bytes)")
        return pdf_bytes
        
    except FileNotFoundError:
        logger.error(f"Local PDF file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading local PDF {file_path}: {e}")
        return None


async def download_document(url: str) -> Optional[bytes]:
    """
    Download document from URL
    
    Args:
        url: Document URL
        
    Returns:
        Document bytes or None if failed
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.read()
                    logger.info(f"Downloaded {len(data)} bytes from {url}")
                    return data
                else:
                    logger.error(f"Failed to download {url}: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error downloading from {url}: {e}")
        return None


def convert_pdf_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Convert PDF to list of image bytes (one per page)
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        List of image bytes (PNG format)
    """
    try:
        try:
            import pdf2image
            from PIL import Image
        except ImportError:
            logger.error("pdf2image or Pillow not installed. Install with: pip install pdf2image pillow")
            raise ValueError("PDF support requires pdf2image. Install with: pip install pdf2image")
        
        # Convert PDF to images
        images = pdf2image.convert_from_bytes(pdf_bytes, fmt='png')
        
        if not images:
            raise ValueError("No pages found in PDF")
        
        # Convert PIL images to bytes
        image_bytes_list = []
        for img in images:
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            image_bytes_list.append(img_bytes.getvalue())
        
        logger.info(f"Successfully converted {len(image_bytes_list)} PDF pages to images")
        return image_bytes_list
        
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        return []
