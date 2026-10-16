import sys
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')
ocr = RapidOCR()
doc = pymupdf.open('uptaed voter list/36_1791587153.pdf.pdf')

for page_idx in [1, 2]:
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=150)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img_np = img_np[:, :, :3]
    res, _ = ocr(img_np)
    print(f"\n--- Part 36 Page {page_idx+1}: {len(res) if res else 0} OCR items ---")
    for r in (res or [])[:20]:
        ym = (r[0][0][1] + r[0][2][1]) / 2
        xm = (r[0][0][0] + r[0][1][0]) / 2
        print(f"x={xm:4.0f}, y={ym:4.0f} | {r[1]}")
