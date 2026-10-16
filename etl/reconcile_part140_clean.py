import os
import sys
import re
import openpyxl
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

excel_file = "electrol-portal-NEW-main/uptaed voter list/140_1791587656.xlsx"
electors_140 = parse_excel_part140(excel_file)
print(f"Extracted {len(electors_140)} authentic electors from {excel_file}")

# 1. First, purge artificial dummy rows in Part 140 (name is '#' or name starts with 'Voter ')
print("Purging dummy '#' and 'Voter...' records from Part 140...")
purged_hash = sb.table("electors").delete().eq("part_number", "140").eq("name", "#").execute()
print(f"Purged {len(purged_hash.data)} '#' rows.")
purged_voter = sb.table("electors").delete().eq("part_number", "140").ilike("name", "Voter%").execute()
print(f"Purged {len(purged_voter.data)} 'Voter...' rows.")

# 2. Now reconcile authentic electors
print("Reconciling authentic electors into Part 140...")
updated = 0
inserted = 0

for idx, el in enumerate(electors_140):
    ep = el["epic_number"]
    ser = el["serial_number"]
    nm = el["name"]
    
    # Try match by epic
    matched_id = None
    if ep:
        res_ep = sb.table("electors").select("id").eq("part_number", "140").eq("epic_number", ep).execute()
        if res_ep.data:
            matched_id = res_ep.data[0]["id"]
            
    # Try match by name if not matched by epic
    if not matched_id and nm:
        res_nm = sb.table("electors").select("id").eq("part_number", "140").ilike("name", nm).execute()
        if res_nm.data:
            matched_id = res_nm.data[0]["id"]
            
    # Try match by serial if still not matched
    if not matched_id and ser:
        res_ser = sb.table("electors").select("id").eq("part_number", "140").eq("serial_number", ser).execute()
        if res_ser.data:
            matched_id = res_ser.data[0]["id"]
            
    if matched_id:
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
        try:
            sb.table("electors").update(update_dict).eq("id", matched_id).execute()
            updated += 1
        except Exception as e:
            if "unique constraint" in str(e):
                update_dict.pop("epic_number", None)
                sb.table("electors").update(update_dict).eq("id", matched_id).execute()
                updated += 1
            else:
                print(f"Update error for {nm}: {e}")
    else:
        try:
            sb.table("electors").insert(el).execute()
            inserted += 1
        except Exception as e:
            if "unique constraint" in str(e):
                el_copy = dict(el)
                el_copy["epic_number"] = None
                sb.table("electors").insert(el_copy).execute()
                inserted += 1
            else:
                print(f"Insert error for {nm}: {e}")
        
    if (idx + 1) % 500 == 0 or (idx + 1) == len(electors_140):
        print(f"Reconciled {idx + 1}/{len(electors_140)} (Updated: {updated}, Inserted: {inserted})")

print("Part 140 reconciliation complete!")
