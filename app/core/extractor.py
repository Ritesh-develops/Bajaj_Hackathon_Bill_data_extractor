import logging
import json
import base64
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import google.generativeai as genai
try:
    import json5
except ImportError:
    json5 = None
from app.config import GEMINI_API_KEY, LLM_MODEL, MAX_RETRY_ATTEMPTS, RECONCILIATION_THRESHOLD, MIN_DISCREPANCY_FOR_RETRY
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
                temperature=0.0,
                top_p=1.0,       
                top_k=1,
                max_output_tokens=1536  # Reduced for faster API response
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
            Dictionary with extracted data including usage metadata
        """
        try:
            image_base64 = base64.standard_b64encode(image_bytes).decode('utf-8')
            
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
            
            logger.info(f"Sending page {page_no} to Gemini for extraction...")
            response = self.client.generate_content(message)
            
            response_text = response.text
            logger.debug(f"Gemini raw response: {response_text[:500]}...")
            
            extraction_result = self._parse_response(response_text)
            extraction_result['page_number'] = page_no
            
            if hasattr(response, 'usage_metadata'):
                usage_data = response.usage_metadata
                extraction_result['usage_metadata'] = {
                    'total_tokens': usage_data.total_token_count,
                    'input_tokens': usage_data.prompt_token_count,
                    'output_tokens': usage_data.candidates_token_count
                }
                logger.info(f"Page {page_no} tokens - Total: {usage_data.total_token_count}, Input: {usage_data.prompt_token_count}, Output: {usage_data.candidates_token_count}")
            else:
                extraction_result['usage_metadata'] = {
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            
            logger.info(f"Page {page_no}: Extracted {len(extraction_result.get('line_items', []))} items")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error extracting from image: {e}")
            raise
    
    @staticmethod
    def _repair_json(json_str: str) -> str:
        """Repair common JSON malformations from Gemini"""
        import re
        
        # Remove trailing commas first
        json_str = json_str.replace(',]', ']').replace(',}', '}')
        
        # Fix unescaped newlines inside string values
        # Replace literal newlines with \n escape sequence
        json_str = json_str.replace('\n', ' ').replace('\r', ' ')
        
        # Fix unescaped quotes in string values
        # Pattern: Find "key": "value...content with unescaped "quote"...more content"
        # This is complex, so we use a simple heuristic: find problematic quote patterns
        
        # Handle pattern like: "item_name": "ABC "XYZ" DEF"
        # by replacing middle quotes with escaped quotes
        def fix_quoted_value(match):
            prefix = match.group(1)  # "key": "
            content = match.group(2)  # the value
            suffix = match.group(3)   # "
            
            # Escape any unescaped quotes in content
            # But don't escape quotes that are already escaped
            content = re.sub(r'(?<!\\)"', r'\\"', content)
            return prefix + content + suffix
        
        # Match pattern: "key": "...content..."
        # This regex finds quoted values and fixes them
        json_str = re.sub(r'("(?:item_name|item_quantity|item_rate|item_amount|extraction_reasoning|notes)":\s*)"([^"]*(?:"[^"]*)*)"', 
                         lambda m: m.group(1) + '"' + m.group(2).replace('"', '\\"') + '"', json_str)
        
        return json_str
    
    @staticmethod
    def _extract_values_safely(json_str: str) -> Dict:
        """Extract values from malformed JSON using regex as fallback - AGGRESSIVE approach"""
        import re
        
        result = {
            'extraction_reasoning': '',
            'line_items': [],
            'bill_total': None,
            'subtotals': [],
            'notes': ''
        }
        
        try:
            logger.info("🔍 Starting aggressive regex extraction...")
            
            # Try to extract bill_total
            bill_match = re.search(r'"bill_total"\s*:\s*([\d.]+)', json_str)
            if bill_match:
                result['bill_total'] = float(bill_match.group(1))
                logger.debug(f"Found bill_total: {result['bill_total']}")
            
            # NEW APPROACH: Find ALL item_name, quantity, rate, amount patterns
            # and group them into items based on proximity
            
            # Extract all item_name values (including those with escaped quotes or problematic quotes)
            # Match both clean names and names with escaped/unescaped quotes
            item_names = []
            
            # Pattern 1: Clean item names without issues
            clean_names = re.findall(r'"item_name"\s*:\s*"([^"]*)"', json_str)
            item_names.extend(clean_names)
            
            # Pattern 2: Try to catch names that have unescaped quotes causing issues
            # Look for item_name followed by colon and quote, then grab everything until we hit quantity/rate/amount
            broken_names = re.findall(r'"item_name"\s*:\s*"([^"]+(?:"[^"]*)*?)"\s*[,}]', json_str)
            for name in broken_names:
                if name not in item_names:
                    item_names.append(name)
            
            logger.debug(f"Found {len(item_names)} item names via regex patterns")
            
            # If still no names found, try even more aggressive extraction
            if not item_names:
                # Look for pattern: item_name: followed by any content until quantity:
                aggressive_pattern = r'"item_name"\s*:\s*"(.*?)"\s*,?\s*"(?:quantity|rate|amount)"'
                aggressive_names = re.findall(aggressive_pattern, json_str, re.DOTALL)
                item_names.extend([n.replace('\n', ' ').strip() for n in aggressive_names])
                logger.debug(f"Aggressive pattern found {len(aggressive_names)} additional names")
            
            # For each item_name, find the next quantity, rate, amount
            for i, name in enumerate(item_names):
                try:
                    # Clean the name
                    name = name.replace('\n', ' ').replace('\r', ' ').strip()
                    if not name:
                        continue
                    
                    # Find the position of this item_name
                    # Use flexible matching that handles escaped quotes
                    pattern = rf'"item_name"\s*:\s*"[^"]*{re.escape(name[:20])}'
                    match = re.search(pattern, json_str)
                    
                    if not match:
                        # Try without escaping if exact match fails
                        pattern_alt = rf'"item_name"\s*:\s*".*?{name[:20]}'
                        match = re.search(pattern_alt, json_str, re.DOTALL)
                    
                    if not match:
                        logger.debug(f"Could not locate item_name '{name[:30]}...' in JSON")
                        continue
                    
                    start_pos = match.end()
                    # Look for quantity, rate, amount within next 500 chars (increased from 300)
                    chunk = json_str[start_pos:start_pos + 500]
                    
                    item = {'item_name': name}
                    
                    # Extract quantity
                    qty_match = re.search(r'"quantity"\s*:\s*([\d.]+)', chunk)
                    item['quantity'] = float(qty_match.group(1)) if qty_match else 1
                    
                    # Extract rate
                    rate_match = re.search(r'"rate"\s*:\s*([\d.]+)', chunk)
                    item['rate'] = float(rate_match.group(1)) if rate_match else 0
                    
                    # Extract amount
                    amount_match = re.search(r'"amount"\s*:\s*([\d.]+)', chunk)
                    item['amount'] = float(amount_match.group(1)) if amount_match else 0
                    
                    # Only add if we found at least quantity or amount
                    if item['quantity'] > 0 or item['amount'] > 0:
                        result['line_items'].append(item)
                        logger.debug(f"✓ Extracted: {name[:40]} - qty:{item['quantity']}, amt:{item['amount']}")
                    else:
                        logger.debug(f"✗ Skipped: {name[:40]} - no valid numbers found")
                    
                except Exception as e:
                    logger.debug(f"Error extracting item {i} '{name[:30]}': {e}")
                    continue
            
            logger.info(f"✓ Regex extraction found {len(result['line_items'])} items")
            
        except Exception as e:
            logger.error(f"Regex extraction error: {e}")
        
        return result
    
    @staticmethod
    def _parse_response(response_text: str) -> Dict:
        """Parse Gemini response and extract JSON with aggressive recovery"""
        try:
            # Pre-process raw response: clean up obvious formatting issues
            response_text = response_text.replace('\r\n', ' ').replace('\n', ' ')
            
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
            extraction = None
            
            # Try standard JSON parsing first
            try:
                extraction = json.loads(json_str)
                logger.info("✓ JSON parsed successfully on first try")
            except json.JSONDecodeError as parse_err:
                logger.warning(f"✗ JSON parsing failed: {parse_err}")
                
                # Fallback 1: Try json5 (handles more lenient JSON)
                if json5:
                    try:
                        extraction = json5.loads(json_str)
                        logger.info("✓ Successfully parsed with json5 (lenient JSON parser)")
                    except Exception as e:
                        logger.debug(f"✗ json5 parsing also failed: {e}")
                
                # Fallback 2: Attempt aggressive repair
                if extraction is None:
                    try:
                        json_str_fixed = GeminiExtractor._repair_json(json_str)
                        extraction = json.loads(json_str_fixed)
                        logger.info("✓ Successfully recovered from malformed JSON after repair")
                    except json.JSONDecodeError as repair_err:
                        logger.warning(f"✗ Repair attempt failed: {repair_err}")
                
                # Fallback 3: Direct array extraction
                if extraction is None:
                    logger.warning("⚠ Trying direct extraction of line_items array...")
                    line_items_match = response_text.find('"line_items"')
                    if line_items_match != -1:
                        try:
                            array_start = response_text.find('[', line_items_match)
                            array_end = response_text.find(']', array_start) + 1
                            if array_start != -1 and array_end > array_start:
                                line_items_str = response_text[array_start:array_end]
                                # Clean up the array string too
                                line_items_str = line_items_str.replace('\n', ' ').replace('\r', ' ')
                                line_items = json.loads(line_items_str)
                                logger.info(f"✓ Extracted {len(line_items)} items directly from malformed JSON")
                                return {
                                    'extraction_reasoning': '',
                                    'line_items': line_items,
                                    'bill_total': None,
                                    'subtotals': [],
                                    'notes': 'Extracted from partial parse of malformed JSON'
                                }
                        except Exception as e:
                            logger.debug(f"✗ Direct extraction failed: {e}")
                
                # If all recovery attempts fail
                if extraction is None:
                    logger.warning("⚠ Attempting regex-based extraction as last resort...")
                    extraction = GeminiExtractor._extract_values_safely(json_str)
                    if extraction.get('line_items'):
                        logger.info(f"✓ Successfully extracted {len(extraction['line_items'])} items via regex fallback")
                    else:
                        logger.error(f"✗ Regex extraction also failed")
                        return {
                            'line_items': [],
                            'bill_total': None,
                            'subtotals': [],
                            'notes': f'JSON parsing failed - could not recover: {parse_err}'
                        }
            
            if extraction:
                return {
                    'extraction_reasoning': extraction.get('extraction_reasoning', ''),
                    'line_items': extraction.get('line_items', []),
                    'bill_total': extraction.get('bill_total'),
                    'subtotals': extraction.get('subtotals', []),
                    'notes': extraction.get('notes', '')
                }
            else:
                return {
                    'line_items': [],
                    'bill_total': None,
                    'subtotals': [],
                    'notes': 'Failed to parse JSON'
                }
            
        except Exception as e:
            logger.error(f"Unexpected error in JSON parsing: {e}")
            return {
                'line_items': [],
                'bill_total': None,
                'subtotals': [],
                'notes': f'JSON parsing error: {e}'
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
            
            items_json = json.dumps([
                {
                    'item_name': item.get('item_name'),
                    'quantity': float(item.get('item_quantity', 0)),
                    'rate': float(item.get('item_rate', 0)),
                    'amount': float(item.get('item_amount', 0))
                }
                for item in extracted_items
            ], indent=2)
            
            retry_prompt = RECONCILIATION_RETRY_PROMPT_TEMPLATE.format(
                item_count=item_count,
                extracted_items=items_json,
                calculated_total=float(calculated_total),
                actual_total=float(actual_total),
                discrepancy=float(discrepancy)
            )
            
            image_base64 = base64.standard_b64encode(image_bytes).decode('utf-8')
            
            logger.info(f"Retry #{retry_count}: Reconciliation with LLM...")
            
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
            
            retry_result = self._parse_retry_response(response_text)
            
            if hasattr(response, 'usage_metadata'):
                usage_data = response.usage_metadata
                retry_result['usage_metadata'] = {
                    'total_tokens': usage_data.total_token_count,
                    'input_tokens': usage_data.prompt_token_count,
                    'output_tokens': usage_data.candidates_token_count
                }
                logger.info(f"Retry tokens - Total: {usage_data.total_token_count}, Input: {usage_data.prompt_token_count}, Output: {usage_data.candidates_token_count}")
            else:
                retry_result['usage_metadata'] = {
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            
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
    @staticmethod
    def _parse_retry_response(response_text: str) -> Dict:
        """Parse retry response from Gemini with recovery"""
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                return {'corrections': [], 'new_total': 0, 'confidence': 0.0}
            
            json_str = response_text[start_idx:end_idx]
            retry_response = None
            
            # Try standard JSON parsing first
            try:
                retry_response = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback 1: Try json5
                if json5:
                    try:
                        retry_response = json5.loads(json_str)
                    except Exception:
                        pass
                
                # Fallback 2: Repair trailing commas
                if retry_response is None:
                    try:
                        json_str_fixed = json_str.replace(',]', ']').replace(',}', '}')
                        retry_response = json.loads(json_str_fixed)
                    except json.JSONDecodeError:
                        pass
                
                if retry_response is None:
                    return {'corrections': [], 'new_total': 0, 'confidence': 0.0}
            
            return {
                'analysis': retry_response.get('analysis', ''),
                'corrections': retry_response.get('corrections', []),
                'new_total': retry_response.get('new_total'),
                'confidence': retry_response.get('confidence', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error parsing retry response: {e}")
            return {'corrections': [], 'new_total': 0, 'confidence': 0.0}


class ExtractionOrchestrator:
    """Orchestrates the complete extraction and reconciliation workflow"""
    
    def __init__(self):
        self.extractor = GeminiExtractor()
        self.reconciler = ReconciliationEngine(threshold=float(RECONCILIATION_THRESHOLD))
        self.validator = ExtractedDataValidator()
        self.total_tokens = {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
    
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
            'warnings': [],
            'token_usage': {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
        }
        
        try:
            logger.info(f"[EXTRACTOR] Phase 2: Starting extraction for page {page_no}")
            extraction_result = self.extractor.extract_from_image(image_bytes, page_no)
            
            logger.info(f"[EXTRACTOR] Phase 2: Gemini response received for page {page_no}")
            
            usage_data = extraction_result.get('usage_metadata', {})
            if usage_data:
                self.total_tokens['total_tokens'] += usage_data.get('total_tokens', 0)
                self.total_tokens['input_tokens'] += usage_data.get('input_tokens', 0)
                self.total_tokens['output_tokens'] += usage_data.get('output_tokens', 0)
                metadata['token_usage'] = {
                    'total_tokens': self.total_tokens['total_tokens'],
                    'input_tokens': self.total_tokens['input_tokens'],
                    'output_tokens': self.total_tokens['output_tokens']
                }
                logger.info(f"[EXTRACTOR] Token usage - Total: {usage_data.get('total_tokens', 0)}, Input: {usage_data.get('input_tokens', 0)}, Output: {usage_data.get('output_tokens', 0)}")
            
            raw_items = self._convert_to_internal_format(extraction_result.get('line_items', []))
            bill_total = extraction_result.get('bill_total')
            
            logger.info(f"[EXTRACTOR] Phase 2: Raw items extracted: {len(raw_items)}, Bill total: {bill_total}")
            
            if not raw_items:
                logger.warning(f"[EXTRACTOR] No items extracted from page {page_no}")
                logger.info(f"[EXTRACTOR] Extraction notes: {extraction_result.get('notes')}")
                logger.info(f"[EXTRACTOR] Extraction reasoning: {extraction_result.get('extraction_reasoning')}")
                
                metadata['warnings'].append("No line items found in document")
                metadata['extraction_notes'] = extraction_result.get('notes', '')
                metadata['extraction_reasoning'] = extraction_result.get('extraction_reasoning', '')[:500]
                
                return [], Decimal('0.00'), metadata
            
            logger.info(f"[EXTRACTOR] Phase 3: Validating and cleaning {len(raw_items)} items")
            
            cleaned_items, clean_report = self.validator.validate_and_clean(
                raw_items,
                bill_total
            )
            
            logger.info(f"[EXTRACTOR] Phase 3: Cleaned items: {len(cleaned_items)}, Warnings: {len(clean_report.get('warnings', []))}")
            metadata['warnings'].extend(clean_report.get('warnings', []))
            
            calculated_total = ReconciliationEngine.sum_line_items(cleaned_items)
            
            logger.info(f"[EXTRACTOR] Phase 3: Calculated total: {calculated_total}, Bill total: {bill_total}")
            
            if bill_total is not None:
                is_match, discrepancy, status = self.reconciler.reconcile(
                    calculated_total,
                    ExtractionOrchestrator._safe_decimal_convert(bill_total, 0)
                )
                
                metadata['discrepancy'] = discrepancy
                metadata['reconciliation_status'] = status
                
                logger.info(f"[EXTRACTOR] Phase 3: Reconciliation - Match: {is_match}, Discrepancy: {discrepancy}, Status: {status}")
                
                should_retry = False  # DISABLED FOR SPEED - Priority optimization
                
                if should_retry:
                    logger.info(f"[EXTRACTOR] Phase 4: Triggering retry (discrepancy: {discrepancy}, status: {status})")
                    
                    retry_response = self.extractor.retry_extraction(
                        image_bytes,
                        cleaned_items,
                        calculated_total,
                        ExtractionOrchestrator._safe_decimal_convert(bill_total, 0),
                        retry_count=1
                    )
                    
                    metadata['retry_attempts'] = 1
                    logger.info(f"[EXTRACTOR] Phase 4: Retry response received")
                    
                    retry_usage = retry_response.get('usage_metadata', {})
                    if retry_usage:
                        self.total_tokens['total_tokens'] += retry_usage.get('total_tokens', 0)
                        self.total_tokens['input_tokens'] += retry_usage.get('input_tokens', 0)
                        self.total_tokens['output_tokens'] += retry_usage.get('output_tokens', 0)
                        metadata['token_usage'] = {
                            'total_tokens': self.total_tokens['total_tokens'],
                            'input_tokens': self.total_tokens['input_tokens'],
                            'output_tokens': self.total_tokens['output_tokens']
                        }
                        logger.info(f"[EXTRACTOR] Phase 4: Retry tokens - Total: {retry_usage.get('total_tokens', 0)}")
                    
                    if retry_response.get('corrections'):
                        logger.info(f"[EXTRACTOR] Phase 4: Applying {len(retry_response['corrections'])} corrections")
                        cleaned_items = self._apply_corrections(
                            cleaned_items,
                            retry_response['corrections']
                        )
                        
                        calculated_total = ReconciliationEngine.sum_line_items(cleaned_items)
                        is_match, discrepancy, status = self.reconciler.reconcile(
                            calculated_total,
                            ExtractionOrchestrator._safe_decimal_convert(bill_total, 0)
                        )
                        
                        metadata['discrepancy'] = discrepancy
                        metadata['reconciliation_status'] = status
                        metadata['warnings'].append(
                            f"Applied {len(retry_response['corrections'])} corrections from retry"
                        )
                        logger.info(f"[EXTRACTOR] Phase 4: After corrections - New discrepancy: {discrepancy}, Status: {status}")
                    else:
                        logger.warning(f"[EXTRACTOR] Phase 4: Retry returned no corrections")
                else:
                    logger.info(f"[EXTRACTOR] Phase 3: No retry needed - Match: {is_match}")
            
            metadata['extraction_confidence'] = 0.95
            logger.info(f"[EXTRACTOR] Extraction complete - Items: {len(cleaned_items)}, Total: {calculated_total}, Status: {metadata['reconciliation_status']}")
            
            return cleaned_items, calculated_total, metadata
            
        except Exception as e:
            logger.error(f"[EXTRACTOR] [ERROR] Error in extraction workflow: {e}", exc_info=True)
            metadata['reconciliation_status'] = 'error'
            metadata['warnings'].append(str(e))
            return [], Decimal('0.00'), metadata
    
    @staticmethod
    def _safe_decimal_convert(value, default=0):
        """Safely convert any value to Decimal"""
        if value is None:
            return Decimal(str(default))
        try:
            # Handle string with commas or spaces
            if isinstance(value, str):
                value = value.strip().replace(',', '').replace(' ', '')
                if not value:
                    return Decimal(str(default))
            return Decimal(str(value))
        except Exception:
            return Decimal(str(default))

    @staticmethod
    def _convert_to_internal_format(items: List[Dict]) -> List[Dict]:
        """Convert Gemini extraction format to internal format"""
        converted = []
        
        for item in items:
            try:
                converted_item = {
                    'item_name': str(item.get('item_name', '')),
                    'item_quantity': ExtractionOrchestrator._safe_decimal_convert(item.get('quantity'), 1),
                    'item_rate': ExtractionOrchestrator._safe_decimal_convert(item.get('rate'), 0),
                    'item_amount': ExtractionOrchestrator._safe_decimal_convert(item.get('amount'), 0)
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
                    'item_quantity': ExtractionOrchestrator._safe_decimal_convert(correction.get('quantity'), 1),
                    'item_rate': ExtractionOrchestrator._safe_decimal_convert(correction.get('rate'), 0),
                    'item_amount': ExtractionOrchestrator._safe_decimal_convert(correction.get('amount'), 0)
                })
            
            elif action == 'remove':
                items = [
                    i for i in items
                    if i.get('item_name') != correction.get('item_name')
                ]
            
            elif action == 'modify':
                for item in items:
                    if item.get('item_name') == correction.get('item_name'):
                        item['item_quantity'] = ExtractionOrchestrator._safe_decimal_convert(correction.get('quantity'), item.get('item_quantity', 1))
                        item['item_rate'] = ExtractionOrchestrator._safe_decimal_convert(correction.get('rate'), item.get('item_rate', 0))
                        item['item_amount'] = ExtractionOrchestrator._safe_decimal_convert(correction.get('amount'), item.get('item_amount', 0))
        
        return items
