"""Gemini Vision LLM extraction module"""

import logging
import json
import base64
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import google.generativeai as genai
from app.config import GEMINI_API_KEY, LLM_MODEL, MAX_RETRY_ATTEMPTS, RECONCILIATION_THRESHOLD
from app.models.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
    RECONCILIATION_RETRY_PROMPT_TEMPLATE
)
from app.core.logic import ReconciliationEngine, ExtractedDataValidator

logger = logging.getLogger(__name__)


class GeminiExtractor:
    """Handles extraction using Google Gemini Vision API"""
    
    def __init__(self, api_key: str = None, model: str = None):
        """Initialize Gemini client"""
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or LLM_MODEL
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not provided")
        
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,  # Deterministic extraction - 0 = always same result
                top_p=1.0,        # Use all tokens equally
                top_k=1,          # Only consider highest probability token
                max_output_tokens=4096
            )
        )
        
        logger.info(f"Initialized Gemini extractor with model: {self.model} (temperature=0.0 for deterministic results)")
    
    def extract_from_image(self, image_bytes: bytes, page_no: str = "1") -> Dict:
        """
        Extract line items from a bill image using Gemini Vision
        
        Args:
            image_bytes: Image file bytes
            page_no: Page number
            
        Returns:
            Dictionary with extracted data
        """
        try:
            # Encode image to base64
            image_base64 = base64.standard_b64encode(image_bytes).decode('utf-8')
            
            # Prepare the message with image
            message = genai.types.ContentDict(
                parts=[
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    EXTRACTION_USER_PROMPT_TEMPLATE,
                ]
            )
            
            # Call Gemini API
            logger.info(f"Sending page {page_no} to Gemini for extraction...")
            response = self.client.generate_content(message)
            
            # Parse response
            response_text = response.text
            logger.debug(f"Gemini raw response: {response_text[:500]}...")
            
            # Extract JSON from response
            extraction_result = self._parse_response(response_text)
            extraction_result['page_number'] = page_no
            
            logger.info(f"Page {page_no}: Extracted {len(extraction_result.get('line_items', []))} items")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error extracting from image: {e}")
            raise
    
    @staticmethod
    def _parse_response(response_text: str) -> Dict:
        """Parse Gemini response and extract JSON"""
        try:
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON found in response, returning empty extraction")
                return {
                    'line_items': [],
                    'bill_total': None,
                    'subtotals': [],
                    'notes': 'Failed to parse response'
                }
            
            json_str = response_text[start_idx:end_idx]
            extraction = json.loads(json_str)
            
            # Standardize the response format
            return {
                'extraction_reasoning': extraction.get('extraction_reasoning', ''),
                'line_items': extraction.get('line_items', []),
                'bill_total': extraction.get('bill_total'),
                'subtotals': extraction.get('subtotals', []),
                'notes': extraction.get('notes', '')
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {
                'line_items': [],
                'bill_total': None,
                'subtotals': [],
                'notes': f'JSON parsing failed: {e}'
            }
    
    def retry_extraction(
        self,
        image_bytes: bytes,
        extracted_items: List[Dict],
        calculated_total: Decimal,
        actual_total: Decimal,
        retry_count: int = 1
    ) -> Dict:
        """
        Retry extraction with reconciliation feedback
        
        Used when there's a mismatch between calculated and actual totals
        """
        try:
            discrepancy = actual_total - calculated_total
            item_count = len(extracted_items)
            
            # Format items for display
            items_json = json.dumps([
                {
                    'item_name': item.get('item_name'),
                    'quantity': float(item.get('item_quantity', 0)),
                    'rate': float(item.get('item_rate', 0)),
                    'amount': float(item.get('item_amount', 0))
                }
                for item in extracted_items
            ], indent=2)
            
            # Create retry prompt
            retry_prompt = RECONCILIATION_RETRY_PROMPT_TEMPLATE.format(
                item_count=item_count,
                extracted_items=items_json,
                calculated_total=float(calculated_total),
                actual_total=float(actual_total),
                discrepancy=float(discrepancy)
            )
            
            # Encode image to base64
            image_base64 = base64.standard_b64encode(image_bytes).decode('utf-8')
            
            logger.info(f"Retry #{retry_count}: Reconciliation with LLM...")
            
            # Call Gemini with retry prompt
            message = genai.types.ContentDict(
                parts=[
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    retry_prompt,
                ]
            )
            
            response = self.client.generate_content(message)
            response_text = response.text
            
            logger.debug(f"Retry response: {response_text[:500]}...")
            
            # Parse retry response
            retry_result = self._parse_retry_response(response_text)
            
            return retry_result
            
        except Exception as e:
            logger.error(f"Error in retry extraction: {e}")
            return {
                'corrections': [],
                'new_total': float(calculated_total),
                'confidence': 0.0,
                'error': str(e)
            }
    
    @staticmethod
    def _parse_retry_response(response_text: str) -> Dict:
        """Parse retry response from Gemini"""
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                return {'corrections': [], 'new_total': 0, 'confidence': 0.0}
            
            json_str = response_text[start_idx:end_idx]
            retry_response = json.loads(json_str)
            
            return {
                'analysis': retry_response.get('analysis', ''),
                'corrections': retry_response.get('corrections', []),
                'new_total': retry_response.get('new_total'),
                'confidence': retry_response.get('confidence', 0.0)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in retry response: {e}")
            return {'corrections': [], 'new_total': 0, 'confidence': 0.0}


class ExtractionOrchestrator:
    """Orchestrates the complete extraction and reconciliation workflow"""
    
    def __init__(self):
        self.extractor = GeminiExtractor()
        self.reconciler = ReconciliationEngine(threshold=float(RECONCILIATION_THRESHOLD))
        self.validator = ExtractedDataValidator()
    
    def extract_bill(
        self,
        image_bytes: bytes,
        page_no: str = "1"
    ) -> Tuple[List[Dict], Decimal, Dict]:
        """
        Complete extraction workflow with reconciliation
        
        Returns: (cleaned_items, reconciled_total, metadata)
        """
        metadata = {
            'page_no': page_no,
            'extraction_confidence': 0.0,
            'reconciliation_status': 'pending',
            'discrepancy': Decimal('0.00'),
            'retry_attempts': 0,
            'warnings': []
        }
        
        try:
            # Phase 2: Extract from image
            logger.info(f"Phase 2: Starting extraction for page {page_no}")
            extraction_result = self.extractor.extract_from_image(image_bytes, page_no)
            
            # Convert to our internal format
            raw_items = self._convert_to_internal_format(extraction_result.get('line_items', []))
            bill_total = extraction_result.get('bill_total')
            
            if not raw_items:
                logger.warning(f"No items extracted from page {page_no}")
                return [], Decimal('0.00'), metadata
            
            logger.info(f"Phase 3: Validating and cleaning {len(raw_items)} items")
            
            # Phase 3: Validate and clean
            cleaned_items, clean_report = self.validator.validate_and_clean(
                raw_items,
                bill_total
            )
            
            metadata['warnings'].extend(clean_report.get('warnings', []))
            
            # Calculate totals
            calculated_total = ReconciliationEngine.sum_line_items(cleaned_items)
            
            logger.info(f"Calculated total: {calculated_total}, Bill total: {bill_total}")
            
            # Phase 3: Reconciliation check
            if bill_total is not None:
                is_match, discrepancy, status = self.reconciler.reconcile(
                    calculated_total,
                    Decimal(str(bill_total))
                )
                
                metadata['discrepancy'] = discrepancy
                metadata['reconciliation_status'] = status
                
                # Phase 4: Agentic retry if needed
                if not is_match and metadata['retry_attempts'] < MAX_RETRY_ATTEMPTS:
                    logger.info(f"Phase 4: Triggering retry (discrepancy: {discrepancy})")
                    
                    retry_response = self.extractor.retry_extraction(
                        image_bytes,
                        cleaned_items,
                        calculated_total,
                        Decimal(str(bill_total)),
                        retry_count=1
                    )
                    
                    metadata['retry_attempts'] = 1
                    
                    # Apply corrections if suggested
                    if retry_response.get('corrections'):
                        cleaned_items = self._apply_corrections(
                            cleaned_items,
                            retry_response['corrections']
                        )
                        
                        # Recalculate
                        calculated_total = ReconciliationEngine.sum_line_items(cleaned_items)
                        is_match, discrepancy, status = self.reconciler.reconcile(
                            calculated_total,
                            Decimal(str(bill_total))
                        )
                        
                        metadata['discrepancy'] = discrepancy
                        metadata['reconciliation_status'] = status
                        metadata['warnings'].append(
                            f"Applied {len(retry_response['corrections'])} corrections from retry"
                        )
            
            metadata['extraction_confidence'] = 0.95  # Default high confidence after cleanup
            
            return cleaned_items, calculated_total, metadata
            
        except Exception as e:
            logger.error(f"Error in extraction workflow: {e}")
            metadata['reconciliation_status'] = 'error'
            metadata['warnings'].append(str(e))
            return [], Decimal('0.00'), metadata
    
    @staticmethod
    def _convert_to_internal_format(items: List[Dict]) -> List[Dict]:
        """Convert Gemini extraction format to internal format"""
        converted = []
        
        for item in items:
            try:
                converted_item = {
                    'item_name': str(item.get('item_name', '')),
                    'item_quantity': Decimal(str(item.get('quantity', 0))),
                    'item_rate': Decimal(str(item.get('rate', 0))),
                    'item_amount': Decimal(str(item.get('item_amount', 0)))
                }
                converted.append(converted_item)
            except Exception as e:
                logger.warning(f"Error converting item: {e}")
                continue
        
        return converted
    
    @staticmethod
    def _apply_corrections(items: List[Dict], corrections: List[Dict]) -> List[Dict]:
        """Apply corrections from retry response"""
        for correction in corrections:
            action = correction.get('action', '').lower()
            
            if action == 'add':
                items.append({
                    'item_name': correction.get('item_name'),
                    'item_quantity': Decimal(str(correction.get('quantity', 0))),
                    'item_rate': Decimal(str(correction.get('rate', 0))),
                    'item_amount': Decimal(str(correction.get('amount', 0)))
                })
            
            elif action == 'remove':
                items = [
                    i for i in items
                    if i.get('item_name') != correction.get('item_name')
                ]
            
            elif action == 'modify':
                for item in items:
                    if item.get('item_name') == correction.get('item_name'):
                        item.update({
                            'item_quantity': Decimal(str(correction.get('quantity', item['item_quantity']))),
                            'item_rate': Decimal(str(correction.get('rate', item['item_rate']))),
                            'item_amount': Decimal(str(correction.get('amount', item['item_amount'])))
                        })
        
        return items
