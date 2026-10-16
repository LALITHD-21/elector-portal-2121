import pymupdf
import numpy as np
import cv2
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()

for pdf_name in ["32_1791587153.pdf.pdf", "36_1791587153.pdf.pdf"]:
    doc = pymupdf.open(f"updates voter list pdf/{pdf_name}")
    page = doc[1] # Page 2
    pix = page.get_pixmap(dpi=150)
    img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    res, _ = ocr(img)
    print(f"=== {pdf_name} PAGE 2 OCR RESULTS ({len(res)} boxes) ===")
    # Print sample boxes with coordinates: xmin, ymin, xmax, ymax, text
    for b, txt, s in res[:25]:
        box = np.array(b)
        xmin, ymin = box[:, 0].min(), box[:, 1].min()
        xmax, ymax = box[:, 0].max(), box[:, 1].max()
        print(f"  ({xmin:4.0f}, {ymin:4.0f}, {xmax:4.0f}, {ymax:4.0f}): {txt}")
