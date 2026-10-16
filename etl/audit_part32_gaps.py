import os
import re
from supabase import create_client

env_path = 'web/.env.local'
env = {}
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

supabase = create_client(env['NEXT_PUBLIC_SUPABASE_URL'], env['SUPABASE_SERVICE_ROLE_KEY'])

# Fetch all rows for part 32 with pagination
all_rows = []
page_size = 1000
start = 0
while True:
    res = supabase.table('electors').select('serial_number, epic_number, name').eq('part_number', '32').range(start, start + page_size - 1).execute()
    data = res.data
    if not data:
        break
    all_rows.extend(data)
    if len(data) < page_size:
        break
    start += page_size

print(f"Total rows fetched for Part 32: {len(all_rows)}")
serials = set()
null_serials = 0
for r in all_rows:
    s = r.get('serial_number')
    if s is not None:
        serials.add(s)
    else:
        null_serials += 1

print(f"Unique serials: {len(serials)}, Null serials: {null_serials}")
max_s = max(serials) if serials else 0
print(f"Max serial in DB: {max_s}")

gaps = [s for s in range(1, 4565) if s not in serials]
print(f"Total gaps between 1 and 4564: {len(gaps)}")
print(f"First 25 gaps: {gaps[:25]}")
print(f"Last 25 gaps: {gaps[-25:]}")
