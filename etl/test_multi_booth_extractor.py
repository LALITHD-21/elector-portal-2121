import os
import sys
import re
import json
import urllib.request
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

excel_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/uptaed voter list'

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

def parse_excel_booth(excel_file):
    p_num = excel_file.split('_')[0]
    fp = os.path.join(excel_dir, excel_file)
    df = pd.read_excel(fp, dtype=str)
    
    voters = []
    for idx in range(len(df)):
        row_vals = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v) and str(v).strip() != '']
        if not row_vals: continue
        row_str = ' '.join(row_vals)
        
        # Skip header rows
        if any(h in row_str for h in ['GRADUATES\' CONSTITUENCY', 'Name of State', 'COMPONENTS OF THE ROLL', 'Table of Content', 'Name of the Elector']):
            continue
            
        # Parse serial: usually in first or second column or '# <num>'
        serial = None
        s_cand = row_vals[0]
        # remove newlines in serial like '104\n5' -> '1045'
        s_clean = s_cand.replace('\n', '').replace(' ', '').replace('#', '')
        if s_clean.isdigit():
            serial = int(s_clean)
        else:
            m_s = re.search(r'(?:#\s*|^)(\d{1,5})(?:\s|$)', row_str)
            if m_s: serial = int(m_s.group(1))
            
        # Parse EPIC
        m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?[A-Za-z0-9]{5,9})', row_str)
        epic = clean_epic(m_ep.group(1)) if m_ep else None
        
        # Parse Age & Sex
        m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', row_str)
        age = int(m_age.group(1)) if m_age else None
        
        sex = None
        if re.search(r'\b(Female|F)\b', row_str, re.IGNORECASE):
            sex = 'F'
        elif re.search(r'\b(Male|M)\b', row_str, re.IGNORECASE):
            sex = 'M'
            
        # Name: typically column 1 or 2
        name = None
        rel = None
        if len(row_vals) >= 3:
            # find first cell with letters that is not a serial
            text_cells = [c for c in row_vals if not re.match(r'^[#\d\s]+$', c) and c not in ['Male', 'Female', 'M', 'F', 'Photo', 'Available', 'Karnataka']]
            if len(text_cells) > 0: name = clean_text(text_cells[0])
            if len(text_cells) > 1: rel = clean_text(text_cells[1])
            
        if name and epic and serial:
            voters.append({
                "part_number": p_num,
                "serial_number": serial,
                "epic_number": epic,
                "name": name,
                "relative_name": rel,
                "age": age,
                "sex": sex,
                "source_file": excel_file,
                "source_page_or_row": f"Row {idx + 1}"
            })
            
    return voters

test_files = ['33_1791587153.xlsx', '34_1791587153.xlsx', '35_1791587153.xlsx', '100_1791587428.xlsx']
for tf in test_files:
    voters = parse_excel_booth(tf)
    p = tf.split('_')[0]
    
    # check against DB
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/electors?part_number=eq.{p}&select=epic_number", headers=headers)
    with urllib.request.urlopen(req) as resp:
        db_data = json.loads(resp.read().decode('utf-8'))
        db_epics = {str(d['epic_number']).upper().strip() for d in db_data if d.get('epic_number')}
        
    missing = [v for v in voters if v['epic_number'] not in db_epics]
    print(f"File {tf:22s} | Parsed: {len(voters):4d} voters | In DB: {len(db_epics):4d} | Truly Missing in DB: {len(missing):3d}")
    if missing:
        print(f"   Sample missing: Serial #{missing[0]['serial_number']} | {missing[0]['epic_number']} | {missing[0]['name']}")
