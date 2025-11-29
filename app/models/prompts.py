EXTRACTION_SYSTEM_PROMPT = """You are a bill extraction expert. Extract line items (products/services only, NOT totals/taxes).

RULES:
1. Extract: item_name, quantity, rate (unit price), amount (total)
2. IGNORE: "Total", "Subtotal", "Tax", "GST", "VAT", "Discount", "Carry Forward"
3. Be precise with numbers, preserve decimal places
4. For handwritten: do your best, set confidence lower
5. Return valid JSON only"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract line items from this bill. Return ONLY this JSON:

{{
    "extraction_reasoning": "Brief explanation",
    "line_items": [
        {{"item_name": "name", "quantity": 1, "rate": 0, "amount": 100}}
    ],
    "bill_total": 1000,
    "subtotals": [],
    "notes": ""
}}

Rules:
- Extract product/service lines only, skip totals/taxes/discounts
- For each item: name, qty (1 if missing), rate, amount
- If rate unclear, use amount value
- Handwritten OK, do your best
- Return valid JSON"""

RECONCILIATION_RETRY_PROMPT_TEMPLATE = """Extracted {item_count} items. Sum: {calculated_total}, Bill total: {actual_total}, Mismatch: {discrepancy}

Items:
{extracted_items}

Check the image again. Did I miss items or misread numbers? Return JSON:

{{
    "analysis": "What you found",
    "corrections": [
        {{"action": "add|remove|modify", "item_name": "name", "quantity": 1, "rate": 0, "amount": 100}}
    ],
    "new_total": 0,
    "confidence": 0.9
}}"""

VALIDATION_PROMPT_TEMPLATE = """Review this bill extraction for accuracy:

Extracted Items:
{items_json}

Bill Total: {bill_total}
Calculated Total: {calculated_total}
Match: {matches}

Please verify:
1. All line items are actual products/services (not taxes, fees, or totals)
2. No duplicate items
3. All amounts are correct (quantity × rate = amount)
4. The sum matches the bill total

Respond with:
{{
    "is_valid": true/false,
    "issues": ["list of any issues found"],
    "corrections": ["list of corrections needed"],
    "confidence": 0-1
}}"""
