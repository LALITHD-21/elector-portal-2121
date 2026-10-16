import os
import sys
import re
import json
import time
from datetime import datetime
import pymupdf
import pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('web/.env.local')
SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

import urllib.request

def fetch_db_electors_part(part_str):
    print(f"Fetching existing electors from DB for Part {part_str}...")
    electors = []
    offset = 0
    batch_size = 1000
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Range-Unit': 'items',
        'Prefer': 'count=exact'
    }

    while True:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/electors?part_number=eq.{part_str}&select=id,serial_number,epic_number,name,relative_name,age,sex,address&limit={batch_size}&offset={offset}",
            headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            content_range = resp.headers.get('content-range')
            total = int(content_range.split('/')[1]) if content_range else 0
            data = json.loads(resp.read().decode('utf-8'))
            if not data: break
            electors.extend(data)
            offset += len(data)
            if offset >= total or len(data) < batch_size: break

    print(f"Loaded {len(electors)} existing records for Part {part_str} from DB.")
    return electors

def clean_text(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^[\s\.,_\-!#~;:\'\"\|]+|[\s\.,_\-!#~;:\'\"\|]+$', '', s).strip()
    if s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    s = re.sub(r'^IN:MO', 'NMO', s)
    m = re.search(r'([A-Z]{2,4}\d{6,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) <= 11: return ep
    return None

def parse_p36_page(page, pno):
    blocks = page.get_text("blocks")
    content_blocks = [b for b in blocks if b[1] >= 65 and b[3] <= page.rect.height - 30]
    if not content_blocks: return []

    # Find serial number blocks (x < 65)
    serial_blocks = [
        b for b in content_blocks 
        if b[0] < 65 and (b[2] - b[0]) < 60 and re.match(r'^\d{1,5}$', b[4].strip())
    ]
    serial_blocks.sort(key=lambda b: b[1])
    if not serial_blocks: return []

    voters = []
    for i, sb in enumerate(serial_blocks):
        serial = int(sb[4].strip())
        y_top = sb[1] - 15
        y_bottom = serial_blocks[i+1][1] - 5 if i + 1 < len(serial_blocks) else sb[3] + 65

        band_blocks = [
            b for b in content_blocks 
            if b[1] >= y_top and b[1] < y_bottom and b != sb
        ]
        band_blocks.sort(key=lambda b: b[0])

        combined_text = "\n".join(b[4].strip() for b in band_blocks)

        epic = None
        age = None
        sex = None
        name = None
        rel = None
        addr_cands = []
        qual = None
        occ = None

        m_ep = re.search(r'([A-Za-z]{2,4}[:\.\s]?\d{6,8})', combined_text)
        if m_ep:
            epic = clean_epic(m_ep.group(1))

        m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', combined_text)
        if m_age: age = int(m_age.group(1))
        if re.search(r'\b(Male|Female|M|F)\b', combined_text, re.IGNORECASE):
            if re.search(r'\b(Female|F)\b', combined_text, re.IGNORECASE):
                sex = 'F'
            else:
                sex = 'M'

        detail_blocks = [b for b in band_blocks if b[0] >= 50 and b[0] < 460]
        if detail_blocks:
            lines = [clean_text(l) for b in detail_blocks for l in b[4].split('\n') if clean_text(l)]
            lines = [l for l in lines if l not in ['Karnataka', 'Photo', 'Available', 'Electoral', 'Part No', 'Chitradurga']]
            if len(lines) > 0 and not re.match(r'^\d+$', lines[0]): name = lines[0]
            if len(lines) > 1 and not re.match(r'^\d+$', lines[1]): rel = lines[1]
            if len(lines) > 2: addr_cands = lines[2:]

        qual_blocks = [b for b in band_blocks if b[0] >= 450 and b[0] < 680]
        if qual_blocks:
            q_lines = [clean_text(l) for b in qual_blocks for l in b[4].split('\n') if clean_text(l)]
            for ql in q_lines:
                if ql.upper() in ['BA', 'BCOM', 'BSC', 'MA', 'MSC', 'MCOM', 'BE', 'BTECH', 'MTECH', 'BCA', 'MCA', 'BBA', 'MBA']:
                    qual = ql
                elif ql.upper() in ['TEACHER', 'PENSIONER', 'ENGINEER', 'SOFTWARE ENGINEER', 'SELF EMPLOYEE', 'OWN BUSINESS', 'HOUSEWIFE']:
                    occ = ql

        voters.append({
            "serial_number": serial,
            "epic_number": epic,
            "name": name,
            "relative_name": rel,
            "address": ", ".join(addr_cands) if addr_cands else None,
            "qualification": qual,
            "occupation": occ,
            "age": age,
            "sex": sex,
            "page": pno + 1
        })

    return voters

def run_extraction_part36():
    batch_id = f"batch_36_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    reports_dir = f"etl/reports/{batch_id}"
    os.makedirs(reports_dir, exist_ok=True)
    checkpoints_dir = "etl/checkpoints"
    os.makedirs(checkpoints_dir, exist_ok=True)
    checkpoint_file = os.path.join(checkpoints_dir, "p36_checkpoint.json")

    pdf_path = "C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chit.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} does not exist.")
        return

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Opened PDF: {pdf_path} ({total_pages} pages)")

    existing_db = fetch_db_electors_part("36")
    db_by_serial = {}
    db_by_epic = {}
    for r in existing_db:
        if r.get('serial_number'):
            db_by_serial[r['serial_number']] = r
        if r.get('epic_number'):
            norm_ep = re.sub(r'[^A-Z0-9]', '', str(r['epic_number']).upper())
            db_by_epic[norm_ep] = r

    new_valid = []
    already_in_db = []
    conflicts = []
    quarantined = []
    duplicate_in_batch = []
    batch_seen_epics = set()
    batch_seen_serials = set()

    chunk_size = 50
    start_time = time.time()

    print(f"\nProcessing Part 36 pages in chunks of {chunk_size}...")

    for pno in range(1, total_pages):
        page = doc[pno]
        parsed_on_page = parse_p36_page(page, pno)

        for v in parsed_on_page:
            serial = v['serial_number']
            epic = v['epic_number']
            name = v['name']
            rel = v['relative_name']

            row_data = {
                **v,
                "part_number": "36",
                "district": "Chitradurga",
                "taluk": "Chitradurga",
                "ac_name": "Chitradurga",
                "polling_station_name": "Kasaba Hobli, Chitradurga",
                "polling_address": "Entire Kasaba hobli, Chitradurga Taluk & District, Karnataka",
                "source_file": os.path.basename(pdf_path),
                "source_page_or_row": f"Page {pno + 1}",
                "import_batch_id": batch_id,
                "imported_at": datetime.now().isoformat()
            }

            if not name or len(name) < 2:
                quarantined.append({**row_data, "reason": "Missing or too short name"})
                continue

            if epic and epic in batch_seen_epics:
                duplicate_in_batch.append({**row_data, "reason": f"Duplicate EPIC in batch: {epic}"})
                continue
            if serial in batch_seen_serials:
                duplicate_in_batch.append({**row_data, "reason": f"Duplicate Serial in batch: {serial}"})
                continue

            if epic: batch_seen_epics.add(epic)
            batch_seen_serials.add(serial)

            in_db_by_serial = db_by_serial.get(serial)
            in_db_by_epic = db_by_epic.get(epic) if epic else None

            if in_db_by_epic:
                already_in_db.append({**row_data, "db_id": in_db_by_epic.get('id'), "match": "epic"})
            elif in_db_by_serial:
                db_name = in_db_by_serial.get('name') or ''
                if db_name.lower().replace(' ', '') == (name or '').lower().replace(' ', ''):
                    already_in_db.append({**row_data, "db_id": in_db_by_serial.get('id'), "match": "serial_and_name"})
                else:
                    conflicts.append({
                        "serial_number": serial,
                        "pdf_epic": epic,
                        "pdf_name": name,
                        "pdf_rel": rel,
                        "db_id": in_db_by_serial.get('id'),
                        "db_epic": in_db_by_serial.get('epic_number'),
                        "db_name": in_db_by_serial.get('name'),
                        "db_rel": in_db_by_serial.get('relative_name'),
                        "page": pno + 1
                    })
            else:
                new_valid.append(row_data)

        if pno % chunk_size == 0 or pno == total_pages - 1:
            elapsed = time.time() - start_time
            ppm = (pno / elapsed) * 60 if elapsed > 0 else 0
            eta_min = ((total_pages - pno) / ppm) if ppm > 0 else 0
            print(f"  Chunk: Page {pno}/{total_pages} | New Valid: {len(new_valid)} | In DB: {len(already_in_db)} | Quarantined: {len(quarantined)} | {ppm:.1f} p/min | ETA: {eta_min:.1f}m")
            with open(checkpoint_file, 'w', encoding='utf-8') as cf:
                json.dump({"last_page": pno, "new_valid_count": len(new_valid)}, cf)

    print("\nGenerating Phase 3 Reports & CSV Artifacts for Part 36...")
    pd.DataFrame(new_valid).to_csv(os.path.join(reports_dir, "new_voters.csv"), index=False, encoding='utf-8')
    pd.DataFrame(already_in_db).to_csv(os.path.join(reports_dir, "already_in_db.csv"), index=False, encoding='utf-8')
    pd.DataFrame(duplicate_in_batch).to_csv(os.path.join(reports_dir, "duplicates_in_batch.csv"), index=False, encoding='utf-8')
    pd.DataFrame(conflicts).to_csv(os.path.join(reports_dir, "differences_report.csv"), index=False, encoding='utf-8')

    if quarantined:
        pd.DataFrame(quarantined).to_excel(os.path.join(reports_dir, "quarantine_review.xlsx"), index=False)
    else:
        pd.DataFrame([{"message": "Zero quarantined rows"}]).to_excel(os.path.join(reports_dir, "quarantine_review.xlsx"), index=False)

    rollback_sql = f"-- Rollback script for Part 36 Batch {batch_id}\nDELETE FROM public.electors WHERE import_batch_id = '{batch_id}';\n"
    with open(os.path.join(reports_dir, "rollback.sql"), "w", encoding="utf-8") as rf:
        rf.write(rollback_sql)

    total_processed = len(new_valid) + len(already_in_db) + len(duplicate_in_batch) + len(quarantined) + len(conflicts)
    summary_md = f"""# Extraction & Recovery Summary: Part 36
- **Batch ID**: `{batch_id}`
- **Source PDF**: `{pdf_path}`
- **Total Pages Scanned**: {total_pages}
- **Total Voters Evaluated**: {total_processed}
- **New Valid Missing Voters Recovered**: {len(new_valid)}
- **Already Existing in DB**: {len(already_in_db)}
- **Field Conflicts (Review Needed)**: {len(conflicts)}
- **Quarantined**: {len(quarantined)}
- **Duplicates in Batch**: {len(duplicate_in_batch)}
- **Artifacts Saved to**: `{reports_dir}`
"""
    with open(os.path.join(reports_dir, "summary.md"), "w", encoding="utf-8") as sf:
        sf.write(summary_md)

    print("\n" + "=" * 60)
    print(" EXTRACTION COMPLETED FOR PART 36")
    print(f" New Valid Recovered: {len(new_valid)}")
    print(f" Already in DB: {len(already_in_db)}")
    print(f" Conflicts: {len(conflicts)}")
    print(f" Quarantined: {len(quarantined)}")
    print(f" Reports: {reports_dir}")
    print("=" * 60)

if __name__ == "__main__":
    run_extraction_part36()
