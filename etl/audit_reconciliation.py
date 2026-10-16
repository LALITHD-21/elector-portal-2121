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

parts = ['10', '13', '28', '36', '72']
all_extracted = []
for p in parts:
    with open(f'etl/reports/part_{p}_extracted.json', 'r', encoding='utf-8') as f:
        voters = json.load(f)
        all_extracted.extend(voters)

print(f"Total extracted voters from 5 verified digital rolls: {len(all_extracted)}")

# Check against live electors table for each part
reconciliation_summary = []
all_missing_new_records = []

for p in parts:
    part_voters = [v for v in all_extracted if str(v['part_number']) == str(p)]
    
    # Query all electors currently in Supabase for this part
    # Paginate using range
    db_records = []
    page_size = 1000
    curr_start = 0
    while True:
        res = sb.from_('electors').select('serial_number, epic_number, name').eq('part_number', p).range(curr_start, curr_start + page_size - 1).execute()
        rows = res.data or []
        db_records.extend(rows)
        if len(rows) < page_size:
            break
        curr_start += page_size

    db_serials = set(r['serial_number'] for r in db_records if r.get('serial_number'))
    db_epics = set(r['epic_number'] for r in db_records if r.get('epic_number'))

    # Compare
    new_by_serial = [v for v in part_voters if v['serial_number'] not in db_serials]
    existing_by_serial = [v for v in part_voters if v['serial_number'] in db_serials]
    
    # Filter those whose EPIC is also not in db
    truly_new_voters = [v for v in new_by_serial if not v.get('epic_number') or v['epic_number'] not in db_epics]
    all_missing_new_records.extend(truly_new_voters)

    reconciliation_summary.append({
        'part': p,
        'official_pdf_count': len(part_voters),
        'currently_in_db': len(db_records),
        'already_matched': len(existing_by_serial),
        'missing_from_db': len(truly_new_voters),
        'potential_duplicates_prevented': len(part_voters) - len(truly_new_voters)
    })

print("\n=== RECONCILIATION SUMMARY (OFFICIAL PDF vs DATABASE) ===")
print(f"{'Part':>5} | {'Official PDF':>12} | {'Current in DB':>13} | {'Already in DB':>13} | {'MISSING (NEW)':>13} | {'Dups Prevented':>14}")
print("-" * 80)
for r in reconciliation_summary:
    print(f"{r['part']:>5} | {r['official_pdf_count']:>12} | {r['currently_in_db']:>13} | {r['already_matched']:>13} | {r['missing_from_db']:>13} | {r['potential_duplicates_prevented']:>14}")

total_missing = sum(r['missing_from_db'] for r in reconciliation_summary)
print("-" * 80)
print(f"TOTAL MISSING VOTERS FOUND & READY TO SYNC: {total_missing}")

with open('etl/reports/reconciliation_missing_audit.json', 'w', encoding='utf-8') as f:
    json.dump({
        'summary': reconciliation_summary,
        'total_new_voters': len(all_missing_new_records),
        'new_records_sample': all_missing_new_records[:20]
    }, f, indent=2, ensure_ascii=False)

pd.DataFrame(all_missing_new_records).to_csv('etl/reports/missing_voters_to_sync.csv', index=False)
print("Saved missing records dataset to etl/reports/missing_voters_to_sync.csv")
