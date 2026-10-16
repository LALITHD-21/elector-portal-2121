import os
import sys
import re
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://hupyghfkxnbzkpkaxlcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1cHlnaGZreG5iemtwa2F4bGNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIzMDY5MCwiZXhwIjoyMTAyODA2NjkwfQ.7a4tJ68i-rxmRyj4BhWbh06nlFkz3DkvMuU6sYtNV4s"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

BOOTH_140 = {
    "district": "Kolar",
    "taluk": "Kolar",
    "ac_name": "Kolar",
    "part_number": "140",
    "polling_station_name": "Taluk Office, Kolar",
    "polling_address": "Kolar Entire Kasba Hobli, Kolar Taluk, Kolar District, Karnataka"
}

def clean_str(s):
    if s is None: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^[\s\.,_\-!#~;:\'\"\|]+|[\s\.,_\-!#~;:\'\"\|]+$', '', s).strip()
    if not s or s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', '#']: return None
    return s

def clean_epic(s):
    if s is None: return None
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

def parse_excel_part140(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    sheet = wb.active
    
    electors = []
    for idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if idx < 8: continue
        vals = [c for c in row if c is not None]
        if len(vals) < 4: continue
        
        v_str = ' '.join([str(c) for c in vals])
        if 'Name of the Elector' in v_str or 'SINo' in v_str or 'Type of revision' in v_str:
            continue
            
        ser = None
        start_idx = 0
        if isinstance(vals[0], int):
            ser = vals[0]
            start_idx = 1
        elif isinstance(vals[0], str):
            m_s = re.search(r'\b(\d{1,5})\b', vals[0])
            if m_s:
                ser = int(m_s.group(1))
                start_idx = 1
            elif vals[0].strip() == '#' and len(vals) > 1 and (isinstance(vals[1], int) or re.search(r'^\d+$', str(vals[1]).strip())):
                ser = int(str(vals[1]).strip())
                start_idx = 2
                
        if start_idx >= len(vals): continue
        
        name = clean_str(vals[start_idx])
        rel = clean_str(vals[start_idx + 1]) if start_idx + 1 < len(vals) else None
        
        addr, qual, occ, age, sex, epic = None, None, None, None, None, None
        
        remaining = vals[start_idx + 2:]
        for item in remaining:
            item_str = str(item).strip()
            if isinstance(item, int) and 18 <= item <= 110 and age is None:
                age = item
            elif isinstance(item, str) and re.match(r'^\d{2}$', item_str) and 18 <= int(item_str) <= 110 and age is None:
                age = int(item_str)
            elif item_str.upper() in ['M', 'F', 'O', 'MALE', 'FEMALE']:
                sex = item_str[0].upper()
            elif re.search(r'[A-Za-z]{2,4}\d{6,8}', item_str) or 'KT/' in item_str:
                epic = clean_epic(item_str)
            elif any(k in item_str.lower() for k in ['(vtc)', '(post)', '(dist)', '(tq)', 'road', 'layout', 'nagar', 'kolar', 'street', 'beedi']):
                if addr is None: addr = clean_str(item_str)
                else: addr += ' ' + clean_str(item_str)
            elif any(k in item_str.lower() for k in ['ba', 'bcom', 'bsc', 'be', 'btech', 'ma', 'mcom', 'msc', 'bed', 'llb', 'phd']):
                qual = clean_str(item_str)
            elif any(k in item_str.lower() for k in ['teacher', 'engineer', 'advocate', 'lecturer', 'business', 'house wife', 'professor', 'doctor']):
                occ = clean_str(item_str)
                
        if not epic:
            epic = clean_epic(v_str)
            
        if name or epic or ser:
            electors.append({
                "serial_number": ser,
                "epic_number": epic,
                "name": name,
                "relative_name": rel,
                "address": addr,
                "qualification": qual,
                "occupation": occ,
                "age": age,
                "sex": sex,
                "district": BOOTH_140["district"],
                "taluk": BOOTH_140["taluk"],
                "ac_name": BOOTH_140["ac_name"],
                "part_number": BOOTH_140["part_number"],
                "polling_station_name": BOOTH_140["polling_station_name"],
                "polling_address": BOOTH_140["polling_address"],
                "source_file": "140_1791587656.xlsx"
            })
            
    return electors

print("Step 1: Reading 140 Excel...", flush=True)
excel_file = "electrol-portal-NEW-main/uptaed voter list/140_1791587656.xlsx"
electors_140 = parse_excel_part140(excel_file)
print(f"Extracted {len(electors_140)} authentic electors from {excel_file}", flush=True)

print("Step 2: Fetching all existing Part 140 records from Supabase into memory...", flush=True)
existing_records = []
PAGE_SIZE = 1000
offset = 0
while True:
    r = sb.table("electors").select("id, serial_number, epic_number, name").eq("part_number", "140").range(offset, offset + PAGE_SIZE - 1).execute()
    existing_records.extend(r.data)
    if len(r.data) < PAGE_SIZE:
        break
    offset += PAGE_SIZE

print(f"Loaded {len(existing_records)} existing records for Part 140.", flush=True)

by_epic = {}
by_name = {}
by_ser = {}
for r in existing_records:
    r_id = r["id"]
    if r.get("epic_number"):
        by_epic[r["epic_number"].upper()] = r_id
    if r.get("name"):
        nm_clean = r["name"].strip().lower().replace('#', '').strip()
        if nm_clean and nm_clean not in by_name:
            by_name[nm_clean] = r_id
    if r.get("serial_number"):
        by_ser[r["serial_number"]] = r_id

print("Step 3: Planning updates and inserts for remaining records...", flush=True)
tasks_update = []
tasks_insert = []

used_ids = set()

# Get IDs of records already reconciled
already_done_serials = set()
offset = 0
while True:
    r = sb.table("electors").select("serial_number").eq("part_number", "140").eq("source_file", "140_1791587656.xlsx").range(offset, offset + 999).execute()
    for row in r.data:
        if row.get("serial_number"):
            already_done_serials.add(row["serial_number"])
    if len(r.data) < 1000:
        break
    offset += 1000

print(f"Found {len(already_done_serials)} already reconciled serials.", flush=True)

for el in electors_140:
    ser = el["serial_number"]
    if ser in already_done_serials:
        continue
        
    ep = el["epic_number"]
    nm = el["name"]
    nm_clean = nm.strip().lower() if nm else None
    
    matched_id = None
    if ep and ep.upper() in by_epic:
        matched_id = by_epic[ep.upper()]
    elif nm_clean and nm_clean in by_name:
        cand_id = by_name[nm_clean]
        if cand_id not in used_ids:
            matched_id = cand_id
    elif ser and ser in by_ser:
        cand_id = by_ser[ser]
        if cand_id not in used_ids:
            matched_id = cand_id
            
    if matched_id:
        used_ids.add(matched_id)
        update_dict = {
            "serial_number": el["serial_number"],
            "name": el["name"],
            "relative_name": el["relative_name"],
            "age": el["age"],
            "sex": el["sex"],
            "address": el["address"],
            "qualification": el["qualification"],
            "occupation": el["occupation"],
            "district": el["district"],
            "taluk": el["taluk"],
            "ac_name": el["ac_name"],
            "polling_station_name": el["polling_station_name"],
            "polling_address": el["polling_address"],
            "source_file": el["source_file"]
        }
        if el["epic_number"]:
            update_dict["epic_number"] = el["epic_number"]
        tasks_update.append((matched_id, update_dict))
    else:
        tasks_insert.append(el)

print(f"Remaining updates: {len(tasks_update)}, Remaining inserts: {len(tasks_insert)}", flush=True)

def do_update(item):
    matched_id, udict = item
    for attempt in range(3):
        try:
            sb.table("electors").update(udict).eq("id", matched_id).execute()
            return True
        except Exception as e:
            if "unique constraint" in str(e):
                udict.pop("epic_number", None)
                try:
                    sb.table("electors").update(udict).eq("id", matched_id).execute()
                    return True
                except:
                    return False
            import time
            time.sleep(1)
    return False

updated_cnt = 0
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(do_update, item) for item in tasks_update]
    for idx, f in enumerate(as_completed(futures)):
        if f.result():
            updated_cnt += 1
        if (idx + 1) % 100 == 0 or (idx + 1) == len(futures):
            print(f"Updates progress: {idx + 1}/{len(futures)} ({updated_cnt} success)", flush=True)

def do_insert(el):
    for attempt in range(3):
        try:
            sb.table("electors").insert(el).execute()
            return True
        except Exception as e:
            if "unique constraint" in str(e):
                el_copy = dict(el)
                el_copy["epic_number"] = None
                try:
                    sb.table("electors").insert(el_copy).execute()
                    return True
                except:
                    return False
            import time
            time.sleep(1)
    return False

inserted_cnt = 0
if tasks_insert:
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(do_insert, el) for el in tasks_insert]
        for idx, f in enumerate(as_completed(futures)):
            if f.result():
                inserted_cnt += 1
            if (idx + 1) % 100 == 0 or (idx + 1) == len(futures):
                print(f"Inserts progress: {idx + 1}/{len(futures)} ({inserted_cnt} success)", flush=True)

print(f"Fast Part 140 reconciliation complete! (Updated: {updated_cnt}, Inserted: {inserted_cnt})", flush=True)
