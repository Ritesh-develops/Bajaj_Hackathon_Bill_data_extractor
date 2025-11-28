"""Unit tests for reconciliation and validation logic"""

import pytest
from decimal import Decimal
from app.core.logic import (
    DataCleaner,
    DoubleCountingGuard,
    ReconciliationEngine,
    ExtractedDataValidator
)


class TestDataCleaner:
    """Tests for DataCleaner"""
    
    def test_standardize_currency_format(self):
        """Test converting currency formats to Decimal"""
        assert DataCleaner.standardize_number("$1,200.50") == Decimal("1200.50")
        assert DataCleaner.standardize_number("₹1,00,000.00") == Decimal("100000.00")
        assert DataCleaner.standardize_number("1200.50") == Decimal("1200.50")
    
    def test_standardize_number_invalid(self):
        """Test handling of invalid numbers"""
        assert DataCleaner.standardize_number("invalid") is None
        assert DataCleaner.standardize_number("") is None
    
    def test_clean_item_name(self):
        """Test item name cleaning"""
        assert DataCleaner.clean_item_name("  Livi 300mg Tab  ") == "Livi 300mg Tab"
        assert DataCleaner.clean_item_name("---Item Name---") == "Item Name"


class TestDoubleCountingGuard:
    """Tests for DoubleCountingGuard"""
    
    def test_double_count_keyword_detection(self):
        """Test detection of double-count keywords"""
        assert DoubleCountingGuard.is_double_count_keyword("TOTAL") is True
        assert DoubleCountingGuard.is_double_count_keyword("Subtotal") is True
        assert DoubleCountingGuard.is_double_count_keyword("GST") is True
        assert DoubleCountingGuard.is_double_count_keyword("Product Name") is False
    
    def test_filter_double_counts(self):
        """Test filtering of double-count items"""
        items = [
            {"item_name": "Livi 300mg Tab", "amount": 448},
            {"item_name": "Metnuro", "amount": 124.03},
            {"item_name": "Total", "amount": 572.03},
        ]
        
        clean, removed = DoubleCountingGuard.filter_double_counts(items)
        
        assert len(clean) == 2
        assert len(removed) == 1
        assert removed[0]["item_name"] == "Total"


class TestReconciliationEngine:
    """Tests for ReconciliationEngine"""
    
    def test_calculate_line_item_total(self):
        """Test line item total calculation"""
        total = ReconciliationEngine.calculate_line_item_total(
            Decimal("14"),
            Decimal("32")
        )
        assert total == Decimal("448.00")
    
    def test_sum_line_items(self):
        """Test summing line items"""
        items = [
            {"amount": Decimal("448.00")},
            {"amount": Decimal("124.03")},
            {"amount": Decimal("838.12")},
        ]
        
        total = ReconciliationEngine.sum_line_items(items)
        assert total == Decimal("1410.15")
    
    def test_reconcile_exact_match(self):
        """Test reconciliation with exact match"""
        reconciler = ReconciliationEngine()
        is_match, discrepancy, status = reconciler.reconcile(
            Decimal("1699.84"),
            Decimal("1699.84")
        )
        
        assert is_match is True
        assert discrepancy == Decimal("0.00")
        assert status == "exact_match"
    
    def test_reconcile_within_threshold(self):
        """Test reconciliation within acceptable threshold"""
        reconciler = ReconciliationEngine(threshold=0.1)  # 0.1%
        is_match, discrepancy, status = reconciler.reconcile(
            Decimal("1700.00"),
            Decimal("1700.50")
        )
        
        assert is_match is True
        assert status == "within_threshold"
    
    def test_validate_line_item_amounts(self):
        """Test validation of line item amounts"""
        reconciler = ReconciliationEngine()
        
        items = [
            {
                "item_name": "Item 1",
                "item_quantity": Decimal("14"),
                "item_rate": Decimal("32"),
                "item_amount": Decimal("448.00")
            }
        ]
        
        is_valid, errors = reconciler.validate_line_item_amounts(items)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_line_item_amounts_mismatch(self):
        """Test validation detects amount mismatches"""
        reconciler = ReconciliationEngine()
        
        items = [
            {
                "item_name": "Item 1",
                "item_quantity": Decimal("14"),
                "item_rate": Decimal("32"),
                "item_amount": Decimal("500.00")  # Should be 448
            }
        ]
        
        is_valid, errors = reconciler.validate_line_item_amounts(items)
        assert is_valid is False
        assert len(errors) > 0


class TestExtractedDataValidator:
    """Tests for ExtractedDataValidator"""
    
    def test_validate_and_clean(self):
        """Test complete validation and cleaning pipeline"""
        validator = ExtractedDataValidator()
        
        items = [
            {
                "item_name": "  Livi 300mg Tab  ",
                "item_quantity": "14",
                "item_rate": "32",
                "item_amount": "448"
            }
        ]
        
        cleaned, report = validator.validate_and_clean(items, Decimal("448"))
        
        assert len(cleaned) == 1
        assert cleaned[0]["item_name"] == "Livi 300mg Tab"
        assert cleaned[0]["item_quantity"] == Decimal("14")
        assert report["final_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
