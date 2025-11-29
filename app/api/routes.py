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
import time
from datetime import datetime

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
        logger.info(f"========== EXTRACTION REQUEST START ==========")
        logger.info(f"Document URL: {document_url}")
        logger.info(f"Request timestamp: {__import__('datetime').datetime.now().isoformat()}")
        
        logger.info("Downloading document...")
        document_bytes = await download_document(document_url)
        
        if not document_bytes:
            logger.error("Failed to download document - returned None")
            raise ValueError("Failed to download document")
        
        logger.info(f"Downloaded {len(document_bytes)} bytes")
        
        is_pdf = detect_document_type(document_bytes, document_url)
        logger.info(f"Detected document type: {'PDF' if is_pdf else 'Image'}")
        
        if is_pdf:
            logger.info("Processing as PDF document")
            result = await process_pdf_extraction(document_bytes)
        else:
            logger.info("Processing as Image document")
            result = await process_image_extraction(document_bytes)
        
        logger.info(f"Extraction result - Success: {result.is_success}, Items: {result.data.total_item_count if result.data else 0}, Tokens: {result.token_usage.total_tokens}")
        logger.info(f"========== EXTRACTION REQUEST END ==========")
        
        if result.is_success:
            print(f"\n{'='*60}")
            print(f"FINAL RESULT: SUCCESS ✓")
            print(f"Items extracted: {result.data.total_item_count}")
            print(f"Total tokens: {result.token_usage.total_tokens}")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print(f"FINAL RESULT: FAILED ✗")
            print(f"Error: {result.error}")
            print(f"{'='*60}\n")
        
        return result
        
    except ValueError as e:
        logger.error(f"[VALIDATION ERROR] {str(e)}")
        logger.info(f"========== EXTRACTION REQUEST END (FAILED) ==========")
        print(f"\n{'='*60}")
        print(f"VALIDATION ERROR ✗")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        return BillExtractionResponse(
            is_success=False,
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[UNEXPECTED ERROR] {str(e)}", exc_info=True)
        logger.info(f"========== EXTRACTION REQUEST END (FAILED) ==========")
        print(f"\n{'='*60}")
        print(f"UNEXPECTED ERROR ✗")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
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
        if url_or_path.startswith(('file://', 'C:', 'D:', 'E:', '/', '\\\\')):
            file_path = url_or_path
            if file_path.startswith('file://'):
                file_path = file_path[7:]  
                if len(file_path) > 2 and file_path[2] == ':':  
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
        
        if 'drive.google.com' in url_or_path:
            url_or_path = convert_google_drive_link(url_or_path)
            logger.info(f"Converted Google Drive link to direct download URL")
        
        async with aiohttp.ClientSession() as session:
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
                        
                        if data.startswith(b'<!DOCTYPE') or data.startswith(b'<html'):
                            logger.warning("Got HTML response, likely a redirect. Checking if it's a Google Drive link...")
                            raise ValueError("URL returned HTML instead of file content. This may be due to access restrictions.")
                        
                        logger.info(f"Downloaded {len(data)} bytes from URL")
                        return data
                    else:
                        logger.error(f"Failed to download: HTTP {response.status}")
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
        if '/file/d/' in drive_link:
            file_id = drive_link.split('/file/d/')[1].split('/')[0]
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            logger.info(f"Extracted Google Drive file ID: {file_id}")
            return direct_url
        
        if '/folders/' in drive_link:
            logger.warning("Google Drive folder links are not supported, trying original URL")
            return drive_link
        
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
        if document_bytes.startswith(b'%PDF'):
            return True
        
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return True
        
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
        
        logger.info("Preprocessing image with OCR enhancements...")
        processed_image = image_processor.process_document(image_bytes, skip_deskew=True)
        processed_bytes = ImageProcessor.image_to_bytes(processed_image)
        logger.info(f"Processed image to {len(processed_bytes)} bytes")
        
        logger.info("Starting extraction orchestration...")
        cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
            processed_bytes,
            page_no="1"
        )
        
        logger.info(f"Extraction complete - Cleaned items: {len(cleaned_items)}, Reconciliation status: {metadata.get('reconciliation_status')}")
        logger.info(f"Token usage - Total: {metadata.get('token_usage', {}).get('total_tokens', 0)}, Input: {metadata.get('token_usage', {}).get('input_tokens', 0)}, Output: {metadata.get('token_usage', {}).get('output_tokens', 0)}")
        
        if not cleaned_items:
            logger.warning("No line items extracted from document")
            return BillExtractionResponse(
                is_success=False,
                token_usage={
                    'total_tokens': metadata.get('token_usage', {}).get('total_tokens', 0),
                    'input_tokens': metadata.get('token_usage', {}).get('input_tokens', 0),
                    'output_tokens': metadata.get('token_usage', {}).get('output_tokens', 0)
                },
                error="No line items could be extracted from the document"
            )
        
        logger.info(f"Creating response with {len(cleaned_items)} items...")
        bill_items = [
            {
                "item_name": item['item_name'],
                "item_quantity": float(item['item_quantity']),
                "item_rate": float(item['item_rate']),
                "item_amount": float(item['item_amount'])
            }
            for item in cleaned_items
        ]
        
        logger.info(f"Item details: {[(item['item_name'][:30], item['item_amount']) for item in bill_items[:5]]}")
        
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
            f"[IMAGE] Final response ready - Items: {len(cleaned_items)}, "
            f"Tokens: {metadata.get('token_usage', {}).get('total_tokens', 0)}, Status: SUCCESS"
        )
        
        # Print to stdout for visibility in Render logs
        print(f"========== IMAGE EXTRACTION SUCCESS ==========")
        print(f"Items extracted: {len(cleaned_items)}")
        print(f"Total amount: {sum(float(item['item_amount']) for item in bill_items)}")
        print(f"Reconciliation status: {metadata.get('reconciliation_status')}")
        print(f"Tokens used: {metadata.get('token_usage', {}).get('total_tokens', 0)}")
        print(f"========== RESPONSE RETURNED ==========")
        
        # Log exact JSON response for agent visibility
        import json
        response_dict = response.model_dump(by_alias=True)
        response_json = json.dumps(response_dict, indent=2, default=str)
        
        print(f"\n========== EXACT JSON RESPONSE FOR AGENT ==========")
        print(response_json)
        print(f"========== END JSON RESPONSE ==========\n")
        
        logger.info(f"[IMAGE] [RESPONSE] JSON Response Structure:\n{response_json[:500]}...")
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        print(f"[IMAGE] VALIDATION ERROR: {str(e)}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in image processing: {e}", exc_info=True)
        print(f"[IMAGE] UNEXPECTED ERROR: {str(e)}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )


async def process_pdf_extraction(pdf_bytes: bytes) -> BillExtractionResponse:
    """
    Process PDF extraction (multiple pages) with detailed timing
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        BillExtractionResponse with extracted data from all pages
    """
    try:
        time_start = time.time()
        logger.info(f"[PDF] [TIMING START] Extraction started at {datetime.now().isoformat()}")
        
        logger.info(f"[PDF] Converting PDF to images (size: {len(pdf_bytes)} bytes)...")
        time_convert_start = time.time()
        image_list = convert_pdf_to_images(pdf_bytes)
        time_convert_end = time.time()
        
        logger.info(f"[PDF] [TIMING] PDF conversion took {time_convert_end - time_convert_start:.2f}s")
        logger.info(f"[PDF] Converted PDF to {len(image_list)} page(s)")
        logger.info(f"[PDF] Starting concurrent page processing (max 6 concurrent)...")
        
        all_items = []
        pagewise_items = []
        total_token_usage = {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
        extraction_diagnostics = []
        page_timings = {}
        
        def process_single_page(page_no: int, image_bytes: bytes) -> dict:
            """Process a single PDF page (synchronous - blocking API call)"""
            page_time_start = time.time()
            logger.info(f"[PDF] Processing page {page_no}/{len(image_list)} (size: {len(image_bytes)} bytes)...")
            
            processed_image = image_processor.process_document(image_bytes, skip_deskew=True)
            processed_bytes = ImageProcessor.image_to_bytes(processed_image)
            
            logger.info(f"[PDF] Page {page_no} - Processed image to {len(processed_bytes)} bytes")
            
            extraction_time_start = time.time()
            cleaned_items, reconciled_total, metadata = orchestrator.extract_bill(
                processed_bytes,
                page_no=str(page_no)
            )
            extraction_time_end = time.time()
            page_time_end = time.time()
            
            page_timings[page_no] = {
                'total': page_time_end - page_time_start,
                'extraction_only': extraction_time_end - extraction_time_start
            }
            
            page_token_usage = metadata.get('token_usage', {})
            
            logger.info(f"[PDF] Page {page_no} [TIMING] Extraction took {extraction_time_end - extraction_time_start:.2f}s, Total page time: {page_time_end - page_time_start:.2f}s")
            logger.info(f"[PDF] Page {page_no} - Extraction status: {metadata.get('reconciliation_status')}, Items found: {len(cleaned_items)}, Tokens: {page_token_usage.get('total_tokens', 0)}")
            
            if cleaned_items:
                logger.info(f"[PDF] Page {page_no}: Extracted {len(cleaned_items)} items")
                
                bill_items = [
                    {
                        "item_name": item['item_name'],
                        "item_quantity": float(item['item_quantity']),
                        "item_rate": float(item['item_rate']),
                        "item_amount": float(item['item_amount'])
                    }
                    for item in cleaned_items
                ]
                
                return {
                    'page_no': page_no,
                    'items': cleaned_items,
                    'bill_items': bill_items,
                    'token_usage': page_token_usage,
                    'success': True
                }
            else:
                logger.warning(f"[PDF] Page {page_no}: No items extracted. Notes: {metadata.get('extraction_notes', '')}")
                return {
                    'page_no': page_no,
                    'items': [],
                    'bill_items': [],
                    'token_usage': page_token_usage,
                    'notes': metadata.get('extraction_notes', ''),
                    'reasoning': metadata.get('extraction_reasoning', '')[:200],
                    'success': False
                }
        
        # Process pages with thread pool for true parallelism (Gemini API is blocking I/O)
        import concurrent.futures
        
        logger.info(f"[PDF] [CONCURRENT] Starting thread pool concurrent processing...")
        print(f"\n[PDF] Starting concurrent processing of {len(image_list)} pages (max 15 workers)...")
        
        time_concurrent_start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(process_single_page, page_no, image_bytes) 
                for page_no, image_bytes in enumerate(image_list, start=1)
            ]
            logger.info(f"[PDF] [CONCURRENT] Submitted {len(futures)} pages to thread pool (15 workers)")
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        time_concurrent_end = time.time()
        
        logger.info(f"[PDF] [CONCURRENT] All {len(results)} pages completed concurrently in {time_concurrent_end - time_concurrent_start:.2f}s")
        print(f"[PDF] ✓ Concurrent processing complete - All {len(results)} pages processed in {time_concurrent_end - time_concurrent_start:.2f}s\n")
        
        # Aggregate results
        time_aggregate_start = time.time()
        logger.info(f"[PDF] Aggregating results from {len(results)} concurrent tasks...")
        success_count = 0
        for result in sorted(results, key=lambda x: x['page_no']):
            page_token_usage = result['token_usage']
            total_token_usage['total_tokens'] += page_token_usage.get('total_tokens', 0)
            total_token_usage['input_tokens'] += page_token_usage.get('input_tokens', 0)
            total_token_usage['output_tokens'] += page_token_usage.get('output_tokens', 0)
            
            if result['success']:
                success_count += 1
                all_items.extend(result['items'])
                pagewise_items.append(
                    PageLineItems(
                        page_no=str(result['page_no']),
                        page_type="Bill Detail",
                        bill_items=result['bill_items']
                    )
                )
                logger.info(f"[PDF] [AGGREGATED] Page {result['page_no']}: {len(result['items'])} items")
            else:
                extraction_diagnostics.append({
                    "page": result['page_no'],
                    "notes": result.get('notes', ''),
                    "reasoning": result.get('reasoning', '')
                })
                logger.warning(f"[PDF] [AGGREGATED] Page {result['page_no']}: No items")
        
        time_aggregate_end = time.time()
        logger.info(f"[PDF] [TIMING] Aggregation took {time_aggregate_end - time_aggregate_start:.2f}s")
        logger.info(f"[PDF] [AGGREGATED] Results: {success_count}/{len(results)} pages successful, {len(all_items)} total items")
        
        if not all_items:
            logger.error(f"[PDF] No line items extracted from PDF after processing {len(image_list)} pages")
            diagnostic_msg = "No line items extracted from PDF. "
            if extraction_diagnostics:
                for diag in extraction_diagnostics:
                    diagnostic_msg += f"Page {diag['page']}: {diag['notes']} | "
            
            logger.error(f"[PDF] Diagnostic info: {diagnostic_msg}")
            print(f"[PDF] FAILED - No items extracted from {len(image_list)} pages")
            return BillExtractionResponse(
                is_success=False,
                token_usage=total_token_usage,
                error=diagnostic_msg or "No line items could be extracted from the PDF. This may be a handwritten or scanned document that requires manual review."
            )
        
        logger.info(f"[PDF] Successfully extracted {len(all_items)} total items from {len(image_list)} page(s) [CONCURRENT]")
        print(f"[PDF] ✓ SUCCESS - {len(all_items)} items from {len(image_list)} pages (concurrent)")
        
        extracted_data = ExtractedBillData(
            pagewise_line_items=pagewise_items,
            total_item_count=len(all_items)
        )
        
        response = BillExtractionResponse(
            is_success=True,
            token_usage=total_token_usage,
            data=extracted_data
        )
        
        time_end = time.time()
        total_time = time_end - time_start
        
        logger.info(
            f"[PDF] Final response ready - Items: {len(all_items)}, Pages: {len(image_list)}, "
            f"Tokens: {total_token_usage.get('total_tokens', 0)}, Status: SUCCESS"
        )
        
        # Print detailed timing breakdown
        print(f"========== PDF EXTRACTION TIMING BREAKDOWN ==========")
        print(f"PDF conversion: {time_convert_end - time_convert_start:.2f}s")
        print(f"Concurrent processing: {time_concurrent_end - time_concurrent_start:.2f}s")
        print(f"Aggregation: {time_aggregate_end - time_aggregate_start:.2f}s")
        print(f"---")
        print(f"TOTAL TIME: {total_time:.2f}s")
        print(f"Time per page: {total_time / len(image_list):.2f}s")
        print(f"---")
        print(f"Pages processed: {len(image_list)}")
        print(f"Total items extracted: {len(all_items)}")
        total_amount = sum(float(item.item_amount) for page in pagewise_items for item in page.bill_items)
        print(f"Total amount: {total_amount}")
        print(f"Tokens used: {total_token_usage.get('total_tokens', 0)}")
        print(f"========== PDF RESPONSE RETURNED ==========\n")
        
        # Log per-page timings
        logger.info(f"[PDF] [TIMING] Per-page breakdown:")
        for page_no in sorted(page_timings.keys()):
            timings = page_timings[page_no]
            logger.info(f"[PDF] [TIMING] Page {page_no}: Total {timings['total']:.2f}s (extraction: {timings['extraction_only']:.2f}s)")
        
        # Log exact JSON response for agent visibility
        import json
        response_dict = response.model_dump(by_alias=True)
        response_json = json.dumps(response_dict, indent=2, default=str)
        
        print(f"\n========== EXACT JSON RESPONSE FOR AGENT ==========")
        print(response_json)
        print(f"========== END JSON RESPONSE ==========\n")
        
        logger.info(f"[PDF] [RESPONSE] JSON Response Structure:\n{response_json[:500]}...")
        
        return response
        
    except ValueError as e:
        logger.error(f"[PDF] [VALIDATION ERROR] {str(e)}")
        print(f"[PDF] VALIDATION ERROR: {str(e)}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PDF] [UNEXPECTED ERROR] {str(e)}", exc_info=True)
        print(f"[PDF] UNEXPECTED ERROR: {str(e)}")
        return BillExtractionResponse(
            is_success=False,
            token_usage={'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0},
            error=f"Internal server error: {str(e)}"
        )



def convert_pdf_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Convert PDF to list of image bytes (one per page)
    
    Uses PyMuPDF (fitz) - no external dependencies needed.
    
    Args:
        pdf_bytes: PDF file bytes
        
    Returns:
        List of image bytes (PNG format)
    """
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
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                
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
        
    except ImportError as e:
        error_msg = (
            "PyMuPDF is required for PDF conversion and is not installed.\n"
            "Install with: pip install PyMuPDF\n"
            "This is the recommended PDF library - no external Poppler needed."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error converting PDF: {e}", exc_info=True)
        raise ValueError(f"Failed to convert PDF to images: {e}")
