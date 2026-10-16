import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('web/.env.local')

sb = create_client(os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

# Fetch all serial numbers for Part 32
db_serials = []
page_size = 1000
start = 0
while True:
    res = sb.from_('electors').select('serial_number').eq('part_number', '32').range(start, start + page_size - 1).execute()
    rows = res.data or []
    db_serials.extend([r['serial_number'] for r in rows if r.get('serial_number')])
    if len(rows) < page_size:
        break
    start += page_size

print(f"Part 32: Total serials in DB = {len(db_serials)}")
if db_serials:
    min_sno = min(db_serials)
    max_sno = max(db_serials)
    missing = set(range(1, max_sno + 1)) - set(db_serials)
    print(f"Serial range in DB: {min_sno} to {max_sno}")
    print(f"Total missing serial numbers in Part 32: {len(missing)}")
    print(f"First 25 missing serials: {sorted(list(missing))[:25]}")
