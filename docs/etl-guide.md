# ETL Pipeline Guide — Elector Lookup Portal

> How to set up, run, and troubleshoot the Python ETL pipeline.

---

## 1. Overview

The ETL (Extract, Transform, Load) pipeline is a standalone Python project that:
1. **Extracts** raw elector data from Excel (`.xlsx`) and PDF (`.pdf`) files
2. **Cleans** and normalizes every field (EPIC, names, addresses, age, sex)
3. **Validates** and deduplicates records
4. **Ingests** cleaned data into Supabase PostgreSQL via upsert

The pipeline is **idempotent** — running it again on the same data produces the same result without duplicates.

---

## 2. Prerequisites

- **Python 3.12.x** installed
- **pip** + **venv** available
- Supabase project created with schema applied (see `etl/schema.sql`)
- Source files placed in `data/excel/` and/or `data/pdf/`
- `etl/.env` configured with credentials

---

## 3. Setup

```bash
# Navigate to the ETL directory
cd etl

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment

Copy the example and fill in real values:

```bash
cp .env.example .env
```

Edit `etl/.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
DATABASE_URL=postgresql://postgres:your-password@db.your-project.supabase.co:5432/postgres
```

> ⚠️ **NEVER commit `.env`** — it contains admin-level credentials that bypass RLS.

---

## 4. Usage

### Full Run (Extract → Clean → Validate → Ingest)

```bash
python main.py --source ../data --ingest
```

### Dry Run (No Ingestion)

```bash
python main.py --source ../data --dry-run
```

### Extract and Clean Only (Output to CSV)

```bash
python main.py --source ../data --output ./output/cleaned.csv
```

### Ingest from Pre-cleaned CSV

```bash
python main.py --input ./output/cleaned.csv --ingest
```

### Verbose Logging

```bash
python main.py --source ../data --dry-run --verbose
```

---

## 5. Pipeline Stages

### Stage 1: Extract (`extract.py`)

| Source | Method | Library | Notes |
|--------|--------|---------|-------|
| Excel (`.xlsx`) | `pandas.read_excel()` | openpyxl | Handles multiple sheets per file |
| PDF (`.pdf`) | `pdfplumber.open()` | pdfplumber | Extracts tables page by page |

- Adds `source_file` and `source_sheet` columns for traceability
- Skips blank pages and empty rows
- If a file fails to parse, logs error and continues with remaining files

### Stage 2: Clean (`clean.py`)

| Field | Cleaning Logic |
|-------|---------------|
| `epic_number` | Strip non-alnum, uppercase, validate `^[A-Z]{3}\d{7}$` |
| `name` | Strip, collapse whitespace, preserve original casing |
| `relative_name` | Same as name, preserve "S/o", "D/o", "W/o" prefixes |
| `address` | Replace `\n` with `, `, collapse commas, strip edges |
| `age` | Extract first integer, validate 18–120 range |
| `sex` | Map Male/Female/M/F → `M`/`F` |
| `qualification` | Strip and collapse whitespace |
| `occupation` | Strip and collapse whitespace |
| `photo_url` | Always set to `NULL` (⚠️ PENDING) |

### Stage 3: Validate (`validate.py`)

1. **Drop** rows with invalid/missing EPIC numbers
2. **Drop** rows with null names
3. **Remove** exact duplicate rows
4. **Deduplicate** by EPIC number (keep first, flag rest)
5. **Flag** out-of-range ages (but keep records)
6. **Output** duplicates to `output/duplicates_<timestamp>.csv`
7. **Generate** validation report

### Stage 4: Ingest (`ingest.py`)

- **Method:** psycopg2 `execute_values` with `ON CONFLICT DO UPDATE` (upsert)
- **Speed:** ~200k rows in < 30 seconds
- **Idempotent:** Re-running produces same result, no duplicates
- **Fallback:** REST API via `supabase-py` (slower, ~5-10 minutes)

---

## 6. Output Files

After each run, the pipeline produces:

| File | Location | Description |
|------|----------|-------------|
| Run report | `output/report_<timestamp>.txt` | Full statistics: rows processed, dropped, flagged, ingested |
| Duplicates | `output/duplicates_<timestamp>.csv` | Records with duplicate EPIC numbers (all but first) |
| Invalid EPICs | `output/invalid_epics_<timestamp>.csv` | Records with EPIC numbers that failed validation |
| Cleaned data | `output/cleaned.csv` (if `--output` used) | Full cleaned dataset before ingestion |

---

## 7. Testing Strategy

### Test on Small Sample First

```bash
# Place a small test file (100 rows) in data/excel/
# Run dry-run first
python main.py --source ../data --dry-run --verbose

# If report looks good, run with ingestion
python main.py --source ../data --ingest

# Verify in Supabase SQL Editor:
# SELECT count(*) FROM electors;
```

### Verify Idempotency

```bash
# Run the same ingestion twice
python main.py --source ../data --ingest
python main.py --source ../data --ingest

# Row count should be identical after both runs
```

---

## 8. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: pdfplumber` | venv not activated | Activate venv, re-run `pip install -r requirements.txt` |
| `psycopg2.OperationalError: could not connect` | Wrong `DATABASE_URL` in `.env` | Check credentials in Supabase Dashboard → Settings → Database |
| `UniqueViolation` errors | Duplicate EPICs in source data | Normal — the upsert handles this. Check duplicates CSV. |
| PDF extraction returns 0 rows | PDF has no extractable tables | Try different `table_settings` in pdfplumber, or the PDF may use images instead of text |
| Column mapping warnings | Source file has unusual column names | Add the column name variant to `COLUMN_MAP` in `clean.py` |
| `permission denied for table electors` | Using anon key instead of service role key | Check `SUPABASE_SERVICE_ROLE_KEY` in `.env` — ETL must use service role |

---

## 9. Re-running the ETL

The ETL is designed to be re-run at any time:

- **New data files:** Place them in `data/`, run the pipeline. New records are inserted, existing records are updated.
- **Corrected data:** Re-run with updated source files. The upsert updates changed fields.
- **Schema changes:** If the schema changes, update `schema.sql`, run it in Supabase SQL Editor, then re-run ETL.
- **Full reset:** To start fresh, `TRUNCATE TABLE electors;` in SQL Editor, then run ETL.

---

## 10. Zero-Drop PDF Electoral Roll Re-Extraction & Recovery Architecture

### Root Cause Analysis
During comprehensive cross-audit between original Karnataka Electoral Roll PDFs, Adobe OCR converted Excels, and the Supabase database:
- **Adobe OCR Drop Issue:** Adobe OCR silently dropped whole multi-page table supplements (e.g. In Part 112, Adobe stopped exporting at Page 282, dropping pages 283–687 entirely).
- **Search Logic Inconsistencies:** Search was failing on valid 7–13 character EPICs, zero-padded variants (`WWS579886` vs `WWS0579886`), and numeric serial inputs (`347`, `103 347`).

### Re-Extraction & Recovery Workflow
1. **PyMuPDF Spatial Grid Clustering:** Scans raw PDF text layers and spatial bounding boxes (`words`), segmenting voter rows by horizontal Y-bands and vertical columns (Serial, Name, Relative, Address, Age, Sex, EPIC).
2. **Sequential Serial Verification:** Validates that voters increment sequentially $1..N$ within each booth, detecting OCR artifacts on serial numbers.
3. **Strict Validation & Quarantine:** Records strictly matching `^[A-Z]{3}\d{7}$` with valid non-address names are classified as `new_valid`. Ambiguous OCR values are placed in `quarantine_review.xlsx` with suggested corrections and page references.
4. **Controlled Transactional Insert:** Uses `ON CONFLICT (epic_number) DO NOTHING` with `batch_recovery_<timestamp>` provenance tags, ensuring 100% idempotency.
5. **Search Proof Verification:** Every inserted EPIC is verified against the live `/api/search` production endpoint, guaranteeing 0 not-found electors.
