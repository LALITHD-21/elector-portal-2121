import sys
import re
import cv2
import numpy as np
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

path = 'C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chikkaballapur nandi & kasba hobli 2026_ocred.pdf'
doc = pymupdf.open(path)

col_x = [19, 57, 176, 295, 453, 533, 612, 647, 682, 761, 821]

def clean_str(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^[\s\.,_\-!#~;:\'\"\|]+|[\s\.,_\-!#~;:\'\"\|]+$', '', s).strip()
    if not s or s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', '#']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    m = re.search(r'([A-Z]{3}\d{7})', s)
    if m: return m.group(1)[:11]
    m2 = re.search(r'([A-Z]{2,4}\d{6,8})', s)
    if m2: return m2.group(1)[:11]
    return None

all_voters = []
for pno in range(1, 10):
    page = doc[pno]
    pix = page.get_pixmap(dpi=72)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if pix.n >= 3 else img
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (150, 1))
    horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    row_sums = np.sum(horizontal > 0, axis=1)
    divider_y = np.where(row_sums > 300)[0]
    
    dividers = []
    if len(divider_y) > 0:
        curr = [divider_y[0]]
        for y in divider_y[1:]:
            if y - curr[-1] <= 4: curr.append(y)
            else:
                dividers.append(int(np.mean(curr)))
                curr = [y]
        dividers.append(int(np.mean(curr)))
        
    dividers = [y for y in dividers if y >= 70]
    for r in range(len(dividers)-1):
        y0, y1 = dividers[r], dividers[r+1]
        ser_raw = page.get_text('text', clip=pymupdf.Rect(col_x[0], y0, col_x[1], y1))
        name = clean_str(page.get_text('text', clip=pymupdf.Rect(col_x[1], y0, col_x[2], y1)))
        rel = clean_str(page.get_text('text', clip=pymupdf.Rect(col_x[2], y0, col_x[3], y1)))
        addr = clean_str(page.get_text('text', clip=pymupdf.Rect(col_x[3], y0, col_x[4], y1)))
        age_raw = page.get_text('text', clip=pymupdf.Rect(col_x[6], y0, col_x[7], y1))
        sex_raw = page.get_text('text', clip=pymupdf.Rect(col_x[7], y0, col_x[8], y1))
        epic_raw = page.get_text('text', clip=pymupdf.Rect(col_x[8], y0, col_x[9], y1))
        
        m_ser = re.search(r'\b(\d{1,5})\b', ser_raw)
        ser = int(m_ser.group(1)) if m_ser else None
        
        m_age = re.search(r'\b(1[89]|[2-9]\d)\b', age_raw)
        age = int(m_age.group(1)) if m_age else None
        
        sex = None
        if 'M' in sex_raw.upper(): sex = 'M'
        elif 'F' in sex_raw.upper(): sex = 'F'
        
        epic = clean_epic(epic_raw)
        
        if name and not any(h in name.lower() for h in ['name of', 'sino', 'elector']):
            all_voters.append({
                'ser': ser, 'name': name, 'rel': rel, 'age': age, 'sex': sex, 'epic': epic
            })

print(f'Extracted {len(all_voters)} voters from pages 2-10:')
for v in all_voters[:10]:
    print(' ', v)
