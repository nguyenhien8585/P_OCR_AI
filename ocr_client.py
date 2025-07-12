import requests
import base64
import time

class SmartOCRClient:
    def __init__(self, api_url, api_key, webhook_url=None, timeout=120, max_retries=3):
        self.api_url = api_url
        self.api_key = api_key
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = max_retries

    def _request(self, payload, retries=0):
        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if retries < self.max_retries:
                time.sleep(2 ** retries)
                return self._request(payload, retries + 1)
            raise e

    def get_account(self):
        payload = {"endpoint": "account", "apiKey": self.api_key}
        return self._request(payload)

    def get_usage(self, period="month"):
        payload = {"endpoint": "usage", "apiKey": self.api_key, "period": period}
        return self._request(payload)

    def get_status(self):
        payload = {"endpoint": "status"}
        return self._request(payload)

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
                "include_images": True,         # Bắt buộc tách ảnh
                "custom_prompt": options.get("customPrompt", ""),
                "output_format": options.get("outputFormat", "text"),
            },
            "metadata": {
                "client_version": "3.0",
                "processing_started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "client_request_id": f"req_{int(time.time()*1000)}"
            }
        }
        return self._request(payload)
