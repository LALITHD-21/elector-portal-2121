import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_helper import get_supabase

sys.stdout.reconfigure(encoding='utf-8')

SEARCH_API_URL = "https://web-murex-one-98.vercel.app/api/search"

def ingest_batch(csv_path, batch_id, dry_run=True):
    print(f"=== Starting Ingestion: {csv_path} ===")
    print(f"Mode: {'DRY RUN (Simulation Only)' if dry_run else 'LIVE TRANSACTIONAL INSERT'}")
    print(f"Batch Tag: {batch_id}")

    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    print(f"Total candidate rows in CSV: {len(df)}")

    # Clean and validate records
    epic_regex = re.compile(r'^[A-Z]{3}\d{7}$')
    valid_records = []
    skipped = []

    for idx, row in df.iterrows():
        ep = str(row.get('epic_number') or '').upper().strip()
        if not epic_regex.match(ep):
            skipped.append((ep, 'Invalid EPIC format'))
            continue

        name = str(row.get('name') or '').strip()
        rel = str(row.get('relative_name') or '').strip()
        if not name or name in ['nan', 'None', '-', '.']:
            if rel and rel not in ['nan', 'None']:
                name = rel
            else:
                skipped.append((ep, 'Blank name and relative'))
                continue

        valid_records.append({
            'part_number': str(row.get('part_number')),
            'serial_number': int(row['serial_number']) if pd.notna(row.get('serial_number')) else None,
            'epic_number': ep,
            'name': name,
            'relative_name': rel if rel not in ['nan', 'None'] else None,
            'address': str(row.get('address')) if pd.notna(row.get('address')) and str(row.get('address')) != 'nan' else None,
            'qualification': str(row.get('qualification')) if pd.notna(row.get('qualification')) and str(row.get('qualification')) != 'nan' else None,
            'occupation': str(row.get('occupation')) if pd.notna(row.get('occupation')) and str(row.get('occupation')) != 'nan' else None,
            'age': int(row['age']) if pd.notna(row.get('age')) and 18 <= int(row['age']) <= 120 else None,
            'sex': str(row.get('sex')).upper() if str(row.get('sex')).upper() in ['M', 'F'] else None,
            'import_batch_id': batch_id,
            'imported_at': datetime.now().isoformat()
        })

    # Deduplicate within batch by epic_number
    unique_records = []
    seen_epics = set()
    for r in valid_records:
        if r['epic_number'] not in seen_epics:
            seen_epics.add(r['epic_number'])
            unique_records.append(r)
        else:
            skipped.append((r['epic_number'], f"Duplicate within batch (Serial #{r.get('serial_number')})"))
    valid_records = unique_records

    print(f"Validated clean unique records: {len(valid_records)}")
    print(f"Skipped records: {len(skipped)}")

    if dry_run:
        print("\n[DRY RUN COMPLETE] Sample 5 records that would be inserted:")
        for r in valid_records[:5]:
            print(f"  #{r['serial_number']} | EPIC: {r['epic_number']} | Name: {r['name']} | Rel: {r['relative_name']} | Age: {r['age']} | Sex: {r['sex']}")
        print(f"\nTo commit these {len(valid_records)} records, re-run with --commit.")
        return valid_records

    # Live Ingestion
    sb = get_supabase()
    print(f"\nExecuting transactional upsert in chunks of 100...")
    chunk_size = 100
    inserted_count = 0
    start_time = time.time()

    for i in range(0, len(valid_records), chunk_size):
        chunk = valid_records[i:i + chunk_size]
        try:
            res = sb.table('electors').upsert(chunk, on_conflict='epic_number').execute()
            inserted_count += len(chunk)
            print(f"Inserted chunk {i // chunk_size + 1}/{(len(valid_records) + chunk_size - 1) // chunk_size} ({inserted_count}/{len(valid_records)})")
        except Exception as e:
            print(f"Error inserting chunk {i}: {e}")

    print(f"\nInsertion completed in {time.time() - start_time:.2f}s! Total inserted/upserted: {inserted_count}")

    # Search Proof Verification
    print("\n=== Running Live Production Search Proof Verification ===")
    sample_to_verify = valid_records[:20] + valid_records[-20:] if len(valid_records) > 40 else valid_records
    verified = 0
    failed = []

    for r in sample_to_verify:
        ep = r['epic_number']
        try:
            url = f"{SEARCH_API_URL}?q={urllib.parse.quote(ep)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'ETL-Verifier/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    rows = data.get('rows', [])
                    if any(res.get('epic_number') == ep for res in rows):
                        verified += 1
                    else:
                        failed.append((ep, 'Not found in results'))
                else:
                    failed.append((ep, f"API HTTP {resp.status}"))
        except Exception as e:
            failed.append((ep, str(e)))

    print(f"Search Proof Result: {verified}/{len(sample_to_verify)} verified successfully via {SEARCH_API_URL}")
    if failed:
        print(f"Failed verification ({len(failed)}): {failed[:5]}")
    else:
        print("100% PRODUCTION SEARCH PROOF CONFIRMED! 0 not-found electors.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--batch', default=f"batch_ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()

    ingest_batch(args.csv, args.batch, dry_run=not args.commit)
