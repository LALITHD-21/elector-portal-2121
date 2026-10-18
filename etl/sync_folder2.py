#!/usr/bin/env python3
r"""
Folder 2 Electoral Roll Synchronizer & Incremental Ingestion
Scans voter destiles -02
Parses all files, resolves booth/station mapping, and upserts any missing/supplementary electors into Supabase.
Enforces multi-tier deduplication on epic_number.
"""

import os
import re
import sys
import glob
import time
import json
import ssl
import openpyxl
import urllib.request

SUPABASE_URL = "https://fxnomgqqenaqpuzervxd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ4bm9tZ3FxZW5hcXB1emVydnhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjMzNzA5MywiZXhwIjoyMTA3OTEzMDkzfQ.c67TOlHqgzjRQu2uvmhJngSFyeJQAQ6s5n_utqPosmM"

BASE_DIR = r"C:\Users\techb\Desktop\electrol-portal-2121\electrol-portal-NEW-main"
FOLDER2_DIR = os.path.join(BASE_DIR, "voter", "voter destiles -02")

# Load Master Maps
with open(os.path.join(BASE_DIR, "etl", "booths_master.json"), "r", encoding="utf-8") as f:
    BOOTH_MASTER = json.load(f)

with open(os.path.join(BASE_DIR, "etl", "polling_stations_master.json"), "r", encoding="utf-8") as f:
    POLLING_MASTER = json.load(f)

def resolve_polling_info(part_str, serial_num):
    part_key = str(part_str).strip()
    candidates = [p for p in POLLING_MASTER if str(p.get("basePart")).strip() == part_key]
    if not candidates:
        return None, None
    if serial_num is not None:
        for c in candidates:
            min_s = c.get("minSerial") or 1
            max_s = c.get("maxSerial") or 999999
            if min_s <= serial_num <= max_s:
                return c.get("buildingName"), c.get("pollingArea")
    primary = candidates[0]
    return primary.get("buildingName"), primary.get("pollingArea")

def clean_epic(val, part=None, serial=None):
    if not val:
        if part and serial:
            return f"P{part}_{serial:04d}"
        return None
    s = str(val).strip().upper()
    s = re.sub(r'[\s\.\-_/\\,]', '', s)
    
    if len(s) > 16 or any(w in s for w in ['SCHOOL', 'ROOM', 'MAIDAN', 'HOSPITAL', 'COLLEGE', 'BUILDING', 'PANCHAYAT', 'TEMPLE', 'GOVT']):
        if part and serial:
            return f"P{part}_{serial:04d}"
        return None

    if len(s) < 4:
        if part and serial:
            return f"P{part}_{serial:04d}"
        return None

    if s.startswith("NM0"):
        s = "NMO" + s[3:]
    elif s.startswith("1KI"):
        s = "IKI" + s[3:]
    elif s.startswith("5GZ"):
        s = "SGZ" + s[3:]
    return s

def clean_serial(val):
    if val is None:
        return None
    s = str(val).strip()
    s = re.sub(r'[#\s\r\n]', '', s)
    m = re.search(r'\d+', s)
    if m:
        try:
            return int(m.group(0))
        except:
            pass
    return None

def clean_text(val):
    if val is None:
        return None
    t = str(val).strip()
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'^[\.\-,:;]+|[\.\-,:;]+$', '', t).strip()
    return t if t else None

def clean_sex(val):
    if not val:
        return None
    s = str(val).strip().upper()
    if 'M' in s or s.startswith('PUR') or s.startswith('MALE'):
        return 'M'
    if 'F' in s or s.startswith('STR') or s.startswith('FEMALE') or s.startswith('W'):
        return 'F'
    return None

def clean_age(val):
    if val is None:
        return None
    try:
        m = re.search(r'\d+', str(val))
        if m:
            age = int(m.group(0))
            if 18 <= age <= 125:
                return age
    except:
        pass
    return None

def extract_column_indices(header_row):
    col_map = {}
    for idx, cell in enumerate(header_row):
        if not cell or not isinstance(cell, str):
            continue
        text = cell.strip().lower()
        if any(k in text for k in ['sino', 'sl no', 'slno', 'serial']):
            col_map.setdefault('serial', idx)
        elif 'name of the elector' in text or 'elector name' in text:
            col_map.setdefault('name', idx)
        elif any(k in text for k in ['father', 'mother', 'husband', 'relative']):
            col_map.setdefault('relative', idx)
        elif 'address' in text:
            col_map.setdefault('address', idx)
        elif 'qualification' in text:
            col_map.setdefault('qualification', idx)
        elif 'occupation' in text or 'occupcation' in text:
            col_map.setdefault('occupation', idx)
        elif 'age' in text:
            col_map.setdefault('age', idx)
        elif 'sex' in text or 'gender' in text:
            col_map.setdefault('sex', idx)
        elif 'epic' in text:
            col_map.setdefault('epic', idx)
    return col_map

def parse_folder2_file(filepath):
    filename = os.path.basename(filepath)
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True)
    except Exception as e:
        return []

    ws = wb.active
    
    # 1. Detect part number from first 16 rows
    part_num = None
    for row in ws.iter_rows(min_row=1, max_row=16, values_only=True):
        for cell in row:
            if cell and isinstance(cell, str):
                pm = re.search(r'Part\s*N\s*o\s*:\s*(\d+)', cell, re.IGNORECASE)
                if pm:
                    part_num = str(int(pm.group(1)))
                    break
        if part_num:
            break

    if not part_num:
        wb.close()
        return []

    booth_info = BOOTH_MASTER.get(part_num, {})
    district = booth_info.get("district")
    taluk = booth_info.get("taluk")
    ac_name = booth_info.get("ac_name")

    # 2. Find Header row
    header_row_idx = None
    col_map = {}
    rows_iter = ws.iter_rows(values_only=True)
    
    current_idx = 0
    for row in rows_iter:
        current_idx += 1
        non_empty = [c for c in row if c is not None]
        if any(('sino' in str(c).lower() or 'sl no' in str(c).lower() or 'name of the elector' in str(c).lower()) for c in non_empty):
            header_row_idx = current_idx
            col_map = extract_column_indices(row)
            break

    epic_col = col_map.get('epic')
    if not header_row_idx or epic_col is None:
        wb.close()
        return []

    electors = []
    current_serial = 0
    serial_col = col_map.get('serial')
    name_col = col_map.get('name')
    rel_col = col_map.get('relative')
    addr_col = col_map.get('address')
    qual_col = col_map.get('qualification')
    occ_col = col_map.get('occupation')
    age_col = col_map.get('age')
    sex_col = col_map.get('sex')

    for row in rows_iter:
        if not row or all(c is None for c in row):
            continue
            
        first_cell = str(row[0] or '').strip().lower()
        if 'total number' in first_cell or 'supplement' in first_cell:
            break

        if any(('sino' in str(c).lower() or 'name of the elector' in str(c).lower()) for c in row[:5] if c is not None):
            continue

        raw_serial = None
        if serial_col is not None and serial_col < len(row):
            raw_serial = row[serial_col]
        serial = clean_serial(raw_serial)
        
        if serial is None and serial_col is not None and (serial_col + 1) < len(row):
            serial = clean_serial(row[serial_col + 1])
            
        if serial is not None:
            current_serial = serial
        else:
            current_serial += 1
            serial = current_serial

        raw_epic = row[epic_col] if epic_col < len(row) else None
        epic = clean_epic(raw_epic, part=part_num, serial=serial)
        if not epic:
            continue

        raw_name = row[name_col] if (name_col is not None and name_col < len(row)) else None
        name = clean_text(raw_name)
        if not name or name.lower() == 'name of the elector':
            continue

        raw_rel = row[rel_col] if (rel_col is not None and rel_col < len(row)) else None
        relative_name = clean_text(raw_rel)

        raw_addr = row[addr_col] if (addr_col is not None and addr_col < len(row)) else None
        address = clean_text(raw_addr)

        raw_qual = row[qual_col] if (qual_col is not None and qual_col < len(row)) else None
        qualification = clean_text(raw_qual)

        raw_occ = row[occ_col] if (occ_col is not None and occ_col < len(row)) else None
        occupation = clean_text(raw_occ)

        raw_age = row[age_col] if (age_col is not None and age_col < len(row)) else None
        age = clean_age(raw_age)

        raw_sex = row[sex_col] if (sex_col is not None and sex_col < len(row)) else None
        sex = clean_sex(raw_sex)

        b_name, b_area = resolve_polling_info(part_num, serial)

        electors.append({
            "part_number": part_num,
            "serial_number": serial,
            "epic_number": epic,
            "name": name,
            "relative_name": relative_name,
            "age": age,
            "sex": sex,
            "address": address,
            "qualification": qualification,
            "occupation": occupation,
            "district": district,
            "ac_name": ac_name,
            "taluk": taluk,
            "polling_station_name": b_name,
            "polling_address": b_area,
            "source_file": filename
        })

    wb.close()
    # Deduplicate within file by epic_number to prevent PostgREST conflict error
    unique_map = {}
    for r in electors:
        unique_map[r["epic_number"]] = r
    return list(unique_map.values())

def post_records(chunk):
    url = f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal'
    }
    ctx = ssl.create_default_context()
    data = json.dumps(chunk).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        return len(chunk)

def upsert_batch(records, batch_size=200):
    total = len(records)
    upserted = 0
    for i in range(0, total, batch_size):
        chunk = records[i:i + batch_size]
        success = False
        for retry in range(2):
            try:
                upserted += post_records(chunk)
                success = True
                break
            except Exception as e:
                time.sleep(1)
        if not success:
            # Fallback to micro-batches of 25 to isolate and save every record
            micro_size = 25
            for j in range(0, len(chunk), micro_size):
                sub_chunk = chunk[j:j + micro_size]
                try:
                    upserted += post_records(sub_chunk)
                except Exception as ex:
                    # Single-record fallback
                    for item in sub_chunk:
                        try:
                            upserted += post_records([item])
                        except Exception as item_err:
                            pass
    return upserted

def get_db_total():
    try:
        url = f"{SUPABASE_URL}/rest/v1/electors?select=count"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'count=exact'
        }
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            cr = resp.headers.get('content-range')
            if cr and '/' in cr:
                return int(cr.split('/')[-1])
    except Exception as e:
        print(f"Error getting db total: {e}")
    return None

def main():
    print("=" * 70)
    print("Folder 2 Sync: voter destiles -02 Ingestion & Deduplication")
    print("=" * 70)

    f2_files = sorted(glob.glob(os.path.join(FOLDER2_DIR, "*.xlsx")))
    print(f"Found {len(f2_files)} files in voter destiles -02.")
    start_db_total = get_db_total()
    print(f"Current Electors in Supabase before sync: {start_db_total:,}")

    total_parsed = 0
    total_upserted = 0
    valid_files = 0

    for idx, fpath in enumerate(f2_files):
        fname = os.path.basename(fpath)
        records = parse_folder2_file(fpath)
        if not records:
            continue

        valid_files += 1
        part_no = records[0]["part_number"]
        total_parsed += len(records)

        upserted = upsert_batch(records)
        total_upserted += upserted

        print(f"[{idx+1:3d}/{len(f2_files)}] Part {part_no:3s} | {fname[:40]:40s} | Records: {len(records):4d} | Synced: {upserted:4d}")

    end_db_total = get_db_total()

    print("\n" + "=" * 70)
    print("FOLDER 2 SYNC SUMMARY")
    print("=" * 70)
    print(f"Valid Files Processed   : {valid_files} / {len(f2_files)}")
    print(f"Total Unique Electors   : {total_parsed:,}")
    print(f"Total Records Upserted  : {total_upserted:,}")
    print(f"Database Elector Count  : {end_db_total:,} (Net Added: {end_db_total - (start_db_total or 0):,})")
    print("=" * 70)

if __name__ == "__main__":
    main()

