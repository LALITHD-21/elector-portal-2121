import os
import re
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('web/.env.local')
sb = create_client(os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

# 1. Load catalog
with open('etl/reports/voters_pdf_catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

pdf_by_part = {}
for c in catalog:
    p = str(c.get('part'))
    pdf_by_part[p] = c

# 2. Get booth summary from database
res = sb.rpc('get_booths_summary').execute()
booths = res.data or []

# Combine by part_number (in case there are multiple entries)
db_by_part = {}
for b in booths:
    p = str(b.get('part_number'))
    db_by_part[p] = db_by_part.get(p, 0) + b.get('total_electors', 0)

# 3. Compare each part
analysis = []
for p_num in range(1, 152):
    sp = str(p_num)
    db_count = db_by_part.get(sp, 0)
    pdf_info = pdf_by_part.get(sp)
    
    pages = pdf_info['pages'] if pdf_info else 0
    # Karnataka Graduates electoral rolls have typically 8-10 electors per page (excluding cover and last page)
    est_voters_in_pdf = max(0, (pages - 2) * 8) if pages > 2 else 0
    
    deficit = est_voters_in_pdf - db_count
    analysis.append({
        'part': p_num,
        'db_count': db_count,
        'pdf_pages': pages,
        'pdf_file': pdf_info['filename'] if pdf_info else 'MISSING_PDF',
        'is_digital': pdf_info['has_digital_text'] if pdf_info else False,
        'est_pdf_voters': est_voters_in_pdf,
        'deficit': deficit
    })

analysis.sort(key=lambda x: x['deficit'], reverse=True)

print("=== TOP 25 PARTS WITH HIGHEST MISSING VOTERS IN DATABASE ===")
print(f"{'Part':>5} | {'DB Count':>8} | {'PDF Pages':>9} | {'Est PDF Voters':>14} | {'Est Missing':>11} | {'Digital?':>8} | File")
print("-" * 90)
for a in analysis[:25]:
    print(f"{a['part']:>5} | {a['db_count']:>8} | {a['pdf_pages']:>9} | {a['est_pdf_voters']:>14} | {a['deficit']:>11} | {str(a['is_digital']):>8} | {a['pdf_file']}")

with open('etl/reports/missing_voters_gap_analysis.json', 'w', encoding='utf-8') as out:
    json.dump(analysis, out, indent=2)
print("\nFull gap analysis saved to etl/reports/missing_voters_gap_analysis.json")
