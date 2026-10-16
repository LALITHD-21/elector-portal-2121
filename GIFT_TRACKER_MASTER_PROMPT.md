# Master Prompt: MLC 2026 Gift Tracker (ಉಡುಗೊರೆ ವಿತರಣಾ ಪೋರ್ಟಲ್)
## Dedicated Private PWA for 1-to-1 Voter Gift Distribution & Anti-Fraud Verification

> [!TIP]
> **How to use this document:** Copy the entire prompt block below (starting from `# SYSTEM ROLE & OBJECTIVE`) and paste it into any advanced AI coding model (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro) or hand it directly to a senior full-stack engineering team. It contains every design token, PostgreSQL database schema, unique anti-duplicate constraints, API contracts, 2-step confirmation modal flow, bilingual dictionary (`en` + `kn`), and PWA specifications required to build a 100% error-free application.

---

```markdown
# SYSTEM ROLE & OBJECTIVE
You are a Principal Full-Stack Engineer and Lead UI/UX Architect specializing in mission-critical electoral logistics, zero-fraud concurrency architectures, and high-performance Progressive Web Applications (PWA).

Your objective is to build a production-ready, fully private Progressive Web App titled:
**"MLC 2026 Gift Tracker" (ಉಡುಗೊರೆ ವಿತರಣಾ ಪೋರ್ಟಲ್)**

The application is built for the electoral campaign of **SHASHI HULIKUNTEMUTT (INC Candidate — Karnataka South-East Graduates' Constituency 2026)** covering **1,92,696 graduate electors across 151 polling stations in 5 districts** (Tumkur, Chitradurga, Davanagere, Kolar, Chikkaballapura).

The primary mission is to track campaign appreciation gifts or voter kits handed over to voters in the field with **STRICT 1-TO-1 ENFORCEMENT (Zero Duplicate Deliveries)**. Under no circumstances can a voter receive a 2nd or 3rd gift.

---

## 1. CORE OPERATIONAL PRINCIPLES & ANTI-FRAUD RULES

1. **Strict 1-Gift-Per-Voter Hard Enforcement:**
   - Client-side checks are NOT trusted alone. The PostgreSQL database must enforce an immutable `CONSTRAINT unique_gift_per_epic UNIQUE (epic_number)`.
   - If two volunteers in the field tap "Issue Gift" on the exact same voter at the exact same millisecond, the database engine MUST physically reject the second write and return a clear `409 Conflict` (Duplicate Blocked).

2. **No Camera / Barcode Scanner:**
   - Field volunteers search solely by **Voter Name** or **EPIC Card Number** (e.g. `SPC3578515` or `Suresh`).
   - Include a **Polling Booth Filter** dropdown so volunteers can lock their view to their assigned booth (e.g., *Part 71 - Handanakere*).

3. **2-Step Confirmation Safety (Anti-Accidental Tap):**
   - Tapping `[ ☑️ Tick: Hand Over Gift / ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ]` does NOT immediately write to the database.
   - It triggers a fast, high-contrast confirmation modal / bottom sheet:
     > **"Confirm Gift Handover?"**  
     > **Elector:** Abhilasha S  
     > **Part / Booth:** Part 71 · Sl. No: 2  
     > **EPIC:** SPC3578515  
     > `[ ✓ Yes, Confirm Handover ]`  `[ Cancel ]`
   - This prevents accidental submissions while walking, scrolling, or operating under bright outdoor sun.

4. **Fully Private & Gated:**
   - Not accessible to the public or political opponents.
   - Protected by a 4-digit Team Passcode (`2026`).
   - Volunteers enter the PIN, their Name (e.g. *"Ramesh K"*), and select their assigned Polling Booth. This session persists in `localStorage`.

5. **Live Field Dashboard & Audit Trail:**
   - Real-time booth progress bar (% of electors gifted in the selected booth).
   - Central Admin Overview with 1-click **Excel / CSV Export** of the audited roll with complete timestamps and volunteer attribution.

---

## 2. TECH STACK & DESIGN SYSTEM

- **Framework:** Next.js 14+ (App Router), React 18, TypeScript
- **Styling:** Tailwind CSS with sovereign civic blue theme, emerald success tokens, and high-contrast amber/red alert states
- **Database:** Supabase PostgreSQL (direct queries against existing `electors` table + new `gift_distributions` table)
- **Icons:** `lucide-react`
- **Typography:** `Plus Jakarta Sans` for UI labels, `JetBrains Mono` for EPIC numbers, Sl numbers, and timestamps, `Noto Sans Kannada` for Kannada script
- **Sound & Haptics:** Web Audio API synth chimes (high pleasant chime on success, double low buzz on duplicate rejection) + `navigator.vibrate([100])`
- **PWA Capabilities:** Standalone manifest (`display: standalone`), short name `GiftTracker`, theme color `#0a1128`, dual-responsive architecture (mobile native bottom-sheet + desktop command center)

---

## 3. DATABASE SCHEMA & ANTI-DUPLICATE ENGINE (PostgreSQL / Supabase)

Execute this script in: **Supabase Dashboard → SQL Editor → Run**:

```sql
-- ====================================================================
-- MLC 2026 GIFT TRACKER - POSTGRESQL SCHEMA
-- ====================================================================

-- 1. Create gift_distributions table
CREATE TABLE IF NOT EXISTS public.gift_distributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Elector Identification (Linked to existing electors dataset)
  epic_number TEXT NOT NULL,
  elector_name TEXT NOT NULL,
  relative_name TEXT,
  part_number TEXT NOT NULL,
  serial_number TEXT NOT NULL,
  district TEXT NOT NULL,
  taluk TEXT NOT NULL,
  polling_station_name TEXT,
  
  -- Volunteer & Delivery Audit
  volunteer_name TEXT NOT NULL,        -- e.g. "Manjunath K"
  volunteer_phone TEXT,                -- Optional
  recipient_mobile TEXT,               -- Mobile number confirmed at delivery (optional)
  booth_part TEXT NOT NULL,            -- Assigned booth part for grouping
  delivery_status TEXT NOT NULL DEFAULT 'DELIVERED', -- 'DELIVERED' or 'REFUSED'
  notes TEXT,                          -- e.g. "Handed over personally"
  
  -- Timestamps
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- ==================================================================
  -- 🔒 ABSOLUTE DATABASE-LEVEL UNIQUE CONSTRAINT:
  -- Guarantees that the database engine physically rejects any second
  -- insert for the exact same EPIC card number.
  -- ==================================================================
  CONSTRAINT unique_gift_per_epic UNIQUE (epic_number)
);

-- 2. High-performance B-Tree indexes for sub-20ms queries
CREATE INDEX IF NOT EXISTS idx_gift_epic ON public.gift_distributions(epic_number);
CREATE INDEX IF NOT EXISTS idx_gift_part ON public.gift_distributions(part_number);
CREATE INDEX IF NOT EXISTS idx_gift_volunteer ON public.gift_distributions(volunteer_name);
CREATE INDEX IF NOT EXISTS idx_gift_issued_at ON public.gift_distributions(issued_at DESC);

-- 3. Enable Row Level Security (RLS) & Policies
ALTER TABLE public.gift_distributions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow service role full access" ON public.gift_distributions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Allow public read of gift distributions" ON public.gift_distributions
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "Allow authenticated/anon insert" ON public.gift_distributions
  FOR INSERT TO anon, authenticated WITH CHECK (true);
```

---

## 4. API CONTRACTS & BACKEND IMPLEMENTATION

### 1. `GET /api/search`
**Parameters:**
- `query` (string, optional): Voter Name or EPIC Number (e.g. `SPC3578515` or `Suresh`)
- `part_number` (string, optional): Booth number filter (e.g. `71`)
- `status` (string, optional): `'all'` | `'pending'` | `'delivered'`
- `limit` (number, default: 50)

**Implementation Logic:**
1. Sanitizes query string to prevent PostgREST injection.
2. Queries the primary `electors` table:
   `electorQuery.or('name.ilike.%' + sanitized + '%,epic_number.ilike.%' + sanitized + '%')`
3. Left-joins `gift_distributions` on `electors.epic_number = gift_distributions.epic_number`.
4. Returns each voter object with live delivery status:
   ```json
   {
     "epic_number": "SPC3578515",
     "name": "Abhilasha S",
     "relative_name": "Arunkumar K S",
     "part_number": "71",
     "serial_number": 2,
     "district": "Tumkur",
     "taluk": "Chikkanayakanahalli",
     "polling_station_name": "Handanakere - Govt Higher Primary School",
     "gift_status": {
       "is_issued": true,
       "volunteer_name": "Manjunath K",
       "issued_at": "2026-10-15T09:42:10.000Z",
       "notes": "Handed over personally"
     }
   }
   ```

### 2. `POST /api/issue`
**Payload:**
```json
{
  "epic_number": "SPC3578515",
  "elector_name": "Abhilasha S",
  "relative_name": "Arunkumar K S",
  "part_number": "71",
  "serial_number": "2",
  "district": "Tumkur",
  "taluk": "Chikkanayakanahalli",
  "polling_station_name": "Handanakere",
  "volunteer_name": "Manjunath K",
  "volunteer_phone": "9845012345",
  "recipient_mobile": "9988776655",
  "notes": "Handed over personally"
}
```

**Atomic Transaction & Error Handling:**
- Attempts to insert into `gift_distributions`.
- **On Success:** Returns `HTTP 201 Created` with the inserted record.
- **On Duplicate Conflict (Postgres code `23505`):**
  - Catches the unique constraint violation.
  - Queries `gift_distributions` to retrieve existing delivery details.
  - Returns `HTTP 409 Conflict`:
    ```json
    {
      "success": false,
      "error": "DUPLICATE_GIFT_BLOCKED",
      "message": "This voter has already been issued a gift!",
      "existing_record": {
        "issued_by": "Ramesh K",
        "issued_at": "2026-10-14T11:24:00.000Z",
        "part_number": "71"
      }
    }
    ```

### 3. `GET /api/stats`
Returns aggregated analytics:
- `total_constituency_electors`: 192,696
- `total_gifts_delivered`: Total count from `gift_distributions`
- `booth_issued`: Count of gifts delivered in the requested booth
- `recent_activity`: Last 10 verified handovers with timestamps

### 4. `GET /api/export`
**Parameters:** `?admin_pin=2026` or `8899`
Generates a streaming `.csv` file containing all rows in `gift_distributions` ordered by `issued_at DESC`.

---

## 5. USER INTERFACE & MOBILE SCREEN FLOW

### Screen 1: Private Gate & Volunteer Login (`PinGateModal.tsx`)
- Sovereign Royal Blue gradient card with INC Hand Emblem and bilingual title.
- **Passcode Input:** 4-digit PIN (`2026`) with large, touch-friendly keypad.
- **Volunteer Profile Input:**
  - Full Name: (e.g. *"Manjunath K"*)
  - Assigned Booth: Dropdown of 151 booths (pre-filtered by district/taluk).
- **Submit Button:** `[ Enter Distribution Portal / ಪ್ರವೇಶಿಸಿ ]`
- Persists session in `localStorage` under key `mlc_gift_volunteer_session`.

---

### Screen 2: Main Search & Tick Registry (`page.tsx`)

```text
┌────────────────────────────────────────────────────────┐
│ 🏛️ MLC 2026 GIFT TRACKER · ಉಡುಗೊರೆ ವಿತರಣೆ             │
│ Volunteer: Manjunath K (Booth 71)            [Exit]    │
├────────────────────────────────────────────────────────┤
│ 📊 BOOTH 71 PROGRESS: 52 / 852 Gifts (6.1%)            │
│ [███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]        │
├────────────────────────────────────────────────────────┤
│ 🔍 [ Search Voter Name or EPIC (e.g. Suresh / SPC)   ] │
│ Filter: [ Booth 71 - Handanakere ▼ ] [ All | Not Given]│
├────────────────────────────────────────────────────────┤
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ SL. 2 · PART 71                     [ ⚪ NOT GIVEN ]│ │
│ │ Abhilasha S                                        │ │
│ │ Relative: Arunkumar K S                            │ │
│ │ EPIC: SPC3578515 · Chikkanayakanahalli             │ │
│ │ ────────────────────────────────────────────────── │ │
│ │ [ ☑️ TICK: HAND OVER GIFT / ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ]     │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ SL. 14 · PART 71                  [ 🟢 GIFT ISSUED ]│ │
│ │ Chandrashekar M                                    │ │
│ │ Relative: Mallappa                                 │ │
│ │ EPIC: IUO1294812 · Handanakere                     │ │
│ │ ────────────────────────────────────────────────── │ │
│ │ ✓ Given on 15 Oct, 10:14 AM by Manjunath K         │ │
│ │ 🔒 [ Delivery Confirmed - Locked ]                 │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

#### Card Visual States:
1. **⚪ Pending State (`is_issued: false`):**
   - Clean white card with slate border.
   - Prominent blue action button:
     `[ ☑️ Tick: Hand Over Gift / ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ]`
2. **🟢 Delivered State (`is_issued: true`):**
   - Soft emerald green background (`bg-emerald-50 border-emerald-300`).
   - Emerald badge: `[ ✓ GIFT DELIVERED / ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ]`.
   - Displays: *"Delivered by [Volunteer Name] ([Date, Time])"*.
   - Button is disabled and replaced with a locked confirmation pill.
3. **🔴 Duplicate Attempt Alert (Modal):**
   - If an elector already received a gift, any attempt to mark again pops up an unavoidable siren alert:
     > **⚠️ DUPLICATE BLOCKED! / ಈಗಾಗಲೇ ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ**  
     > **Voter:** Abhilasha S (EPIC: SPC3578515)  
     > **Already Issued By:** Ramesh K (Team South Booth 71)  
     > **Delivered At:** 14 Oct 2026, 11:42 AM  
     > *Duplicate delivery has been strictly rejected by the database engine.*

---

### Screen 3: 2-Step Confirmation Modal (`ConfirmGiftModal.tsx`)
When the volunteer taps `[ ☑️ Tick: Hand Over Gift ]`, render a high-visibility modal before saving:

```text
┌────────────────────────────────────────────────────────┐
│ 🎁 Confirm Gift Handover                               │
│ ಉಡುಗೊರೆ ಹಸ್ತಾಂತರವನ್ನು ಖಚಿತಪಡಿಸಿ                        │
├────────────────────────────────────────────────────────┤
│ Are you sure you want to mark gift as issued to:       │
│                                                        │
│ 👤 Elector:   ABHILASHA S                              │
│ 📜 Relative:  Arunkumar K S                            │
│ 🔢 Sl No:     2   ·   Part / Booth: 71                 │
│ 🆔 EPIC:      SPC3578515                               │
│                                                        │
│ ⚠️ Note: This action cannot be undone.                 │
│ Only 1 gift is permitted per elector.                  │
├────────────────────────────────────────────────────────┤
│ [ ✓ YES, CONFIRM & ISSUE ]            [ CANCEL ]       │
└────────────────────────────────────────────────────────┘
```

On confirming:
1. Sends `POST /api/issue`.
2. Plays pleasant sound chime.
3. Card updates to Emerald Green in `<150ms`.
4. Booth progress bar increments immediately.

---

### Screen 4: Live Command Center & Excel Export (`AdminStatsModal.tsx`)
Accessible via the Admin button with PIN `8899` or `2026`:
1. **Global Metrics:**
   - Total Graduates: 1,92,696
   - Total Gifts Delivered across all 5 districts
   - Anti-Duplicate status (100% Enforced)
2. **Recent Activity Feed:**
   - Live chronological stream showing which volunteer marked gifts in real-time.
3. **1-Click Audit Export:**
   - Button: `[ 📥 Export Audited Roll (Excel / CSV) ]`
   - Downloads a clean spreadsheet with:
     `EPIC Number | Voter Name | Relative Name | Part No | Serial No | District | Taluk | Volunteer Name | Recipient Mobile | Exact Timestamp`.

---

## 6. BILINGUAL DICTIONARY (English & Kannada)

```typescript
export const translations = {
  en: {
    appTitle: "MLC 2026 Gift Tracker",
    appSubtitle: "Dedicated 1-to-1 Voter Gift Distribution Portal",
    candidateName: "SHASHI HULIKUNTEMUTT",
    candidateConstituency: "Karnataka South-East Graduates' Constituency",
    partyBadge: "INC Candidate",
    pinTitle: "Volunteer Access Gate",
    pinSubtitle: "Enter your 4-digit team access PIN to proceed",
    pinPlaceholder: "Enter 4-Digit PIN",
    nameLabel: "Volunteer Full Name",
    namePlaceholder: "e.g. Ramesh Kumar",
    boothLabel: "Assigned Polling Booth / Part",
    selectBooth: "-- Select your assigned booth --",
    enterPortal: "Enter Distribution Portal",
    invalidPin: "Invalid PIN. Please enter the authorized 4-digit team passcode.",
    missingFields: "Please enter your name and select your assigned booth.",
    searchPlaceholder: "Search Voter Name or EPIC (e.g. Suresh / SPC...)",
    allBooths: "All Polling Booths",
    filterTitle: "Filter by Booth:",
    filterStatusAll: "All Voters",
    filterStatusPending: "Not Gifted",
    filterStatusDelivered: "Gift Delivered",
    boothProgress: "Booth Progress",
    giftsDelivered: "Gifts Delivered",
    target: "Total Electors",
    slNo: "Sl. No",
    partNo: "Part",
    relativeLabel: "Relative",
    epicLabel: "EPIC No",
    boothLabelCard: "Booth",
    notGivenBadge: "NOT GIVEN",
    issuedBadge: "GIFT DELIVERED",
    tickButton: "☑️ Tick: Hand Over Gift",
    issuedBy: "Delivered by",
    issuedAt: "Time",
    confirmTitle: "Confirm Gift Handover",
    confirmKannada: "ಉಡುಗೊರೆ ಹಸ್ತಾಂತರವನ್ನು ಖಚಿತಪಡಿಸಿ",
    confirmMsg: "Are you sure you want to mark 1 gift as handed over to:",
    confirmElector: "Elector Name",
    confirmSl: "Serial No",
    confirmBooth: "Part / Booth",
    confirmEpic: "EPIC Card",
    confirmWarning: "⚠️ Strictly 1 gift per voter. Once confirmed, this record is locked permanently.",
    confirmBtn: "✓ Yes, Confirm Handover",
    cancelBtn: "Cancel",
    duplicateTitle: "DUPLICATE BLOCKED!",
    duplicateKannada: "ಎಚ್ಚರಿಕೆ: ನಕಲು ವಿತರಣೆ ನಿರ್ಬಂಧಿಸಲಾಗಿದೆ!",
    duplicateMsg: "This elector has ALREADY received a gift. Second gift is strictly prohibited.",
    duplicateIssuedBy: "Already Delivered By",
    duplicateTime: "Delivery Timestamp",
    duplicateStatus: "Delivery Locked",
    adminBtn: "Admin Dashboard",
    adminTitle: "Campaign Command Center",
    exportBtn: "📥 Export Audited Roll (Excel / CSV)",
    totalVoters: "Total Constituency Electors",
    totalGifts: "Total Gifts Issued",
    percentCompleted: "Completed",
    exitBtn: "Log Out",
    searching: "Searching graduate electors...",
    noResults: "No graduate electors found matching your search.",
  },
  kn: {
    appTitle: "MLC 2026 ಉಡುಗೊರೆ ಟ್ರ್ಯಾಕರ್",
    appSubtitle: "ಖಾಸಗಿ 1-ವ್ಯಕ್ತಿಗೆ-1 ಉಡುಗೊರೆ ವಿತರಣಾ ಪೋರ್ಟಲ್",
    candidateName: "ಶಶಿ ಹುಲಿಕುಂಟೆಮಠ",
    candidateConstituency: "ಕರ್ನಾಟಕ ಆಗ್ನೇಯ ಪದವೀಧರರ ಕ್ಷೇತ್ರ",
    partyBadge: "ಕಾಂಗ್ರೆಸ್ (INC) ಅಭ್ಯರ್ಥಿ",
    pinTitle: "ಕಾರ್ಯಕರ್ತರ ಪ್ರವೇಶ ದ್ವಾರ",
    pinSubtitle: "ಮುಂದುವರಿಯಲು ನಿಮ್ಮ 4-ಅಂಕಿಯ ತಂಡದ ಪಿನ್ ನಮೂದಿಸಿ",
    pinPlaceholder: "4-ಅಂಕಿಯ ಪಿನ್ ನಮೂದಿಸಿ",
    nameLabel: "ಕಾರ್ಯಕರ್ತರ ಪೂರ್ಣ ಹೆಸರು",
    namePlaceholder: "ಉದಾ: ರಮೇಶ್ ಕುಮಾರ್",
    boothLabel: "ನಿಗದಿಪಡಿಸಿದ ಮತಗಟ್ಟೆ (ಬೂತ್)",
    selectBooth: "-- ನಿಮ್ಮ ಬೂತ್ ಆಯ್ಕೆಮಾಡಿ --",
    enterPortal: "ವಿತರಣಾ ಪೋರ್ಟಲ್‌ಗೆ ಪ್ರವೇಶಿಸಿ",
    invalidPin: "ತಪ್ಪಾದ ಪಿನ್. ದಯವಿಟ್ಟು ಸರಿಯಾದ 4-ಅಂಕಿಯ ತಂಡದ ಪಾಸ್‌ಕೋಡ್ ನಮೂದಿಸಿ.",
    missingFields: "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ನಮೂದಿಸಿ ಮತ್ತು ಬೂತ್ ಆಯ್ಕೆಮಾಡಿ.",
    searchPlaceholder: "ಮತದಾರರ ಹೆಸರು ಅಥವಾ EPIC ನಮೂದಿಸಿ (ಉದಾ: Suresh / SPC...)",
    allBooths: "ಎಲ್ಲಾ ಮತಗಟ್ಟೆಗಳು",
    filterTitle: "ಬೂತ್ ಫಿಲ್ಟರ್:",
    filterStatusAll: "ಎಲ್ಲಾ ಮತದಾರರು",
    filterStatusPending: "ಉಡುಗೊರೆ ನೀಡಿಲ್ಲ",
    filterStatusDelivered: "ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ",
    boothProgress: "ಬೂತ್ ಪ್ರಗತಿ",
    giftsDelivered: "ವಿತರಿಸಲಾದ ಉಡುಗೊರೆಗಳು",
    target: "ಒಟ್ಟು ಮತದಾರರು",
    slNo: "ಕ್ರ.ಸಂ",
    partNo: "ಭಾಗ",
    relativeLabel: "ಸಂಬಂಧಿ",
    epicLabel: "ಎಪಿಕ್ ಸಂಖ್ಯೆ",
    boothLabelCard: "ಮತಗಟ್ಟೆ",
    notGivenBadge: "ನೀಡಿಲ್ಲ",
    issuedBadge: "ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ",
    tickButton: "☑️ ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ಎಂದು ಗುರುತಿಸಿ",
    issuedBy: "ವಿತರಿಸಿದವರು",
    issuedAt: "ಸಮಯ",
    confirmTitle: "ಉಡುಗೊರೆ ಹಸ್ತಾಂತರವನ್ನು ಖಚಿತಪಡಿಸಿ",
    confirmKannada: "ಉಡುಗೊರೆ ಹಸ್ತಾಂತರವನ್ನು ಖಚಿತಪಡಿಸಿ",
    confirmMsg: "ಈ ಮತದಾರರಿಗೆ 1 ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ ಎಂದು ಖಚಿತಪಡಿಸಲು ಬಯಸುವಿರಾ:",
    confirmElector: "ಮತದಾರರ ಹೆಸರು",
    confirmSl: "ಕ್ರಮ ಸಂಖ್ಯೆ",
    confirmBooth: "ಭಾಗ / ಬೂತ್ ಸಂಖ್ಯೆ",
    confirmEpic: "EPIC ಕಾರ್ಡ್",
    confirmWarning: "⚠️ ಒಬ್ಬ ಮತದಾರರಿಗೆ ಕೇವಲ 1 ಉಡುಗೊರೆ ಮಾತ್ರ. ಒಮ್ಮೆ ಖಚಿತಪಡಿಸಿದ ನಂತರ ಇದನ್ನು ಬದಲಾಯಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ.",
    confirmBtn: "✓ ಹೌದು, ಖಚಿತಪಡಿಸಿ",
    cancelBtn: "ರದ್ದುಮಾಡಿ",
    duplicateAlertTitle: "ಎಚ್ಚರಿಕೆ: ನಕಲು ವಿತರಣೆ ನಿರ್ಬಂಧಿಸಲಾಗಿದೆ!",
    duplicateKannada: "ಈ ಮತದಾರರಿಗೆ ಈಗಾಗಲೇ ಉಡುಗೊರೆ ನೀಡಲಾಗಿದೆ!",
    duplicateMsg: "ಈ ಮತದಾರರು ಈಗಾಗಲೇ ಉಡುಗೊರೆ ಪಡೆದಿದ್ದಾರೆ. ಎರಡನೇ ಉಡುಗೊರೆಯನ್ನು ಕಟ್ಟುನಿಟ್ಟಾಗಿ ನಿಷೇಧಿಸಲಾಗಿದೆ.",
    duplicateIssuedBy: "ಈಗಾಗಲೇ ವಿತರಿಸಿದ ಕಾರ್ಯಕರ್ತರು",
    duplicateTime: "ವಿತರಿಸಲಾದ ಸಮಯ",
    duplicateStatus: "ವಿತರಣೆ ಲಾಕ್ ಆಗಿದೆ",
    adminBtn: "ಅಡ್ಮಿನ್ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
    adminTitle: "ಕಮಾಂಡ್ ಸೆಂಟರ್",
    exportBtn: "📥 ವರದಿ ಡೌನ್‌ಲೋಡ್ (Excel / CSV)",
    totalVoters: "ಒಟ್ಟು ಪದವೀಧರ ಮತದಾರರು",
    totalGifts: "ಒಟ್ಟು ನೀಡಲಾದ ಉಡುಗೊರೆಗಳು",
    percentCompleted: "ಪೂರ್ಣಗೊಂಡಿದೆ",
    exitBtn: "ನಿರ್ಗಮಿಸಿ (ಲಾಗ್‌ಔಟ್)",
    searching: "ಪದವೀಧರ ಮತದಾರರನ್ನು ಹುಡುಕಲಾಗುತ್ತಿದೆ...",
    noResults: "ಯಾವುದೇ ಮತದಾರರು ಕಂಡುಬಂದಿಲ್ಲ.",
  }
};
```

---

## 7. AUDIO CHIME & BUZZ SYNTHESIZER (`soundEffects.ts`)

```typescript
export function playSuccessChime() {
  if (typeof window === 'undefined') return;
  try {
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const now = ctx.currentTime;
    
    // Note 1: 1046.5 Hz (C6)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(1046.5, now);
    gain1.gain.setValueAtTime(0.15, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.25);

    // Note 2: 1318.5 Hz (E6)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(1318.5, now + 0.12);
    gain2.gain.setValueAtTime(0.18, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.5);

    if (navigator.vibrate) navigator.vibrate([80, 40, 80]);
  } catch (err) {}
}

export function playDuplicateBuzz() {
  if (typeof window === 'undefined') return;
  try {
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const now = ctx.currentTime;
    
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(160, now);
    osc.frequency.setValueAtTime(140, now + 0.15);
    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.45);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.45);

    if (navigator.vibrate) navigator.vibrate([250, 100, 250]);
  } catch (err) {}
}
```

---

## 8. COMPLETE FILE STRUCTURE

```text
mlc-gift-tracker/
├── .env.local                        # Supabase credentials & PORT
├── package.json                      # Next.js 14, Tailwind, Lucide, XLSX
├── tsconfig.json                     # Strict TypeScript config
├── tailwind.config.js                # Civic Blue & Emerald tokens
├── postcss.config.js
├── schema.sql                        # PostgreSQL table & unique constraint
├── README.md                         # Project documentation & run guide
├── app/
│   ├── globals.css                   # Global styles & scrollbar formatting
│   ├── layout.tsx                    # Standalone PWA layout & viewport
│   ├── page.tsx                      # Main Search, Tick & Distribution Feed
│   └── api/
│       ├── search/route.ts           # Search electors + joined gift status
│       ├── issue/route.ts            # Atomic insert with 23505 duplicate catch
│       ├── stats/route.ts            # Aggregated booth & campaign metrics
│       └── export/route.ts           # CSV/Excel export stream
├── components/
│   ├── PinGateModal.tsx              # 4-digit PIN gate + Volunteer Profile
│   ├── VoterGiftCard.tsx             # White/Emerald card with tick button
│   ├── ConfirmGiftModal.tsx          # 2-step anti-accidental tap confirmation
│   ├── DuplicateAlertModal.tsx       # Red alert siren modal on duplicate
│   ├── BoothProgressBar.tsx         # Live % counter for assigned booth
│   └── AdminStatsModal.tsx           # Command center & Excel download
├── lib/
│   ├── boothMaster.ts                # 151 Polling Stations & Districts map
│   ├── soundEffects.ts               # Web Audio API chime & buzz synthesizers
│   ├── supabaseServer.ts             # Server-side Supabase client with fallback
│   └── translations.ts               # Strongly-typed bilingual dictionary
└── public/
    ├── icon-192.png                  # PWA high-res icon
    ├── icon-512.png                  # PWA high-res icon
    └── manifest.json                 # PWA Web Manifest
```

---

## 9. ACCEPTANCE CRITERIA & VERIFICATION CHECKLIST

1. **Zero Impact on Original Electoral Portal:** The original repository must remain 100% clean, untouched, and uncommitted.
2. **Search Speed:** Searching by Name or EPIC returns electors within 200ms.
3. **2-Step Safety:** Tapping `[ ☑️ Tick: Hand Over Gift ]` triggers the confirmation modal. No record is written until `[ ✓ Yes, Confirm Handover ]` is tapped.
4. **Duplicate Rejection:** Any duplicate attempt physically fails at the database level (`409 Conflict`), displays the red siren alert with the name of the previous volunteer and timestamp, and triggers the audio rejection buzz.
5. **Audited Roll Export:** The CSV export includes `EPIC, Name, Relative, Part, Serial, District, Taluk, Volunteer Name, Timestamps`.
```
