import os
import sys
import json
import time
from supabase import create_client

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://hupyghfkxnbzkpkaxlcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1cHlnaGZreG5iemtwa2F4bGNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIzMDY5MCwiZXhwIjoyMTAyODA2NjkwfQ.7a4tJ68i-rxmRyj4BhWbh06nlFkz3DkvMuU6sYtNV4s"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

BOOTH_112 = {
    "district": "Chikkaballapur",
    "taluk": "Chickballapur",
    "ac_name": "Chikkaballapur",
    "part_number": "112",
    "polling_station_name": "Taluk Office, Chickballapur",
    "polling_address": "Nandi and Kasaba Hobli, Chickballapur Taluk, Chikkaballapura District, Karnataka"
}

with open("etl/part112_parsed_text.json", "r", encoding="utf-8") as f:
    parsed_voters = json.load(f)

print(f"Loaded {len(parsed_voters)} voters from cache.")

# Fetch existing DB records for Part 112 (IDs, serials, epics, names)
print("Fetching live Part 112 records from database...")
db_by_serial = {}
db_by_epic = {}
offset = 0
while True:
    try:
        res = sb.table('electors').select('id, serial_number, epic_number, name').eq('part_number', '112').range(offset, offset + 999).execute()
        if not res.data: break
        for r in res.data:
            if r['serial_number'] is not None:
                db_by_serial[r['serial_number']] = r
            if r['epic_number']:
                db_by_epic[r['epic_number'].strip().upper()] = r
        if len(res.data) < 1000: break
        offset += 1000
    except Exception as e:
        time.sleep(1)
        continue

print(f"DB Part 112: {len(db_by_serial)} unique serials, {len(db_by_epic)} unique EPICs.")

updated_count = 0
inserted_count = 0
to_insert_batch = []

for v in parsed_voters:
    ser = v['serial_number']
    epic = v['epic_number']
    name = v['name']
    rel = v['relative_name']
    age = v['age']
    sex = v['sex']
    addr = v['address']
    
    # 1. Check match by EPIC
    matched_row = None
    if epic and epic in db_by_epic:
        matched_row = db_by_epic[epic]
    elif ser and ser in db_by_serial:
        matched_row = db_by_serial[ser]
        
    if matched_row:
        # Check if row has dummy name or missing serial
        curr_name = matched_row.get('name') or ''
        curr_ser = matched_row.get('serial_number')
        
        needs_update = False
        update_data = {}
        
        if (curr_name.startswith('Voter ') or len(curr_name) <= 2) and name and len(name) > 2:
            update_data['name'] = name
            needs_update = True
        if rel and not matched_row.get('relative_name'):
            update_data['relative_name'] = rel
            needs_update = True
        if age and not matched_row.get('age'):
            update_data['age'] = age
            needs_update = True
        if sex and not matched_row.get('sex'):
            update_data['sex'] = sex
            needs_update = True
        if curr_ser is None and ser is not None:
            update_data['serial_number'] = ser
            needs_update = True
        if not matched_row.get('district'):
            update_data['district'] = BOOTH_112['district']
            update_data['taluk'] = BOOTH_112['taluk']
            update_data['ac_name'] = BOOTH_112['ac_name']
            needs_update = True
            
        if needs_update:
            try:
                sb.table('electors').update(update_data).eq('id', matched_row['id']).execute()
                updated_count += 1
            except Exception as e:
                pass
    else:
        # Completely missing from DB -> INSERT!
        new_row = {
            "part_number": "112",
            "serial_number": ser,
            "epic_number": epic,
            "name": name if name else None,
            "relative_name": rel if rel else None,
            "address": addr,
            "age": age,
            "sex": sex,
            "district": BOOTH_112['district'],
            "taluk": BOOTH_112['taluk'],
            "ac_name": BOOTH_112['ac_name'],
            "polling_station_name": BOOTH_112['polling_station_name'],
            "polling_address": BOOTH_112['polling_address'],
            "source_file": "112_1791587543.pdf.pdf"
        }
        to_insert_batch.append(new_row)
        if len(to_insert_batch) >= 100:
            try:
                sb.table('electors').insert(to_insert_batch).execute()
                inserted_count += len(to_insert_batch)
                to_insert_batch = []
            except Exception as e:
                print("Insert batch error:", e)
                to_insert_batch = []

if to_insert_batch:
    try:
        sb.table('electors').insert(to_insert_batch).execute()
        inserted_count += len(to_insert_batch)
    except Exception as e:
        print("Final insert batch error:", e)

print(f"\n==================================================")
print(f" PART 112 SYNC SUMMARY (Pages 1 to 282)")
print(f"==================================================")
print(f" Updated placeholder/incomplete records: {updated_count}")
print(f" Inserted completely missing voters:     {inserted_count}")
