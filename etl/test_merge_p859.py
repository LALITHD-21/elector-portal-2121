import pymupdf
import re

doc = pymupdf.open(r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\36e_1791966609.pdf')
p = doc[858]
blocks = [b for b in p.get_text('blocks') if 60 <= b[1] <= 560 and b[0] < 48]

# Sort by y_mid
items = []
for b in blocks:
    txt = b[4].strip()
    ym = (b[1] + b[3]) / 2.0
    items.append({'txt': txt, 'ym': ym, 'y0': b[1], 'y1': b[3]})

items.sort(key=lambda x: x['ym'])

print("Raw items:")
for it in items:
    print(f"  y={it['ym']:.1f} -> {repr(it['txt'])}")

# Merge fragments that belong to same voter row (y distance < 25)
merged_rows = []
for it in items:
    if not merged_rows:
        merged_rows.append(it)
    else:
        prev = merged_rows[-1]
        if abs(it['ym'] - prev['ym']) < 25:
            # Combine
            prev['txt'] = prev['txt'] + '' + it['txt']
            prev['ym'] = (prev['ym'] + it['ym']) / 2.0
        else:
            merged_rows.append(it)

print("\nMerged rows:")
for r in merged_rows:
    # Clean digits
    clean_num = re.sub(r'[^\d]', '', r['txt'])
    print(f"  y={r['ym']:.1f} -> {clean_num}")
