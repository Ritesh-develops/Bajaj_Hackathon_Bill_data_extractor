import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aiohttp
from app.models.schemas import BillItemRequest, BillExtractionResponse, ExtractedBillData, PageLineItems
from app.core.image_processing import ImageProcessor
from app.core.extractor import ExtractionOrchestrator
from decimal import Decimal

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
