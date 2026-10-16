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
    m = re.search(r'([A-Za-z]{2,4}\d{6,8})', s)
    if m:
        ep = m.group(1)
        if ep.startswith('INMO'): ep = 'NMO' + ep[4:]
        if len(ep) <= 11: return ep
    return None

pdf_path = "C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chikkaballapur nandi & kasba hobli 2026_ocred.pdf"
doc = pymupdf.open(pdf_path)

print("=" * 70)
print(f" FULL EXTRACTION OF PART 112 OCR'd PDF ({len(doc)} pages)")
print("=" * 70)

all_voters = []

for pno in range(1, len(doc) - 1): # skip cover and last summary
    txt = doc[pno].get_text()
    voter_chunks = re.split(r'\n(?=\d{1,5}\s*\n)', txt)
    chunks = voter_chunks[1:]
    
    for i in range(0, len(chunks), 2):
        c1 = chunks[i]
        c2 = chunks[i+1] if i+1 < len(chunks) else ''
        
        l1 = [clean_str(l) for l in c1.split('\n') if clean_str(l)]
        if not l1: continue
        
        ser_val = int(l1[0]) if l1[0].isdigit() and int(l1[0]) <= 5000 else None
        
        # Filter noise lines
        clean_lines = [l for l in l1 if not any(k in l.lower() for k in ['sino', 'name of the elector', 'father', 'mother', 'husband', 'residence', 'qualification', 'occup', 'table of content', 'electoral rolls', 'part no', 'chikkaballapur'])]
        
        name_val = clean_lines[0] if len(clean_lines) > 0 and len(clean_lines[0]) >= 2 else None
        rel_val = clean_lines[1] if len(clean_lines) > 1 and len(clean_lines[1]) >= 2 else None
        
        m_ep = re.search(r'([A-Za-z]{2,4}[:\.\s]?\d{6,8})', c2) or re.search(r'([A-Za-z]{2,4}[:\.\s]?\d{6,8})', c1)
        epic_val = clean_epic(m_ep.group(1)) if m_ep else None
        
        m_age = re.search(r'\b(1[89]|[2-9]\d)\b', c2) or re.search(r'\b(1[89]|[2-9]\d)\b', c1)
        age_val = int(m_age.group(1)) if m_age else None
        
        sex_val = None
        if re.search(r'\bM\b', c2) or re.search(r'\bM\b', c1): sex_val = 'M'
        elif re.search(r'\bF\b', c2) or re.search(r'\bF\b', c1): sex_val = 'F'
        
        if epic_val or name_val or ser_val:
            all_voters.append({
                "page": pno + 1,
                "serial_number": ser_val,
                "epic_number": epic_val,
                "name": name_val,
                "relative_name": rel_val,
                "age": age_val,
                "sex": sex_val
            })

print(f"Extracted {len(all_voters)} voter records across {len(doc)} pages.")
print(f"Sample: {all_voters[:3]}")

# Save to cache
with open("etl/part112_full_master.json", "w", encoding="utf-8") as f:
    json.dump(all_voters, f, indent=2)
print("Saved to etl/part112_full_master.json")
