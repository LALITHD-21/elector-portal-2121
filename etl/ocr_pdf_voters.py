import os
import sys
import re
import json
import time
from datetime import datetime
import pymupdf
from rapidocr_onnxruntime import RapidOCR
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# Initialize RapidOCR engine
ocr_engine = RapidOCR()

def clean_text(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'[\$#@!~%^*()_+=\[\]{};:\"\'\<\>?/\\|]+', '', s).strip()
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
    s = re.sub(r'^IN:MO', 'NMO', s)
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

def ocr_page_voters(doc, pno, running_serial, part_num="32"):
    page = doc[pno]
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    
    ocr_result, _ = ocr_engine(img_bytes)
    if not ocr_result: return [], running_serial
    
    # Filter out header elements (y < 120 in image coordinates)
    # pixmap height at 150 dpi is typically ~1754
    img_h = pix.height
    header_threshold = img_h * 0.08
    footer_threshold = img_h * 0.96
    
    content_items = [
        item for item in ocr_result 
        if item[0][0][1] >= header_threshold and item[0][2][1] <= footer_threshold
    ]
    
    # Cluster OCR items into horizontal voter bands by Y center
    bands_y = []
    sorted_items = sorted(content_items, key=lambda it: (it[0][0][1] + it[0][2][1]) / 2)
    
    for it in sorted_items:
        y_center = (it[0][0][1] + it[0][2][1]) / 2
        placed = False
        for by in bands_y:
            if abs(y_center - by['y_mean']) < (img_h * 0.045): # within ~75 pixels band
                by['items'].append(it)
                by['y_mean'] = sum((x[0][0][1] + x[0][2][1]) / 2 for x in by['items']) / len(by['items'])
                placed = True
                break
        if not placed:
            bands_y.append({'y_mean': y_center, 'items': [it]})
            
    voter_bands = []
    for by in bands_y:
        items = by['items']
        text = ' '.join(it[1] for it in items)
        if any(h in text for h in ['Table of Content', 'Name of State', 'Components of', 'Page 1 of', 'Electoral Rolls', 'Name of the Elector', 'Modification, Sex:']):
            continue
        if len(items) >= 4:
            voter_bands.append(items)
            
    voter_bands.sort(key=lambda items: sum((it[0][0][1] + it[0][2][1]) / 2 for it in items) / len(items))
    
    voters = []
    for items in voter_bands:
        text = ' '.join(it[1] for it in items)
        
        # 1. Parse EPIC
        m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?[A-Za-z0-9]{5,9})', text)
        epic = clean_epic(m_ep.group(1)) if m_ep else None
        
        # 2. Parse serial
        m_s = re.search(r'(?:[#§s8\*\$]|\b)\s*(\d{1,5})\s*(?:\s|$)', text)
        detected_serial = int(m_s.group(1)) if m_s else None
        
        if detected_serial and abs(detected_serial - (running_serial + 1)) <= 3:
            serial = detected_serial
        else:
            serial = running_serial + 1
        running_serial = serial
        
        # 3. Parse Age & Sex
        m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', text)
        age = int(m_age.group(1)) if m_age else None
        sex = 'F' if re.search(r'\b(Female|F)\b', text, re.IGNORECASE) else ('M' if re.search(r'\b(Male|M)\b', text, re.IGNORECASE) else None)
        
        # 4. Parse Name & Relative
        # filter out non-name tokens
        name_cand = None
        rel_cand = None
        for it in items:
            t = clean_text(it[1])
            if not t or re.match(r'^\d+$', t) or t in ['Male', 'Female', 'M', 'F', 'Photo', 'Available', 'Karnataka', 'BA', 'BSC', 'BCOM', 'BE']:
                continue
            if not name_cand:
                name_cand = t
            elif not rel_cand:
                rel_cand = t
                break
                
        voters.append({
            "part_number": part_num,
            "serial_number": serial,
            "epic_number": epic,
            "name": name_cand,
            "relative_name": rel_cand,
            "age": age,
            "sex": sex,
            "page": pno + 1
        })
        
    return voters, running_serial

def test_ocr_pdf(pdf_path, max_pages=10, part_num="32"):
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Opened PDF: {pdf_path} ({total_pages} total pages)")
    print(f"Testing high-accuracy RapidOCR on first {max_pages} pages...")
    
    start_time = time.time()
    all_voters = []
    running_serial = 0
    
    for pno in range(1, max_pages + 1):
        p_start = time.time()
        voters, running_serial = ocr_page_voters(doc, pno, running_serial, part_num)
        all_voters.extend(voters)
        print(f"Page {pno + 1}: Extracted {len(voters)} voters in {time.time() - p_start:.2f}s (Running Total: {len(all_voters)})", flush=True)
        for v in voters:
            print(f"   Serial #{v['serial_number']:4d} | EPIC: {str(v['epic_number']):11s} | Name: {str(v['name']):25s} | Rel: {str(v['relative_name']):20s} | Age: {str(v['age']):3s} | Sex: {str(v['sex'])}")
            
    print(f"\nCompleted OCR on {max_pages} pages in {time.time() - start_time:.2f} seconds!")
    print(f"Total Voters Extracted: {len(all_voters)}")

if __name__ == '__main__':
    target_pdf = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list/32_1791587153.pdf.pdf'
    test_ocr_pdf(target_pdf, max_pages=5, part_num="32")
