import os
import sys
import re
import json
import time
import urllib.request
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase environment variables missing!")
    sys.exit(1)

valid_csv = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase4_dry_run_reconciliation/new_valid.csv'
if not os.path.exists(valid_csv):
    print(f"Error: {valid_csv} not found!")
    sys.exit(1)

df = pd.read_csv(valid_csv)
print(f"Loaded {len(df)} validated new voters from {valid_csv}")

# Step 1: Baseline count check
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

# Prepare records
records_to_insert = []
for _, r in df.iterrows():
    serial = int(r['serial_number']) if pd.notna(r['serial_number']) else None
    age = int(r['age']) if pd.notna(r['age']) else None
    
    # Store page info inside source_file for provenance
    src_file = str(r.get('source_file') or '')
    src_page = str(r.get('source_page_or_row') or '')
    combined_source = f"{src_file} ({src_page})" if src_page else src_file
    
    rec = {
        "serial_number": serial,
        "epic_number": str(r['epic_number']).strip().upper(),
        "name": str(r['name']).strip(),
        "relative_name": str(r['relative_name']).strip() if pd.notna(r['relative_name']) else None,
        "address": str(r['address']).strip() if pd.notna(r['address']) else None,
        "qualification": str(r['qualification']).strip() if pd.notna(r['qualification']) else None,
        "occupation": str(r['occupation']).strip() if pd.notna(r['occupation']) else None,
        "age": age,
        "sex": str(r['sex']).strip().upper() if pd.notna(r['sex']) else None,
        "part_number": str(r['part_number']).strip(),
        "district": str(r.get('district') or '').strip() or None,
        "taluk": str(r.get('taluk') or '').strip() or None,
        "ac_name": str(r.get('ac_name') or '').strip() or None,
        "polling_station_name": str(r.get('polling_station_name') or '').strip() or None,
        "polling_address": str(r.get('polling_address') or '').strip() or None,
        "source_file": combined_source,
        "import_batch_id": str(r['import_batch_id']).strip(),
        "imported_at": str(r['imported_at']).strip()
    }
    records_to_insert.append(rec)

print(f"Prepared {len(records_to_insert)} payload objects.")

# Step 2: Transactional Insert in chunks with resolution=ignore-duplicates
headers_insert = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=ignore-duplicates,return=representation'
}

chunk_size = 100
total_inserted = 0
inserted_records = []

print("\nStarting controlled transactional insert...")
for i in range(0, len(records_to_insert), chunk_size):
    chunk = records_to_insert[i:i+chunk_size]
    payload_bytes = json.dumps(chunk).encode('utf-8')
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number",
        data=payload_bytes,
        headers=headers_insert,
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        resp_data = json.loads(resp.read().decode('utf-8'))
        total_inserted += len(resp_data)
        inserted_records.extend(resp_data)
        print(f"Chunk {i//chunk_size + 1}: submitted {len(chunk)}, inserted {len(resp_data)} (Running Total: {total_inserted})")

# Step 3: Post-Insert Count Verification
post_count = get_db_count()
delta = post_count - baseline_count

print("\n=== POST-INSERT RECONCILIATION ===")
print(f"Baseline Count: {baseline_count}")
print(f"Post-Insert Count: {post_count}")
print(f"Observed Delta: +{delta}")
print(f"Expected Inserted: {len(records_to_insert)}")
print(f"Actual Records Returned by DB Insert: {total_inserted}")

if delta == len(records_to_insert):
    print("SUCCESS: Delta matches expected count exactly (100% matched)!")
else:
    print(f"Notice: Delta is {delta}, expected {len(records_to_insert)}. Difference accounted for by ON CONFLICT DO NOTHING: {len(records_to_insert) - delta}")

# Step 4: Idempotency Verification Re-run
print("\n=== IDEMPOTENCY VERIFICATION ===")
print("Re-running identical insert payload against electors table...")
re_inserted = 0
for i in range(0, len(records_to_insert), chunk_size):
    chunk = records_to_insert[i:i+chunk_size]
    payload_bytes = json.dumps(chunk).encode('utf-8')
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number",
        data=payload_bytes,
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
    print("SUCCESS: Pipeline is strictly 100% idempotent!")
else:
    print("WARNING: Pipeline idempotency check failed!")

# Save inserted IDs report
report_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/phase5_insert_results'
os.makedirs(report_dir, exist_ok=True)
with open(os.path.join(report_dir, 'inserted_electors.json'), 'w', encoding='utf-8') as f:
    json.dump(inserted_records, f, indent=2)

print(f"\nSaved insert verification logs to {report_dir}")
