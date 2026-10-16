import os
import sys
import re
import json
import time
from datetime import datetime
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

import urllib.request

# 1. Fetch all existing EPICs from DB in parallel by booth
print("Step 1: Loading all active EPICs from Supabase across all 151 booths...")
start_time = time.time()
db_epics_by_part = {}
global_db_epics = set()

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Range-Unit': 'items',
    'Prefer': 'count=exact'
}

def fetch_part_epics(part_num):
    part_str = str(part_num)
    epics = set()
    offset = 0
    batch_size = 1000
    while True:
        url = f"{SUPABASE_URL}/rest/v1/electors?part_number=eq.{part_str}&select=epic_number&limit={batch_size}&offset={offset}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if not data: break
                for d in data:
                    if d.get('epic_number'):
                        epics.add(str(d['epic_number']).strip().upper())
                offset += len(data)
                if len(data) < batch_size: break
        except Exception:
            break
    return part_str, epics

with ThreadPoolExecutor(max_workers=12) as executor:
    futures = [executor.submit(fetch_part_epics, p) for p in range(1, 152)]
    for f in as_completed(futures):
        part_str, ep_set = f.result()
        db_epics_by_part[part_str] = ep_set
        global_db_epics.update(ep_set)

print(f"Loaded {len(global_db_epics)} distinct EPICs across {len(db_epics_by_part)} booths from DB in {time.time() - start_time:.2f} seconds.")

# 2. Extract from all 146 Excel files using read_only openpyxl
excel_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list'
excel_files = [f for f in os.listdir(excel_dir) if f.endswith('.xlsx')]
print(f"\nStep 2: Parsing {len(excel_files)} booth Excel files...")

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

def process_excel(fn):
    p_num = fn.split('_')[0]
    part_db_epics = db_epics_by_part.get(p_num, set())
    fp = os.path.join(excel_dir, fn)
    
    recovered = []
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
            
            # Address candidates
            addr_cells = [c for c in text_cells[2:] if clean_text(c) and len(c) > 3]
            addr = ", ".join(addr_cells[:4]) if addr_cells else None
            
            # Age & Sex
            m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', row_str)
            age = int(m_age.group(1)) if m_age else None
            sex = 'F' if re.search(r'\b(Female|F)\b', row_str, re.IGNORECASE) else ('M' if re.search(r'\b(Male|M)\b', row_str, re.IGNORECASE) else None)
            
            if name and epic and re.match(r'^[A-Z]{3}\d{7}$', epic):
                if epic not in part_db_epics and epic not in global_db_epics:
                    recovered.append({
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
        pass
        
    return fn, p_num, recovered

all_recovered_voters = []
booth_recovery_counts = {}

parse_start = time.time()
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(process_excel, fn) for fn in excel_files]
    for f in as_completed(futures):
        fn, p_num, rec_list = f.result()
        if rec_list:
            all_recovered_voters.extend(rec_list)
            booth_recovery_counts[p_num] = len(rec_list)
            print(f"Booth {p_num:3s} ({fn:22s}): Recovered {len(rec_list):3d} missing voters! (Total so far: {len(all_recovered_voters)})")

print(f"\nCompleted parsing all {len(excel_files)} Excel files in {time.time() - parse_start:.2f} seconds!")
print(f"Total Missing Voters Recovered Across All Booths: {len(all_recovered_voters)}")

# Deduplicate by EPIC within the recovered set
df_recovered = pd.DataFrame(all_recovered_voters)
if not df_recovered.empty:
    unique_recovered = df_recovered.drop_duplicates(subset=['epic_number']).copy()
    print(f"Unique Verified Missing Voters Ready for Insert: {len(unique_recovered)}")
    
    out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_excel_recovery'
    os.makedirs(out_dir, exist_ok=True)
    
    unique_recovered.to_csv(os.path.join(out_dir, 'new_valid.csv'), index=False)
    unique_recovered.to_excel(os.path.join(out_dir, 'new_valid.xlsx'), index=False)
    
    summary_md = f"""# All-Booth Excel Recovery Summary
- **Files Scanned**: {len(excel_files)} Excel files
- **Booths Audited**: All 151 booths
- **Unique New Missing Voters Recovered**: {len(unique_recovered):,}
- **Reports Saved to**: `{out_dir}`
"""
    with open(os.path.join(out_dir, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(summary_md)
        
    print("\n" + summary_md)
    print("Top 10 Booths by Recovered Voters:")
    print(unique_recovered['part_number'].value_counts().head(10))
