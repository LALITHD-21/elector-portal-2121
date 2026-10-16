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

env_path = 'c:/Users/techb/Desktop/electrol-portal-NEW-main/electrol-portal-NEW-main/web/.env.local'
load_dotenv(env_path)

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
    s = re.sub(r'[\$#@!~%^*()_+=\[\]{};:\"\'\<\>?/\\|]+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    if s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil', 'photo', 'available']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    s = re.sub(r'^IN:MO', 'NMO', s)
    s = re.sub(r'^NM0', 'NMO', s)
    
    # D to 0 in 4th char
    if len(s) == 10 and re.match(r'^[A-Z]{3}[DO]\d{6}$', s):
        s = s[:3] + '0' + s[4:]
    elif len(s) == 9 and re.match(r'^[A-Z]{3}\d{6}$', s):
        s = s[:3] + '0' + s[3:]
    elif len(s) == 11 and re.match(r'^[A-Z]{3}0\d{7}$', s):
        s = s[:3] + s[4:]
        
    m = re.search(r'([A-Z]{2,4}\d{5,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) == 9: ep = ep[:3] + '0' + ep[3:]
        return ep
    return None

def extract_page_voters(page, pno, running_serial):
    words = page.get_text('words')
    content_words = [w for w in words if w[1] >= 65 and w[3] <= page.rect.height - 25]
    if not content_words: return [], running_serial

    rows_y = []
    sorted_words = sorted(content_words, key=lambda w: w[1])
    for w in sorted_words:
        y = w[1]
        placed = False
        for ry in rows_y:
            if abs(y - ry['y_mean']) < 24:
                ry['words'].append(w)
                ry['y_mean'] = sum(x[1] for x in ry['words']) / len(ry['words'])
                placed = True
                break
        if not placed:
            rows_y.append({'y_mean': y, 'words': [w]})

    voter_rows = []
    for ry in rows_y:
        ws = ry['words']
        min_x = min(w[0] for w in ws)
        max_x = max(w[2] for w in ws)
        text = ' '.join(w[4] for w in ws)
        if any(h in text for h in ['Table of Content', 'Name of State', 'Components of', 'Page 1 of', 'Area : Entire Kasaba Hobli', 'Name of the Elector', 'Modification, Sex:']):
            continue
        if max_x - min_x > 350 and len(ws) >= 4:
            voter_rows.append(ws)

    voter_rows.sort(key=lambda ws: min(w[1] for w in ws))

    voters = []
    for ws in voter_rows:
        # Serial: x < 55
        s_words = [w[4] for w in ws if w[0] < 55]
        s_text = ' '.join(s_words)
        m_s = re.search(r'(?:[#§s8\*\$]|\b)\s*(\d{1,5})\s*(?:\n|\b|$)', s_text)
        detected_serial = int(m_s.group(1)) if m_s else None

        if detected_serial and abs(detected_serial - (running_serial + 1)) <= 3:
            serial = detected_serial
        else:
            serial = running_serial + 1
        running_serial = serial

        # Name: 55 <= x < 175
        name_words = [w[4] for w in ws if 55 <= w[0] < 175]
        name = clean_text(' '.join(name_words))

        # Relative: 175 <= x < 290
        rel_words = [w[4] for w in ws if 175 <= w[0] < 290]
        rel = clean_text(' '.join(rel_words))

        # Address: 290 <= x < 450
        addr_words = [w[4] for w in ws if 290 <= w[0] < 450]
        addr = clean_text(' '.join(addr_words))

        # Age: 600 <= x < 650
        age_words = [w[4] for w in ws if 600 <= w[0] < 650]
        m_age = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', ' '.join(age_words))
        age = int(m_age.group(1)) if m_age else None

        # Sex: 640 <= x < 680
        sex_words = [w[4] for w in ws if 640 <= w[0] < 680]
        sex_text = ' '.join(sex_words)
        sex = 'F' if 'F' in sex_text.upper() else ('M' if 'M' in sex_text.upper() else None)

        # EPIC: x >= 650
        epic_words = [w[4] for w in ws if w[0] >= 650]
        m_ep = re.search(r'([A-Za-z5\$]{2,4}[:\.\s]?[A-Za-z0-9]{5,9})', ' '.join(epic_words))
        epic = clean_epic(m_ep.group(1)) if m_ep else None

        voters.append({
            "serial_number": serial,
            "epic_number": epic,
            "name": name,
            "relative_name": rel,
            "address": addr,
            "qualification": None,
            "occupation": None,
            "age": age,
            "sex": sex,
            "page": pno + 1
        })

    return voters, running_serial

def run():
    batch_id = f"batch_140_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    reports_dir = f"etl/reports/{batch_id}"
    os.makedirs(reports_dir, exist_ok=True)

    pdf_path = "C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/kolar entire kasba hobli - 2026 (3)_ocred.pdf"
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Opened PDF: {pdf_path} ({total_pages} pages)")

    existing_db = fetch_db_electors_part("140")
    db_by_serial = {r['serial_number']: r for r in existing_db if r.get('serial_number')}
    db_by_epic = {re.sub(r'[^A-Z0-9]', '', str(r['epic_number']).upper()): r for r in existing_db if r.get('epic_number')}

    new_valid = []
    already_in_db = []
    conflicts = []
    quarantined = []
    duplicate_in_batch = []
    batch_seen_epics = set()

    running_serial = 0
    start_time = time.time()

    print(f"Starting extraction across all {total_pages} pages...")

    for pno in range(1, total_pages):
        page = doc[pno]
        parsed_on_page, running_serial = extract_page_voters(page, pno, running_serial)

        for v in parsed_on_page:
            serial = v['serial_number']
            epic = v['epic_number']
            name = v['name']
            rel = v['relative_name']

            row_data = {
                **v,
                "part_number": "140",
                "district": "Kolar",
                "taluk": "Kolar",
                "ac_name": "Kolar",
                "polling_station_name": "Taluk Office, Kolar",
                "polling_address": "Kolar Entire Kasba Hobli, Kolar Taluk, Kolar District, Karnataka",
                "source_file": os.path.basename(pdf_path),
                "source_page_or_row": f"Page {pno + 1}",
                "import_batch_id": batch_id,
                "imported_at": datetime.now().isoformat()
            }

            if not name or len(name) < 3:
                quarantined.append({**row_data, "quarantine_reason": "Missing or short name"})
                continue

            if not epic or not re.match(r'^[A-Z]{3}\d{7}$', epic):
                quarantined.append({**row_data, "quarantine_reason": f"Non-standard/missing EPIC: {epic}"})
                continue

            if epic in batch_seen_epics:
                duplicate_in_batch.append({**row_data, "quarantine_reason": f"Duplicate EPIC in batch: {epic}"})
                continue

            batch_seen_epics.add(epic)

            in_db_by_epic = db_by_epic.get(epic)

            if in_db_by_epic:
                db_name = str(in_db_by_epic.get('name') or '').strip().lower()
                pdf_name = str(name or '').strip().lower()
                if db_name == pdf_name or db_name.replace(' ', '') == pdf_name.replace(' ', ''):
                    already_in_db.append({**row_data, "db_id": in_db_by_epic.get('id'), "match": "exact_epic_and_name"})
                else:
                    conflicts.append({
                        **row_data,
                        "conflict_type": "EPIC_COLLISION_DIFFERENT_PERSON",
                        "db_id": in_db_by_epic.get('id'),
                        "db_name": in_db_by_epic.get('name'),
                        "db_serial": in_db_by_epic.get('serial_number'),
                        "pdf_name": name,
                        "pdf_serial": serial
                    })
            else:
                new_valid.append(row_data)

        if (pno + 1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = (pno + 1) / (elapsed / 60)
            print(f"Page {pno + 1}/{total_pages} | New Valid: {len(new_valid)} | In DB: {len(already_in_db)} | Conflicts: {len(conflicts)} | Quarantined: {len(quarantined)} | Speed: {rate:.1f} p/min")

    # Save artifacts
    pd.DataFrame(new_valid).to_csv(os.path.join(reports_dir, 'new_voters.csv'), index=False)
    pd.DataFrame(already_in_db).to_csv(os.path.join(reports_dir, 'already_in_db.csv'), index=False)
    pd.DataFrame(conflicts).to_csv(os.path.join(reports_dir, 'differences_report.csv'), index=False)
    pd.DataFrame(quarantined).to_excel(os.path.join(reports_dir, 'quarantine_review.xlsx'), index=False)
    pd.DataFrame(duplicate_in_batch).to_csv(os.path.join(reports_dir, 'duplicates_in_batch.csv'), index=False)

    summary_content = f"""# Extraction & Recovery Summary: Part 140
- **Batch ID**: `{batch_id}`
- **Source PDF**: `{pdf_path}`
- **Total Pages Scanned**: {total_pages}
- **New Valid Missing Voters Recovered**: {len(new_valid)}
- **Already Existing in DB**: {len(already_in_db)}
- **EPIC Collisions / Conflicts**: {len(conflicts)}
- **Quarantined**: {len(quarantined)}
- **Duplicates in Batch**: {len(duplicate_in_batch)}
- **Reports Directory**: `{reports_dir}`
"""
    with open(os.path.join(reports_dir, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(summary_content)

    print("\n" + summary_content)

if __name__ == '__main__':
    run()
