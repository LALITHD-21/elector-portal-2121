import json

with open('etl/reports/missing_voters_gap_analysis.json', 'r', encoding='utf-8') as f:
    analysis = json.load(f)

# Filter for parts where deficit > 0
missing_parts = [a for a in analysis if a['deficit'] > 50]
print(f"Total parts with significant missing voter deficit (>50 voters): {len(missing_parts)}")
total_deficit = sum(a['deficit'] for a in missing_parts)
print(f"Total estimated missing voters across all these parts: {total_deficit}")

print("\nAll parts with deficit > 50:")
for a in missing_parts:
    print(f"Part {a['part']:>3}: DB={a['db_count']:>5}, PDF_Pages={a['pdf_pages']:>4}, Est_PDF_Voters={a['est_pdf_voters']:>5}, Deficit={a['deficit']:>5} | Digital={a['is_digital']} | {a['pdf_file']}")
