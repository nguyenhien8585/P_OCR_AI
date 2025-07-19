# config.py - Cấu hình API endpoints

# API cho OCR client hiện tại (nếu vẫn dùng)
API_URL = "https://your-current-ocr-api.com"
API_KEY = "your-current-ocr-api-key"

# Mistral API configuration
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

# Mistral API Keys (thay bằng keys thật)
MISTRAL_API_KEYS = [
    "3OLLsQhSn7SFx4kBzEjeRJ7S4MikrdcO"
]

# Timeout settings
REQUEST_TIMEOUT = 120
MAX_RETRIES = 3

# Image processing settings
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
SUPPORTED_FORMATS = ["png", "jpg", "jpeg", "webp"]

# OCR settings
MAX_TOKENS = 4000
TEMPERATURE = 0.1
