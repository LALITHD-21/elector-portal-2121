const path = require('path');
const fs = require('fs');
const envPath = path.resolve(__dirname, '../web/.env.local');
const envContent = fs.readFileSync(envPath, 'utf8');
const env = {};
for (const line of envContent.split('\n')) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, '');
}
const { createClient } = require(path.resolve(__dirname, '../web/node_modules/@supabase/supabase-js'));
const supabase = createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY);

async function check() {
  const { data: topSerials } = await supabase
    .from('electors')
    .select('serial_number, name, epic_number')
    .eq('part_number', '36')
    .order('serial_number', { ascending: false })
    .limit(10);
  console.log('Top 10 serials in DB for Part 36:', topSerials);

  const { data: jan } = await supabase
    .from('electors')
    .select('serial_number, name, epic_number')
    .eq('part_number', '36')
    .ilike('name', '%JANARDHANA PG%');
  console.log('JANARDHANA PG in DB:', jan);
}
check().catch(console.error);
