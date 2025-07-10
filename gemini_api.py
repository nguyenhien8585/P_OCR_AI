import requests
import base64
from dotenv import load_dotenv
import os
from PIL import Image
from io import BytesIO

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def extract_content_with_gemini(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": "Extract text and layout (including math, titles, captions, and figure references) for Word/LaTeX export."},
                {"inline_data": {
                    "mime_type": "image/png",
                    "data": img_b64
                }}
            ]
        }]
    }

    response = requests.post(
        f"{ENDPOINT}?key={API_KEY}",
        json=payload
    )
    result = response.json()
    try:
        return result['candidates'][0]['content']['parts'][0]['text']
    except:
        return "[Error] Could not extract content."
