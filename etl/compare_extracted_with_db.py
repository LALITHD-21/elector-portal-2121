import os
import sys
import re
import json
import time
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

csv_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_extracted/all_excel_electors.csv'
df = pd.read_csv(csv_path, dtype={'part_number': str, 'serial_number': str})

# Filter records with standard EPIC and valid name
std_pattern = r'^[A-Z]{3}\d{7}$'
valid_mask = df['epic_number'].apply(lambda x: bool(re.match(std_pattern, str(x))) if pd.notna(x) else False)
valid_df = df[valid_mask].drop_duplicates(subset=['epic_number']).copy()
print(f"Loaded {len(valid_df):,} unique candidates with standard EPICs for database cross-check.")

# Check in chunks of 100 via Supabase REST API
headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}'
}

epics_list = valid_df['epic_number'].tolist()
chunk_size = 100
chunks = [epics_list[i:i+chunk_size] for i in range(0, len(epics_list), chunk_size)]
print(f"Divided into {len(chunks):,} chunks of {chunk_size} EPICs for parallel live check...")

already_in_db_epics = set()
start_check = time.time()
completed = 0

def check_chunk(chunk):
    epic_str = ','.join(chunk)
    url = f"{SUPABASE_URL}/rest/v1/electors?epic_number=in.({epic_str})&select=epic_number"
    req = urllib.request.Request(url, headers=headers)
    found = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            found = [str(d['epic_number']).upper().strip() for d in data if d.get('epic_number')]
    except Exception as e:
        pass
    return found

with ThreadPoolExecutor(max_workers=12) as executor:
    futures = [executor.submit(check_chunk, c) for c in chunks]
    for f in as_completed(futures):
        res = f.result()
        already_in_db_epics.update(res)
        completed += 1
        if completed % 200 == 0 or completed == len(chunks):
            print(f"Checked {completed}/{len(chunks)} chunks... Matched {len(already_in_db_epics):,} in DB so far.", flush=True)

elapsed = time.time() - start_check
print(f"\nLive database check completed in {elapsed:.2f} seconds!")
print(f"Total Candidates Evaluated: {len(valid_df):,}")
print(f"Matched Already in Database: {len(already_in_db_epics):,}")

# Filter truly missing voters
is_in_db = valid_df['epic_number'].isin(already_in_db_epics)
df_already = valid_df[is_in_db]
df_new_missing = valid_df[~is_in_db].copy()

print(f"TRULY MISSING NEW VOTERS IDENTIFIED: {len(df_new_missing):,}")

# Tag with unified batch ID and timestamp
batch_id = 'batch_all_booths_recovery_20261016'
df_new_missing['import_batch_id'] = batch_id
df_new_missing['imported_at'] = datetime.now().isoformat()

out_dir = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/etl/reports/all_booths_recovery_set'
os.makedirs(out_dir, exist_ok=True)

df_new_missing.to_csv(os.path.join(out_dir, 'new_valid_missing_voters.csv'), index=False)
df_new_missing.to_excel(os.path.join(out_dir, 'new_valid_missing_voters.xlsx'), index=False)
df_already.to_csv(os.path.join(out_dir, 'already_in_db.csv'), index=False)

summary_md = f"""# All-Booth Master Recovery Summary
- **Audit Timestamp**: {datetime.now().isoformat()}
- **Total Unique Candidates with Valid Standard EPICs Extracted**: {len(valid_df):,}
- **Existing Voters Verified in Database**: {len(already_in_db_epics):,}
- **TRULY MISSING VOTERS RECOVERED (Ready for Insert)**: {len(df_new_missing):,}
- **Reports Saved to**: `{out_dir}`
"""
with open(os.path.join(out_dir, 'summary.md'), 'w', encoding='utf-8') as f:
    f.write(summary_md)

print("\n" + summary_md)
print("Top 15 Booths with Most Missing Voters Recovered:")
print(df_new_missing['part_number'].value_counts().head(15))
