import streamlit as st
from PIL import Image
import io
import base64
import requests

# Prompt sinh theo chế độ
def getPrompt(mode):
    if mode == "latex":
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:

QUY TẮC ĐỊNH DẠNG VĂN BẢN VÀ CÔNG THỨC:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'): 
   - Thay 'Câu X:' bằng \\begin{ex}
   - Thêm \\choice trước phương án A
   - Đặt mỗi phương án trong cặp dấy {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
   - Kết thúc bằng \\end{ex}

2. Với câu hỏi trắc nghiệm có lời giải:
   - Thêm \\True trước phương án đúng
   - Đặt lời giải trong \\loigiai{}

3. Với bài tập tự luận (bắt đầu bằng 'Bài X:' hoặc 'Bài X.'):
   - Thay 'Bài X:' bằng \\begin{bt}
   - Đặt lời giải trong \\loigiai{}
   - Kết thúc bằng \\end{bt}

4. Với danh sách (a), b), c)...):
   - Bọc trong \\begin{enumerate} và \\end{enumerate}
   - Thay mỗi chữ cái bằng \\item

5. Công thức toán học: Giữ nguyên định dạng LaTeX như $...$ hoặc $$...$$

KHÔNG thêm giải thích hay bình luận gì thêm. Trả về văn bản đã được định dạng LaTeX."""
    else:
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.

YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng \${...}\$
   - Inline: \${x^2 + 2x + 1}\$
   - Hệ: \$\\begin{cases} ... \\end{cases}\$
   - Ký hiệu: ví dụ \${Oxyz}\$, \${A}\$, \${AB}\$, \${0{,}1\%}\$, \${CD}\$, \${1}\$,.....

4. Với bảng biểu: dùng markdown nếu có thể
5. Dạng bài:
   - Trắc nghiệm:
     Câu X: Nội dung
     A. Đáp án A
     B. Đáp án B
     C. Đáp án C
     D. Đáp án D
   - Đúng/Sai: a), b), c)...
   - Tự luận: Câu X: ... (Lời giải...)

✅ Gợi ý thêm:
- Nếu ảnh dài hoặc nhiều trang, chia nhỏ xử lý từng ảnh để tránh thiếu trang.
- Khi lưu kết quả, nên xuất file Word định dạng .docx để hiển thị tiếng Việt chuẩn và hỗ trợ tốt Unicode.

KHÔNG giải thích. KHÔNG bịa thêm. Trả về văn bản gốc."""

# Gọi API AI.VN
def call_ai_vn_api(image: Image.Image, prompt: str, api_key: str):
    # Chuyển ảnh thành base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    url = "https://api.sv2.llm.ai.vn/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "openai:gpt-4o",
        "messages": [
            {"role": "system", "content": "Bạn là công cụ OCR thông minh chuyên chuyển ảnh thành văn bản hoặc LaTeX."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Lỗi API: {response.status_code} - {response.text}")

# === Streamlit App ===
st.set_page_config(page_title="PDF to LaTeX/Word", layout="centered")
st.title("📄 Chuyển ảnh đề sang LaTeX / Word bằng GPT-4o AI.VN")

# Nhập API key
api_key = st.text_input("🔐 Nhập API Key từ AI.VN:", type="password")

# Chọn chế độ xử lý
mode = st.radio("🎯 Chế độ chuyển đổi:", ["latex", "word"], format_func=lambda m: "LaTeX (soạn đề)" if m == "latex" else "Word (giữ nguyên gốc)")

# Tải ảnh
uploaded_image = st.file_uploader("🖼️ Tải ảnh PNG/JPG/JPEG", type=["png", "jpg", "jpeg"])

if uploaded_image and api_key:
    image = Image.open(uploaded_image)
    st.image(image, caption="Ảnh đã tải lên", use_column_width=True)

    if st.button("🚀 Bắt đầu chuyển đổi"):
        with st.spinner("⏳ Đang xử lý bằng GPT-4o từ AI.VN..."):
            try:
                result = call_ai_vn_api(image, getPrompt(mode), api_key)
                st.success("✅ Hoàn tất!")
                st.code(result, language="latex" if mode == "latex" else "text")
                st.download_button("📥 Tải kết quả", result, file_name=f"output.{ 'tex' if mode == 'latex' else 'txt'}", mime="text/plain")
            except Exception as e:
                st.error(f"❌ Đã xảy ra lỗi: {e}")
