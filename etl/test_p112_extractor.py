import pymupdf
import re
import json

doc = pymupdf.open("updates voter list pdf/112_1791587543.pdf.pdf")

voters = []
for pno in range(1, 282):
    blocks = doc[pno].get_text("blocks")
    for b in blocks:
        text = b[4].strip()
        epic_match = re.search(r'([A-Za-z]{2,5}\d{5,9})', text)
        if epic_match:
            voters.append({
                "page": pno + 1,
                "epic": epic_match.group(1).upper(),
                "text": text
            })

print(f"Extracted {len(voters)} voter blocks with EPIC from pages 2-282")
if voters:
    print("Sample 1:")
    print(voters[0]["text"])
    print("-" * 40)
    print("Sample 2:")
    print(voters[1]["text"])
