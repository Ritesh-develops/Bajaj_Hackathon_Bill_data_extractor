from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from decimal import Decimal

class BillItemRequest(BaseModel):
    """Request schema for bill extraction"""
    document: HttpUrl = Field(..., description="URL of the bill document (image or PDF)")


class BillItem(BaseModel):
    """Individual line item in a bill"""
    item_name: str = Field(..., description="Exactly as mentioned in the bill")
    item_amount: Decimal = Field(..., description="Net Amount of the item post discounts as mentioned in the bill")
    item_rate: Decimal = Field(..., description="Exactly as mentioned in the bill")
    item_quantity: Decimal = Field(..., description="Quantity of the item")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v % 1 else int(v)
        }


class PageLineItems(BaseModel):
    """Line items for a single page"""
    page_no: str = Field(..., description="Page number")
    page_type: str = Field(default="Bill Detail", description="Type of page (Bill Detail | Final Bill | Pharmacy)")
    bill_items: List[BillItem] = Field(..., description="List of bill items on this page")


class TokenUsage(BaseModel):
    """Token usage statistics from LLM calls"""
    total_tokens: int = Field(..., description="Cumulative tokens from all LLM calls")
    input_tokens: int = Field(..., description="Cumulative input tokens from all LLM calls")
    output_tokens: int = Field(..., description="Cumulative output tokens from all LLM calls")


class ExtractedBillData(BaseModel):
    """Extracted and reconciled bill data"""
    pagewise_line_items: List[PageLineItems] = Field(..., description="Line items organized by page")
    total_item_count: int = Field(..., description="Total number of line items extracted")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v % 1 else int(v)
        }


class BillExtractionResponse(BaseModel):
    """Response schema for bill extraction API"""
    is_success: bool = Field(..., description="Whether extraction was successful (Status code 200 and valid schema)")
    token_usage: TokenUsage = Field(..., description="Token usage statistics from LLM calls")
    data: Optional[ExtractedBillData] = Field(None, description="Extracted bill data")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v % 1 else int(v)
        }


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""
    total_pages: int
    extraction_confidence: float  
    reconciliation_status: str 
    discrepancy: Decimal
    retry_attempts: int
