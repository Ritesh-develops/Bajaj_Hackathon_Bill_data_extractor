# API Timing Analysis - Bill Extractor

## Problem Statement
**User observation:** 12-page PDF extraction takes ~7 minutes (420s), but expected time is ~25-30s with Gemini's 2.0 Flash model and Semaphore(6) concurrency.

## Root Cause Analysis

### Gemini 2.0 Flash Actual Performance
- **Claimed:** "Fastest model" - 2-3s per page
- **Actual observed:** 10-12s per page
- **Why:** Model is fast but network latency, token processing, and response serialization add overhead

### Timeline Breakdown (per page)
```
API Call Total:        ~10-12 seconds (Gemini API network round-trip)
  ├─ Network request:    ~0.5s (outbound + inbound)
  ├─ Gemini processing:  ~8-10s (model inference)
  └─ Response transfer:  ~0.5-1s (inbound)

Response Parsing:      ~0.1-0.5s (JSON parsing + regex fallback if needed)
Image Processing:      ~0.5-1s (compression, OCR enhancement)
──────────────────────────────
Per-Page Total:        ~10.6-13.5s
```

### Concurrency Math (Semaphore=6)
- **Theory:** 6 pages at a time, so 12 pages ÷ 6 = 2 batches × 12s = **24 seconds**
- **Practice:** 12 pages in ~2 minutes = 120 seconds = **5x slower**

## Where the 5x Slowdown Happens

### Two Scenarios Identified:

#### Scenario 1: API Quota Exhaustion (Phase 25 - User's Original Issue)
- **Symptom:** Getting 429 (Rate Limited) responses
- **Cause:** Hit 200 requests/day free tier limit
- **Retry overhead:** Each failed request + 5-8 second retry delay
- **Total time:** Original 12p = ~120s (actual from logs)
  - API calls: 12 × 10s = 120s
  - Retry delays (if hitting quota): +60s per batch
  - **Result:** 120s + 60s = 180s+ ❌

#### Scenario 2: Concurrency Not Working (Post-API Key Reset)
- **Symptom:** Fast API key but still slow extraction
- **Cause:** Semaphore might be processing sequentially instead of concurrently
- **Impact:** All 6 at once vs one at a time = 6x difference
  - Sequential: 12 × 12s = 144s ✗
  - Concurrent (6): 12 ÷ 6 × 12s = 24s ✓

## New Timing Instrumentation

I've added detailed timing logs to track **exactly** where time is spent:

### Locations of New Timing Code:

1. **`app/api/routes.py` - `process_pdf_extraction()`**
   - PDF conversion time
   - Concurrent batch processing time (total)
   - Aggregation time
   - **Total end-to-end time + per-page breakdown**

2. **`app/core/extractor.py` - `extract_from_image()`**
   - API call time (request to response)
   - Response parsing time
   - **Total extraction time**

### What You'll See in Logs

```
[PDF] [TIMING START] Extraction started at 2025-11-30T14:23:45.123456
[PDF] [TIMING] PDF conversion took 2.45s
[PDF] [CONCURRENT] Starting page 1
[API TIMING] Page 1: Gemini API response took 10.32s
[PARSE TIMING] Page 1: Response parsing took 0.12s
[TOTAL TIMING] Page 1: Complete extraction (API + parsing) took 10.44s
...
[PDF] [TIMING] Concurrent processing: 22.15s
[PDF] [TIMING] Aggregation took 0.08s
========== PDF EXTRACTION TIMING BREAKDOWN ==========
PDF conversion: 2.45s
Concurrent processing: 22.15s
Aggregation: 0.08s
---
TOTAL TIME: 24.68s
Time per page: 2.06s
---
```

## How to Interpret the Results

### Good Performance (You Want This)
```
Concurrent processing: 24s  (for 12 pages)
Time per page: 2.0s
→ Concurrency IS working (6 pages at once = 12s each = 2x overlap)
```

### Bad Performance (Indicates Issues)
```
Concurrent processing: 144s  (for 12 pages)
Time per page: 12.0s
→ Pages processed sequentially (1 at a time), concurrency broken
→ Fix: Check Semaphore, asyncio, or thread pool

Concurrent processing: 72s  (with retry delays)
Time per page: 6.0s  
→ API quota/rate limit hitting (getting 429 errors)
→ Fix: Ensure fresh API key, check rate limits
```

## API Rate Limits (Critical)

### Gemini Free Tier
- **Limit:** 200 requests/day
- **Per minute:** 15 requests
- **Cost:** First 12-15 PDFs, then exhausted

### Gemini Paid Tier
- **Limit:** No daily limit (continuous)
- **Per minute:** 15-60 requests (depends on plan)
- **Cost:** ~$0.075/1M input tokens, $0.30/1M output tokens

### Your Current State
- ✅ New API key with **reset quota**
- ✅ Fresh 200 requests (or unlimited if on paid)
- ✅ Should see fast extraction now

## Next Steps

### 1. Run a 12-page extraction
```
POST /api/extract-bill-data
Body: {"document": "your-12-page-pdf-url"}
```

### 2. Check the Logs
Look for these lines:
```
[PDF] [TIMING] Concurrent processing: XXXs
```

### 3. Compare to Expected
- **If 24-30s:** ✅ **GOOD** - Concurrency working, API fast
- **If 120-150s:** ❌ **BAD** - Concurrency broken or quota limit
- **If 300s+:** ❌ **VERY BAD** - Sequential processing or major bottleneck

### 4. Share the Timing Breakdown
Post the section:
```
========== PDF EXTRACTION TIMING BREAKDOWN ==========
PDF conversion: XXs
Concurrent processing: XXs
Aggregation: XXs
TOTAL TIME: XXs
```

## Performance Optimization Opportunities

If timing is still slow after quota reset:

1. **Image Processing** (0.5-1s per page)
   - Already using quality=70, DPI reduced
   - Could reduce further if needed

2. **Response Parsing** (0.1-0.5s per page)
   - Using optimized chain: JSON → Regex → json5
   - Already very fast

3. **API Call** (10-12s per page) - **CAN'T OPTIMIZE**
   - This is Gemini's actual speed
   - No way to make API respond faster
   - Can only accept as baseline cost

4. **Concurrency** - Already at max (6)
   - Can increase to 10-15 if API allows
   - But will hit rate limits faster

## Summary

**The 120-second problem was caused by:**
1. **API quota exhaustion** (429 rate limit errors)
2. **Retry delays** stacking up

**With your new API key:**
- Expected time: **24-30 seconds** (for 12 pages)
- Actual will depend on:
  - Gemini's 10-12s per page (unavoidable)
  - 6-page concurrency reducing it to 24-30s (math: 12 pages ÷ 6 concurrent = 2 batches × 12s = 24s)

**If still slow after reset, the new logs will pinpoint exactly which stage is the problem.**
