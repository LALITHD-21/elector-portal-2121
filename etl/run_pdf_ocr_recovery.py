import os
import sys
import re
import time
import json
import argparse
import pymupdf
import numpy as np
import pandas as pd
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')

ocr = RapidOCR()

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

def parse_page_ocr(doc, page_idx, part_num, running_serial):
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=100)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img_np = img_np[:, :, :3]

    h, w, _ = img_np.shape
    top_crop = int(h * 0.25) if page_idx <= 1 else int(h * 0.12)
    bot_crop = int(h * 0.95)
    right_crop = int(w * 0.92)

    cropped = img_np[top_crop:bot_crop, :right_crop]
    res, _ = ocr(cropped)
    if not res:
        return [], running_serial

    items = []
    for r in res:
        box = r[0]
        txt = r[1].strip()
        score = r[2]
        x_mid = (box[0][0] + box[1][0]) / 2
        y_mid = ((box[0][1] + box[2][1]) / 2) + top_crop
        items.append({'text': txt, 'x': x_mid, 'y': y_mid, 'score': score, 'box': box})

    filtered = []
    for it in items:
        t_low = it['text'].lower()
        if any(h in t_low for h in ['name of the elector', 'father/mother', 'place of ordinary', 'residence', 'qualification', 'occupation', 'elector\'s photo']):
            continue
        filtered.append(it)

    col_sno_max = w * 0.09
    anchors = []
    for it in filtered:
        if it['x'] < col_sno_max:
            m = re.search(r'\b(\d{1,5})\b', it['text'])
            if m:
                s_val = int(m.group(1))
                anchors.append({'sno': s_val, 'y': it['y']})

    anchors.sort(key=lambda a: a['y'])

    clean_anchors = []
    for a in anchors:
        if not clean_anchors or (a['y'] - clean_anchors[-1]['y'] > 30):
            clean_anchors.append(a)

    bands = []
    for i, a in enumerate(clean_anchors):
        top_y = top_crop if i == 0 else (clean_anchors[i-1]['y'] + a['y']) / 2
        bot_y = bot_crop if i == len(clean_anchors) - 1 else (a['y'] + clean_anchors[i+1]['y']) / 2
        bands.append({'sno': a['sno'], 'top': top_y, 'bot': bot_y, 'items': []})

    if not bands:
        step = (bot_crop - top_crop) / 8.0
        for i in range(8):
            bands.append({'sno': None, 'top': top_crop + i * step, 'bot': top_crop + (i+1) * step, 'items': []})

    for it in filtered:
        ym = it['y']
        for b in bands:
            if b['top'] <= ym < b['bot']:
                b['items'].append(it)
                break

    x_name_max = w * 0.22
    x_rel_max = w * 0.36
    x_addr_max = w * 0.53
    x_qual_max = w * 0.63
    x_occ_max = w * 0.72
    x_age_max = w * 0.77
    x_sex_max = w * 0.82
    x_epic_max = w * 0.92

    voters = []
    for b in bands:
        if not b['items']:
            continue

        cols = {'names': [], 'rels': [], 'addrs': [], 'quals': [], 'occs': [], 'ages': [], 'sexes': [], 'epics': []}
        for it in b['items']:
            xm = it['x']
            txt = it['text']
            if xm < col_sno_max:
                pass
            elif xm < x_name_max:
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

        name = clean_text(' '.join(cols['names']))
        rel = clean_text(' '.join(cols['rels']))
        addr = clean_text(', '.join(cols['addrs']))
        qual = clean_text(' '.join(cols['quals']))
        occ = clean_text(' '.join(cols['occs']))

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

        sno = b['sno']
        if sno and (running_serial == 0 or abs(sno - (running_serial + 1)) <= 3):
            running_serial = sno
        else:
            running_serial = running_serial + 1
            sno = running_serial

        voters.append({
            'part_number': str(part_num),
            'serial_number': sno,
            'epic_number': epic,
            'name': name,
            'relative_name': rel,
            'address': addr,
            'qualification': qual,
            'occupation': occ,
            'age': age,
            'sex': sex,
            'page': page_idx + 1
        })

    return voters, running_serial

def run_extraction(pdf_path, part_num, start_page, end_page, output_prefix, init_serial=None, resume=True):
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    end_page = min(end_page, total_pages - 1)
    
    os.makedirs('etl/reports', exist_ok=True)
    out_json = f'etl/reports/{output_prefix}.json'
    out_csv = f'etl/reports/{output_prefix}.csv'

    all_voters = []
    processed_pages = set()
    running_serial = init_serial if init_serial is not None else 0

    if resume and os.path.exists(out_json):
        try:
            with open(out_json, 'r', encoding='utf-8') as f:
                all_voters = json.load(f)
            processed_pages = set(v['page'] - 1 for v in all_voters)
            if all_voters:
                running_serial = max(v['serial_number'] for v in all_voters if v.get('serial_number'))
            print(f"Resuming {output_prefix}: Loaded {len(all_voters)} existing voters across {len(processed_pages)} pages. Last serial: {running_serial}")
        except Exception as e:
            print(f"Could not load existing file for resume: {e}")

    print(f"=== Starting OCR Extraction: Part {part_num} ===")
    print(f"PDF: {pdf_path} (Total pages: {total_pages})")
    print(f"Target page range: {start_page} to {end_page} ({end_page - start_page + 1} pages)")

    t_start = time.time()
    pages_done = 0

    for p in range(start_page, end_page + 1):
        if p in processed_pages:
            continue

        t0 = time.time()
        voters, running_serial = parse_page_ocr(doc, p, part_num, running_serial)
        all_voters.extend(voters)
        pages_done += 1
        el = time.time() - t0
        print(f"Page {p+1:3d}/{total_pages}: {len(voters):2d} voters (Running: {len(all_voters):4d}, Serial #{running_serial:4d}) [{el:.2f}s]", flush=True)

        if pages_done % 5 == 0 or p == end_page:
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(all_voters, f, ensure_ascii=False, indent=2)
            pd.DataFrame(all_voters).to_csv(out_csv, index=False)
            print(f"   [Checkpoint saved: {len(all_voters)} voters across {pages_done} pages processed]", flush=True)

    t_total = time.time() - t_start
    print(f"\nBatch complete! {len(all_voters)} total voters ({pages_done} new pages in {t_total:.1f}s).")
    print(f"Saved to {out_json} and {out_csv}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', default='c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list/32_1791587153.pdf.pdf')
    parser.add_argument('--part', default='32')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=10)
    parser.add_argument('--out', default='ocr_test_p32')
    parser.add_argument('--init_serial', type=int, default=None)
    parser.add_argument('--no-resume', action='store_true')
    args = parser.parse_args()

    run_extraction(args.pdf, args.part, args.start, args.end, args.out, init_serial=args.init_serial, resume=not args.no_resume)
