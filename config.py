import os

# API Configuration
class APIConfig:
    # Mistral AI API
    MISTRAL_API_BASE_URL = "https://api.mistral.ai/v1"
    MISTRAL_MODEL = "mistral-large-latest"
    
    # Gemini AI API
    GEMINI_MODEL = "gemini-1.5-flash"
    
    # API Keys from environment variables (for production)
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# OCR Configuration
class OCRConfig:
    # PDF processing
    PDF_DPI = 300  # DPI for PDF to image conversion
    MAX_FILE_SIZE_MB = 200  # Maximum file size in MB
    
    # Image processing
    MAX_IMAGE_SIZE = (2048, 2048)  # Maximum image dimensions
    IMAGE_QUALITY = 95  # JPEG quality for compression
    
    # Math formula detection patterns
    MATH_PATTERNS = [
        r'\b([a-zA-Z]\w*\s*[\+\-\*/\^=]\s*[a-zA-Z0-9\+\-\*/\^=\s\(\)]+)\b',
        r'\b\d+/\d+\b',
        r'\b[a-zA-Z]\d*\^\d+\b',
        r'√\([^)]+\)|√\d+',
        r'\b(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega)\b',
        r'[∫∑∏∆∇±×÷≤≥≠≈∞]',
        r'\b[a-zA-Z]\d*[_\^][a-zA-Z0-9]+\b',
        r'\([a-zA-Z0-9\+\-\*/\^=\s]+\)'
    ]

# UI Configuration
class UIConfig:
    # App metadata
    APP_TITLE = "P_OCR PDF AI 2025"
    APP_ICON = "📄"
    PAGE_LAYOUT = "wide"
    
    # Styling
    PRIMARY_COLOR = "#667eea"
    SECONDARY_COLOR = "#764ba2"
    
    # File upload settings
    SUPPORTED_FORMATS = ['pdf', 'png', 'jpg', 'jpeg']
    MAX_DISPLAY_IMAGES = 10  # Maximum images to display in UI

# Export Configuration
class ExportConfig:
    # Word document settings
    DEFAULT_FONT = "Calibri"
    DEFAULT_FONT_SIZE = 11
    IMAGE_WIDTH_INCHES = 4
    
    # File naming
    OUTPUT_PREFIX = "OCR_Result"
    TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# Prompts for AI models
class PromptTemplates:
    GEMINI_OCR_PROMPT = """
    Trích xuất tất cả văn bản từ hình ảnh này một cách chính xác nhất. Yêu cầu đặc biệt:
    
    1. Nhận diện tất cả công thức toán học và bọc chúng bằng ${...}$
    2. Ví dụ: x^2 + y^2 = z^2 phải thành ${x^2 + y^2 = z^2}$
    3. Giữ nguyên định dạng và bố cục văn bản gốc
    4. Hỗ trợ cả tiếng Việt và tiếng Anh
    5. Không bỏ sót bất kỳ nội dung nào
    6. Đối với các ký hiệu toán học đặc biệt, sử dụng ký hiệu LaTeX phù hợp
    
    Hãy trả về văn bản đã được xử lý với tất cả công thức được bọc đúng định dạng.
    """
    
    MISTRAL_OCR_PROMPT = """
    Trích xuất tất cả văn bản từ hình ảnh này. Đặc biệt chú ý:
    - Nhận diện chính xác tất cả công thức toán học
    - Bọc mọi công thức toán học bằng ${...}$
    - Giữ nguyên định dạng và bố cục văn bản
    - Hỗ trợ tiếng Việt và tiếng Anh
    """

# Error messages
class ErrorMessages:
    API_KEY_MISSING = "API key không được cung cấp"
    FILE_TOO_LARGE = "File quá lớn. Vui lòng chọn file nhỏ hơn {max_size}MB"
    UNSUPPORTED_FORMAT = "Định dạng file không được hỗ trợ"
    PROCESSING_ERROR = "Lỗi khi xử lý file: {error}"
    API_ERROR = "Lỗi API: {error}"
    EXPORT_ERROR = "Lỗi khi xuất file: {error}"

# Success messages
class SuccessMessages:
    CONFIG_SAVED = "✅ Đã lưu cấu hình API!"
    OCR_COMPLETED = "✅ Hoàn thành OCR!"
    WORD_CREATED = "✅ File Word đã được tạo!"
    FILE_UPLOADED = "📄 File đã được upload thành công!"

# Development settings
class DevConfig:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    MOCK_API_RESPONSES = os.getenv("MOCK_API", "False").lower() == "true"
    
    # Mock responses for testing
    MOCK_OCR_RESULT = """
    Đây là văn bản mẫu được trích xuất từ OCR.
    
    Ví dụ công thức toán học: ${x^2 + y^2 = z^2}$
    
    Phương trình bậc hai: ${ax^2 + bx + c = 0}$
    
    Tích phân: ${∫f(x)dx}$
    """
