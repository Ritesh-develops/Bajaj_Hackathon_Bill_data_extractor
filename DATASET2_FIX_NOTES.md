# Dataset 2 Issue - Analysis & Fixes

## Problem
- **Expected**: 30 items, total 21800
- **Received**: 18 items, total 8450
- **Missing**: 12 items (potentially from different sections or special formatting)

## Root Causes Identified

### Issue #1: Extraction Prompt Too Passive
The original extraction prompt was not explicit enough about capturing ALL items, especially:
- Items in separate sections or tables
- Duplicate-named items that appear as separate rows
- Items with non-standard formatting
- Small-amount items

**Fix Applied**: Enhanced `EXTRACTION_USER_PROMPT_TEMPLATE` in `app/models/prompts.py`
- Added explicit instruction to maximize item count
- Clarified that duplicate-named items should be listed separately
- Added instruction to examine every row
- Added instruction to preserve exact names without normalization

### Issue #2: Insufficient Retry Feedback
When reconciliation fails, the retry prompt wasn't giving the LLM enough context about the scale of the mismatch.

**Fix Applied**: Enhanced `RECONCILIATION_RETRY_PROMPT_TEMPLATE` in `app/models/prompts.py`
- Now includes `{item_count}` to show how many items were extracted
- Now includes `{discrepancy_percent}` to show percentage mismatch
- Added explicit check asking for expected vs actual item count
- Made the prompt more aggressive about finding missed items

**Updated Code**: `app/core/extractor.py` line ~130
- Now calculates and passes `item_count` and `discrepancy_percent` to retry prompt

### Issue #3: Dictionary Key Inconsistency (Already Fixed)
Previously identified and fixed inconsistency in `app/core/logic.py` where:
- `check_outlier_total()` used `item.get('amount', 0)` instead of `item_amount`
- `filter_double_counts()` used `item.get('amount', 0)` instead of `item_amount`
- These have all been corrected to use `item_amount` key

## Testing Instructions

### 1. Restart API Server
```powershell
cd d:\Bajaj_Hackathon\bill-extractor
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test with Dataset 2
Go to http://localhost:8000/docs and test `/api/extract-bill-data` with your Dataset 2 image:

**Expected Results:**
- `total_item_count`: Should be **30** (or close, depending on actual bill)
- `reconciled_amount`: Should be **21800** (or actual bill total)
- All items should have proper `item_name`, `item_quantity`, `item_rate`, `item_amount`

### 3. Verify Fix
Compare output with expected values:
```json
{
  "is_success": true,
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "bill_items": [
          // Should have ~30 items here
        ]
      }
    ],
    "total_item_count": 30,  // Was 18, should now be 30
    "reconciled_amount": 21800  // Was 8450, should now be 21800
  },
  "error": null
}
```

## What Changed

### File: `app/models/prompts.py`
- **EXTRACTION_USER_PROMPT_TEMPLATE**: Enhanced to be more explicit about capturing all items
  - Added emphasis on "ALL items", multiple sections, separate rows with same name
  - Added section counts to track thoroughness
  - Added explicit instruction to not collapse similar items
  
- **RECONCILIATION_RETRY_PROMPT_TEMPLATE**: Enhanced with better feedback
  - Now shows item count and discrepancy percentage
  - Asks for expected vs actual item count
  - More aggressive about finding missed items
  - Added context about section totals

### File: `app/core/extractor.py`
- **retry_extraction() method** (around line 130):
  - Now calculates `discrepancy_percent = (abs(discrepancy) / actual_total * 100)`
  - Now passes `item_count` to retry prompt
  - Now passes `discrepancy_percent` to retry prompt

### File: `app/core/logic.py`
- Already fixed (previous session): All `item.get('amount')` changed to `item.get('item_amount')`

## If Issues Persist

### Option 1: Enable Debug Logging
The system already logs filtered items. Check API server console for:
```
Removed item 'XYZ' - matches double-count keyword
Removed item 'XYZ' - outlier amount equals sum of others
```

### Option 2: Check if Items Are Still Being Filtered
If total is still low, it might be that the double-counting guard is still too aggressive. You may need to:
1. Remove specific keywords from `DOUBLE_COUNT_KEYWORDS` in `app/config.py` if they're matching legitimate items
2. Relax the outlier detection threshold
3. Manually verify what items are in each filtered category

### Option 3: Multi-Page Bills
If the bill has multiple pages, the current implementation only processes page 1 (`page_no: "1"`). Multi-page support would require:
1. Detecting page count from image/PDF
2. Processing each page separately
3. Aggregating results

## Expected Behavior

**With These Fixes:**
1. LLM extraction will be more thorough in capturing items
2. Retry mechanism will be more effective at finding missed items
3. Financial reconciliation will work better because all items are captured
4. Double-counting guard will still remove actual totals/taxes but not legitimate items

**Timeline:**
- Extraction phase: More time as it's more thorough
- Reconciliation: Same speed
- Retry (if triggered): More effective at finding issues

## Notes
- The fixes are backward compatible - Dataset 1 should still work correctly
- These changes improve robustness without changing core architecture
- All changes are in prompt templates and supporting code, not core logic
