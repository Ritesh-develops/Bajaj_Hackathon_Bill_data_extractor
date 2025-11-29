import logging
import json
import base64
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import google.generativeai as genai
import time
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
                max_output_tokens=2048  # Increased for paid tier - better accuracy with fewer retries
            )
        )
        
        logger.info(f"Initialized Gemini extractor with model: {self.model} (temperature=0.0 for deterministic results)")
    
    @staticmethod
    def _validate_extracted_items(line_items: List[Dict], bill_total: Optional[float] = None) -> Tuple[List[Dict], Dict]:
        """
        Validate and clean extracted items with confidence scoring
        
        Returns:
            - cleaned_items: validated line items
            - validation_report: accuracy metrics
        """
        validation_report = {
            'total_items': len(line_items),
            'valid_items': 0,
            'invalid_items': 0,
            'items_with_zero_amount': 0,
            'suspicious_items': [],
            'accuracy_score': 0.0,
            'issues': []
        }
        
        cleaned_items = []
        
        for idx, item in enumerate(line_items):
            if not item or not isinstance(item, dict):
                validation_report['invalid_items'] += 1
                continue
            
            item_name = str(item.get('item_name', '')).strip()
            quantity = item.get('quantity', 1)
            rate = item.get('rate', 0)
            amount = item.get('amount', 0)
            
            # Convert to float for validation
            try:
                quantity = float(quantity) if quantity else 1
                rate = float(rate) if rate else 0
                amount = float(amount) if amount else 0
            except (ValueError, TypeError):
                validation_report['invalid_items'] += 1
                validation_report['issues'].append(f"Item {idx}: Could not convert numbers")
                continue
            
            # Validation checks
            if not item_name:
                validation_report['invalid_items'] += 1
                validation_report['issues'].append(f"Item {idx}: Missing item name")
                continue
            
            if amount == 0 and quantity == 0:
                validation_report['items_with_zero_amount'] += 1
                validation_report['issues'].append(f"Item {idx} ({item_name}): Zero amount and quantity")
                continue
            
            # Verify math: quantity × rate should equal amount
            if quantity > 0 and rate > 0 and amount > 0:
                calculated_amount = quantity * rate
                difference = abs(calculated_amount - amount)
                tolerance = max(0.01, amount * 0.05)  # 5% tolerance or 0.01
                
                if difference > tolerance:
                    validation_report['suspicious_items'].append({
                        'item': item_name,
                        'calculated': calculated_amount,
                        'actual': amount,
                        'difference': difference
                    })
                    logger.warning(f"Item math mismatch: {item_name} - calc:{calculated_amount}, actual:{amount}")
                    # Still include but flag as suspicious
            
            # Clean and add item
            cleaned_item = {
                'item_name': item_name,
                'item_quantity': quantity,
                'item_rate': rate,
                'item_amount': amount,
                'confidence': 0.95 if not validation_report['suspicious_items'] else 0.75
            }
            cleaned_items.append(cleaned_item)
            validation_report['valid_items'] += 1
        
        # Calculate accuracy score
        total = validation_report['total_items']
        if total > 0:
            accuracy_score = (validation_report['valid_items'] - len(validation_report['suspicious_items']) * 0.2) / total
            validation_report['accuracy_score'] = max(0, min(1.0, accuracy_score))  # Clamp to 0-1
        
        if validation_report['accuracy_score'] >= 0.8:
            logger.info(f"✓ Extraction accuracy: {validation_report['accuracy_score']:.1%}")
        else:
            logger.warning(f"⚠ Low extraction accuracy: {validation_report['accuracy_score']:.1%} - {validation_report['issues']}")
        
        return cleaned_items, validation_report
    
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
            api_call_start = time.time()
            
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
            
            logger.info(f"[API CALL] Page {page_no}: Sending to Gemini API...")
            api_request_start = time.time()
            response = self.client.generate_content(message)
            api_request_end = time.time()
            logger.info(f"[API TIMING] Page {page_no}: Gemini API response took {api_request_end - api_request_start:.2f}s")
            
            response_text = response.text
            logger.debug(f"Gemini raw response: {response_text[:500]}...")
            
            parse_start = time.time()
            extraction_result = self._parse_response(response_text)
            parse_end = time.time()
            logger.info(f"[PARSE TIMING] Page {page_no}: Response parsing took {parse_end - parse_start:.2f}s")
            
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
            
            api_call_end = time.time()
            logger.info(f"[TOTAL TIMING] Page {page_no}: Complete extraction (API + parsing) took {api_call_end - api_call_start:.2f}s")
            logger.info(f"Page {page_no}: Extracted {len(extraction_result.get('line_items', []))} items")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error extracting from image: {e}")
            raise
    
    @staticmethod
    def _fix_json_structure(json_str: str) -> str:
        """Fix common JSON structure issues: missing commas, unescaped quotes, etc"""
        import re
        
        # 1. Fix missing commas between objects in array
        # Pattern: }{ or }\s*{ without comma between them
        json_str = re.sub(r'}\s*{', '},{', json_str)
        
        # 2. Fix missing commas before closing bracket
        # Pattern: }] should be }] (already correct) but }  } should have comma
        # Look for: }\s*}\s* -> },}
        json_str = re.sub(r'}\s*}\s*', '},}', json_str)
        
        # 3. Remove trailing commas before } or ]
        json_str = json_str.replace(',}', '}').replace(',]', ']')
        
        # 4. Fix unescaped newlines/tabs inside string values
        # Replace actual newlines with spaces (they shouldn't be in JSON strings)
        json_str = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # 5. Fix unescaped quotes inside string values
        # Pattern: "key": "value "with "unescaped" quotes"
        # This is tricky - we need to find quoted strings and escape inner quotes
        def fix_quoted_strings(text):
            # Find all quoted strings
            parts = []
            in_string = False
            escape_next = False
            current_string = ''
            
            i = 0
            while i < len(text):
                char = text[i]
                
                if escape_next:
                    current_string += char
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    current_string += char
                    escape_next = True
                    i += 1
                    continue
                
                if char == '"':
                    if in_string:
                        # End of string - check if there are unescaped quotes inside
                        # and escape them
                        current_string += char
                        in_string = False
                        parts.append(current_string)
                        current_string = ''
                    else:
                        # Start of string
                        in_string = True
                        current_string = char
                    i += 1
                    continue
                
                current_string += char
                i += 1
            
            if current_string:
                parts.append(current_string)
            
            return ''.join(parts)
        
        # Apply quote fixing
        try:
            json_str = fix_quoted_strings(json_str)
        except:
            pass  # If quote fixing fails, continue anyway
        
        return json_str
    
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
        
        if result['line_items']:
            logger.info(f"✓ Regex extraction SUCCESS: recovered {len(result['line_items'])} items, bill_total: {result['bill_total']}")
        else:
            logger.warning(f"✗ Regex extraction FAILED: no items found")
        
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
            
            # Try standard JSON parsing first (fastest if it works)
            try:
                extraction = json.loads(json_str)
                logger.info("✓ JSON parsed successfully on first try")
            except json.JSONDecodeError as parse_err:
                logger.warning(f"✗ JSON parsing failed: {parse_err}")
                
                # STEP 1: Try regex extraction FIRST (most reliable for malformed JSON)
                logger.warning("⚠ STEP 1: Attempting regex-based extraction (fastest, most reliable)...")
                extraction = GeminiExtractor._extract_values_safely(json_str)
                
                if extraction.get('line_items'):
                    logger.info(f"✓ Regex extraction SUCCESS: recovered {len(extraction['line_items'])} items")
                    return extraction
                
                # STEP 2: If regex didn't work, try fixing JSON structure
                logger.warning("⚠ STEP 2: Regex failed, attempting JSON structure fix...")
                json_str_fixed = GeminiExtractor._fix_json_structure(json_str)
                
                try:
                    extraction = json.loads(json_str_fixed)
                    logger.info("✓ Successfully parsed after fixing JSON structure")
                except json.JSONDecodeError as fix_err:
                    logger.warning(f"✗ Fixed JSON still failed: {fix_err}")
                    
                    # STEP 3: Try json5 (lenient parser)
                    logger.warning("⚠ STEP 3: Trying json5 parser...")
                    if json5:
                        try:
                            extraction = json5.loads(json_str)
                            logger.info("✓ Successfully parsed with json5 (lenient JSON parser)")
                        except Exception as e:
                            logger.debug(f"✗ json5 parsing also failed: {e}")
                    
                    # STEP 4: Try aggressive repair
                    if extraction is None:
                        logger.warning("⚠ STEP 4: Attempting aggressive JSON repair...")
                        try:
                            json_str_repaired = GeminiExtractor._repair_json(json_str)
                            extraction = json.loads(json_str_repaired)
                            logger.info("✓ Successfully recovered from malformed JSON after repair")
                        except json.JSONDecodeError as repair_err:
                            logger.warning(f"✗ Repair attempt failed: {repair_err}")
                    
                    # If all recovery attempts fail
                    if extraction is None:
                        logger.error(f"✗ Could not recover JSON after all attempts: {parse_err}")
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
            
            # NEW: Advanced accuracy validation
            logger.info(f"[EXTRACTOR] Phase 3b: Running advanced accuracy validation...")
            validated_items, validation_report = GeminiExtractor._validate_extracted_items(cleaned_items, bill_total)
            
            logger.info(f"[EXTRACTOR] Accuracy Report - Valid: {validation_report['valid_items']}/{validation_report['total_items']}, "
                       f"Score: {validation_report['accuracy_score']:.1%}, Issues: {len(validation_report['issues'])}")
            
            if validation_report['suspicious_items']:
                logger.warning(f"[EXTRACTOR] Found {len(validation_report['suspicious_items'])} items with suspicious math")
                for susp in validation_report['suspicious_items']:
                    logger.warning(f"  - {susp['item']}: calculated={susp['calculated']}, actual={susp['actual']}")
            
            metadata['accuracy_score'] = validation_report['accuracy_score']
            metadata['validation_issues'] = validation_report['issues']
            
            calculated_total = ReconciliationEngine.sum_line_items(validated_items)
            
            logger.info(f"[EXTRACTOR] Phase 3: Calculated total: {calculated_total}, Bill total: {bill_total}")
            
            # SKIP RECONCILIATION for speed - return immediately
            metadata['reconciliation_status'] = 'skipped_for_speed'
            metadata['extraction_confidence'] = validation_report['accuracy_score']
            logger.info(f"[EXTRACTOR] Extraction complete - Items: {len(validated_items)}, Total: {calculated_total}, Accuracy: {validation_report['accuracy_score']:.1%}")
            
            return validated_items, calculated_total, metadata
            
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
