import pymupdf
import numpy as np
import cv2
import re
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()

# Standard column X-ranges (normalized across 150 DPI page: width ~1755)
# Column 1: SINo             (x: 40 - 130)
# Column 2: Name             (x: 130 - 370)
# Column 3: Relative         (x: 370 - 590)
# Column 4: Address          (x: 590 - 945)
# Column 5: Qualification    (x: 945 - 1110)
# Column 6: Occupation       (x: 1110 - 1270)
# Column 7: Age              (x: 1270 - 1350)
# Column 8: Sex              (x: 1350 - 1430)
# Column 9: EPIC             (x: 1430 - 1590)
# Column 10: Photo           (x: 1590 - 1730)

def extract_voters_from_page(page_img):
    res, _ = ocr(page_img)
    if not res:
        return []
    
    # Filter out header area (y < 310) and footer area (y > 1180)
    data_boxes = []
    for b, txt, s in res:
        box = np.array(b)
        ymin, ymax = box[:, 1].min(), box[:, 1].max()
        xmin, xmax = box[:, 0].min(), box[:, 0].max()
        xcenter = (xmin + xmax) / 2
        ycenter = (ymin + ymax) / 2
        
        # Skip headers / footers
        if ycenter < 310 or ycenter > 1180:
            continue
        
        # Skip "Photo", "Available", "#-Modification"
        if txt.strip() in ['Photo', 'Available', '#-Modification', '#', 'EPIC:']:
            continue
            
        data_boxes.append({
            'xmin': xmin, 'xmax': xmax, 'ymin': ymin, 'ymax': ymax,
            'xcenter': xcenter, 'ycenter': ycenter, 'text': txt.strip()
        })
    
    # Find serial number markers (Column 1: xcenter < 130)
    # A serial number box is typically purely digits (e.g. "1", "2", "345")
    serial_boxes = []
    for b in data_boxes:
        if b['xcenter'] < 130 and re.match(r'^\d{1,5}$', b['text']):
            serial_boxes.append(b)
            
    # Sort serial boxes by ycenter
    serial_boxes.sort(key=lambda b: b['ycenter'])
    
    # If no serial boxes found in Column 1, fall back to Y-gap clustering
    if not serial_boxes:
        # Fall back to EPIC boxes in Column 9
        epic_boxes = [b for b in data_boxes if 1420 < b['xcenter'] < 1590 and re.search(r'[A-Za-z]{2,5}\d{5,8}', b['text'])]
        epic_boxes.sort(key=lambda b: b['ycenter'])
        anchors = epic_boxes
    else:
        anchors = serial_boxes
        
    if not anchors:
        return []
        
    # Define row boundary intervals
    # Row i spans from midway between anchor[i-1] and anchor[i] to midway between anchor[i] and anchor[i+1]
    rows = []
    for i in range(len(anchors)):
        prev_y = (anchors[i-1]['ycenter'] + anchors[i]['ycenter']) / 2 if i > 0 else 310
        next_y = (anchors[i]['ycenter'] + anchors[i+1]['ycenter']) / 2 if i < len(anchors) - 1 else 1180
        
        # Collect all boxes within this Y-range
        row_boxes = [b for b in data_boxes if prev_y <= b['ycenter'] < next_y]
        
        # Classify by X-column
        col_ser = []
        col_name = []
        col_rel = []
        col_addr = []
        col_qual = []
        col_occ = []
        col_age = []
        col_sex = []
        col_epic = []
        
        for b in row_boxes:
            xc = b['xcenter']
            t = b['text']
            if xc < 130:
                col_ser.append(t)
            elif 130 <= xc < 370:
                col_name.append(t)
            elif 370 <= xc < 590:
                col_rel.append(t)
            elif 590 <= xc < 945:
                col_addr.append(t)
            elif 945 <= xc < 1110:
                col_qual.append(t)
            elif 1110 <= xc < 1270:
                col_occ.append(t)
            elif 1270 <= xc < 1350:
                col_age.append(t)
            elif 1350 <= xc < 1430:
                col_sex.append(t)
            elif 1430 <= xc < 1590:
                col_epic.append(t)
                
        # Parse fields
        # Serial
        ser_val = None
        for s in col_ser:
            m = re.search(r'\b(\d{1,5})\b', s)
            if m:
                ser_val = int(m.group(1))
                break
        if not ser_val and anchors is serial_boxes:
            m = re.search(r'\b(\d{1,5})\b', anchors[i]['text'])
            if m: ser_val = int(m.group(1))
            
        # Name
        name_val = " ".join(col_name).strip() if col_name else None
        if name_val and len(name_val) < 2: name_val = None
        
        # Relative
        rel_val = " ".join(col_rel).strip() if col_rel else None
        if rel_val and len(rel_val) < 2: rel_val = None
        
        # Address
        addr_val = " ".join(col_addr).strip() if col_addr else None
        
        # Age
        age_val = None
        for a in col_age:
            m = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', a)
            if m:
                age_val = int(m.group(1))
                break
                
        # Sex
        sex_val = None
        for s in col_sex:
            su = s.upper()
            if 'M' in su and 'F' not in su: sex_val = 'M'; break
            elif 'F' in su: sex_val = 'F'; break
            elif 'O' in su: sex_val = 'O'; break
            
        # EPIC
        epic_val = None
        for e in col_epic:
            eu = re.sub(r'[^A-Z0-9]', '', e.upper())
            m = re.search(r'([A-Z]{2,4}\d{6,8})', eu)
            if m:
                cand = m.group(1)
                if len(cand) <= 11:
                    epic_val = cand
                    break
                    
        rows.append({
            'serial_number': ser_val,
            'name': name_val,
            'relative_name': rel_val,
            'address': addr_val,
            'qualification': " ".join(col_qual).strip() if col_qual else None,
            'occupation': " ".join(col_occ).strip() if col_occ else None,
            'age': age_val,
            'sex': sex_val,
            'epic_number': epic_val
        })
        
    return rows

# Test on Page 2 of Part 112, 32, and 36!
for pdf_name in ['112_1791587543.pdf.pdf', '32_1791587153.pdf.pdf', '36_1791587153.pdf.pdf']:
    doc = pymupdf.open(f'updates voter list pdf/{pdf_name}')
    page = doc[1]
    pix = page.get_pixmap(dpi=150)
    img = cv2.imdecode(np.frombuffer(pix.tobytes('png'), np.uint8), cv2.IMREAD_COLOR)
    voters = extract_voters_from_page(img)
    print(f"\n=================== {pdf_name} (Page 2) ===================")
    print(f"Extracted {len(voters)} voter rows:")
    for v in voters:
        print(f"  SL={v['serial_number']:<4} EPIC={str(v['epic_number']):<11} Age={str(v['age']):<3} Sex={str(v['sex']):<2} Name={str(v['name']):<22} Rel={str(v['relative_name']):<22}")
