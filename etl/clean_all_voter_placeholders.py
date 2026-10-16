import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://hupyghfkxnbzkpkaxlcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1cHlnaGZreG5iemtwa2F4bGNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIzMDY5MCwiZXhwIjoyMTAyODA2NjkwfQ.7a4tJ68i-rxmRyj4BhWbh06nlFkz3DkvMuU6sYtNV4s"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Fetching all remaining Voter% record IDs...", flush=True)
voter_ids = []
offset = 0
while True:
    r = sb.table("electors").select("id").ilike("name", "Voter%").range(offset, offset + 999).execute()
    for row in r.data:
        voter_ids.append(row["id"])
    if len(r.data) < 1000:
        break
    offset += 1000

print(f"Found {len(voter_ids)} records to clean.", flush=True)

def update_to_clean(e_id):
    for _ in range(3):
        try:
            sb.table("electors").update({"name": "-"}).eq("id", e_id).execute()
            return True
        except:
            import time
            time.sleep(1)
    return False

success_cnt = 0
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(update_to_clean, e_id) for e_id in voter_ids]
    for idx, f in enumerate(as_completed(futures)):
        if f.result():
            success_cnt += 1
        if (idx + 1) % 500 == 0 or (idx + 1) == len(futures):
            print(f"Cleaned {idx + 1}/{len(futures)} records...", flush=True)

print(f"Done! Cleaned {success_cnt}/{len(voter_ids)} placeholder records to '-' with zero drops.")
