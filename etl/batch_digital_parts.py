import os
import json
from test_digital_extractor import parse_digital_pdf

digital_targets = [
    ('10', r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\10e_1791811086.pdf'),
    ('13', r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\13E_1791811086.pdf'),
    ('28', r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\28E_1791811630.pdf'),
    ('36', r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\36e_1791966609.pdf'),
    ('72', r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\72e_1791875014.pdf')
]

results = []
for part, path in digital_targets:
    voters, summary = parse_digital_pdf(path, expected_part=part)
    unique_voters = {}
    for v in voters:
        unique_voters[(v['part_number'], v['serial_number'])] = v

    serials = sorted(list(unique_voters.keys()), key=lambda k: k[1])
    min_sno = serials[0][1] if serials else 0
    max_sno = serials[-1][1] if serials else 0
    expected_serials = set(range(min_sno, max_sno + 1))
    actual_serials = set(k[1] for k in serials)
    missing = expected_serials - actual_serials

    results.append({
        'part': part,
        'extracted': len(voters),
        'unique': len(unique_voters),
        'min_sno': min_sno,
        'max_sno': max_sno,
        'missing_count': len(missing),
        'summary': summary
    })
    print(f"Part {part:>2}: Extracted={len(voters):>5}, Range={min_sno}-{max_sno}, MissingSerials={len(missing)}, Duplicates={len(voters)-len(unique_voters)}")

os.makedirs('etl/reports', exist_ok=True)
with open('etl/reports/digital_parts_audit.json', 'w') as f:
    json.dump(results, f, indent=2)
