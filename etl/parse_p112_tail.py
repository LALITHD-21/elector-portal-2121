import os
import sys
import re
import json
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = "C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chikkaballapur nandi & kasba hobli 2026_ocred.pdf"
doc = pymupdf.open(pdf_path)

def clean_str(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^[\s\.,_\-!#~;:\'"]+|[\s\.,_\-!#~;:\'"]+$', '', s).strip()
    if not s or s in ['.', '-', '_', 'None', 'null', 'NULL', 'NA', 'N/A', 'NIL']: return None
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

parsed_records = []

for pno in range(282, len(doc) - 1): # pages 283 to 686
    page = doc[pno]
    blocks = page.get_text("blocks")
    
    # Filter voter blocks (y > 100, y < 1180)
    for b in blocks:
        txt = b[4].strip()
        if any(h in txt for h in ["Table of Content", "Part No: 112", "Name of the Elector", "Electoral Rolls"]):
            continue
        
        # Look for EPIC in block
        m_epic = re.search(r'([A-Za-z]{2,4}\d{6,8})', txt)
        epic_val = clean_epic(m_epic.group(1)) if m_epic else None
        
        # Look for serial
        ser_val = None
        m_ser = re.search(r'\b(1[7-9]\d{2}|[2-4]\d{3})\b', txt)
        if m_ser:
            ser_val = int(m_ser.group(1))
            
        # Look for age & sex
        age_val = None
        m_age = re.search(r'\b(1[89]|[2-9]\d)\b', txt)
        if m_age and int(m_age.group(1)) != ser_val:
            age_val = int(m_age.group(1))
            
        sex_val = 'M' if re.search(r'\bM\b', txt) else ('F' if re.search(r'\bF\b', txt) else None)
        
        lines = [clean_str(l) for l in txt.split('\n') if clean_str(l)]
        # Filter lines
        valid_lines = [l for l in lines if l and not any(k in l.lower() for k in ['photo', 'available', 'modification', 'residence', 'chikkaballapur', 'qualification', 'karnataka', 'post', 'tq', 'dist'])]
        
        name_val = valid_lines[0] if len(valid_lines) > 0 else None
        rel_val = valid_lines[1] if len(valid_lines) > 1 else None
        
        if epic_val or ser_val or name_val:
            parsed_records.append({
                "page": pno + 1,
                "serial_number": ser_val,
                "epic_number": epic_val,
                "name": name_val,
                "relative_name": rel_val,
                "age": age_val,
                "sex": sex_val
            })

print(f"Extracted {len(parsed_records)} blocks from pages 283 to 686 of Part 112.")
with_epic = [r for r in parsed_records if r['epic_number']]
print(f"Blocks with valid EPIC: {len(with_epic)}")
for r in with_epic[:5]:
    print(f"  P{r['page']} SL={r['serial_number']} EPIC={r['epic_number']} Name={r['name']} Rel={r['relative_name']}")

with open("etl/part112_tail_parsed.json", "w", encoding="utf-8") as f:
    json.dump(with_epic, f, indent=2)
