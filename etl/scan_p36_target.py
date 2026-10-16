import os
import sys
import pymupdf
import numpy as np
import cv2
import re
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
doc = pymupdf.open("updates voter list pdf/36_1791587153.pdf.pdf")

print(f"Deep scanning {len(doc)} pages of Part 36 for 3458064...")

matches = []

# Part 36 has 1608 pages of voters
for pno in range(1, 1608):
    pix = doc[pno].get_pixmap(dpi=100)
    img = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    h, w, _ = img.shape
    crop = img[int(h*0.2):int(h*0.95), int(w*0.70):w]
    res, _ = ocr(crop)
    if res:
        for b, txt, s in res:
            t = txt.upper().replace(' ', '')
            if '3458064' in t or '34580' in t or ('ZFB' in t and '3458' in t):
                matches.append((pno + 1, txt))
                print(f"Part 36 Page {pno+1}: {txt}")
                with open("etl/found_part36_target.txt", "a", encoding="utf-8") as f:
                    f.write(f"Page {pno+1}: {txt}\n")

print(f"\nPart 36 scan finished. Total matches: {len(matches)}")
