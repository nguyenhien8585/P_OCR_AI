from PIL import Image
import base64
import io

def extract_figures_from_image(img_bytes, num_parts=2):
    """
    Tách ảnh thành các vùng đều nhau theo chiều dọc (mặc định 2 phần).
    Nếu muốn chia nhỏ hơn, tăng num_parts lên (3, 4,...).
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    width, height = img.size
    h_part = height // num_parts
    figures = []
    for idx in range(num_parts):
        top = idx * h_part
        bottom = (idx + 1) * h_part if idx < num_parts - 1 else height
        crop = img.crop((0, top, width, bottom))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        figures.append({"name": f"figure-{idx}.jpeg", "base64": b64})
    return figures
