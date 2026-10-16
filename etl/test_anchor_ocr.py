import sys
import re
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')
ocr = RapidOCR()
doc = pymupdf.open('uptaed voter list/32_1791587153.pdf.pdf')

def clean_text(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'[\$#@!~%^*_+=\[\]{};:\"\'\<\>?/\\|]+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    if s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', 'photo', 'available']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    s = re.sub(r'^NM0', 'NMO', s)
    
    if len(s) == 10 and re.match(r'^[A-Z]{3}[DO]\d{6}$', s):
        s = s[:3] + '0' + s[4:]
    elif len(s) == 9 and re.match(r'^[A-Z]{3}\d{6}$', s):
        s = s[:3] + '0' + s[3:]
    elif len(s) == 11 and re.match(r'^[A-Z]{3}0\d{7}$', s):
        s = s[:3] + s[4:]
        
    m = re.search(r'([A-Z]{2,4}\d{5,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) == 9: ep = ep[:3] + '0' + ep[3:]
        return ep
    return None

def parse_page_blocks(page_idx, running_serial):
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=150)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img_np = img_np[:, :, :3]
    res, _ = ocr(img_np)
    if not res:
        return [], running_serial

    # Filter out header (y < 150) and footer (y > 1160)
    body_items = [r for r in res if 150 <= ((r[0][0][1] + r[0][2][1]) / 2) <= 1160]

    # Find serial anchors (items where xm < 140 and text has a number)
    anchors = []
    for it in body_items:
        xm = (it[0][0][0] + it[0][1][0]) / 2
        ym = (it[0][0][1] + it[0][2][1]) / 2
        txt = it[1].strip()
        if xm < 140:
            m = re.search(r'\b(\d{1,5})\b', txt)
            if m:
                s_val = int(m.group(1))
                # Check if it makes sense as a serial
                anchors.append({'sno': s_val, 'y': ym, 'item': it})

    anchors.sort(key=lambda a: a['y'])

    # Deduplicate anchors that are too close in Y (< 40px)
    clean_anchors = []
    for a in anchors:
        if not clean_anchors or (a['y'] - clean_anchors[-1]['y'] > 45):
            clean_anchors.append(a)

    # Determine Y boundary bands for each voter block
    # If no anchors found (rare), divide height into equal slots
    bands = []
    for i, a in enumerate(clean_anchors):
        top_y = 150 if i == 0 else (clean_anchors[i-1]['y'] + a['y']) / 2
        bot_y = 1160 if i == len(clean_anchors) - 1 else (a['y'] + clean_anchors[i+1]['y']) / 2
        bands.append({'sno': a['sno'], 'top': top_y, 'bot': bot_y, 'items': []})

    # Assign all body items into their corresponding voter band
    for it in body_items:
        ym = (it[0][0][1] + it[0][2][1]) / 2
        for b in bands:
            if b['top'] <= ym < b['bot']:
                b['items'].append(it)
                break

    voters = []
    for b in bands:
        cols = {'sno': b['sno'], 'names': [], 'rels': [], 'addrs': [], 'quals': [], 'occs': [], 'ages': [], 'sexes': [], 'epics': []}
        for it in b['items']:
            xm = (it[0][0][0] + it[0][1][0]) / 2
            txt = it[1].strip()
            if xm < 140:
                pass
            elif xm < 380:
                cols['names'].append(txt)
            elif xm < 620:
                cols['rels'].append(txt)
            elif xm < 920:
                cols['addrs'].append(txt)
            elif xm < 1100:
                cols['quals'].append(txt)
            elif xm < 1260:
                cols['occs'].append(txt)
            elif xm < 1350:
                cols['ages'].append(txt)
            elif xm < 1440:
                cols['sexes'].append(txt)
            elif xm < 1620:
                cols['epics'].append(txt)

        # Clean values
        name = clean_text(' '.join(cols['names']))
        rel = clean_text(' '.join(cols['rels']))
        addr = clean_text(', '.join(cols['addrs']))
        qual = clean_text(' '.join(cols['quals']))
        occ = clean_text(' '.join(cols['occs']))
        
        # Parse age
        age = None
        for at in cols['ages']:
            m = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', at)
            if m:
                age = int(m.group(1))
                break
                
        # Parse sex
        sex = None
        for st in cols['sexes']:
            if re.search(r'\b(Female|F)\b', st, re.I):
                sex = 'F'
                break
            elif re.search(r'\b(Male|M)\b', st, re.I):
                sex = 'M'
                break

        # Parse epic
        epic = None
        for et in cols['epics']:
            cleaned_ep = clean_epic(et)
            if cleaned_ep:
                epic = cleaned_ep
                break
        if not epic:
            # Check entire block text for EPIC pattern
            all_txt = ' '.join(it[1] for it in b['items'])
            m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?[A-Za-z0-9]{5,9})', all_txt)
            if m_ep:
                epic = clean_epic(m_ep.group(1))

        # Check serial continuity
        sno = b['sno']
        if sno and abs(sno - (running_serial + 1)) <= 2:
            running_serial = sno
        else:
            running_serial = running_serial + 1
            sno = running_serial

        voters.append({
            'part_number': '32',
            'serial_number': sno,
            'name': name,
            'relative_name': rel,
            'address': addr,
            'qualification': qual,
            'occupation': occ,
            'age': age,
            'sex': sex,
            'epic_number': epic,
            'page': page_idx + 1
        })

    return voters, running_serial

running_serial = 0
for p in [1, 2, 3]:
    voters, running_serial = parse_page_blocks(p, running_serial)
    print(f"\n--- Page {p+1}: {len(voters)} voters (Running Serial: {running_serial}) ---")
    for v in voters:
        print(f"#{v['serial_number']:3d} | EPIC: {str(v['epic_number']):11s} | {str(v['name']):22s} | Rel: {str(v['relative_name']):18s} | Age: {str(v['age']):3s} | Sex: {str(v['sex']):2s} | Qual: {str(v['qualification']):6s} | Addr: {str(v['address'])[:30]}")
