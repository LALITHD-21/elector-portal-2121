import sys
import re
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

def clean_str(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^[\s\.,_\-!#~;:\'\"\|]+|[\s\.,_\-!#~;:\'\"\|]+$', '', s).strip()
    if not s or s.lower() in ['.', '-', '_', 'none', 'null', 'na', 'n/a', 'nil']: return None
    return s

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    m = re.search(r'([A-Z]{2,4}\d{6,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) <= 12:
            return ep
    return None

def parse_pdf_stream(pdf_path, max_pages=15):
    doc = pymupdf.open(pdf_path)
    print(f"Testing {pdf_path}: total pages {len(doc)}")
    
    parsed_voters = []
    for pno in range(1, min(max_pages, len(doc) - 1)):
        txt = doc[pno].get_text()
        # Split by Photo Available / Available
        # Or split by patterns
        blocks = re.split(r'(?:Photo\s*Available|Available\b)', txt, flags=re.IGNORECASE)
        for b in blocks:
            b = b.strip()
            if len(b) < 15: continue
            
            lines = [clean_str(l) for l in b.split('\n') if clean_str(l)]
            # Filter header noise
            lines = [l for l in lines if not any(h in l.lower() for h in [
                'part no', 'table of content', 'electoral roll', 'final electoral',
                'name of the elector', 'father/mother', 'address (place', 'qualification',
                'photo of the elector', 'karnataka legislative', 'graduates'
            ])]
            if not lines: continue
            
            # Check for serial number in first or second line
            ser = None
            start_idx = 0
            m_s = re.match(r'^(?:#\s*|Sl\s*No\s*[:\.]?\s*)?(\d{1,5})$', lines[0])
            if m_s and int(m_s.group(1)) <= 15000:
                ser = int(m_s.group(1))
                start_idx = 1
                
            if start_idx >= len(lines): continue
            
            name = lines[start_idx]
            rel = lines[start_idx + 1] if start_idx + 1 < len(lines) else None
            
            # Skip if name looks like address or header
            if any(h in name.lower() for h in ['karnataka', '(vtc)', '(post)', '(dist)', 'ward', 'cross', 'layout', 'college', 'nagar']):
                continue
                
            # If rel has address marker, split or clean
            if rel and any(h in rel.lower() for h in ['(vtc)', '(post)', '(dist)', 'karnataka']):
                rel = None
                
            # EPIC extraction
            epic = clean_epic(b)
            
            # Age and Sex
            m_age = re.search(r'\b(1[89]|[2-9]\d)\s*[\/\|\[\s]\s*([MF])\b', b)
            if m_age:
                age = int(m_age.group(1))
                sex = m_age.group(2)
            else:
                m_age2 = re.search(r'\b(1[89]|[2-9]\d)\b', b)
                age = int(m_age2.group(1)) if m_age2 else None
                m_sex2 = re.search(r'\b([MF])\b', b)
                sex = m_sex2.group(1) if m_sex2 else None
                
            parsed_voters.append({
                'page': pno + 1,
                'ser': ser,
                'name': name,
                'rel': rel,
                'age': age,
                'sex': sex,
                'epic': epic
            })
            
    print(f"Extracted {len(parsed_voters)} voters from first {max_pages} pages.")
    for v in parsed_voters[:12]:
        print(v)

# Test Part 36
parse_pdf_stream('C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chit.pdf', 12)
# Test Part 140
parse_pdf_stream('C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/kolar entire kasba hobli - 2026 (3)_ocred.pdf', 12)
# Test Part 112
parse_pdf_stream('C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/chikkaballapur nandi & kasba hobli 2026_ocred.pdf', 12)
