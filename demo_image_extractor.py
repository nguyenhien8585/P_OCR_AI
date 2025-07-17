import streamlit as st
from PIL import Image
import io
from image_extractor import ImageExtractor

# Cấu hình trang
st.set_page_config(
    page_title="Demo Tách Ảnh & Chèn Đúng Vị Trí",
    page_icon="🖼️",
    layout="wide"
)

st.title("🖼️ Demo: Tách Ảnh và Chèn Đúng Vị Trí")
st.markdown("Ứng dụng demo để hiểu cách hoạt động của ImageExtractor")

# Khởi tạo
if 'extractor' not in st.session_state:
    st.session_state.extractor = ImageExtractor()

# Sidebar để cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình")
    
    # Tùy chỉnh tham số
    min_area_ratio = st.slider("Diện tích tối thiểu (%)", 0.1, 5.0, 0.8, 0.1) / 100
    min_width = st.slider("Chiều rộng tối thiểu (px)", 30, 200, 70, 10)
    min_height = st.slider("Chiều cao tối thiểu (px)", 30, 200, 70, 10)
    max_figures = st.slider("Số ảnh tối đa", 1, 20, 8, 1)
    
    # Cập nhật tham số
    st.session_state.extractor.min_area_ratio = min_area_ratio
    st.session_state.extractor.min_width = min_width
    st.session_state.extractor.min_height = min_height
    st.session_state.extractor.max_figures = max_figures
    
    st.markdown("---")
    st.markdown("### 📋 Hướng dẫn:")
    st.markdown("""
    1. Upload ảnh chứa hình/bảng
    2. Nhập văn bản có từ khóa
    3. Xem kết quả tách ảnh
    4. Xem văn bản đã chèn ảnh
    """)

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📤 Input")
    
    # Upload ảnh
    uploaded_file = st.file_uploader(
        "Chọn ảnh chứa hình/bảng:",
        type=['png', 'jpg', 'jpeg'],
        help="Ảnh nên chứa các hình minh họa hoặc bảng số liệu"
    )
    
    # Văn bản mẫu
    sample_text = """Câu 1. Cho hàm số y = x² + 2x + 1. Hãy vẽ đồ thị hàm số.

Xem bảng giá trị sau đây để tính toán:

Câu 2. Tính giá trị của biểu thức theo hình vẽ bên dưới.

Dựa vào biểu đồ thống kê, hãy trả lời câu hỏi.

Câu 3. Quan sát hình minh họa và cho biết kết quả."""
    
    # Input văn bản
    input_text = st.text_area(
        "Nhập văn bản có từ khóa:",
        value=sample_text,
        height=300,
        help="Văn bản nên có các từ khóa như: hình, bảng, đồ thị, biểu đồ, minh họa..."
    )

with col2:
    st.header("📤 Output")
    
    if uploaded_file:
        # Hiển thị ảnh gốc
        image = Image.open(uploaded_file)
        st.subheader("🖼️ Ảnh gốc:")
        st.image(image, caption="Ảnh đã upload", use_column_width=True)
        
        # Xử lý khi click button
        if st.button("🚀 Tách ảnh và chèn vào văn bản", type="primary"):
            with st.spinner("Đang xử lý..."):
                # Đọc ảnh
                image_bytes = uploaded_file.getvalue()
                
                # Tách ảnh
                figures, h, w = st.session_state.extractor.extract_figures_and_tables(image_bytes)
                
                # Chèn vào văn bản
                result_text = st.session_state.extractor.insert_figures_into_text(
                    input_text, figures, h, w
                )
                
                # Lưu kết quả
                st.session_state.figures = figures
                st.session_state.result_text = result_text
                st.session_state.original_size = (w, h)

# Hiển thị kết quả
if 'figures' in st.session_state:
    st.markdown("---")
    st.header("📊 Kết quả")
    
    # Tabs cho kết quả
    tab1, tab2, tab3 = st.tabs(["📝 Văn bản đã chèn", "🖼️ Ảnh đã tách", "📊 Thống kê"])
    
    with tab1:
        st.subheader("📝 Văn bản sau khi chèn ảnh/bảng:")
        st.code(st.session_state.result_text, language="markdown")
        
        # Download
        st.download_button(
            "📄 Tải văn bản (.txt)",
            st.session_state.result_text,
            file_name="result_text.txt",
            mime="text/plain"
        )
    
    with tab2:
        st.subheader("🖼️ Các ảnh/bảng đã tách:")
        
        figures = st.session_state.figures
        if figures:
            cols = st.columns(2)
            for i, fig in enumerate(figures):
                with cols[i % 2]:
                    # Decode base64
                    import base64
                    img_bytes = base64.b64decode(fig['base64'])
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    # Hiển thị
                    fig_type = "📊 Bảng" if fig['is_table'] else "🖼️ Hình"
                    st.write(f"**{fig_type}: {fig['name']}**")
                    st.image(img, caption=f"Vị trí: {fig['bbox']}", use_column_width=True)
                    
                    # Download
                    st.download_button(
                        f"📥 Tải {fig['name']}",
                        img_bytes,
                        file_name=fig['name'],
                        mime="image/jpeg",
                        key=f"download_{i}"
                    )
        else:
            st.info("Không tìm thấy ảnh/bảng nào trong ảnh gốc")
    
    with tab3:
        st.subheader("📊 Thống kê chi tiết:")
        
        figures = st.session_state.figures
        w, h = st.session_state.original_size
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Tổng số ảnh", len(figures))
        
        with col2:
            tables = sum(1 for fig in figures if fig['is_table'])
            st.metric("📋 Số bảng", tables)
        
        with col3:
            images = sum(1 for fig in figures if not fig['is_table'])
            st.metric("🖼️ Số hình", images)
        
        with col4:
            st.metric("📐 Kích thước gốc", f"{w}x{h}")
        
        # Chi tiết từng ảnh
        if figures:
            st.subheader("📋 Chi tiết từng ảnh:")
            for i, fig in enumerate(figures):
                x, y, ww, hh = fig['bbox']
                area = ww * hh
                area_percent = (area / (w * h)) * 100
                
                with st.expander(f"{fig['name']} - {'Bảng' if fig['is_table'] else 'Hình'}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Vị trí:** ({x}, {y})")
                        st.write(f"**Kích thước:** {ww} x {hh}")
                    
                    with col2:
                        st.write(f"**Diện tích:** {area:,} pixels")
                        st.write(f"**% ảnh gốc:** {area_percent:.2f}%")

# Footer
st.markdown("---")
st.markdown("""
### 💡 Giải thích thuật toán:

1. **Tiền xử lý ảnh**: Chuyển sang ảnh xám, làm mờ, tăng độ tương phản
2. **Tạo ảnh nhị phân**: Phân ngưỡng adaptive để tách nền và đối tượng  
3. **Tìm contour**: Phát hiện các đường viền của hình/bảng
4. **Lọc theo tiêu chí**: Diện tích, tỷ lệ, vị trí, độ đặc
5. **Phân loại**: Phân biệt hình và bảng dựa trên tỷ lệ khung hình
6. **Chèn vào văn bản**: Dựa trên từ khóa và vị trí trong văn bản

### 🎯 Từ khóa nhận diện:
- **Bảng**: "bảng", "bảng giá trị", "bảng biến thiên", "bảng tần số"
- **Hình**: "hình vẽ", "hình bên", "đồ thị", "biểu đồ", "minh họa"
""")
