import os
from dotenv import load_dotenv

load_dotenv()

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", 20 * 1024 * 1024))  # 20MB
TARGET_DPI = int(os.getenv("TARGET_DPI", 300))
MIN_RESOLUTION = int(os.getenv("MIN_RESOLUTION", 800))

RECONCILIATION_THRESHOLD = float(os.getenv("RECONCILIATION_THRESHOLD", 0.01))  # 0.01%
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", 3))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

DOUBLE_COUNT_KEYWORDS = {
    "total", "subtotal", "vat", "tax", "amount due", 
    "carry forward", "gst", "sgst", "cgst", "igst", 
    "discount", "fee", "charge", "shipping", "grand total"
}
