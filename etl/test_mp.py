import os
import sys
import time
import pymupdf
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor
from rapidocr_onnxruntime import RapidOCR

_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr

def ocr_single_page(args):
    pdf_path, pno, dpi = args
    ocr = get_ocr()
    doc = pymupdf.open(pdf_path)
    pix = doc[pno].get_pixmap(dpi=dpi)
    img = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    t0 = time.time()
    res, _ = ocr(img)
    return pno, len(res) if res else 0, time.time() - t0

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    pdf_path = "updates voter list pdf/112_1791587543.pdf.pdf"
    tasks = [(pdf_path, pno, 100) for pno in range(283, 291)] # 8 pages
    
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(ocr_single_page, tasks))
    total_time = time.time() - t0
    
    print(f"8 pages processed in parallel with 4 workers: {total_time:.2f}s ({total_time/8:.2f}s/page)")
    for pno, n_boxes, dur in results:
        print(f"  Page {pno+1}: {n_boxes} boxes in {dur:.2f}s")
