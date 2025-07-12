import streamlit as st
from ocr_client import SmartOCRClient
import base64

# ================== CONFIG ==================
API_URL = "https://script.google.com/macros/s/AKfycby6GUWKFttjWTDJuQuX5IAeGAzS5tQULLja3SHbSfZIhQyaWVMuxyRNAE-fykxnznkqIw/exec"
API_KEY = "sk_nguyenhien21022020_pro_mcwzovbjz11wklh8zk"  # Thay bằng key thực tế
WEBHOOK_URL = ""             # Có thể thêm nếu cần

client = SmartOCRClient(API_URL, API_KEY, WEBHOOK_URL)

# ================== UI ======================
st.title("SMART OCR Client v3.0 (Python + Streamlit)")
st.write("Chuyển ảnh/PDF sang text và tự động tách ảnh (base64)")

st.sidebar.header("Account & Usage")
if st.sidebar.button("Get account info"):
    st.json(client.get_account())
if st.sidebar.button("Get usage (month)"):
    st.json(client.get_usage("month"))

st.header("1️⃣ Upload file để OCR và tách ảnh")

uploaded_file = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "jpg", "jpeg", "png"])
if uploaded_file:
    file_bytes = uploaded_file.read()
    mime_type = uploaded_file.type
    file_name = uploaded_file.name

    with st.spinner("Đang nhận diện OCR..."):
        ocr_result = client.convert(file_bytes, file_name, mime_type)

    st.subheader("Kết quả nhận diện văn bản:")
    st.text_area("Text content", ocr_result.get("data", {}).get("text_content", ""), height=300)

    st.subheader("Thông tin tài liệu:")
    st.json(ocr_result.get("data", {}))

    # ========== Tách ảnh dưới dạng base64 ==========
    images = []
    data = ocr_result.get("data", {})
    # Giả định kết quả trả về có trường images là mảng base64 (bổ sung endpoint nếu cần)
    if "images" in data and data["images"]:
        st.subheader("Ảnh minh họa tách ra từ file:")
        for idx, img_b64 in enumerate(data["images"], 1):
            st.image(img_b64, caption=f"Image {idx}", use_column_width=True)
            # Cho phép tải ảnh
            href = f'<a href="data:image/png;base64,{img_b64}" download="image{idx}.png">Tải ảnh {idx}</a>'
            st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("Không tìm thấy ảnh minh họa trong file này hoặc API chưa hỗ trợ tách ảnh.")

    st.success("Hoàn thành xử lý!")
