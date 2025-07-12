import requests
import base64
import time

class EnhancedSmartOCRClient:
    def __init__(self, api_url, api_key, timeout=120, max_retries=3):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def convert(self, file_bytes, file_name, mime_type, options=None):
        if options is None:
            options = {}
        file_data = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode()}"
        payload = {
            "endpoint": "convert",
            "apiKey": self.api_key,
            "file_data": file_data,
            "file_name": file_name,
            "options": {
                "language": options.get("language", "auto"),
                "include_page_numbers": options.get("includePageNumbers", True),
                "include_images": True,
                "custom_prompt": options.get("customPrompt", ""),
                "output_format": options.get("outputFormat", "text"),
            },
            "metadata": {
                "client_version": "3.0",
                "processing_started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "client_request_id": f"req_{int(time.time()*1000)}"
            }
        }
        for retry in range(self.max_retries):
            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if retry < self.max_retries - 1:
                    time.sleep(2 ** retry)
                else:
                    raise e
