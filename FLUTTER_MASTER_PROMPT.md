# Master Prompt: Convert Karnataka MLC 2026 Electoral Portal (Next.js) to Flutter (iOS, Android & Web)

> [!TIP]
> **How to use this document:** Copy the entire prompt block below (starting from `# SYSTEM ROLE & OBJECTIVE`) and paste it into any advanced coding AI or hand it directly to a senior Flutter engineering team. It contains every design token, hex color, gradient, typography rule, bilingual dictionary (`en` + `kn`), data model, business logic rule, screen specification, the redesigned candidate voter slip layout, and API contract required to build a 1:1 pixel-accurate Flutter application.

---

```markdown
# SYSTEM ROLE & OBJECTIVE
You are a Principal Flutter Architect & Lead UI/UX Designer. Your task is to build a production-grade, 1:1 pixel-accurate **Flutter Application (iOS, Android, and Web)** replicating the **Karnataka MLC Election 2026 Electoral Voter Lookup & Campaign Management Portal** for candidate **SHASHI HULIKUNTEMUTT (INC Candidate — South-East Graduates' Constituency, Karnataka)** covering **1,92,696 graduate voters** across **151 polling stations** in 5 districts (Tumkur, Chitradurga, Davanagere, Kolar, Chikkaballapura).

You must preserve the exact visual identity, sovereign civic aesthetic, gradients, micro-animations, bilingual support (English & Kannada), offline capabilities, high-resolution Voter Slip PNG generation/printing, WhatsApp sharing, Form 18 Enrolment & Correction workflows, Live Application Tracker, Team Login with rate-limit countdown, Admin Request Desk, and Electoral Analytics Dashboard.

---

## 1. TECH STACK & FLUTTER PACKAGES
Use **Flutter 3.24+ (Dart 3.5+)** with Clean Feature-First Architecture:
- **State Management:** `flutter_riverpod` (`Notifier` / `AsyncNotifier`)
- **Routing:** `go_router` (supporting deep links like `/search`, `/track?ref=REQ-...`, `/team`, `/admin/requests`, `/analytics`)
- **Networking / Backend:** `supabase_flutter` + `dio` (for REST API endpoints & PostgREST queries)
- **Local Storage:** `shared_preferences` (language preference `voter_portal_language`, last tracked ID `electrol_last_tracked_ref`, login lockout timestamp `team_login_locked_until`, recent searches)
- **Typography:** `google_fonts` (`Plus Jakarta Sans` for UI, `JetBrains Mono` for EPIC numbers, serial numbers, reference IDs, and timers, `Noto Sans Kannada` for Kannada script)
- **Icons:** `lucide_icons` (1:1 match with `lucide-react` used in the web app)
- **Voter Slip Capture & Print:** `screenshot` or `RenderRepaintBoundary` (`toImage(pixelRatio: 3.0)`) + `printing` + `pdf` + `gal` / `image_gallery_saver`
- **Sharing & External Links:** `share_plus` + `url_launcher` (WhatsApp `https://wa.me/?text=...` and `tel:+919845123456`)
- **Excel Export (Admin):** `excel` or `syncfusion_flutter_xlsio`
- **Charts (Analytics):** `fl_chart`
- **Animations & Shimmer:** `flutter_animate` + `shimmer`

---

## 2. CLEAN ARCHITECTURE PROJECT STRUCTURE
Organize `lib/` strictly as follows:

```text
lib/
├── main.dart
├── app.dart
├── core/
│   ├── constants/
│   │   ├── app_assets.dart
│   │   ├── constituency_data.dart       # 5 Districts, 35 Taluks, Hoblis/Wards
│   │   ├── booth_master.dart            # 151 Polling Stations & Auxiliary Booth resolution
│   │   └── status_map.dart              # 11 RequestStatuses, Stepper config, Bilingual messages
│   ├── theme/
│   │   ├── app_colors.dart              # Exact Slate/Blue/Brand/INC Tricolor tokens
│   │   ├── app_gradients.dart           # Royal Blue Hero, Tricolor stripe, Ambient Orbs
│   │   ├── app_shadows.dart             # 2xs, xs, soft-sm, card-hover, elevated
│   │   ├── app_typography.dart          # Plus Jakarta Sans + JetBrains Mono + Noto Sans Kannada
│   │   └── app_theme.dart
│   ├── i18n/
│   │   ├── language_provider.dart       # Riverpod Notifier ('en' | 'kn') persisted in SharedPreferences
│   │   └── translations.dart            # Complete strongly-typed Translations class (en & kn)
│   ├── router/
│   │   └── app_router.dart              # GoRouter configuration with AuthGuard for /admin & /analytics
│   └── utils/
│       ├── epic_formatter.dart          # normalizeEpic(), isValidEpic(), formatEpicForDisplay()
│       ├── postgrest_sanitizer.dart     # sanitizePostgrestTerm()
│       └── whatsapp_helper.dart
├── shared/
│   └── widgets/
│       ├── ambient_sovereign_scaffold.dart  # Fixed background with Tricolor top bar, blurred orbs & tech-grid
│       ├── app_badge.dart
│       ├── app_button.dart
│       ├── app_bottom_sheet.dart
│       ├── highlight_text.dart          # Highlights matched search substrings in #DBEAFE bg & #172554 text
│       └── pagination_bar.dart
└── features/
    ├── search/
    │   ├── data/
    │   │   ├── models/
    │   │   │   ├── search_result_row.dart
    │   │   │   ├── booth_header_info.dart
    │   │   │   ├── search_facets.dart
    │   │   │   └── search_filters_state.dart
    │   │   └── search_repository.dart   # Smart Query Router (EPIC -> Mobile -> Relative -> Name -> Booth)
    │   ├── domain/
    │   │   └── search_controller.dart   # Debounced search (220ms), pagination, filter state
    │   └── presentation/
    │       ├── screens/
    │       │   └── search_screen.dart
    │       └── widgets/
    │           ├── candidate_hero_banner.dart
    │           ├── ballot_paper_guide_card.dart
    │           ├── search_filters_card.dart
    │           ├── search_results_grid.dart
    │           ├── search_row_card.dart
    │           ├── elector_detail_modal.dart
    │           └── voter_slip_modal.dart      # Pixel-accurate reference structure with ballot guide
    ├── requests/
    │   ├── data/
    │   │   ├── voter_request_model.dart
    │   │   └── requests_repository.dart
    │   └── presentation/
    │       ├── modals/
    │       │   ├── request_add_voter_modal.dart   # Form 18 Enrolment & Correction mode
    │       │   └── dark_location_picker_dialog.dart # Dark slate-900 Taluk & Hobli radio picker
    │       └── screens/
    │           └── track_status_screen.dart       # Public live tracker with 5-step vertical stepper
    ├── auth/
    │   ├── data/
    │   │   └── auth_repository.dart
    │   └── presentation/
    │       └── team_login_screen.dart   # 5-attempt lockout with 02:00 MM:SS countdown timer
    ├── admin/
    │   └── presentation/
    │       ├── screens/
    │       │   └── admin_requests_screen.dart
    │       └── widgets/
    │           └── admin_request_detail_drawer.dart
    └── analytics/
        └── presentation/
            ├── screens/
            │   └── analytics_dashboard_screen.dart
            └── widgets/
                ├── hierarchy_tiles.dart
                ├── kpi_tiles.dart
                ├── district_strength_chart.dart
                ├── gender_donut_chart.dart
                ├── age_pyramid_chart.dart
                └── booth_table.dart
```

---

## 3. DESIGN SYSTEM & VISUAL TOKENS (1:1 TAILWIND MAPPING)

### 3.1 Color Palette (`AppColors`)
- **Canvas Background:** `#F8FAFC` (`slate-50` with 95% opacity)
- **Card Surface:** `#FFFFFF` (often `Colors.white.withOpacity(0.95)` with `BackdropFilter` blur)
- **Primary Text:** `#0F172A` (`slate-900`)
- **Secondary Text:** `#475569` (`slate-600`) / `#64748B` (`slate-500`)
- **Muted / Label Text:** `#94A3B8` (`slate-400`)
- **Borders:** `#E2E8F0` (`slate-200`) / `#F1F5F9` (`slate-100`)
- **Royal Blue Theme (Candidate Hero, Voter Slip & Primary Actions):**
  - `blue-50`: `#EFF6FF`
  - `blue-100`: `#DBEAFE`
  - `blue-200`: `#BFDBFE`
  - `blue-600`: `#2563EB` (Primary CTA Button)
  - `blue-700`: `#1D4ED8` (Candidate banner, verification bar & emphasis)
  - `blue-800`: `#1E40AF`
  - `blue-900`: `#1E3A8A`
  - `blue-950`: `#172554`
- **Brand Indigo:**
  - `brand-50`: `#EEF2FF`
  - `brand-500`: `#6366F1`
  - `brand-600`: `#4F46E5`
  - `brand-700`: `#4338CA`
- **Indian National Congress (INC) Tricolor Accents:**
  - Saffron: `#FF671F` (or `#FF9933` in badge)
  - White: `#FFFFFF`
  - India Green: `#046A38` (or `#138808` in badge)
- **Semantic Status Colors:**
  - Emerald (WhatsApp / Verified / Enrolled): `#10B981` (`emerald-500`), `#059669` (`emerald-600`), `#ECFDF5` (`emerald-50`)
  - Amber (Candidate tag `INC Candidate` / Sl. No. 1 Badge): `#F59E0B` (`amber-500`), `#FCD34D` (`amber-300`)
  - Rose (Errors / Rejections / Clear Filters): `#E11D48` (`rose-600`), `#FFF1F2` (`rose-50`), `#FECDD3` (`rose-200`)

### 3.2 Gradients (`AppGradients`)
1. **Candidate Hero Card Gradient:**
   - `LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1E40AF), Color(0xFF2563EB), Color(0xFF0284C7)])`
2. **Top 3px Sovereign Civic Glow Stripe & Card Top 4px Stripe:**
   - `LinearGradient(colors: [Color(0xFFFF671F), Color(0xFFFFFFFF), Color(0xFF046A38)])`
3. **Ballot Sl. No. 1 Pill Gradient:**
   - `LinearGradient(colors: [Color(0xFFF59E0B), Color(0xFFF97316)])`
4. **Elector Detail Avatar Square & Top Shimmer Bar:**
   - `LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2563EB), Color(0xFF4F46E5), Color(0xFF7C3AED)])`

---

## 4. ASSETS TO BUNDLE IN `pubspec.yaml`
Copy these assets directly from the Next.js `web/public/` folder into `assets/images/`:
- `assets/images/candidate-avatar.jpg` — Candidate portrait of Shashi Hulikuntemutt
- `assets/images/inc-logo.png` — Indian National Congress hand symbol badge
- `assets/images/congress-flag.png` — Right-aligned semi-transparent background flag in Hero Banner
- `assets/images/ballot-candidate-guide.png` — High-resolution official ballot paper specimen (`823x295`) showing Sl. No. 1 Shashi Hulikuntemutt with preferential vote `"1"`
- `assets/images/location-pin.png` — Location pin icon used in voter cards and detail modals
- `assets/images/app-logo.png` — App icon

---

## 5. COMPLETE BILINGUAL TRANSLATION SYSTEM (`en` & `kn`)
Create a `LanguageNotifier` storing `'en'` or `'kn'` in `SharedPreferences` (`voter_portal_language`). Toggling language updates the entire UI instantaneously without reloading or losing search state.

| Key | English (`en`) | Kannada (`kn`) |
| :--- | :--- | :--- |
| `mlcElection` | `MLC ELECTION 2026` | `ವಿಧಾನ ಪರಿಷತ್ ಚುನಾವಣೆ 2026` |
| `constituencyTitle` | `South-East Graduates' Constituency, Karnataka` | `ಕರ್ನಾಟಕ ಆಗ್ನೇಯ ಪದವೀಧರರ ಕ್ಷೇತ್ರ` |
| `candidateName` | `SHASHI HULIKUNTEMUTT` | `ಶಶಿ ಹುಲಿಕುಂಟೆಮಠ್` |
| `candidateRole` | `INC Candidate` | `ಕಾಂಗ್ರೆಸ್ ಅಭ್ಯರ್ಥಿ` |
| `voterCountText` | `1,92,696 graduate voters listed` | `1,92,696 ನೋಂದಾಯಿತ ಪದವೀಧರ ಮತದಾರರು` |
| `findNameTitle` | `Find your name in the voter list` | `ಮತದಾರರ ಪಟ್ಟಿಯಲ್ಲಿ ನಿಮ್ಮ ಹೆಸರು ಹುಡುಕಿ` |
| `searchPlaceholder` | `Type your name or EPIC number...` | `ನಿಮ್ಮ ಹೆಸರು ಅಥವಾ EPIC ಸಂಖ್ಯೆ ನಮೂದಿಸಿ...` |
| `addRelativeBtn` | `+ Add father / husband name` | `+ ತಂದೆ / ಪತಿಯ ಹೆಸರು ಸೇರಿಸಿ` |
| `hideRelativeBtn` | `− Hide relative name` | `− ಸಂಬಂಧಿಕರ ಹೆಸರು ಮರೆಮಾಡಿ` |
| `relativePlaceholder` | `Relative / Father / Husband name...` | `ಸಂಬಂಧಿಕರು / ತಂದೆ / ಪತಿಯ ಹೆಸರು...` |
| `searchTip` | `Tip: type at least 3 letters. Names are in English as per the voter list.` | `ಸುಳಿವು: ಕನಿಷ್ಠ 3 ಅಕ್ಷರಗಳನ್ನು ಟೈಪ್ ಮಾಡಿ. ಅಧಿಕೃತ ಪಟ್ಟಿಯ ಪ್ರಕಾರ ಹೆಸರುಗಳು ಲಭ್ಯವಿವೆ.` |
| `ballotGuideBadge` | `Official Ballot Paper Guide` | `ಅಧಿಕೃತ ಮತಪತ್ರ ಮಾದರಿ ಮಾರ್ಗದರ್ಶಿ` |
| `ballotSlNoBadge` | `Sl. No. 1` | `ಕ್ರಮ ಸಂಖ್ಯೆ: 1` |
| `ballotInstructionHeader` | `Preferential Voting Procedure` | `ಮತಪತ್ರದಲ್ಲಿ ಮತ ಚಲಾಯಿಸುವ ವಿಧಾನ` |
| `allPlaces` | `All places` | `ಎಲ್ಲಾ ಪ್ರದೇಶಗಳು` |
| `tumkur` | `Tumkur` | `ತುಮಕೂರು` |
| `chitradurga` | `Chitradurga` | `ಚಿತ್ರದುರ್ಗ` |
| `davanagere` | `Davanagere` | `ದಾವಣಗೆರೆ` |
| `kolar` | `Kolar` | `ಕೋಲಾರ` |
| `chikkaballapura` | `Chikkaballapura` | `ಚಿಕ್ಕಬಳ್ಳಾಪುರ` |
| `districtLabel` | `District / Constituency Region` | `ಜಿಲ್ಲೆ / ಕ್ಷೇತ್ರದ ವ್ಯಾಪ್ತಿ` |
| `talukLabel` | `Taluk` | `ತಾಲೂಕು` |
| `acLabel` | `Assembly Constituency (AC)` | `ವಿಧಾನಸಭಾ ಕ್ಷೇತ್ರ (AC)` |
| `partLabel` | `Polling Station / Part Number` | `ಮತಗಟ್ಟೆ / ಭಾಗ ಸಂಖ್ಯೆ` |
| `villageLabel` | `Village / Area` | `ಗ್ರಾಮ / ಬಡಾವಣೆ` |
| `clearFilters` | `Clear Filters` | `ಫಿಲ್ಟರ್ ತೆರವುಗೊಳಿಸಿ` |
| `votersFound` | `Voters Found` | `ಮತದಾರರು ಕಂಡುಬಂದಿದ್ದಾರೆ` |
| `exactEpicMatch` | `Exact EPIC Match` | `ಖಚಿತ EPIC ಹೊಂದಾಣಿಕೆ` |
| `fuzzyMatch` | `Fuzzy / Transliteration Match` | `ಹೆಸರಿನ ಹೊಂದಾಣಿಕೆ` |
| `noVotersFound` | `No Voters Found` | `ಯಾವುದೇ ಮತದಾರರ ಮಾಹಿತಿ ದೊರೆತಿಲ್ಲ` |
| `clearFiltersRetry` | `Clear Filters & Retry` | `ಫಿಲ್ಟರ್ ತೆರವುಗೊಳಿಸಿ ಮತ್ತೆ ಹುಡುಕಿ` |
| `fatherSpouseLabel` | `Father/Spouse:` | `ತಂದೆ/ಪತಿ:` |
| `partLabelShort` | `Part` | `ಭಾಗ` |
| `serialLabelShort` | `Serial` | `ಕ್ರ.ಸಂ` |
| `boothInfoTitle` | `Official Polling Station Information` | `ಅಧಿಕೃತ ಮತಗಟ್ಟೆ ಮಾಹಿತಿ` |
| `closeBtn` | `Close` | `ಮುಚ್ಚಿ` |

---

## 6. SCREEN SPECIFICATIONS & LATEST VOTER SLIP STRUCTURE

### 6.1 Main Voter Search Screen (`/search`)
1. **Top Utility Bar:** INC Badge pill + Install App / Share + Bilingual language switch (`English` / `ಕನ್ನಡ`).
2. **Candidate Hero Banner:**
   - 4px Tricolor top bar.
   - Congress flag watermark on right (22% opacity).
   - Candidate avatar frame (`candidate-avatar.jpg`, `96x96` mobile / `144x144` desktop).
   - Candidate Name: `SHASHI HULIKUNTEMUTT` (white, w900).
   - Two pills: INC Candidate pill (`inc-logo.png` + `INC Candidate`) and Listed Voters pill (`1,92,696 graduate voters listed`).
3. **Search Input Card:** Live search input for Name or EPIC number + Accordion toggle for `+ Add father / husband name`.
4. **Official Ballot Paper Voting Guide Card:** Header with `Sparkles` icon, `Official Ballot Paper Guide`, and `Sl. No. 1` pill + High-res specimen image (`ballot-candidate-guide.png`).
5. **Collapsible Filters:** Horizontal district pills (`All places`, `Tumkur`, `Chitradurga`, `Davanagere`, `Kolar`, `Chikkaballapura`) + AC, Part, and Village filters.
6. **Live Search Results Grid:** Cards with highlight text, Monospace EPIC badge, Taluk chip, and Part/Serial numbers.

---

### 6.2 Official Downloadable Voter Information Slip (`VoterSlipModal`)
This represents the downloadable and printable voter information slip card wrapped in a `RepaintBoundary` with `maxWidth: 460px`, `BorderRadius.circular(16)` and `1px solid #E2E8F0`:

```dart
Card(
  elevation: 2,
  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
  clipBehavior: Clip.antiAlias,
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      // 1. TOP CANDIDATE BANNER (Royal Blue)
      Container(
        color: const Color(0xFF1D4ED8), // Royal Blue (bg-blue-700)
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // Candidate Portrait Avatar Frame
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Image.asset('assets/images/candidate-avatar.jpg', fit: BoxFit.cover, alignment: Alignment.topCenter),
              ),
            ),
            const SizedBox(width: 14),
            // Candidate Metadata
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("South-East Graduates' Constituency", style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFFDBEAFE))),
                  const SizedBox(height: 2),
                  const Text("SHASHI HULIKUNTEMUTT", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white)),
                  const SizedBox(height: 4),
                  const Text("INC Candidate", style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFFFCD34D))),
                ],
              ),
            ),
          ],
        ),
      ),

      // 2. SLIP BODY
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Slip Header
            Row(
              children: const [
                Text("Voter Information Slip", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFF0F172A))),
                SizedBox(width: 8),
                Text("ಮತದಾರರ ಮಾಹಿತಿ ಚೀಟಿ", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF64748B))),
              ],
            ),
            const SizedBox(height: 14),

            // Part No. & Serial No. Blue Box
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF), // bg-blue-50
                border: Border.all(color: const Color(0xFFBFDBFE)), // border-blue-200
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text("Part No. / ಭಾಗ ಸಂಖ್ಯೆ", style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF64748B))),
                      Text(partNo, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: Color(0xFF1D4ED8), fontFamily: 'JetBrainsMono')),
                    ],
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      const Text("Serial No. / ಕ್ರಮ ಸಂಖ್ಯೆ", style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF64748B))),
                      Text(serialNo, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: Color(0xFF1D4ED8), fontFamily: 'JetBrainsMono')),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Elector Details with Clean Dividers
            _buildDetailRow("Name / ಹೆಸರು", electorName, isBold: true),
            _buildDetailRow("Father / Mother / Husband / ತಂದೆ / ತಾಯಿ / ಪತಿ", relativeName),
            _buildDetailRow("EPIC No. / ಎಪಿಕ್ ಸಂಖ್ಯೆ", epic, isMono: true),
            _buildDetailRow("Polling station / ಮತಗಟ್ಟೆ", "$boothName - $boothRoom"),
            _buildDetailRow("Taluk / City / ತಾಲ್ಲೂಕು / ನಗರ", talukCity),
            if (pollingArea.isNotEmpty)
              _buildDetailRow("Hobli / Ward · Area / ಹೋಬಳಿ / ವಾರ್ಡ್ · ಪ್ರದೇಶ", pollingArea),

            const SizedBox(height: 12),

            // Kannada Callout Header
            const Text(
              "ನಿಮ್ಮ ಪ್ರಥಮ ಪ್ರಾಶಸ್ತ್ಯ ಮತ ನೀಡಿ ಬೆಂಬಲಿಸಿ",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Color(0xFF1D4ED8)),
            ),
            const SizedBox(height: 8),

            // Official Candidate Ballot Guide Specimen
            Container(
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFCBD5E1)),
                borderRadius: BorderRadius.circular(12),
              ),
              clipBehavior: Clip.antiAlias,
              child: Image.asset('assets/images/ballot-candidate-guide.png', fit: BoxFit.contain),
            ),
          ],
        ),
      ),

      const SizedBox(height: 16),

      // 3. BOTTOM ROYAL BLUE VERIFICATION BANNER
      Container(
        color: const Color(0xFF1D4ED8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: const [
            Text("Please verify your details. Vote on polling day.", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Colors.white)),
            SizedBox(height: 2),
            Text("shashihulikuntemutt.com", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: Color(0xFFDBEAFE))),
          ],
        ),
      ),
    ],
  ),
)
```

**Actions Below Voter Slip Modal:**
1. **Save Image Button (`#2563EB` Blue):** Captures `RepaintBoundary` at `pixelRatio: 3.0` as `VoterSlip_{EPIC}.png` and saves to gallery.
2. **Print Voter Slip Button (`#EFF6FF` Light Blue):** Uses `printing` package (`Printing.layoutPdf`) to produce single-page A4 printout centered at `145mm`.
3. **Share to WhatsApp Button (`#10B981` Emerald):** Opens `https://wa.me/?text=...` with full formatted bilingual elector details.
4. **Close Button:** Dismisses modal.

---

### 6.3 Other App Screens & Modules
- **Public Application Tracker (`/track`):** Search by Reference ID (`REQ-2026-KA-XXXXX`) or EPIC + 5-step vertical progress stepper with live timestamps and direct WhatsApp / call helpline.
- **Team Login (`/team`):** 5-attempt rate-limit lockout with 120s countdown timer (`02:00` -> `00:00`).
- **Admin Requests Desk (`/admin/requests`):** KPI summary strip, filter by status/taluk, batch status updates, and Excel export.
- **Analytics Dashboard (`/analytics`):** Real-time voter breakdown, district strength bar charts, gender donut chart, and age pyramid using `fl_chart`.

---

## 7. SMART SEARCH ROUTER LOGIC (`SearchRepository`)
Implement intelligent 6-mode search routing against Supabase `electors`:
1. **Mode A (`epic`):** If query matches EPIC format (`^[A-Z]{3}\d{7}$`, `KA/...`, `TYA...`) -> Exact match `.eq('epic_number', q).limit(1)`.
2. **Mode B (`mobile`):** If 10 digits -> `.ilike('whatsapp_mob', '%$q%')`.
3. **Mode C1 (`relative_name`):** Cross-matched with elector name.
4. **Mode C2 (Multi-word Intelligent Matching):** If user types 2 words (e.g. `"Naveen TS"` or `"Nandini Hiremath"`), match name, relative name, space-stripped name, and cross-field combinations `(name ILIKE w1 AND relative_name ILIKE w2)` OR `(name ILIKE w2 AND relative_name ILIKE w1)`.
5. **Mode D (`booth`):** If `part` filter without query -> sort by `serial_number` ascending.

---

## 8. DELIVERABLES & QUALITY BAR
1. Complete, compilable, null-safe Dart code with zero analyzer warnings (`flutter analyze` passes with 0 errors).
2. Zero `RenderFlex overflowed` errors across small phones (`320px–390px`) and desktop screens.
3. 60fps/120fps smooth scrolling performance with shimmer skeleton loaders.
```
