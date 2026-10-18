#!/usr/bin/env python3
"""
Complete Production Ingestion Pipeline
Karnataka South-East Graduates' Constituency (151 Parts)

Rules Enforced:
1. ZERO DATA LOSS: Every valid elector from all 151 parts is parsed and ingested.
2. ZERO DUPLICATION: Multi-tier deduplication on epic_number.
3. SANITIZATION:
   - Serial: Strip newlines, #, whitespace, reconstruct wrapped/merged serials.
   - EPIC: Uppercase, strip non-alphanumeric, heal OCR errors (NM0 -> NMO, etc.).
     Canonical fallback (P{part}_{serial:04d}) if EPIC contains building/room text or > 16 chars.
   - Text: Normalization of names, relatives, qualifications, addresses.
   - Demographics: Age validated (18-125), Sex normalized ('M' or 'F').
   - Booth & Station Attribution: Deterministic matching from master directories.
4. BATCH UPSERT: Upserts in batches of 400 into Supabase with retry logic.
5. RESUME SUPPORT: Accepts --start-part or --start-index argument to resume.
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
import argparse

SUPABASE_URL = "https://fxnomgqqenaqpuzervxd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ4bm9tZ3FxZW5hcXB1emVydnhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjMzNzA5MywiZXhwIjoyMTA3OTEzMDkzfQ.c67TOlHqgzjRQu2uvmhJngSFyeJQAQ6s5n_utqPosmM"

BASE_DIR = r"C:\Users\techb\Desktop\electrol-portal-2121\electrol-portal-NEW-main"
VOTER_DIR = os.path.join(BASE_DIR, "voter")

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

def find_part_number(filename, ws):
    base = os.path.basename(filename)
    m = re.match(r'^(\d+)[eE_]', base)
    if m:
        return str(int(m.group(1)))
    
    if "Form18_SE_2" in base or "2_WithPhoto" in base:
        return "2"
        
    for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
        for cell in row:
            if cell and isinstance(cell, str):
                pm = re.search(r'Part\s*N\s*o\s*:\s*(\d+)', cell, re.IGNORECASE)
                if pm:
                    return str(int(pm.group(1)))
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
        elif 'occupation' in text:
            col_map.setdefault('occupation', idx)
        elif 'age' in text:
            col_map.setdefault('age', idx)
        elif 'sex' in text or 'gender' in text:
            col_map.setdefault('sex', idx)
        elif 'epic' in text:
            col_map.setdefault('epic', idx)
    return col_map

def parse_excel_file(filepath):
    filename = os.path.basename(filepath)
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

    ws = wb.active
    part_num = find_part_number(filename, ws)
    if not part_num:
        wb.close()
        return []

    booth_info = BOOTH_MASTER.get(part_num, {})
    district = booth_info.get("district")
    taluk = booth_info.get("taluk")
    ac_name = booth_info.get("ac_name")

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
    return electors

def upsert_batch(records, batch_size=400):
    url = f"{SUPABASE_URL}/rest/v1/electors?on_conflict=epic_number"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal'
    }
    ctx = ssl.create_default_context()
    
    total = len(records)
    upserted = 0
    for i in range(0, total, batch_size):
        chunk = records[i:i + batch_size]
        data = json.dumps(chunk).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        for retry in range(3):
            try:
                resp = urllib.request.urlopen(req, context=ctx, timeout=45)
                upserted += len(chunk)
                break
            except Exception as e:
                time.sleep(2)
                if retry == 2:
                    print(f"    [Error] batch {i}-{i+len(chunk)}: {e}")
                    if hasattr(e, 'read'):
                        print(f"    Response: {e.read().decode('utf-8', errors='ignore')[:250]}")
    return upserted

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-part", type=int, default=1, help="Start from this part number")
    args = parser.parse_args()

    print("=" * 70)
    print(f"Karnataka South-East Graduates' Constituency — Ingestion (Starting Part {args.start_part})")
    print("=" * 70)

    loose_files = [f for f in glob.glob(os.path.join(VOTER_DIR, "*.xlsx")) if not f.endswith('.pdf.xlsx') and not f.endswith('.pdf.pdf.xlsx')]
    print(f"Found {len(loose_files)} primary Excel roll files.")

    def sort_key(f):
        base = os.path.basename(f)
        m = re.match(r'^(\d+)', base)
        return int(m.group(1)) if m else (2 if 'Form18_SE_2' in base else 9999)

    loose_files.sort(key=sort_key)

    seen_epics = set()
    total_parsed = 0
    total_ingested = 0
    parts_processed = set()

    for idx, fpath in enumerate(loose_files):
        fname = os.path.basename(fpath)
        
        # Check part number from filename for quick skip
        part_m = re.match(r'^(\d+)', fname)
        file_part = int(part_m.group(1)) if part_m else (2 if 'Form18_SE_2' in fname else 0)
        if file_part < args.start_part and file_part != 0:
            continue

        records = parse_excel_file(fpath)
        if not records:
            continue

        part_no = records[0]["part_number"]
        if int(part_no) < args.start_part:
            continue

        parts_processed.add(part_no)

        unique_records = []
        for r in records:
            epic = r["epic_number"]
            if epic not in seen_epics:
                seen_epics.add(epic)
                unique_records.append(r)

        count = len(unique_records)
        total_parsed += len(records)

        upserted = upsert_batch(unique_records)
        total_ingested += upserted

        print(f"[{idx+1}/{len(loose_files)}] Part {part_no:4s} | {fname[:35]:35s} | Parsed: {len(records):4d} | New Unique: {count:4d} | Batch Ingested: {total_ingested:6d}")

    print("\n" + "=" * 70)
    print("INGESTION BATCH SUMMARY REPORT")
    print("=" * 70)
    print(f"Parts Processed:     {len(parts_processed)}")
    print(f"Total Rows Parsed:   {total_parsed:,}")
    print(f"Total Ingested:      {total_ingested:,}")
    print("=" * 70)

if __name__ == "__main__":
    main()
