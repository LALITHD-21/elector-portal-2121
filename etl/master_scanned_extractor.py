import os
import sys
import re
import json
import time
import argparse
import pymupdf
import numpy as np
import cv2
import pandas as pd
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')
ocr = RapidOCR()

def clean_str(s):
    if not s or pd.isna(s): return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'[\$#@!~%^*()_+=\[\]{};:\"\'\<\>?/\\|]+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    if s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', 'photo', 'available']: return None
    return s

def clean_epic(s):
    if not s or pd.isna(s): return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('-', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    s = re.sub(r'^NM0', 'NMO', s)
    s = re.sub(r'^1KI', 'IKI', s)
    
    m = re.search(r'([A-Z]{2,4}\d{5,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) == 9 and re.match(r'^[A-Z]{3}\d{6}$', ep):
            ep = ep[:3] + '0' + ep[3:]
        elif len(ep) == 11 and re.match(r'^[A-Z]{3}0\d{7}$', ep):
            ep = ep[:3] + ep[4:]
        return ep
    return None

def extract_scanned_page(page, dpi=150):
    pix = page.get_pixmap(dpi=dpi)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img_np = img_np[:, :, :3]

    h, w, _ = img_np.shape
    res, _ = ocr(img_np)
    if not res:
        return []

    # Filter header and footer
    data_boxes = []
    for b, txt, score in res:
        box = np.array(b)
        ymin, ymax = box[:, 1].min(), box[:, 1].max()
        xmin, xmax = box[:, 0].min(), box[:, 0].max()
        xcenter = (xmin + xmax) / 2.0
        ycenter = (ymin + ymax) / 2.0

        # Skip headers (top ~15%) and footers (bottom ~5%)
        if ycenter < h * 0.15 or ycenter > h * 0.96:
            continue
        
        t_clean = txt.strip()
        if t_clean.lower() in ['photo', 'available', 'photo available', 'elector\'s photo', '#-modification', 'sl no', 'name of the elector']:
            continue

        data_boxes.append({
            'xmin': xmin, 'xmax': xmax, 'ymin': ymin, 'ymax': ymax,
            'xcenter': xcenter, 'ycenter': ycenter, 'text': t_clean
        })

    # Find serial number markers (xcenter < w * 0.08)
    sno_col_max = w * 0.08
    serial_boxes = []
    for b in data_boxes:
        if b['xcenter'] < sno_col_max:
            m = re.search(r'#?\s*(\d{1,6})\b', b['text'])
            if m:
                serial_boxes.append({
                    'sno': int(m.group(1)),
                    'y': b['ycenter']
                })

    serial_boxes.sort(key=lambda s: s['y'])
    clean_serials = []
    for s in serial_boxes:
        if not clean_serials or abs(s['y'] - clean_serials[-1]['y']) > 30:
            clean_serials.append(s)

    if not clean_serials:
        return []

    # Build horizontal row bands
    bands = []
    for i, s in enumerate(clean_serials):
        top_y = (h * 0.15) if i == 0 else (clean_serials[i-1]['y'] + s['y']) / 2.0
        bot_y = (h * 0.96) if i == len(clean_serials) - 1 else (s['y'] + clean_serials[i+1]['y']) / 2.0
        bands.append({
            'sno': s['sno'],
            'top': top_y,
            'bot': bot_y,
            'items': []
        })

    for b in data_boxes:
        if b['xcenter'] < sno_col_max:
            continue
        ym = b['ycenter']
        for band in bands:
            if band['top'] <= ym < band['bot']:
                band['items'].append(b)
                break

    # Column x boundaries (normalized fractions of page width)
    x_name_max = w * 0.22
    x_rel_max = w * 0.36
    x_addr_max = w * 0.55
    x_qual_max = w * 0.65
    x_occ_max = w * 0.73
    x_age_max = w * 0.78
    x_sex_max = w * 0.83
    x_epic_max = w * 0.95

    voters = []
    for b in bands:
        if not b['items']:
            continue

        cols = {'names': [], 'rels': [], 'addrs': [], 'quals': [], 'occs': [], 'ages': [], 'sexes': [], 'epics': []}
        for it in b['items']:
            xm = it['xcenter']
            txt = it['text']
            if xm < x_name_max:
                cols['names'].append(txt)
            elif xm < x_rel_max:
                cols['rels'].append(txt)
            elif xm < x_addr_max:
                cols['addrs'].append(txt)
            elif xm < x_qual_max:
                cols['quals'].append(txt)
            elif xm < x_occ_max:
                cols['occs'].append(txt)
            elif xm < x_age_max:
                cols['ages'].append(txt)
            elif xm < x_sex_max:
                cols['sexes'].append(txt)
            elif xm < x_epic_max:
                cols['epics'].append(txt)

        name = clean_str(' '.join(cols['names']))
        rel = clean_str(' '.join(cols['rels']))
        addr = clean_str(', '.join(cols['addrs']))
        qual = clean_str(' '.join(cols['quals']))
        occ = clean_str(' '.join(cols['occs']))

        age = None
        for at in cols['ages']:
            m = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', at)
            if m:
                age = int(m.group(1))
                break

        sex = None
        for st in cols['sexes']:
            if re.search(r'\b(Female|F)\b', st, re.I):
                sex = 'F'
                break
            elif re.search(r'\b(Male|M)\b', st, re.I):
                sex = 'M'
                break

        epic = None
        for et in cols['epics']:
            cleaned_ep = clean_epic(et)
            if cleaned_ep:
                epic = cleaned_ep
                break
        if not epic:
            all_txt = ' '.join(it['text'] for it in b['items'])
            m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?[A-Za-z0-9]{5,9})', all_txt)
            if m_ep:
                epic = clean_epic(m_ep.group(1))

        if not (name or rel or epic):
            continue

        voters.append({
            'serial_number': b['sno'],
            'epic_number': epic,
            'name': name,
            'relative_name': rel,
            'address': addr,
            'qualification': qual,
            'occupation': occ,
            'age': age,
            'sex': sex
        })

    return voters

def run_scanned_extraction(pdf_path, part_num, start_page=1, end_page=None):
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    if end_page is None or end_page >= total_pages:
        end_page = total_pages - 1

    print(f"=== Starting Hybrid Scanned Extraction: Part {part_num} ===")
    print(f"PDF: {pdf_path} (Pages {start_page} to {end_page} of {total_pages})")

    all_voters = []
    t_start = time.time()

    for p in range(start_page, end_page + 1):
        t0 = time.time()
        page_voters = extract_scanned_page(doc[p])
        for v in page_voters:
            v['part_number'] = str(part_num)
            v['page'] = p + 1
        all_voters.extend(page_voters)
        el = time.time() - t0
        print(f"  Page {p+1:3d}/{total_pages}: {len(page_voters):2d} voters (Total: {len(all_voters):4d}) [{el:.2f}s]")

    # Continuous serial validation
    unique_voters = {}
    for v in all_voters:
        unique_voters[v['serial_number']] = v

    serials = sorted(list(unique_voters.keys()))
    if serials:
        min_sno = serials[0]
        max_sno = serials[-1]
        missing_gaps = set(range(min_sno, max_sno + 1)) - set(serials)
    else:
        min_sno, max_sno, missing_gaps = 0, 0, set()

    print(f"\nExtraction complete in {time.time() - t_start:.1f}s")
    print(f"Total extracted: {len(all_voters)}, Unique serials: {len(unique_voters)}")
    print(f"Serial range: {min_sno} to {max_sno}, Missing gaps: {len(missing_gaps)}")

    os.makedirs('etl/reports', exist_ok=True)
    out_json = f'etl/reports/scanned_part_{part_num}_extracted.json'
    out_csv = f'etl/reports/scanned_part_{part_num}_extracted.csv'
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(list(unique_voters.values()), f, indent=2, ensure_ascii=False)
    pd.DataFrame(list(unique_voters.values())).to_csv(out_csv, index=False)
    print(f"Saved to {out_json} and {out_csv}")
    return unique_voters

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--part', required=True)
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=5)
    args = parser.parse_args()
    run_scanned_extraction(args.pdf, args.part, args.start, args.end)
