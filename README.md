# 📄 PDF/Ảnh ➜ Word/LaTeX (GPT-4o + PyMuPDF)

Ứng dụng Streamlit chuyển đổi đề PDF hoặc ảnh thành định dạng LaTeX hoặc Word sử dụng GPT-4o (qua AI.VN), hoạt động tốt trên **Streamlit Cloud** nhờ dùng `PyMuPDF` (không cần Poppler).

## 🚀 Tính năng
- Hỗ trợ PDF hoặc ảnh
- Tách trang PDF thành ảnh bằng `fitz` (PyMuPDF)
- OCR nội dung bằng `pytesseract`
- Gửi văn bản + ảnh lên GPT-4o để xử lý định dạng

## 🔧 Cài đặt
```bash
pip install -r requirements.txt
streamlit run app.py
```

## ☁️ Hỗ trợ deploy trên:
- Streamlit Cloud (không cần poppler)
- Replit, Fly.io, Render...

## 📌 Ghi chú
- Cập nhật API key GPT-4o trong `utils.py`
