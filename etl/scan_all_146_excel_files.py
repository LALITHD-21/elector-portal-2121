import os
import sys
import re
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

excel_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list'
excel_files = [f for f in os.listdir(excel_dir) if f.endswith('.xlsx')]
print(f"Found {len(excel_files)} Excel files in {excel_dir}")

def clean_text(s):
    if not s or pd.isna(s): return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'[\$#@!~%^*()_+=\[\]{};:\"\'\<\>?/\\|]+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    if s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', 'photo', 'available']: return None
    return s

def clean_epic(s):
    if not s or pd.isna(s): return None
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

def scan_file(file_name):
    p_num = file_name.split('_')[0]
    fp = os.path.join(excel_dir, file_name)
    try:
        df = pd.read_excel(fp, header=None, dtype=str)
    except Exception as e:
        return []

    # Fetch DB records for this part
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    db_epics = set()
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/electors?part_number=eq.{p_num}&select=epic_number&limit=1000&offset={offset}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if not data: break
                for d in data:
                    if d.get('epic_number'): db_epics.add(str(d['epic_number']).upper().strip())
                offset += len(data)
                if len(data) < 1000: break
        except Exception:
            break

    missing_in_booth = []
    running_serial = 0

    for idx in range(len(df)):
        vals = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v) and str(v).strip() != '']
        if not vals: continue
        row_str = ' '.join(vals)
        if any(h in row_str for h in ['GRADUATES\' CONSTITUENCY', 'Name of State', 'COMPONENTS OF THE ROLL', 'Table of Content', 'Name of the Elector', 'Sl.No', 'SINo']):
            continue

        # Look for EPIC
        m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?\d{5,8})', row_str)
        epic = clean_epic(m_ep.group(1)) if m_ep else None

        # Look for serial
        serial = None
        s_cand = vals[0].replace('\n', '').replace(' ', '').replace('#', '')
        if s_cand.isdigit():
            serial = int(s_cand)
        else:
            m_s = re.search(r'(?:#\s*|^)(\d{1,5})(?:\s|$)', row_str)
            if m_s: serial = int(m_s.group(1))

        if serial: running_serial = serial
        else: serial = running_serial + 1

        # Look for Name and Relative
        text_cells = [c for c in vals if not re.match(r'^[#\d\s]+$', c) and c not in ['Male', 'Female', 'M', 'F', 'Photo', 'Available', 'Karnataka']]
        name = clean_text(text_cells[0]) if len(text_cells) > 0 else None
        rel = clean_text(text_cells[1]) if len(text_cells) > 1 else None

        if name and epic and re.match(r'^[A-Z]{3}\d{7}$', epic):
            if epic not in db_epics:
                missing_in_booth.append({
                    "part_number": p_num,
                    "serial_number": serial,
                    "epic_number": epic,
                    "name": name,
                    "relative_name": rel,
                    "source_file": file_name,
                    "source_page_or_row": f"Row {idx + 1}"
                })

    return missing_in_booth

print("Scanning all 146 Excel files in parallel against live Supabase database...")

total_recovered = []
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(scan_file, fn): fn for fn in excel_files}
    for f in as_completed(futures):
        fn = futures[f]
        try:
            res = f.result()
            if res:
                total_recovered.extend(res)
                print(f"File {fn:22s} -> Found {len(res):3d} missing voters! (Running Total: {len(total_recovered)})")
        except Exception as e:
            print(f"File {fn} error: {e}")

print(f"\n=======================================================")
print(f"TOTAL MISSING VOTERS IDENTIFIED ACROSS ALL 146 EXCEL FILES: {len(total_recovered)}")
print(f"=======================================================")

out_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_missing_from_excel.csv'
pd.DataFrame(total_recovered).to_csv(out_path, index=False)
print(f"Saved full recovered dataset to {out_path}")
