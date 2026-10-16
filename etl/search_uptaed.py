import os
import sys
import glob
import openpyxl
from concurrent.futures import ProcessPoolExecutor

target = "3458064"

def search_file(f):
    try:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        for idx, r in enumerate(ws.iter_rows(values_only=True)):
            row_str = " ".join(str(c) for c in r if c is not None)
            if target in row_str:
                return (f, idx + 1, r)
    except Exception:
        pass
    return None

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    all_files = glob.glob("uptaed voter list/*.xlsx") + glob.glob("new file/*.xlsx")
    print(f"Searching {len(all_files)} files in parallel for {target}...")
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(search_file, all_files))
        
    found = [r for r in results if r is not None]
    if found:
        for f, row_idx, data in found:
            print(f"FOUND IN {f} at row {row_idx}:")
            print(data)
    else:
        print("Not found in any uptaed voter list or new file")
