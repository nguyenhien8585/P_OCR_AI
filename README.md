# 📄 PDF/Ảnh ➜ Word/LaTeX (GPT-4o)

Ứng dụng Streamlit chuyển đổi đề PDF hoặc ảnh thành định dạng LaTeX hoặc Word sử dụng GPT-4o (qua AI.VN).

## 🚀 Tính năng
- Tải lên PDF hoặc ảnh JPEG/PNG
- Tách từng trang PDF thành ảnh
- OCR văn bản (hỗ trợ tiếng Việt)
- Gửi nội dung và ảnh lên GPT-4o để xử lý thông minh
- Xuất ra nội dung định dạng LaTeX hoặc Word

## 🔧 Cài đặt
```bash
git clone https://github.com/ban-user/pdf2latex-gpt4o-app
cd pdf2latex-gpt4o-app
pip install -r requirements.txt
streamlit run app.py
```

## 🧠 Sử dụng GPT-4o AI.VN
Tạo tài khoản tại: https://ai.vn  
Cập nhật API key và `openai.api_base` trong `utils.py`

## 📦 Triển khai trên Streamlit Cloud
- Tạo repo GitHub chứa mã này
- Deploy tại https://streamlit.io/cloud
