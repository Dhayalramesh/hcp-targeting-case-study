# HCP Targeting & Call Planning System

A requirements-to-design case study: a documented **Business Requirements Document → Technical Design Document → working implementation**, built to show the design process explicitly, not just the code.

**Scenario:** A pharma field sales org plans HCP (doctor) visits off spreadsheets and memory. This system segments HCPs by prescribing value and growth trend, recommends call frequency, tracks coverage against plan, and flags declining high-value prescribers before quarter-end.

## Docs (the core deliverable)

1. [**Business Requirements Document**](docs/01_BRD.md) — problem statement, stakeholders, functional/non-functional requirements, success metrics, scope boundaries.
2. [**Technical Design Document**](docs/02_TECHNICAL_DESIGN.md) — architecture, data model, segmentation algorithm, and **explicit tradeoffs** (e.g., why rule-based scoring was chosen over ML, why monthly Rx grain instead of transaction-level) with a requirements traceability table mapping every requirement to the design component that satisfies it.

## Implementation

- **Database:** PostgreSQL (Neon, serverless, free tier) — 6-table schema (`territories`, `reps`, `hcps`, `products`, `prescriptions`, `calls`)
- **Segmentation logic:** standalone SQL views (`sql/scoring.sql`) using `NTILE()` for quartile scoring and `LAG()` window functions for trend/decline detection — kept separate from app code so the formula is reviewable independent of the UI
- **App:** Streamlit, 4 tabs — Rep View, Manager View, Coverage, Decline Alerts

**Live demo:** https://hcp-targeting-case-study-aahumncsuuswf5szw6pnad.streamlit.app/
**Design docs:** browsable directly above on GitHub

## Repo structure
docs/
01_BRD.md
02_TECHNICAL_DESIGN.md
sql/
schema.sql -- table definitions
scoring.sql -- segmentation, coverage, and decline-alert views
seed_data.py -- generates realistic sample data (long-tail Rx distribution)
app/
db.py -- data access layer, parameterized queries
app.py -- Streamlit UI
requirements.txt
runtime.txt -- pins Python 3.11 for Streamlit Cloud compatibility

## Setup (to deploy your own copy)

1. **Create a free Neon Postgres database** at [neon.tech](https://neon.tech) — no card required. Copy the connection string.
2. **Run the schema and scoring views:**
```bash
   psql "$DATABASE_URL" -f sql/schema.sql
   psql "$DATABASE_URL" -f sql/scoring.sql
```
3. **Seed sample data:**
```bash
   pip install psycopg2-binary
   DATABASE_URL="postgresql://..." python sql/seed_data.py
```
4. **Run the app locally:**
```bash
   cd app
   pip install -r requirements.txt
   export DATABASE_URL="postgresql://..."
   streamlit run app.py
```
5. **Deploy on Streamlit Community Cloud:** point it at `app/app.py`, add `DATABASE_URL` under app secrets as:
```toml
   DATABASE_URL = "postgresql://..."
```

## Why this project exists

Built to demonstrate the specific skill a Business Technology Solutions role actually tests for: turning a business problem into a documented technical design *before* writing code, with tradeoffs made explicit rather than implicit. The BRD and TDD are the primary artifact here — the Streamlit app exists to prove the design actually works, the same way a working prototype backs up a design doc in a real engagement.
