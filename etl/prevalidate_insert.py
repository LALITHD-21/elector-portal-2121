import os
import sys
import json
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
sb = create_client(url, key)

df = pd.read_csv('etl/reports/missing_voters_to_sync.csv')
print(f"Loaded {len(df)} records from missing_voters_to_sync.csv")

# 1. Internal uniqueness in batch
dups_in_batch_epic = df[df['epic_number'].notna() & df['epic_number'].duplicated(keep=False)]
print(f"Duplicate EPICs within batch: {len(dups_in_batch_epic)}")

dups_in_batch_part_sno = df[df.duplicated(subset=['part_number', 'serial_number'], keep=False)]
print(f"Duplicate (part, serial) within batch: {len(dups_in_batch_part_sno)}")

# If any duplicates exist in batch, deduplicate keeping first
df_clean = df.drop_duplicates(subset=['part_number', 'serial_number']).copy()
if len(df_clean) < len(df):
    print(f"Deduplicated (part, serial): {len(df)} -> {len(df_clean)}")

# Deduplicate by EPIC keeping first
epics_seen = set()
clean_records = []
epic_drops = 0
for idx, r in df_clean.iterrows():
    ep = r['epic_number']
    if pd.notna(ep) and str(ep).strip():
        ep_clean = str(ep).strip().upper()
        if ep_clean in epics_seen:
            epic_drops += 1
            continue
        epics_seen.add(ep_clean)
        r['epic_number'] = ep_clean
    else:
        r['epic_number'] = None
    clean_records.append(r.to_dict())

print(f"Dropped duplicate EPICs in batch: {epic_drops}")
print(f"Clean candidate records: {len(clean_records)}")

# 2. Check collision against Supabase live table
# Query all existing EPICs in Supabase for these candidate epics
candidate_epics = [r['epic_number'] for r in clean_records if r.get('epic_number')]
print(f"Querying collisions against live DB for {len(candidate_epics)} EPICs...")

colliding_epics = set()
# Chunk queries by 1000
for i in range(0, len(candidate_epics), 1000):
    chunk = candidate_epics[i:i+1000]
    res = sb.from_('electors').select('epic_number').in_('epic_number', chunk).execute()
    for row in (res.data or []):
        colliding_epics.add(row['epic_number'])

print(f"Collisions found in live DB by EPIC: {len(colliding_epics)}")

# Check collisions by (part_number, serial_number)
parts_to_check = list(set(r['part_number'] for r in clean_records))
colliding_part_sno = set()
for p in parts_to_check:
    snos = [r['serial_number'] for r in clean_records if r['part_number'] == p]
    for i in range(0, len(snos), 1000):
        chunk_snos = snos[i:i+1000]
        res = sb.from_('electors').select('part_number, serial_number').eq('part_number', str(p)).in_('serial_number', chunk_snos).execute()
        for row in (res.data or []):
            colliding_part_sno.add((str(row['part_number']), row['serial_number']))

print(f"Collisions found in live DB by (part, serial): {len(colliding_part_sno)}")

# Final pure new records to insert
final_to_insert = []
for r in clean_records:
    ep = r.get('epic_number')
    p = str(r['part_number'])
    s = r['serial_number']
    if ep and ep in colliding_epics:
        continue
    if (p, s) in colliding_part_sno:
        continue
    final_to_insert.append(r)

print(f"\n==========================================")
print(f"FINAL GUARANTEED 0-COLLISION RECORDS TO INSERT: {len(final_to_insert)}")
print(f"==========================================")

with open('etl/reports/final_zero_collision_electors.json', 'w', encoding='utf-8') as f:
    json.dump(final_to_insert, f, indent=2, ensure_ascii=False)
