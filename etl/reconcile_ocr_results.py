import os
import sys
import json
import re
import pandas as pd
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_helper import get_supabase

sys.stdout.reconfigure(encoding='utf-8')

def reconcile_part(part_num, json_files, output_prefix):
    print(f"=== Reconciling OCR Results for Part {part_num} ===")
    all_extracted = []
    seen_keys = set()

    for jf in json_files:
        if not os.path.exists(jf):
            print(f"Warning: File not found: {jf}")
            continue
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"Loaded {len(data)} records from {jf}")
            for r in data:
                # Deduplicate by (part, serial, epic)
                k = (r.get('part_number'), r.get('serial_number'), r.get('epic_number'))
                if k not in seen_keys:
                    seen_keys.add(k)
                    all_extracted.append(r)

    print(f"Total unique records extracted from OCR: {len(all_extracted)}")
    all_extracted.sort(key=lambda r: (r.get('serial_number') or 0))

    # Fetch existing electors from Supabase for this part
    sb = get_supabase()
    all_db = []
    start = 0
    while True:
        res = sb.table('electors').select('id, serial_number, epic_number, name, relative_name').eq('part_number', str(part_num)).range(start, start + 999).execute()
        if not res.data: break
        all_db.extend(res.data)
        if len(res.data) < 1000: break
        start += 1000

    print(f"Total existing records in Supabase for Part {part_num}: {len(all_db)}")
    db_by_epic = {r['epic_number'].upper(): r for r in all_db if r.get('epic_number')}
    db_by_serial = {r['serial_number']: r for r in all_db if r.get('serial_number')}

    new_valid = []
    already_in_db = []
    quarantine = []

    epic_pattern = re.compile(r'^[A-Z]{3}\d{7}$')

    for r in all_extracted:
        ep = (r.get('epic_number') or '').upper().strip()
        sno = r.get('serial_number')
        name = (r.get('name') or '').strip()

        # Check if valid EPIC
        if not ep or not epic_pattern.match(ep):
            quarantine.append({**r, 'reason': 'Invalid or missing EPIC format'})
            continue

        if not name or name in ['-', '.', 'None', 'Photo']:
            # Has valid EPIC, but name needs check
            if r.get('relative_name'):
                name = r.get('relative_name') # Fallback if name was blank in roll

        # Check if already in DB
        if ep in db_by_epic:
            already_in_db.append({
                **r,
                'db_id': db_by_epic[ep]['id'],
                'db_serial': db_by_epic[ep]['serial_number'],
                'db_name': db_by_epic[ep]['name']
            })
        else:
            new_valid.append(r)

    os.makedirs('etl/reports', exist_ok=True)
    out_valid_csv = f'etl/reports/{output_prefix}_new_valid.csv'
    out_existing_csv = f'etl/reports/{output_prefix}_already_in_db.csv'
    out_quarantine_csv = f'etl/reports/{output_prefix}_quarantine.csv'
    out_rollback_sql = f'etl/reports/{output_prefix}_rollback.sql'

    pd.DataFrame(new_valid).to_csv(out_valid_csv, index=False)
    pd.DataFrame(already_in_db).to_csv(out_existing_csv, index=False)
    pd.DataFrame(quarantine).to_csv(out_quarantine_csv, index=False)

    batch_tag = f"batch_ocr_p{part_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with open(out_rollback_sql, 'w', encoding='utf-8') as f:
        f.write(f"-- Rollback SQL for Part {part_num} OCR Import\n")
        f.write(f"DELETE FROM electors WHERE part_number = '{part_num}' AND import_batch_id = '{batch_tag}';\n")

    print("\n=== RECONCILIATION SUMMARY ===")
    print(f"Total Extracted: {len(all_extracted)}")
    print(f"Already in DB:   {len(already_in_db)}")
    print(f"NEW VALID:       {len(new_valid)} (Ready for insertion)")
    print(f"Quarantine:      {len(quarantine)} (Ambiguous / OCR errors)")
    print(f"Reports saved to:")
    print(f"  - {out_valid_csv}")
    print(f"  - {out_existing_csv}")
    print(f"  - {out_quarantine_csv}")
    print(f"  - {out_rollback_sql}")

    return {
        'batch_tag': batch_tag,
        'total': len(all_extracted),
        'already_in_db': len(already_in_db),
        'new_valid': len(new_valid),
        'quarantine': len(quarantine)
    }

if __name__ == '__main__':
    reconcile_part('32', ['etl/reports/p32_batch1.json', 'etl/reports/p32_batch2.json'], 'part32_ocr')
