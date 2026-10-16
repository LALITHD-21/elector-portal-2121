import os
import re
import json
import pymupdf
import pandas as pd

def clean_str(s):
    if not s: return None
    s = re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    return s if s else None

def clean_epic(s):
    if not s: return None
    s = str(s).upper().replace(' ', '').replace(':', '').replace('.', '').replace('-', '').replace('|', '').replace('[', '').replace(']', '')
    s = re.sub(r'^[5\$]GZ', 'SGZ', s)
    s = re.sub(r'^[I1]NMO', 'NMO', s)
    s = re.sub(r'^NM0', 'NMO', s)
    s = re.sub(r'^1KI', 'IKI', s)
    
    m = re.search(r'([A-Z]{2,4}\d{5,8})', s)
    if m:
        ep = m.group(1)
        if len(ep) == 9 and re.match(r'^[A-Z]{3}\d{6}$', ep):
            ep = ep[:3] + '0' + ep[3:]
        elif len(ep) == 11 and re.match(r'^[A-Z]{3}0\d{7}$', ep):
            ep = ep[:3] + ep[4:]
        return ep
    return None

def parse_digital_pdf(pdf_path, expected_part=None):
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    part_num = str(expected_part) if expected_part else None
    
    meta = {'district': None, 'taluk': None, 'area': None}
    if total_pages > 1:
        txt1 = doc[1].get_text()
        m_part = re.search(r'Part\s*No[:\s]+(\d+)', txt1, re.I)
        if m_part and not part_num:
            part_num = m_part.group(1)
        m_dist = re.search(r'District\s*[:\s]+([^\n]+)', txt1, re.I)
        if m_dist: meta['district'] = m_dist.group(1).strip()
        m_taluk = re.search(r'Taluk/Town/City\s*[:\s]+([^\n]+)', txt1, re.I)
        if m_taluk: meta['taluk'] = m_taluk.group(1).strip()

    summary_txt = doc[-1].get_text()
    summary = {}
    m_net = re.search(r'Net\s*Electors\s*\n+(\d+)\s*\n+(\d+)\s*\n+\d+\s*\n+(\d+)', summary_txt, re.I)
    if m_net:
        summary['net_male'] = int(m_net.group(1))
        summary['net_female'] = int(m_net.group(2))
        summary['net_total'] = int(m_net.group(3))
    
    all_voters = []
    current_section = 'Mother Roll'

    for p_idx in range(1, total_pages - 1):
        page = doc[p_idx]
        txt = page.get_text()

        if 'III. Deletions list' in txt or 'DELETIONS LIST' in txt:
            current_section = 'Deletions'
        elif 'Supplement - 1' in txt and 'Additions' in txt:
            current_section = 'Supplement - 1'
        elif 'Supplement - 2' in txt and 'Additions' in txt:
            current_section = 'Supplement - 2'

        blocks = page.get_text('blocks')
        header_cutoff = 120.0 if p_idx == 1 else 60.0
        body_blocks = [b for b in blocks if header_cutoff <= b[1] <= 558]
        
        # Collect all serial fragments at x < 48.0
        raw_sno_items = []
        for b in body_blocks:
            if b[0] < 48.0:
                raw_sno_items.append({
                    'txt': b[4].strip(),
                    'ym': (b[1] + b[3]) / 2.0,
                    'is_modified': '#' in b[4]
                })

        raw_sno_items.sort(key=lambda s: s['ym'])
        
        merged_sno_items = []
        for it in raw_sno_items:
            if not merged_sno_items:
                merged_sno_items.append(it)
            else:
                prev = merged_sno_items[-1]
                if abs(it['ym'] - prev['ym']) < 25:
                    prev['txt'] = prev['txt'] + it['txt']
                    prev['ym'] = (prev['ym'] + it['ym']) / 2.0
                    prev['is_modified'] = prev['is_modified'] or it['is_modified']
                else:
                    merged_sno_items.append(it)

        clean_snos = []
        for m in merged_sno_items:
            lines = [l.strip() for l in m['txt'].split('\n') if l.strip()]
            sno_str = ''
            for l in lines:
                if re.match(r'^[A-Za-z]', l):
                    break
                d = re.sub(r'[^\d]', '', l)
                if d:
                    sno_str += d
                    if len(sno_str) >= 4:
                        break

            if sno_str and len(sno_str) <= 6:
                val = int(sno_str)
                clean_snos.append({
                    'sno': val,
                    'is_modified': m['is_modified'],
                    'y_mid': m['ym']
                })

        if not clean_snos:
            continue

        bands = []
        for i, s in enumerate(clean_snos):
            top_y = header_cutoff if i == 0 else (clean_snos[i-1]['y_mid'] + s['y_mid']) / 2.0
            bot_y = 560.0 if i == len(clean_snos) - 1 else (s['y_mid'] + clean_snos[i+1]['y_mid']) / 2.0
            bands.append({
                'sno': s['sno'],
                'is_modified': s['is_modified'],
                'top': top_y,
                'bot': bot_y,
                'blocks': []
            })

        for b in body_blocks:
            ym = (b[1] + b[3]) / 2.0
            for band in bands:
                if band['top'] <= ym < band['bot']:
                    band['blocks'].append(b)
                    break

        for band in bands:
            band_blocks = sorted(band['blocks'], key=lambda b: b[0])
            name_addr_blocks = [b for b in band_blocks if b[0] < 420]
            qual_occ_detail_blocks = [b for b in band_blocks if b[0] >= 420]

            name, rel, addr, qual, occ, age, sex, epic = None, None, None, None, None, None, None, None

            if name_addr_blocks:
                na_lines = []
                for b in name_addr_blocks:
                    for l in b[4].split('\n'):
                        l_str = l.strip()
                        if re.match(r'^#?\s*\d+\s*$', l_str):
                            continue
                        if l_str:
                            na_lines.append(l_str)

                if len(na_lines) >= 1: name = na_lines[0]
                if len(na_lines) >= 2: rel = na_lines[1]
                if len(na_lines) >= 3: addr = ', '.join(na_lines[2:])

            all_right_lines = []
            for b in qual_occ_detail_blocks:
                all_right_lines.extend([l.strip() for l in b[4].split('\n') if l.strip()])

            # Extract demographics and EPIC from all right lines
            non_meta_lines = []
            for line in all_right_lines:
                # Check for EPIC
                if not epic:
                    cleaned_ep = clean_epic(line)
                    if cleaned_ep:
                        epic = cleaned_ep
                        continue

                # Check for Sex
                if line in ['M', 'Male', 'm', 'MALE'] and not sex:
                    sex = 'M'
                    continue
                elif line in ['F', 'Female', 'f', 'FEMALE'] and not sex:
                    sex = 'F'
                    continue

                # Check for Age
                m_age = re.search(r'^\b(1[89]|[2-9]\d|10\d)\b$', line)
                if m_age and not age:
                    age = int(m_age.group(1))
                    continue

                # Filter photo box
                if line.lower() in ['photo', 'available', 'photo available']:
                    continue

                non_meta_lines.append(line)

            # Assign qualification and occupation from remaining lines
            if len(non_meta_lines) == 1:
                qual = non_meta_lines[0]
            elif len(non_meta_lines) >= 2:
                qual = non_meta_lines[0]
                occ = ' '.join(non_meta_lines[1:])

            # Fallback search for EPIC in case it was in name_addr
            if not epic:
                for b in name_addr_blocks:
                    for l in b[4].split('\n'):
                        cleaned_ep = clean_epic(l)
                        if cleaned_ep:
                            epic = cleaned_ep
                            break

            if not (name or rel or epic):
                continue

            all_voters.append({
                'part_number': part_num,
                'serial_number': band['sno'],
                'is_modified': band['is_modified'],
                'epic_number': epic,
                'name': clean_str(name),
                'relative_name': clean_str(rel),
                'address': clean_str(addr),
                'qualification': clean_str(qual),
                'occupation': clean_str(occ),
                'age': age,
                'sex': sex,
                'district': meta['district'],
                'taluk': meta['taluk'],
                'section': current_section,
                'page': p_idx + 1
            })

    return all_voters, summary

if __name__ == '__main__':
    for p_target in ['10', '13', '28', '36', '72']:
        pdf_map = {
            '10': r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\10e_1791811086.pdf',
            '13': r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\13E_1791811086.pdf',
            '28': r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\28E_1791811630.pdf',
            '36': r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\36e_1791966609.pdf',
            '72': r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\72e_1791875014.pdf'
        }
        voters, summary = parse_digital_pdf(pdf_map[p_target], expected_part=p_target)
        unique_voters = {}
        for v in voters:
            unique_voters[(v['part_number'], v['serial_number'])] = v

        serials = sorted(list(unique_voters.keys()), key=lambda k: k[1])
        min_sno = serials[0][1] if serials else 0
        max_sno = serials[-1][1] if serials else 0
        missing = set(range(min_sno, max_sno + 1)) - set(k[1] for k in serials)
        
        valid_epics = sum(1 for v in unique_voters.values() if v.get('epic_number'))

        out_json = f'etl/reports/part_{p_target}_extracted.json'
        out_csv = f'etl/reports/part_{p_target}_extracted.csv'
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(list(unique_voters.values()), f, indent=2, ensure_ascii=False)
        pd.DataFrame(list(unique_voters.values())).to_csv(out_csv, index=False)

        print(f"Part {p_target:>2}: Total={len(voters):>5}, Unique={len(unique_voters):>5}, ValidEPIC={valid_epics:>5}, MissingGaps={len(missing)}, Dups={len(voters)-len(unique_voters)}")
