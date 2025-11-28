"""Reconciliation and data validation logic"""

import logging
import re
from typing import List, Dict, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
from app.config import DOUBLE_COUNT_KEYWORDS

logger = logging.getLogger(__name__)


class DataCleaner:
    """Utilities for cleaning extracted data"""
    
    @staticmethod
    def standardize_number(value: str) -> Optional[Decimal]:
        """
        Convert various number formats to standard Decimal
        E.g., "$1,200.50" -> Decimal("1200.50")
        """
        try:
            if not isinstance(value, str):
                return Decimal(str(value))
            
            # Remove common currency symbols and spaces
            cleaned = re.sub(r'[\$£€₹\s]', '', value.strip())
            
            # Remove thousands separators (commas) when followed by 3 digits and a decimal
            cleaned = re.sub(r',(?=\d{3}\.)', '', cleaned)
            # Remove other commas that are thousands separators
            cleaned = re.sub(r',(?=\d{3}(?:\D|$))', '', cleaned)
            
            # Convert to Decimal
            return Decimal(cleaned)
        except Exception as e:
            logger.warning(f"Failed to standardize number '{value}': {e}")
            return None
    
    @staticmethod
    def fix_ocr_errors(text: str) -> str:
        """Fix common OCR errors"""
        if not text:
            return text
        
        replacements = {
            'l': '1',  # lowercase L to 1
            'O': '0',  # uppercase O to 0
            'S': '5',  # uppercase S to 5 (in some contexts)
            'B': '8',  # uppercase B to 8 (in some contexts)
        }
        
        # Only apply to purely numeric contexts
        # This is a conservative approach
        result = text
        for old, new in replacements.items():
            # Only replace if surrounded by digits or at boundaries
            result = re.sub(rf'(?<=[0-9]){re.escape(old)}(?=[0-9])', new, result)
        
        return result
    
    @staticmethod
    def clean_item_name(name: str) -> str:
        """Clean and normalize item names"""
        if not name:
            return ""
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove trailing/leading special characters
        name = re.sub(r'^[\s\-\*]+|[\s\-\*]+$', '', name)
        
        # Fix OCR errors specific to text
        name = DataCleaner.fix_ocr_errors(name)
        
        return name


class DoubleCountingGuard:
    """Detect and prevent double-counting of totals, taxes, discounts, etc."""
    
    @staticmethod
    def is_double_count_keyword(text: str) -> bool:
        """Check if text contains double-counting keywords"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        for keyword in DOUBLE_COUNT_KEYWORDS:
            if keyword in text_lower:
                return True
        
        return False
    
    @staticmethod
    def check_outlier_total(items: List[Dict], suspect_amount: Decimal) -> bool:
        """
        Detect if an amount equals the sum of all other items
        This typically indicates a subtotal/total row that was mistakenly included
        Uses dynamic thresholding to avoid false positives on legitimate items
        """
        if not items or len(items) < 2:
            return False
        
        # Calculate sum of all items
        total = sum(
            Decimal(str(item.get('item_amount', 0))) 
            for item in items
        )
        
        if total == 0:
            return False
        
        # Calculate average item amount to establish baseline
        avg_amount = total / len(items)
        
        # If suspect amount is much larger than average (5x+), it's likely a total
        # This prevents filtering legitimate high-value items
        if suspect_amount > avg_amount * Decimal('5'):
            # Additional check: does it equal the sum?
            if abs(suspect_amount - total) < Decimal('0.01'):
                return True
        
        return False
    
    @staticmethod
    def filter_double_counts(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate legitimate line items from totals/taxes/discounts
        Uses context-aware filtering to handle multiple item sections
        
        Returns: (clean_items, removed_items)
        """
        clean_items = []
        removed_items = []
        
        for idx, item in enumerate(items):
            item_name = item.get('item_name', '').lower()
            amount = Decimal(str(item.get('item_amount', 0)))
            
            # Check for keyword matches - strict check only
            if DoubleCountingGuard.is_double_count_keyword(item_name):
                # Before removing, verify this isn't a legitimate item with unfortunate naming
                # Check if it has typical item properties (quantity, rate not 1 or 0)
                qty = Decimal(str(item.get('item_quantity', 0)))
                rate = Decimal(str(item.get('item_rate', 0)))
                
                # If quantity or rate is suspiciously 1 or 0, likely a summary line
                if qty <= 0 or rate == 0:
                    logger.info(f"Removed item '{item_name}' - keyword + suspiciously low qty/rate")
                    removed_items.append(item)
                    continue
                # If it looks like a real item (qty > 1, rate > 0), keep it
                else:
                    logger.info(f"Keeping '{item_name}' - despite keyword, has valid qty/rate: {qty}@{rate}")
            else:
                # For non-keyword items, only check outlier if already have a significant sample
                if len(clean_items) >= 3:
                    suspect = DoubleCountingGuard.check_outlier_total(clean_items, amount)
                    if suspect:
                        logger.info(f"Removed item '{item_name}' - outlier total (amount {amount} vs avg)")
                        removed_items.append(item)
                        continue
            
            clean_items.append(item)
        
        return clean_items, removed_items


class ReconciliationEngine:
    """Handles reconciliation of extracted totals with calculated totals"""
    
    def __init__(self, threshold: float = 0.01):
        """
        Initialize reconciliation engine
        
        Args:
            threshold: Acceptable discrepancy as percentage (default 0.01%)
        """
        self.threshold = Decimal(str(threshold)) / 100
    
    @staticmethod
    def calculate_line_item_total(quantity: Decimal, rate: Decimal) -> Decimal:
        """Calculate total for a line item: quantity * rate"""
        try:
            total = (quantity * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return total
        except Exception as e:
            logger.error(f"Error calculating line item total: {e}")
            return Decimal('0.00')
    
    @staticmethod
    def sum_line_items(items: List[Dict]) -> Decimal:
        """Calculate sum of all line item amounts"""
        try:
            total = sum(
                Decimal(str(item.get('item_amount', 0)))
                for item in items
            )
            return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.error(f"Error summing line items: {e}")
            return Decimal('0.00')
    
    def reconcile(
        self, 
        calculated_total: Decimal, 
        actual_total: Decimal
    ) -> Tuple[bool, Decimal, str]:
        """
        Reconcile calculated total with actual total
        
        Returns: (is_match, discrepancy, status)
        """
        discrepancy = abs(calculated_total - actual_total)
        
        # Check for exact match
        if discrepancy == 0:
            return True, Decimal('0.00'), "exact_match"
        
        # Check if within threshold
        if actual_total > 0:
            percentage_diff = (discrepancy / actual_total)
            if percentage_diff <= self.threshold:
                return True, discrepancy, "within_threshold"
        
        return False, discrepancy, "mismatch"
    
    @staticmethod
    def validate_line_item_amounts(items: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate that item_amount = item_quantity * item_rate for each item
        
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        
        for idx, item in enumerate(items):
            try:
                quantity = Decimal(str(item.get('item_quantity', 0)))
                rate = Decimal(str(item.get('item_rate', 0)))
                amount = Decimal(str(item.get('item_amount', 0)))
                
                calculated = quantity * rate
                
                # Allow small rounding differences
                if abs(calculated - amount) > Decimal('0.01'):
                    errors.append(
                        f"Item {idx}: {item.get('item_name')} - "
                        f"Mismatch: {quantity} * {rate} = {calculated}, but amount is {amount}"
                    )
            except Exception as e:
                errors.append(f"Item {idx}: Error validating amounts - {e}")
        
        return len(errors) == 0, errors


class ExtractedDataValidator:
    """Comprehensive validation of extracted bill data"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
        self.guard = DoubleCountingGuard()
        self.reconciler = ReconciliationEngine()
    
    def validate_and_clean(
        self,
        items: List[Dict],
        bill_total: Optional[Decimal] = None
    ) -> Tuple[List[Dict], Dict]:
        """
        Comprehensive validation and cleaning pipeline
        
        Returns: (cleaned_items, validation_report)
        """
        report = {
            "original_count": len(items),
            "cleaning_steps": [],
            "errors": [],
            "warnings": []
        }
        
        # Step 1: Clean item names and standardize numbers
        cleaned_items = []
        for item in items:
            try:
                clean_item = {
                    "item_name": self.cleaner.clean_item_name(
                        item.get('item_name', '')
                    ),
                    "item_quantity": Decimal(str(item.get('item_quantity', 0))),
                    "item_rate": Decimal(str(item.get('item_rate', 0))),
                    "item_amount": Decimal(str(item.get('item_amount', 0)))
                }
                
                # Fix calculation if needed
                calculated_amount = ReconciliationEngine.calculate_line_item_total(
                    clean_item["item_quantity"],
                    clean_item["item_rate"]
                )
                
                if abs(calculated_amount - clean_item["item_amount"]) > Decimal('0.01'):
                    report["warnings"].append(
                        f"Item '{clean_item['item_name']}': Amount mismatch, "
                        f"correcting from {clean_item['item_amount']} to {calculated_amount}"
                    )
                    clean_item["item_amount"] = calculated_amount
                
                cleaned_items.append(clean_item)
            except Exception as e:
                report["errors"].append(f"Error cleaning item: {e}")
        
        report["cleaning_steps"].append(f"Cleaned {len(cleaned_items)} items")
        
        # Step 2: Remove double-counting entries
        filtered_items, removed = self.guard.filter_double_counts(cleaned_items)
        
        if removed:
            report["cleaning_steps"].append(
                f"Removed {len(removed)} double-count items: "
                f"{', '.join(i.get('item_name', 'unknown') for i in removed)}"
            )
        
        # Step 3: Validate line item amounts
        is_valid, calc_errors = self.reconciler.validate_line_item_amounts(filtered_items)
        if not is_valid:
            report["errors"].extend(calc_errors)
        
        report["final_count"] = len(filtered_items)
        
        return filtered_items, report
