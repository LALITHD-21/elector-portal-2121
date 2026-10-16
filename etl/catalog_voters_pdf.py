import os
import re
import json
import pymupdf

folder = r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF'
files = [f for f in os.listdir(folder) if f.endswith('.pdf')]

# Sort by part number extracted from filename
def get_part_key(name):
    m = re.match(r'^(\d+)', name)
    return int(m.group(1)) if m else 9999

files.sort(key=get_part_key)

print(f"Total PDFs found: {len(files)}")

catalog = []
for f in files:
    m = re.match(r'^(\d+)', f)
    part_num = m.group(1) if m else "Unknown"
    fp = os.path.join(folder, f)
    size_mb = os.path.getsize(fp) / (1024 * 1024)
    try:
        doc = pymupdf.open(fp)
        pages = len(doc)
        
        # Check first page and last page for text
        p1_text = doc[1].get_text() if pages > 1 else doc[0].get_text()
        last_text = doc[-1].get_text() if pages > 0 else ""
        is_digital_text = len(p1_text.strip()) > 200
        
        catalog.append({
            'filename': f,
            'part': part_num,
            'pages': pages,
            'size_mb': round(size_mb, 2),
            'has_digital_text': is_digital_text,
            'p1_sample': p1_text[:120].replace('\n', ' ') if is_digital_text else ""
        })
    except Exception as e:
        catalog.append({
            'filename': f,
            'part': part_num,
            'error': str(e)
        })

os.makedirs('etl/reports', exist_ok=True)
with open('etl/reports/voters_pdf_catalog.json', 'w', encoding='utf-8') as out:
    json.dump(catalog, out, indent=2)

print(f"Catalog saved to etl/reports/voters_pdf_catalog.json")
print(f"First 10 catalog entries:")
for c in catalog[:10]:
    print(f"  Part {c['part']:>3} | File: {c['filename']} | Pages: {c['pages']:>4} | Size: {c['size_mb']:>5.1f}MB | Digital: {c['has_digital_text']}")
