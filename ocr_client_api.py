import requests
import base64
import time

class EnhancedSmartOCRClient:
    def __init__(self, api_url, api_key, timeout=120, max_retries=3, retry_delay_base=1):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base

    def convert(self, file_bytes, file_name, mime_type, options=None):
        """Gửi file tới OCR API và trả về kết quả nhận diện."""
        if options is None:
            options = {}
        # Convert file thành base64
        base64_bytes = base64.b64encode(file_bytes).decode("utf-8")
        base64_data = f'data:{mime_type};base64,{base64_bytes}'
        payload = {
            "endpoint": "convert",
            "apiKey": self.api_key,
            "file_data": base64_data,
            "file_name": file_name or "document",
            "options": {
                "language": options.get("language", "auto"),
                "include_page_numbers": options.get("includePageNumbers", True),
                "include_images": options.get("includeImages", False),
                "custom_prompt": options.get("customPrompt", ""),
                "output_format": options.get("outputFormat", "text")
            },
            "metadata": {
                "client_version": "3.0",
                "processing_started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "client_request_id": "req_" + str(int(time.time()*1000))
            }
        }
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(self.api_url, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    return response.json()
                else:
                    # Có thể thêm logging hoặc xử lý HTTP error ở đây nếu cần
                    err = f"HTTP {response.status_code}: {response.text}"
                    if attempt == self.max_retries:
                        return {"success": False, "error": err}
            except Exception as ex:
                if attempt == self.max_retries:
                    return {"success": False, "error": str(ex)}
            # Retry sau delay tăng dần
            time.sleep(self.retry_delay_base * attempt)
        # Nếu tới đây thì thất bại toàn bộ retry
        return {"success": False, "error": "OCR API failed after retries"}

    def getAccount(self):
        payload = {"endpoint": "account", "apiKey": self.api_key}
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            return response.json()
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    def getStatus(self):
        payload = {"endpoint": "status"}
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            return response.json()
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    def getUsage(self, period="month"):
        payload = {"endpoint": "usage", "apiKey": self.api_key, "period": period}
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            return response.json()
        except Exception as ex:
            return {"success": False, "error": str(ex)}
