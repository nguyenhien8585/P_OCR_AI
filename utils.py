import pytesseract
import openai
import base64
import io

openai.api_key = "YOUR_API_KEY"
openai.api_base = "https://api.sv2.llm.ai.vn/v1"  # hoặc bỏ /v1 nếu không tương thích

def extract_text_ocr(image):
    return pytesseract.image_to_string(image, lang="vie+eng")

def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def call_gpt4o_ai_vn(image, raw_text):
    b64_image = encode_image(image)
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý chuyên phân tích đề thi và xuất ra định dạng LaTeX/Word."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Nội dung OCR:
{raw_text}
Hãy chuyển sang LaTeX chuẩn kèm hướng dẫn chèn ảnh."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }
        ],
        temperature=0.2
    )
    return response.choices[0].message.content
