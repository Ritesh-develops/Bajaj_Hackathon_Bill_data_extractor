EXTRACTION_SYSTEM_PROMPT = """You are a bill extraction expert. Extract line items (products/services only, NOT totals/taxes).

CRITICAL JSON RULES:
1. Use double quotes ONLY
2. NO quotes inside item_name - replace with apostrophe or remove
3. NO newlines inside strings - use spaces instead
4. NO trailing commas before ] or }
5. Return ONLY valid parseable JSON

EXTRACTION RULES:
1. Extract: item_name, quantity, rate (unit price), amount (total)
2. IGNORE: "Total", "Subtotal", "Tax", "GST", "VAT", "Discount", "Carry Forward"
3. Be precise with numbers, preserve decimal places
4. For handwritten: do your best"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Extract line items from this bill. 

CRITICAL: Return ONLY valid JSON. If item name contains quotes, replace with apostrophe or space.

{{
    "extraction_reasoning": "Brief explanation",
    "line_items": [
        {{"item_name": "Product Name", "quantity": 1, "rate": 10.5, "amount": 10.5}}
    ],
    "bill_total": 1000,
    "subtotals": [],
    "notes": ""
}}

FORMATTING RULES:
- item_name: NO quotes inside - use spaces/apostrophes instead
- NO newlines in any string value
- Numbers only for quantity, rate, amount
- Valid JSON structure REQUIRED

Content Rules:
- Extract product/service lines only, skip totals/taxes/discounts
- For each item: name, qty (1 if missing), rate, amount
- If rate unclear, use amount value
- Handwritten OK, do your best
- Return ONLY the JSON object, no extra text"""

RECONCILIATION_RETRY_PROMPT_TEMPLATE = """Extracted {item_count} items. Sum: {calculated_total}, Bill total: {actual_total}, Mismatch: {discrepancy}

Items:
{extracted_items}

Check the image again. Did I miss items or misread numbers? Return ONLY this JSON with proper escaping:

{{
    "analysis": "What you found",
    "corrections": [
        {{"action": "add|remove|modify", "item_name": "name", "quantity": 1, "rate": 0, "amount": 100}}
    ],
    "new_total": 0,
    "confidence": 0.9
}}

CRITICAL FORMATTING RULES:
- ESCAPE any quotes in item names: use \\" instead of "
- NO newlines inside string values - keep everything on one line
- NO unescaped special characters - properly escape all quotes
- Each object must be valid JSON on its own
- Return ONLY the JSON object, no extra text"""

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
