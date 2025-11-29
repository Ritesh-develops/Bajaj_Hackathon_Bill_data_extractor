EXTRACTION_SYSTEM_PROMPT = """You are a precise bill extraction expert. Extract ONLY product/service line items.

JSON FORMAT RULES:
1. Valid JSON only - double quotes, no trailing commas, no newlines in strings
2. Replace quotes in names with apostrophe: "John's" not "John\"s"
3. Numbers precise with decimals preserved

EXTRACTION RULES:
1. Extract fields: item_name, quantity, rate, amount
2. Skip: totals, taxes, discounts, fees, GST, VAT, shipping, "carry forward", subtotals
3. Quantity defaults to 1 if missing/unclear
4. Amount = quantity × rate (verify math)
5. Return ONLY the JSON response, no explanations"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract line items from bill image. Return ONLY valid JSON.

{{
    "line_items": [
        {{"item_name": "Product", "quantity": 1, "rate": 10.50, "amount": 10.50}}
    ],
    "bill_total": 1000.00,
    "notes": ""
}}

RULES:
- item_name: product/service names only, no quotes inside
- quantity: number (default 1), rate: unit price, amount: line total
- Skip: totals, taxes, discounts, fees
- JSON valid, no extra text"""

RECONCILIATION_RETRY_PROMPT_TEMPLATE = """Verify extraction. Sum: {calculated_total}, Bill total: {actual_total}.

Items: {extracted_items}

Review & correct:
1. Missing items?
2. Wrong quantities/rates/amounts?
3. Included non-items (taxes/totals)?

{{
    "corrections": [
        {{"action": "add|remove|modify", "item_name": "name", "quantity": 1, "rate": 0, "amount": 100}}
    ],
    "new_total": 0
}}

JSON only, no extra text."""

VALIDATION_PROMPT_TEMPLATE = """Validate extraction. Items: {items_json}
Bill total: {bill_total}, Calculated: {calculated_total}, Match: {matches}

Verify:
1. All items are products/services (skip taxes/totals)
2. No duplicates
3. amounts correct (qty × rate = amount)

{{
    "is_valid": true,
    "issues": [],
    "confidence": 0.95
}}

JSON only."""
