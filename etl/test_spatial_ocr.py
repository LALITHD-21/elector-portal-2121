import sys
import re
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')
ocr = RapidOCR()
doc = pymupdf.open('uptaed voter list/32_1791587153.pdf.pdf')

for page_idx in [1, 2, 3]:
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=150)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img_np = img_np[:, :, :3]
    res, _ = ocr(img_np)
    if not res:
        print(f"Page {page_idx+1}: No OCR results")
        continue

    # Filter out header (y < 150) and footer (y > 1160)
    body_items = [r for r in res if 150 <= ((r[0][0][1] + r[0][2][1]) / 2) <= 1160]

    # Group by horizontal rows: y within ~35px
    rows = []
    for item in sorted(body_items, key=lambda r: (r[0][0][1] + r[0][2][1]) / 2):
        y_mid = (item[0][0][1] + item[0][2][1]) / 2
        placed = False
        for row in rows:
            if abs(y_mid - row['y']) < 35:
                row['items'].append(item)
                row['y'] = sum((it[0][0][1] + it[0][2][1]) / 2 for it in row['items']) / len(row['items'])
                placed = True
                break
        if not placed:
            rows.append({'y': y_mid, 'items': [item]})

    print(f"\n=== PAGE {page_idx + 1}: Found {len(rows)} voter rows ===")
    for idx, r in enumerate(rows):
        cols = {'sno': [], 'name': [], 'rel': [], 'addr': [], 'qual': [], 'occ': [], 'age': [], 'sex': [], 'epic': []}
        for it in r['items']:
            xm = (it[0][0][0] + it[0][1][0]) / 2
            txt = it[1].strip()
            if xm < 140:
                cols['sno'].append(txt)
            elif xm < 380:
                cols['name'].append(txt)
            elif xm < 620:
                cols['rel'].append(txt)
            elif xm < 920:
                cols['addr'].append(txt)
            elif xm < 1100:
                cols['qual'].append(txt)
            elif xm < 1260:
                cols['occ'].append(txt)
            elif xm < 1350:
                cols['age'].append(txt)
            elif xm < 1440:
                cols['sex'].append(txt)
            elif xm < 1600:
                cols['epic'].append(txt)

        sno = ' '.join(cols['sno'])
        name = ' '.join(cols['name'])
        rel = ' '.join(cols['rel'])
        addr = ' '.join(cols['addr'])
        age = ' '.join(cols['age'])
        sex = ' '.join(cols['sex'])
        epic = ' '.join(cols['epic'])
        y_val = r['y']
        print(f"Row {idx+1:2d} [y={y_val:4.0f}]: SNo: {sno:6s} | Name: {name:22s} | Rel: {rel:20s} | Age: {age:3s} | Sex: {sex:2s} | EPIC: {epic}")
