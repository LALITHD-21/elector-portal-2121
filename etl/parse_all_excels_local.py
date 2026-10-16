import os
import sys
import re
import time
from datetime import datetime
import openpyxl
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

excel_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list'
excel_files = [f for f in os.listdir(excel_dir) if f.endswith('.xlsx')]
print(f"Parsing {len(excel_files)} Excel files locally from {excel_dir}...")

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

def process_file(fn):
    p_num = fn.split('_')[0]
    fp = os.path.join(excel_dir, fn)
    records = []
    
    try:
        wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
        sheet = wb.active
        running_serial = 0
        
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
            vals = [str(v).strip() for v in row if v is not None and str(v).strip() != '']
            if not vals: continue
            row_str = ' '.join(vals)
            
            if any(h in row_str for h in ['GRADUATES\' CONSTITUENCY', 'Name of State', 'COMPONENTS OF THE ROLL', 'Table of Content', 'Name of the Elector', 'Sl.No', 'SINo']):
                continue
                
            m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?\d{5,8})', row_str)
            epic = clean_epic(m_ep.group(1)) if m_ep else None
            
            serial = None
            s_cand = vals[0].replace('\n', '').replace(' ', '').replace('#', '')
            if s_cand.isdigit():
                serial = int(s_cand)
            else:
                m_s = re.search(r'(?:#\s*|^)(\d{1,5})(?:\s|$)', row_str)
                if m_s: serial = int(m_s.group(1))
                
            if serial: running_serial = serial
            else: serial = running_serial + 1
            
            text_cells = [c for c in vals if not re.match(r'^[#\d\s]+$', c) and c not in ['Male', 'Female', 'M', 'F', 'Photo', 'Available', 'Karnataka']]
            name = clean_text(text_cells[0]) if len(text_cells) > 0 else None
            rel = clean_text(text_cells[1]) if len(text_cells) > 1 else None
            
            addr_cells = [c for c in text_cells[2:] if clean_text(c) and len(c) > 3]
            addr = ", ".join(addr_cells[:4]) if addr_cells else None
            
            m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', row_str)
            age = int(m_age.group(1)) if m_age else None
            sex = 'F' if re.search(r'\b(Female|F)\b', row_str, re.IGNORECASE) else ('M' if re.search(r'\b(Male|M)\b', row_str, re.IGNORECASE) else None)
            
            if name:
                records.append({
                    "part_number": p_num,
                    "serial_number": serial,
                    "epic_number": epic,
                    "name": name,
                    "relative_name": rel,
                    "address": addr,
                    "age": age,
                    "sex": sex,
                    "source_file": fn,
                    "source_page_or_row": f"Row {row_idx + 1}"
                })
        wb.close()
    except Exception as e:
        print(f"Error reading {fn}: {e}", flush=True)
        
    return fn, p_num, records

all_records = []
start_time = time.time()
completed = 0

with ThreadPoolExecutor(max_workers=6) as executor:
    futures = {executor.submit(process_file, fn): fn for fn in excel_files}
    for f in as_completed(futures):
        fn = futures[f]
        _, p_num, recs = f.result()
        all_records.extend(recs)
        completed += 1
        if completed % 20 == 0 or completed == len(excel_files):
            print(f"Parsed {completed}/{len(excel_files)} files... Extracted {len(all_records):,} electors so far.", flush=True)

elapsed = time.time() - start_time
print(f"\nFinished parsing all {len(excel_files)} Excel files in {elapsed:.2f} seconds!")
print(f"Total Electors Extracted from Excel: {len(all_records):,}")

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_extracted'
os.makedirs(out_dir, exist_ok=True)
out_csv = os.path.join(out_dir, 'all_excel_electors.csv')

df_all = pd.DataFrame(all_records)
df_all.to_csv(out_csv, index=False)
print(f"Saved extracted dataset to {out_csv} ({os.path.getsize(out_csv)/(1024*1024):.2f} MB)")
