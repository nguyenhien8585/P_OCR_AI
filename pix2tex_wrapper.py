import base64
import io
from PIL import Image

try:
    from pix2tex.cli import LatexOCR
except Exception as e:
    LatexOCR = None

def recognize_latex_from_images(figures):
    if LatexOCR is None:
        # Trả về thông báo lỗi hoặc thông tin không hỗ trợ Pix2Tex
        return [{"name": fig["name"], "latex": "Pix2Tex module not available"} for fig in figures]
    ocr = LatexOCR()
    results = []
    for fig in figures:
        img_bytes = base64.b64decode(fig["base64"])
        image = Image.open(io.BytesIO(img_bytes))
        latex = ocr(image)
        results.append({"name": fig["name"], "latex": latex})
    return results
