import os
import sys
import json
import math
import time
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
sb = create_client(url, key)

with open('etl/stations_dump.json', 'r', encoding='utf-8') as f:
    stations = json.load(f)
station_by_part = {}
for s in stations:
    p = str(s.get('part_number'))
    if p not in station_by_part:
        station_by_part[p] = s

with open('etl/reports/final_zero_collision_electors.json', 'r', encoding='utf-8') as f:
    raw_records = json.load(f)

print(f"Loaded {len(raw_records)} records to insert.")

def sanitize_str(v, max_len=None):
    if v is None: return None
    if isinstance(v, float) and (math.isnan(v) or v != v): return None
    s = str(v).strip()
    if not s or s.lower() in ['nan', 'none', 'null', 'na', 'n/a']:
        return None
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s

cleaned_to_insert = []
for r in raw_records:
    part_str = str(r.get('part_number'))
    st_meta = station_by_part.get(part_str, {})
    
    # Age check
    age_raw = r.get('age')
    age_val = None
    if age_raw is not None and not (isinstance(age_raw, float) and math.isnan(age_raw)):
        try:
            ai = int(age_raw)
            if 18 <= ai <= 120:
                age_val = ai
        except:
            age_val = None

    # Sex check
    sex_raw = sanitize_str(r.get('sex'))
    sex_val = sex_raw if sex_raw in ['M', 'F'] else None

    # EPIC check
    epic_val = sanitize_str(r.get('epic_number'), max_len=11)
    if epic_val:
        epic_val = epic_val.upper()

    # Serial number
    sno_raw = r.get('serial_number')
    sno_val = None
    if sno_raw is not None and not (isinstance(sno_raw, float) and math.isnan(sno_raw)):
        try:
            sno_val = int(sno_raw)
        except:
            sno_val = None

    item = {
        'serial_number': sno_val,
        'epic_number': epic_val,
        'name': sanitize_str(r.get('name')) or 'Unknown',
        'relative_name': sanitize_str(r.get('relative_name')),
        'address': sanitize_str(r.get('address')),
        'qualification': sanitize_str(r.get('qualification'), max_len=100),
        'occupation': sanitize_str(r.get('occupation'), max_len=100),
        'age': age_val,
        'sex': sex_val,
        'part_number': part_str,
        'polling_station_name': st_meta.get('name') or f"Polling Station Part {part_str}",
        'polling_address': st_meta.get('address') or sanitize_str(r.get('address')),
        'district': sanitize_str(r.get('district')),
        'taluk': sanitize_str(r.get('taluk')),
        'ac_name': sanitize_str(r.get('taluk'))
    }
    cleaned_to_insert.append(item)

print(f"Prepared {len(cleaned_to_insert)} fully sanitized records.")

# Test inserting batch 1 (first 10 records)
test_batch = cleaned_to_insert[:10]
res = sb.from_('electors').insert(test_batch).execute()
print(f"Test batch of 10 successfully inserted! Returned {len(res.data)} rows.")

BATCH_SIZE = 200
remaining = cleaned_to_insert[10:]
total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE

success_count = 10
errors = []

for i in range(total_batches):
    batch = remaining[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
    try:
        res = sb.from_('electors').insert(batch).execute()
        success_count += len(res.data or [])
        if (i + 1) % 5 == 0 or (i + 1) == total_batches:
            print(f"Batch {i+1}/{total_batches}: {success_count}/{len(cleaned_to_insert)} inserted successfully.")
    except Exception as e:
        print(f"Error in batch {i+1}: {e}")
        errors.append({'batch': i+1, 'error': str(e)})

print(f"\n==========================================")
print(f"INSERTION COMPLETE!")
print(f"Total Successfully Inserted: {success_count} missing electors")
print(f"Total Errors: {len(errors)}")
print(f"==========================================")
