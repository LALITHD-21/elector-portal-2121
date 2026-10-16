from test_digital_extractor import parse_digital_pdf
import sys

sys.stdout.reconfigure(encoding='utf-8')
pdf = r'C:\Users\techb\Desktop\electrol-portal-NEW-main\electrol-portal-NEW-main\VOTERS PDF\36e_1791966609.pdf'
voters, summary = parse_digital_pdf(pdf, expected_part='36')

sno_1 = [v for v in voters if v['serial_number'] == 1]
print(f"Serial 1 occurs {len(sno_1)} times:")
for v in sno_1:
    print(f"  Page {v['page']}: Name={v['name']}, Section={v['section']}, EPIC={v['epic_number']}")

sno_10 = [v for v in voters if v['serial_number'] == 10]
print(f"\nSerial 10 occurs {len(sno_10)} times:")
for v in sno_10:
    print(f"  Page {v['page']}: Name={v['name']}, Section={v['section']}, EPIC={v['epic_number']}")
