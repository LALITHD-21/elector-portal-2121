import pymupdf
import re
import json

doc = pymupdf.open("updates voter list pdf/112_1791587543.pdf.pdf")

def clean_text(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    # strip OCR noise characters at ends
    s = re.sub(r'^[\s\.,_\-!#~;:\'"]+|[\s\.,_\-!#~;:\'"]+$', '', s).strip()
    return s if s else None

def clean_epic(s):
    if not s: return None
    s = s.upper().replace(' ', '').replace(':', '').replace('.', '')
    # Match standard EPIC formats: 3 letters + 7 digits (e.g. NMO3374717, INM03374717, MHR2730133)
    # or handle prefix errors like INMO -> NMO or INM
    m = re.search(r'([A-Z]{3,4}\d{6,8})', s)
    if m:
        ep = m.group(1)
        if ep.startswith('INMO'):
            ep = 'NMO' + ep[4:]
        if len(ep) <= 11:
            return ep
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
    return 'M' if 'MALE' in s else ('F' if 'FEM' in s else None)

def parse_p112_page(pno):
    page = doc[pno]
    blocks = page.get_text("blocks")
    voters_on_page = []
    
    for b in blocks:
        # Check if this block is a voter block
        # Voter block coordinates: x0 < 60, x1 > 700, y1 - y0 > 30
        if b[0] < 60 and b[2] > 700 and (b[3] - b[1]) > 30:
            text = b[4].strip()
            # Ignore headers
            if any(h in text for h in ["Electoral", "Part No", "Name of the Elector", "father/lMother"]):
                continue
            
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if len(lines) < 3:
                continue
            
            # Find serial number, age, sex, epic
            serial = None
            epic = None
            age = None
            sex = None
            
            # Extract EPIC
            epic_match = re.search(r'([A-Za-z]{2,4}[:\.\s]?\d{6,8})', text)
            if epic_match:
                epic = clean_epic(epic_match.group(1))
            
            # Find lines with single or few numbers
            # Usually serial is an isolated number or preceded by , or .
            # Age is usually 18-100
            # Sex is M or F
            name_candidates = []
            rel_candidates = []
            addr_parts = []
            
            for l in lines:
                l_clean = clean_text(l)
                if not l_clean or l_clean in ['Photo', 'Available', 'I', 'Karnataka', 'IKamataka', '1Kamataka']:
                    continue
                
                # Check for sex
                if l_clean in ['M', 'F', 'O', 'Ml', 'Fl', 'M.', 'F.']:
                    sex = 'M' if 'M' in l_clean else 'F'
                    continue
                
                # Check for age
                m_age = re.match(r'^(\d{2})\.?$', l_clean)
                if m_age and 18 <= int(m_age.group(1)) <= 110 and not age:
                    age = int(m_age.group(1))
                    continue
                
                # Check for serial
                m_ser = re.match(r'^[,\.]?(\d{1,5})[,\.]?$', l_clean)
                if m_ser and not serial:
                    val = int(m_ser.group(1))
                    if val != age and val < 4500:
                        serial = val
                        continue
                
                # Check for EPIC line
                if epic and epic[:4] in l_clean.upper().replace(' ', ''):
                    continue
                
                # Filter out obvious qualification / occupation keywords
                if l_clean.upper() in ['BA', 'BCOM', 'BSC', 'MA', 'MSC', 'MCOM', 'BE', 'BTECH', 'MTECH', 'BCA', 'MCA', 'BBA', 'MBA', 'TEACHER', 'PENSIONER', 'ENGINEER', 'SOFTWARE ENGINEER', 'SELF EMPLOYEE', 'OWN BUSINESS', 'HOUSEWIFE']:
                    continue
                
                # If first candidate, it's name
                if not name_candidates:
                    name_candidates.append(l_clean)
                elif not rel_candidates:
                    rel_candidates.append(l_clean)
                else:
                    addr_parts.append(l_clean)
            
            if name_candidates or epic or serial:
                name = name_candidates[0] if name_candidates else None
                relative = rel_candidates[0] if rel_candidates else None
                address = ", ".join(addr_parts) if addr_parts else None
                
                voters_on_page.append({
                    "serial_number": serial,
                    "epic_number": epic,
                    "name": name,
                    "relative_name": relative,
                    "age": age,
                    "sex": sex,
                    "address": address,
                    "page": pno + 1
                })
                
    return voters_on_page

# Test on pages 1 to 10
sample_voters = []
for p in range(1, 10):
    sample_voters.extend(parse_p112_page(p))

print(f"Parsed {len(sample_voters)} voters from pages 2-10:")
for v in sample_voters[:10]:
    print(f"  Serial {v['serial_number']}: EPIC={v['epic_number']}, Name={v['name']}, Rel={v['relative_name']}, Age={v['age']}, Sex={v['sex']}")
