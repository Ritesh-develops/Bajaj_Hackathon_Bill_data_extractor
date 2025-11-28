"""
Example script to test the Bill Data Extractor API

This script demonstrates how to use the API for bill extraction.
"""

import requests
import json
import time
from typing import Dict, Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{API_BASE_URL}/api/extract-bill-data"


def extract_bill(bill_url: str) -> Dict:
    """
    Extract bill data from a URL
    
    Args:
        bill_url: URL to the bill image
        
    Returns:
        API response dictionary
    """
    payload = {
        "document": bill_url
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"\n{'='*60}")
    print(f"Extracting bill from: {bill_url}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=300  # 5 minutes timeout
        )
        
        response.raise_for_status()
        result = response.json()
        
        return result
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API. Is it running?")
        print(f"   Try: python -m uvicorn app.main:app --reload")
        return {"is_success": False, "error": "Connection error"}
    
    except requests.exceptions.Timeout:
        print("❌ Error: Request timeout. Extraction took too long.")
        return {"is_success": False, "error": "Timeout"}
    
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {response.status_code}")
        print(f"   Response: {response.text}")
        return {"is_success": False, "error": str(e)}
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"is_success": False, "error": str(e)}


def print_results(response: Dict) -> None:
    """Pretty print extraction results"""
    
    if not response.get("is_success"):
        print(f"\n❌ Extraction Failed")
        print(f"Error: {response.get('error', 'Unknown error')}")
        return
    
    print(f"\n✅ Extraction Successful!")
    
    data = response.get("data", {})
    
    print(f"\n📊 Summary:")
    print(f"  Total Items: {data.get('total_item_count', 0)}")
    print(f"  Reconciled Amount: ₹{data.get('reconciled_amount', 0):,.2f}")
    
    # Print items by page
    pagewise_items = data.get("pagewise_line_items", [])
    
    for page in pagewise_items:
        page_no = page.get("page_no", "Unknown")
        items = page.get("bill_items", [])
        
        print(f"\n📄 Page {page_no}:")
        print(f"  {'-'*55}")
        print(f"  {'Item Name':<30} {'Qty':>6} {'Rate':>10} {'Amount':>8}")
        print(f"  {'-'*55}")
        
        for item in items:
            name = item.get("item_name", "")[:28]
            qty = item.get("item_quantity", 0)
            rate = item.get("item_rate", 0)
            amount = item.get("item_amount", 0)
            
            print(f"  {name:<30} {qty:>6.0f} ₹{rate:>9,.2f} ₹{amount:>7,.2f}")
        
        # Calculate and print page total
        page_total = sum(
            item.get("item_amount", 0) for item in items
        )
        print(f"  {'-'*55}")
        print(f"  {'Page Total':<30} {' ':>6} {' ':>10} ₹{page_total:>7,.2f}")


def health_check() -> bool:
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Main function"""
    
    print("\n" + "="*60)
    print("  Bill Data Extractor - API Test Script")
    print("="*60)
    
    # Check if API is running
    print("\n🔍 Checking API status...")
    if not health_check():
        print("❌ API is not running!")
        print("\n   To start the API:")
        print("   1. Activate virtual environment:")
        print("      - Windows: venv\\Scripts\\activate")
        print("      - macOS/Linux: source venv/bin/activate")
        print("\n   2. Install dependencies:")
        print("      pip install -r requirements.txt")
        print("\n   3. Configure .env with GEMINI_API_KEY")
        print("\n   4. Start API:")
        print("      python -m uvicorn app.main:app --reload")
        return
    
    print("✅ API is running!")
    
    # Test URLs
    test_bills = [
        "https://hackrx.blob.core.windows.net/assets/datathon-IIT/sample_2.png?sv=2025-07-05&spr=https&st=2025-11-24T14%3A13%3A22Z&se=2026-11-25T14%3A13%3A00Z&sr=b&sp=r&sig=WFJYfNw0PJdZOpOYlsoAW0XujYGG1x2HSbcDREiFXSU%3D"
    ]
    
    # Run extractions
    for bill_url in test_bills:
        response = extract_bill(bill_url)
        print_results(response)
        
        # Wait between requests if testing multiple
        time.sleep(2)
    
    # Display API documentation
    print(f"\n📚 API Documentation:")
    print(f"   Swagger UI: {API_BASE_URL}/docs")
    print(f"   ReDoc: {API_BASE_URL}/redoc")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
