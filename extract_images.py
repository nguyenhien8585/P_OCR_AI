import fitz  # PyMuPDF
import base64
import io
from PIL import Image

def extract_images_from_pdf(pdf_bytes):
    images = []
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    img_idx = 0
    for page_number in range(len(pdf)):
        page = pdf[page_number]
        image_list = page.get_images(full=True)
        for img in image_list:
            xref = img[0]
            base = pdf.extract_image(xref)
            image_bytes = base["image"]
            ext = base["ext"]
            img_name = f"img-{img_idx}.jpeg"
            # Đảm bảo về JPEG
            try:
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG")
                img_b64 = base64.b64encode(buf.getvalue()).decode()
            except:
                img_b64 = base64.b64encode(image_bytes).decode()
            images.append({"name": img_name, "base64": img_b64})
            img_idx += 1
    return images
