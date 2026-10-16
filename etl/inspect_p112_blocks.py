import pymupdf
import re
import json

doc = pymupdf.open("updates voter list pdf/112_1791587543.pdf.pdf")

def parse_p112_text_page(page_text):
    # Split page by blocks or lines
    lines = [l.strip() for l in page_text.split('\n') if l.strip()]
    # Voters have: Name, Father/Mother/Husband, Address, Qualification, Occupation, Serial, Age, Sex, EPIC
    # Let's inspect line patterns
    return lines

# Let's test on pages 2, 3, 4, 5, 6
for pno in range(1, 6):
    txt = doc[pno].get_text()
    print(f"=== PAGE {pno+1} ===")
    blocks = doc[pno].get_text("blocks")
    for b in blocks:
        # A voter block typically has x0 around 35 and x1 > 700
        # and height between 40 and 100
        if b[0] < 50 and b[2] > 700 and (b[3] - b[1]) > 30 and "Electoral" not in b[4] and "Part No" not in b[4] and "Name of the Elector" not in b[4]:
            print(f"VOTER BLOCK ({b[1]:.1f} - {b[3]:.1f}):")
            b_lines = [l.strip() for l in b[4].split('\n') if l.strip()]
            for bl in b_lines:
                print("   ", bl)
