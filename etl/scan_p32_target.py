import os
import sys
import pymupdf
import numpy as np
import cv2
import re
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
doc = pymupdf.open("updates voter list pdf/32_1791587153.pdf.pdf")

print(f"Deep scanning {len(doc)} pages of Part 32 for variants of ZFB3458064...")

matches = []

for pno in range(1, len(doc) - 1):
    pix = doc[pno].get_pixmap(dpi=100)
    img = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    h, w, _ = img.shape
    # Crop right 35% of page (contains Age, Sex, EPIC, Photo)
    crop = img[int(h*0.2):int(h*0.95), int(w*0.70):w]
    res, _ = ocr(crop)
    if res:
        for b, txt, s in res:
            t = txt.upper().replace(' ', '')
            # Check for patterns matching 3458064 or close fuzzy match
            if '34580' in t or '458064' in t or '3458' in t:
                matches.append((pno + 1, txt))
                print(f"Page {pno+1}: {txt}")

print(f"\nTotal potential matches found: {len(matches)}")
with open("etl/part32_target_matches.json", "w", encoding="utf-8") as f:
    import json
    json.dump(matches, f, indent=2)
