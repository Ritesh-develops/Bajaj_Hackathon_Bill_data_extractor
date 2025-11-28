"""
Test script for Google Drive link handling
"""
import requests
import json

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/extract-bill-data"

def test_google_drive_link():
    """Test with Google Drive link"""
    print("Testing Google Drive Link Conversion...")
    print("="*70)
    
    # The link from your request
    google_drive_link = "https://drive.google.com/file/d/1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA/view?usp=drive_link"
    
    payload = {
        "document": google_drive_link
    }
    
    print(f"Original Link: {google_drive_link}")
    print(f"Expected Direct URL: https://drive.google.com/uc?export=download&id=1AZY6MzGpoe4hP6-yDgvdYuiuNTnCtMZA")
    print()
    
    try:
        print("Sending request...")
        response = requests.post(ENDPOINT, json=payload, timeout=120)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    print("GOOGLE DRIVE LINK TEST")
    print("Make sure the server is running: python -m uvicorn app.main:app --port 8000")
    print()
    
    test_google_drive_link()
