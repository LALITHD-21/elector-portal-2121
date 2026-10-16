import os
import sys
import re
import json
import time
import urllib.request
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

csv_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/master_recovery_final/new_valid_master.csv'
df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} validated master recovery electors from {csv_path}")

# Baseline DB count check
def get_db_count():
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Prefer': 'count=exact',
        'Range-Unit': 'items',
        'Range': '0-0'
    }
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/electors?select=id", headers=headers)
    with urllib.request.urlopen(req) as resp:
        cr = resp.headers.get('content-range')
        return int(cr.split('/')[1]) if cr else 0

baseline_count = get_db_count()
print(f"Baseline Database Count: {baseline_count}")

# Prepare insert payload
payload = []
for _, r in df.iterrows():
    serial = int(r['serial_number']) if pd.notna(r.get('serial_number')) and str(r['serial_number']).strip().isdigit() else None
    age = int(float(r['age'])) if pd.notna(r.get('age')) and str(r['age']).strip() != '' else None
    
    src_file = str(r.get('source_file') or '')
    src_loc = str(r.get('source_page_or_row') or '')
    combined_source = f"{src_file} ({src_loc})" if src_loc else src_file
    
    rec = {
        "serial_number": serial,
        "epic_number": str(r['epic_number']).strip().upper(),
        "name": str(r['name']).strip(),
        "relative_name": str(r['relative_name']).strip() if pd.notna(r.get('relative_name')) else None,
        "address": str(r['address']).strip() if pd.notna(r.get('address')) else None,
        "qualification": str(r['qualification']).strip() if pd.notna(r.get('qualification')) else None,
        "occupation": str(r['occupation']).strip() if pd.notna(r.get('occupation')) else None,
        "age": age,
        "sex": str(r['sex']).strip().upper() if pd.notna(r.get('sex')) else None,
        "part_number": str(r['part_number']).strip(),
        "source_file": combined_source,
        "import_batch_id": str(r['import_batch_id']).strip(),
        "imported_at": str(r['imported_at']).strip()
    }
    payload.append(rec)

print(f"Prepared {len(payload)} validated payloads for insertion.")

# Transactional insert in chunks
headers_insert = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=ignore-duplicates,return=representation'
}

chunk_size = 100
total_inserted = 0
inserted_records = []

print("\nStarting controlled transactional insertion...")
for i in range(0, len(payload), chunk_size):
    chunk = payload[i:i+chunk_size]
    data_bytes = json.dumps(chunk).encode('utf-8')
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number",
        data=data_bytes,
        headers=headers_insert,
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        resp_data = json.loads(resp.read().decode('utf-8'))
        total_inserted += len(resp_data)
        inserted_records.extend(resp_data)
        print(f"Chunk {i//chunk_size + 1}: submitted {len(chunk)}, inserted {len(resp_data)} (Running Total: {total_inserted})")

# Post-insert count verification
post_count = get_db_count()
delta = post_count - baseline_count

print("\n=== POST-INSERT RECONCILIATION ===")
print(f"Baseline Count: {baseline_count}")
print(f"Post-Insert Count: {post_count}")
print(f"Observed Delta: +{delta}")
print(f"Expected Inserted: {len(payload)}")
print(f"Actual Records Returned by DB Insert: {total_inserted}")

# Idempotency re-run verification
print("\n=== IDEMPOTENCY RE-RUN VERIFICATION ===")
re_inserted = 0
for i in range(0, len(payload), chunk_size):
    chunk = payload[i:i+chunk_size]
    data_bytes = json.dumps(chunk).encode('utf-8')
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number",
        data=data_bytes,
        headers=headers_insert,
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        resp_data = json.loads(resp.read().decode('utf-8'))
        re_inserted += len(resp_data)

print(f"Idempotency Re-run Result: Inserted {re_inserted} rows (Expected: 0).")
final_count = get_db_count()
print(f"Final Count after idempotency run: {final_count} (Delta: {final_count - post_count})")

if re_inserted == 0 and final_count == post_count:
    print("SUCCESS: Master recovery pipeline is strictly 100% idempotent!")
else:
    print("WARNING: Idempotency check reported unexpected inserts.")

# Save verification log
out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/master_recovery_final'
with open(os.path.join(out_dir, 'inserted_electors.json'), 'w', encoding='utf-8') as f:
    json.dump(inserted_records, f, indent=2)

print(f"\nSaved insert verification log to {out_dir}/inserted_electors.json")
