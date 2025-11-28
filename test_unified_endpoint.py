"""
Test script for unified /api/extract-bill-data endpoint
Tests both image URLs and PDF local paths
"""
import requests
import json

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/extract-bill-data"

def test_with_url(document_url):
    """Test with any URL (image or PDF)"""
    print(f"\n{'='*70}")
    print(f"Testing: {document_url}")
    print(f"{'='*70}")
    
    payload = {
        "document": document_url
    }
    
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('is_success')}")
            if data.get('is_success'):
                items = data.get('data', {}).get('pagewise_line_items', [])
                total_items = data.get('data', {}).get('total_item_count', 0)
                total_amount = data.get('data', {}).get('reconciled_amount', 0)
                
                print(f"Total Items: {total_items}")
                print(f"Total Amount: {total_amount}")
                print(f"Pages: {len(items)}")
                
                for page in items:
                    print(f"\n  Page {page.get('page_no')}: {len(page.get('bill_items', []))} items")
                    for item in page.get('bill_items', [])[:3]:  # Show first 3 items
                        print(f"    - {item.get('item_name')}: Qty={item.get('item_quantity')}, Rate={item.get('item_rate')}, Amount={item.get('item_amount')}")
                    if len(page.get('bill_items', [])) > 3:
                        print(f"    ... and {len(page.get('bill_items', [])) - 3} more items")
            else:
                print(f"Error: {data.get('error')}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    print("UNIFIED ENDPOINT TEST - /api/extract-bill-data")
    print("Supports both images and PDFs (URLs or local paths)")
    
    # Test cases - modify with your actual URLs/paths
    test_cases = [
        # IMAGE URLS (examples)
        "https://example.com/bill.jpg",
        
        # LOCAL PATHS (examples - replace with your actual paths)
        "C:\\Users\\YourName\\Downloads\\bill.pdf",
        "C:\\Users\\YourName\\Downloads\\invoice.jpg",
        
        # FILE URLS (examples)
        "file://C:/Users/YourName/Downloads/bill.pdf",
    ]
    
    print("\n⚠️  Before running:")
    print("1. Make sure the FastAPI server is running (python -m uvicorn app.main:app --port 8000)")
    print("2. Update test_cases with your actual image/PDF URLs or local paths")
    print("3. Remove the example URLs above\n")
    
    # Uncomment and add your actual test cases:
    # test_with_url("https://your-image-url.com/bill.jpg")
    # test_with_url("D:\\path\\to\\your\\bill.pdf")
    
    print("\nTo test manually, use curl:")
    print("\nFor remote image URL:")
    print('curl -X POST "http://localhost:8000/api/extract-bill-data" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d "{\\"document\\": \\"https://your-url.com/image.jpg\\"}"')
    
    print("\nFor local PDF path:")
    print('curl -X POST "http://localhost:8000/api/extract-bill-data" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d "{\\"document\\": \\"C:\\\\path\\\\to\\\\file.pdf\\"}"')
    
    print("\nFor local image path:")
    print('curl -X POST "http://localhost:8000/api/extract-bill-data" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d "{\\"document\\": \\"D:\\\\path\\\\to\\\\image.jpg\\"}"')
