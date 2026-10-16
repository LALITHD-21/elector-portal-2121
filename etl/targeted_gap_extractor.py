import os
import sys
import re
import json
import time
import pymupdf
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

sys.path.append(os.path.dirname(__file__))
from master_scanned_extractor import extract_scanned_page, clean_epic

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

sb = create_client(os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
PDF_DIR = r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF'

with open('etl/stations_dump.json', 'r', encoding='utf-8') as f:
    stations = json.load(f)
station_by_part = {str(s.get('part_number')): s for s in stations}

def extract_targeted_gaps_for_part(part_num, pdf_filename, max_target_pages=15):
    pdf_path = os.path.join(PDF_DIR, pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} does not exist!")
        return 0

    # 1. Fetch all serials currently in DB for this part
    existing_serials = set()
    start = 0
    while True:
        res = sb.from_('electors').select('serial_number').eq('part_number', str(part_num)).range(start, start + 999).execute()
        rows = res.data or []
        existing_serials.update(r['serial_number'] for r in rows if r.get('serial_number'))
        if len(rows) < 1000: break
        start += 1000

    if not existing_serials:
        print(f"Part {part_num}: No serials in DB!")
        return 0

    max_db_sno = max(existing_serials)
    missing_serials = sorted(list(set(range(1, max_db_sno + 1)) - existing_serials))
    print(f"Part {part_num}: Current DB Serials={len(existing_serials)}, Missing in range 1..{max_db_sno} = {len(missing_serials)}")

    if not missing_serials:
        print(f"Part {part_num} has 0 missing serials in current range!")
        return 0

    # 2. Map missing serials to probable pages (each page has ~8 voters, page 1 is cover)
    # Estimate: page = (sno - 1) // 8 + 1
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    
    target_pages = set()
    for s in missing_serials:
        p_est = (s - 1) // 8 + 1
        if 1 <= p_est < total_pages:
            target_pages.add(p_est)

    target_pages_sorted = sorted(list(target_pages))[:max_target_pages]
    print(f"Targeting {len(target_pages_sorted)} pages containing missing serials: {target_pages_sorted}")

    # 3. Extract only those targeted pages
    recovered_voters = []
    t0 = time.time()
    for p in target_pages_sorted:
        try:
            pv = extract_scanned_page(doc[p])
            for v in pv:
                v['part_number'] = str(part_num)
                v['page'] = p + 1
            # Keep only those truly missing
            new_only = [v for v in pv if v.get('serial_number') not in existing_serials]
            recovered_voters.extend(new_only)
            print(f"  Page {p+1}/{total_pages}: {len(pv)} rows extracted, {len(new_only)} truly missing recovered.")
        except Exception as ex:
            print(f"  Error on page {p}: {ex}")

    # Deduplicate in-memory
    unique_recovered = {}
    for v in recovered_voters:
        sno = v.get('serial_number')
        if sno and sno not in unique_recovered:
            unique_recovered[sno] = v

    print(f"Part {part_num}: Total unique missing electors recovered from target pages = {len(unique_recovered)}")

    if not unique_recovered:
        return 0

    # 4. Ingest with zero collision
    st_meta = station_by_part.get(str(part_num), {})
    records_to_insert = []
    seen_epics = set()

    for v in unique_recovered.values():
        ep = v.get('epic_number')
        if ep:
            ep = clean_epic(ep)
            if ep in seen_epics: ep = None
            else: seen_epics.add(ep)

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

    # Insert into Supabase
    inserted = 0
    for row in records_to_insert:
        try:
            res = sb.from_('electors').insert([row]).execute()
            inserted += len(res.data or [])
        except Exception as e:
            pass

    print(f"  [SUCCESS] Part {part_num}: Successfully synced {inserted} recovered electors into DB!")
    return inserted

if __name__ == '__main__':
    # Test on Part 32
    ins = extract_targeted_gaps_for_part(32, '32_1791587153.pdf', max_target_pages=10)
    print(f"Total inserted for Part 32: {ins}")
