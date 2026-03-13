# appliance-db

Scrape pipeline for building the master database of appliance models,
product codes and error codes. Input to the article generation system.

## Setup

```bash
# 1. Clone and enter project
git clone <your-repo>
cd appliance-db

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your Supabase URL + service key

# 5. Run schema against Supabase
# → Paste contents of db/schema.sql into Supabase SQL Editor and run
```

## Run the pipeline

```bash
# Full pipeline: models → PDFs → error codes → validation
python -m pipeline.run_all

# Specific brand/category
python -m pipeline.run_all --brand samsung --category washing-machines

# Individual steps
python -m pipeline.run_all --step models        # scrape ManualsLib
python -m pipeline.run_all --step error_codes   # extract from PDFs
python -m pipeline.run_all --step status        # print DB summary

# Validate data quality
python -m pipeline.validate
python -m pipeline.validate --brand samsung --category washing-machines
```

## Project structure

```
appliance-db/
├── config/
│   └── settings.py          # Supabase client, env config, active brand/category lists
├── db/
│   └── schema.sql           # Full Supabase schema (run once)
├── scrapers/
│   ├── base_scraper.py      # HTTP fetch, retries, rate limiting, scrape_job logging
│   ├── manualslib.py        # Scraper: models + manual URLs from ManualsLib
│   └── pdf_extractor.py     # Extractor: error codes from manual PDFs
├── pipeline/
│   ├── run_all.py           # Master orchestrator
│   └── validate.py          # Data quality checks
├── data/
│   └── manuals/             # Downloaded PDFs (gitignored)
├── logs/                    # Rotating log files (gitignored)
├── .env                     # Your credentials (gitignored)
├── .env.example             # Template
└── requirements.txt
```

## Expanding to more brands/categories

In `config/settings.py`:

```python
# Activate more brands
ACTIVE_BRAND_SLUGS = ["samsung", "bosch", "lg"]

# Activate more categories  
ACTIVE_CATEGORY_SLUGS = ["washing-machines", "dishwashers", "dryers"]
```

Then run the pipeline again – it picks up only new/pending rows.

## Data flow

```
ManualsLib listing pages
        ↓
models + manual_url (scraper/manualslib.py)
        ↓
manual PDF download + parse (scrapers/pdf_extractor.py)
        ↓
error_codes + error_code_product_codes (Supabase)
        ↓
validate.py confirms data quality
        ↓
Ready for article generation
```

## Notes on ManualsLib scraping

ManualsLib's HTML structure occasionally changes. If the model scraper
returns 0 results, inspect the listing page HTML and update the CSS
selectors in `scrapers/manualslib.py` → `_scrape_listing_page()`.

The selectors to check:
```python
soup.select("div.result-row, li.result-manual, div.manualRow")
link = item.select_one("a.manualTitle, a[href*='/manual/']")
```
