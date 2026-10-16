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
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('|', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^567', 'SGZ', s)
    s = re.sub(r'^1KI', 'IKI', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    m = re.search(r'([A-Z]{3}\d{7})', s)
    if m: return m.group(1)
    m2 = re.search(r'([A-Z]{2,4}\d{6,8})', s)
    if m2: return m2.group(1)
    return None

pdf_path = 'C:/Users/techb/Desktop/electoral-portal-main/pdf-ocr made/kolar entire kasba hobli - 2026 (3)_ocred.pdf'
doc = pymupdf.open(pdf_path)

parsed = []
for pno in range(1, 10):
    page = doc[pno]
    blocks = page.get_text('blocks')
    for b in blocks:
        if b[1] < 60 or b[3] > 550:
            continue
        txt = b[4].strip()
        lines = [clean_str(l) for l in txt.split('\n') if clean_str(l)]
        if len(lines) < 2:
            continue
        
        name = lines[0]
        rel = lines[1] if len(lines) > 1 else None
        
        if any(h in (name or '').lower() for h in ['name of', 'elector', 'part no', 'father', 'table of', 'address', 'qualification', 'kolar (dist)']):
            continue
            
        m_ep = re.search(r'([A-Za-z0-9\$\|\.]{8,15})', txt)
        epic = clean_epic(txt)
        
        m_age = re.search(r'\b(1[89]|[2-9]\d)\s*[\/\|\[\s]\s*([MF])\b', txt)
        if m_age:
            age = int(m_age.group(1))
            sex = m_age.group(2)
        else:
            m_age2 = re.search(r'\b(1[89]|[2-9]\d)\b', txt)
            age = int(m_age2.group(1)) if m_age2 else None
            m_sex2 = re.search(r'\b([MF])\b', txt)
            sex = m_sex2.group(1) if m_sex2 else None
            
        # Serial number search
        # Typically serial appears as a standalone integer or '# 123'
        ser = None
        m_ser = re.findall(r'(?:#\s*|\b)(\d{1,5})\b', txt)
        for cand in m_ser:
            c_int = int(cand)
            if 1 <= c_int <= 5500 and c_int != age:
                ser = c_int
                break
                
        parsed.append({
            'page': pno + 1,
            'name': name,
            'relative_name': rel,
            'age': age,
            'sex': sex,
            'epic': epic,
            'serial': ser
        })

print(f'Parsed {len(parsed)} voters from pages 2-10.')
for p in parsed[:15]:
    print(p)
