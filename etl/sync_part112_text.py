import os
import sys
import re
import json
import time
import pymupdf
from supabase import create_client

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://hupyghfkxnbzkpkaxlcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1cHlnaGZreG5iemtwa2F4bGNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIzMDY5MCwiZXhwIjoyMTAyODA2NjkwfQ.7a4tJ68i-rxmRyj4BhWbh06nlFkz3DkvMuU6sYtNV4s"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

BOOTH_112 = {
    "district": "Chikkaballapur",
    "taluk": "Chickballapur",
    "ac_name": "Chikkaballapur",
    "part_number": "112",
    "polling_station_name": "Taluk Office, Chickballapur",
    "polling_address": "Nandi and Kasaba Hobli, Chickballapur Taluk, Chikkaballapura District, Karnataka"
}

def clean_text(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^[\s\.,_\-!#~;:\'"]+|[\s\.,_\-!#~;:\'"]+$', '', s).strip()
    if s in ['.', '-', '_', 'None', 'null', 'NULL', 'NA', 'N/A', 'NIL']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '')
    m = re.search(r'([A-Z]{2,4}\d{6,8})', s)
    if m:
        ep = m.group(1)
        if ep.startswith('INMO'): ep = 'NMO' + ep[4:]
        if len(ep) <= 11: return ep
    return None

def clean_age(s):
    if not s: return None
    m = re.search(r'\b(1[89]|[2-9]\d|10\d)\b', str(s))
    return int(m.group(1)) if m else None

def clean_sex(s):
    if not s: return None
    s = str(s).upper()
    if 'M' in s and 'F' not in s: return 'M'
    if 'F' in s: return 'F'
    return None

doc = pymupdf.open("updates voter list pdf/112_1791587543.pdf.pdf")

print("=" * 70)
print(" PARSING PART 112 EMBEDDED TEXT LAYER (Pages 1 to 282)")
print("=" * 70)

all_parsed_voters = []
expected_serial = 1

for pno in range(1, 282):
    page = doc[pno]
    blocks = page.get_text("blocks")
    
    # Filter voter blocks
    voter_blocks = []
    for b in blocks:
        if b[0] < 60 and b[2] > 700 and (b[3] - b[1]) > 30:
            txt = b[4].strip()
            if any(h in txt for h in ["Electoral", "Part No", "Name of the Elector", "father/lMother"]):
                continue
            voter_blocks.append(b)
            
    voter_blocks.sort(key=lambda b: b[1]) # Sort by Y
    
    for b in voter_blocks:
        lines = [l.strip() for l in b[4].split('\n') if l.strip()]
        if len(lines) < 2: continue
        
        epic = None
        age = None
        sex = None
        serial = None
        
        # Check EPIC
        m_ep = re.search(r'([A-Za-z]{2,4}[:\.\s]?\d{6,8})', b[4])
        if m_ep:
            epic = clean_epic(m_ep.group(1))
            
        name_cands = []
        rel_cands = []
        addr_cands = []
        
        for l in lines:
            lc = clean_text(l)
            if not lc or lc in ['Photo', 'Available', 'I', 'Karnataka', 'IKamataka', '1Kamataka', 'll-Modnication', '#-Modification']:
                continue
            if lc in ['M', 'F', 'O', 'Ml', 'Fl', 'M.', 'F.']:
                sex = 'M' if 'M' in lc else 'F'
                continue
            m_a = re.match(r'^(\d{2})\.?$', lc)
            if m_a and 18 <= int(m_a.group(1)) <= 110 and not age:
                age = int(m_a.group(1))
                continue
            m_s = re.match(r'^[,\.]?(\d{1,5})[,\.]?$', lc)
            if m_s and not serial:
                val = int(m_s.group(1))
                if val != age and val < 4500:
                    serial = val
                    continue
            if epic and epic[:4] in lc.upper().replace(' ', ''):
                continue
            if lc.upper() in ['BA', 'BCOM', 'BSC', 'MA', 'MSC', 'MCOM', 'BE', 'BTECH', 'MTECH', 'BCA', 'MCA', 'BBA', 'MBA', 'TEACHER', 'PENSIONER', 'ENGINEER', 'SOFTWARE ENGINEER', 'SELF EMPLOYEE', 'OWN BUSINESS', 'HOUSEWIFE']:
                continue
                
            if not name_cands:
                name_cands.append(lc)
            elif not rel_cands:
                rel_cands.append(lc)
            else:
                addr_cands.append(lc)
                
        # If serial wasn't found in text, infer from sequence
        if not serial:
            serial = expected_serial
            
        expected_serial = serial + 1
        
        name = name_cands[0] if name_cands else None
        rel = rel_cands[0] if rel_cands else None
        addr = ", ".join(addr_cands) if addr_cands else None
        
        all_parsed_voters.append({
            "serial_number": serial,
            "epic_number": epic,
            "name": name,
            "relative_name": rel,
            "address": addr,
            "age": age,
            "sex": sex,
            "page": pno + 1
        })

print(f"Total electors parsed from text layer: {len(all_parsed_voters)}")
print(f"First elector: Serial {all_parsed_voters[0]['serial_number']} {all_parsed_voters[0]['name']} ({all_parsed_voters[0]['epic_number']})")
print(f"Last elector: Serial {all_parsed_voters[-1]['serial_number']} {all_parsed_voters[-1]['name']} ({all_parsed_voters[-1]['epic_number']})")

# Save parsed electors to JSON cache
cache_path = "etl/part112_parsed_text.json"
with open(cache_path, "w", encoding="utf-8") as f:
    json.dump(all_parsed_voters, f, indent=2)
print(f"Saved to {cache_path}")
