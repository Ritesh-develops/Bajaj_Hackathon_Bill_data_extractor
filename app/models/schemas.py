from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from decimal import Decimal

class BillItemRequest(BaseModel):
    """Request schema for bill extraction"""
    document: HttpUrl = Field(..., description="URL of the bill document (image or PDF)")


class BillItem(BaseModel):
    """Individual line item in a bill"""
    item_name: str = Field(..., description="Name of the item")
    item_quantity: Decimal = Field(..., description="Quantity of the item")
    item_rate: Decimal = Field(..., description="Unit rate/price of the item")
    item_amount: Decimal = Field(..., description="Total amount for this line item (quantity * rate)")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v % 1 else int(v)
        }


class PageLineItems(BaseModel):
    """Line items for a single page"""
    page_no: str = Field(..., description="Page number")
    bill_items: List[BillItem] = Field(..., description="List of bill items on this page")


class ExtractedBillData(BaseModel):
    """Extracted and reconciled bill data"""
    pagewise_line_items: List[PageLineItems] = Field(..., description="Line items organized by page")
    total_item_count: int = Field(..., description="Total number of line items extracted")
    reconciled_amount: Decimal = Field(..., description="Final reconciled total amount")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v % 1 else int(v)
        }


class BillExtractionResponse(BaseModel):
    """Response schema for bill extraction API"""
    is_success: bool = Field(..., description="Whether extraction was successful")
    data: Optional[ExtractedBillData] = Field(None, description="Extracted bill data")
    error: Optional[str] = Field(None, description="Error message if extraction failed")


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""
    total_pages: int
    extraction_confidence: float  # 0-1
    reconciliation_status: str  # "exact_match", "corrected", "approximated"
    discrepancy: Decimal
    retry_attempts: int
