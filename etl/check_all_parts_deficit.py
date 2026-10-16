import json

with open('etl/reports/missing_voters_gap_analysis.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total parts analyzed: {len(data)}")
already_complete = [d for d in data if d['deficit'] <= 0]
small_deficit = [d for d in data if 0 < d['deficit'] <= 50]
large_deficit = [d for d in data if d['deficit'] > 50]

print(f"Parts already complete or surplus in DB: {len(already_complete)}")
print(f"Parts with tiny difference (1-50): {len(small_deficit)}")
print(f"Parts with significant missing voters (>50): {len(large_deficit)}")

print("\nParts with significant missing voters:")
for d in large_deficit:
    print(f"  Part {d['part']:>3}: DB={d['db_count']:>5}, PDF_Pages={d['pdf_pages']:>4}, EstMissing={d['deficit']:>4} | {d['pdf_file']}")
