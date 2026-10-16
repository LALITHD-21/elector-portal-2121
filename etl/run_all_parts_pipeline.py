import os
import sys
import re
import json
import time
import pymupdf
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

import sys
import os
sys.path.append(os.path.dirname(__file__))
from master_scanned_extractor import extract_scanned_page, clean_epic
from test_digital_extractor import parse_digital_pdf

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

sb = create_client(os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

PDF_DIR = r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF'

with open('etl/stations_dump.json', 'r', encoding='utf-8') as f:
    stations = json.load(f)
station_by_part = {str(s.get('part_number')): s for s in stations}

# Load gap analysis
with open('etl/reports/missing_voters_gap_analysis.json', 'r', encoding='utf-8') as f:
    gap_data = json.load(f)

# Sort deficit parts descending
deficit_parts = [d for d in gap_data if d['deficit'] > 50 and d['part'] not in [10, 36, 72]]
deficit_parts.sort(key=lambda x: x['deficit'], reverse=True)

print(f"==================================================")
print(f"MASTER ALL-PARTS EXTRACTION PIPELINE")
print(f"Total parts to process: {len(deficit_parts)}")
print(f"==================================================")

os.makedirs('etl/reports/all_parts_run', exist_ok=True)

def process_scanned_part(part_num, pdf_filename, max_pages=None):
    pdf_path = os.path.join(PDF_DIR, pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} does not exist!")
        return 0, 0

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    end_p = min(total_pages - 1, max_pages) if max_pages else (total_pages - 1)

    print(f"\n>>> Processing Part {part_num} ({pdf_filename}): {end_p} pages")
    
    # 1. Fetch existing serials and epics from DB to avoid re-extracting
    existing_serials = set()
    start = 0
    while True:
        res = sb.from_('electors').select('serial_number').eq('part_number', str(part_num)).range(start, start + 999).execute()
        rows = res.data or []
        existing_serials.update(r['serial_number'] for r in rows if r.get('serial_number'))
        if len(rows) < 1000: break
        start += 1000

    print(f"  Current DB Serials for Part {part_num}: {len(existing_serials)}")

    all_extracted = []
    t0 = time.time()
    for p in range(1, end_p + 1):
        try:
            page_voters = extract_scanned_page(doc[p])
            for v in page_voters:
                v['part_number'] = str(part_num)
                v['page'] = p + 1
            all_extracted.extend(page_voters)
            if p % 10 == 0 or p == end_p:
                print(f"   Page {p}/{end_p}: Extracted {len(all_extracted)} voters so far... [{time.time()-t0:.1f}s]")
        except Exception as ex:
            print(f"   Error on page {p}: {ex}")

    # Deduplicate in-memory
    unique_voters = {}
    for v in all_extracted:
        sno = v.get('serial_number')
        if sno and sno not in unique_voters:
            unique_voters[sno] = v

    # Filter only those truly missing from DB
    truly_missing = [v for s, v in unique_voters.items() if s not in existing_serials]
    print(f"  Part {part_num} Extraction Done: {len(unique_voters)} total unique, {len(truly_missing)} truly missing to insert.")

    if not truly_missing:
        return 0, 0

    # Ingest in zero-collision batches of 200
    st_meta = station_by_part.get(str(part_num), {})
    records_to_insert = []
    seen_epics = set()

    for v in truly_missing:
        ep = v.get('epic_number')
        if ep:
            ep = clean_epic(ep)
            if ep in seen_epics:
                ep = None
            else:
                seen_epics.add(ep)

        item = {
            'serial_number': v.get('serial_number'),
            'epic_number': ep,
            'name': v.get('name') or 'Unknown',
            'relative_name': v.get('relative_name'),
            'address': v.get('address'),
            'qualification': v.get('qualification')[:100] if v.get('qualification') else None,
            'occupation': v.get('occupation')[:100] if v.get('occupation') else None,
            'age': v.get('age'),
            'sex': v.get('sex'),
            'part_number': str(part_num),
            'polling_station_name': st_meta.get('name') or f"Polling Station Part {part_num}",
            'polling_address': st_meta.get('address') or v.get('address'),
            'district': st_meta.get('district') or 'Karnataka',
            'taluk': st_meta.get('taluk'),
            'ac_name': st_meta.get('taluk')
        }
        records_to_insert.append(item)

    # Insert in batches
    BATCH_SIZE = 100
    inserted = 0
    for i in range(0, len(records_to_insert), BATCH_SIZE):
        chunk = records_to_insert[i:i+BATCH_SIZE]
        try:
            res = sb.from_('electors').insert(chunk).execute()
            inserted += len(res.data or [])
        except Exception as e:
            # Fall back to single record insertion to skip any solitary collision
            for row in chunk:
                try:
                    res_single = sb.from_('electors').insert([row]).execute()
                    inserted += len(res_single.data or [])
                except:
                    pass

    print(f"  [SUCCESS] Part {part_num}: Successfully synced {inserted} recovered electors into DB!")
    return len(truly_missing), inserted

if __name__ == '__main__':
    total_missing_processed = 0
    total_inserted = 0
    
    # Process top 3 high-deficit parts in this pass (Part 124, Part 32, Part 123)
    target_batch = deficit_parts[:3]
    for d in target_batch:
        p_num = d['part']
        pdf_file = d['pdf_file']
        missing_cnt, ins_cnt = process_scanned_part(p_num, pdf_file, max_pages=30)
        total_missing_processed += missing_cnt
        total_inserted += ins_cnt

    print(f"\n==================================================")
    print(f"BATCH COMPLETE! Synced {total_inserted} new electors.")
    print(f"==================================================")
