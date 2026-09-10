# Technical Design Document (TDD)
## HCP Targeting & Call Planning System

| | |
|---|---|
| **Project** | HCP Targeting & Call Planning System |
| **Author** | Dhayal Ramesh |
| **Input document** | [01_BRD.md](./01_BRD.md) |
| **Status** | Design approved, implemented in v1 |

---

## 1. Objective

Translate the requirements in the BRD into a concrete system: a data model, a segmentation algorithm, and an application layer, with explicit tradeoffs recorded at each decision point.

## 2. Requirements Traceability

| BRD Requirement | Design Component |
|---|---|
| FR-01, FR-02, FR-03 | Segmentation scoring engine (§5) — `hcps` table + scoring SQL |
| FR-04 | Streamlit "Rep View" tab, filterable by territory/tier |
| FR-05, FR-06 | `calls` table + coverage/decline SQL views, "Coverage" and "Alerts" tabs |
| FR-07 | Streamlit "Manager View" tab (territory/rep roll-ups) |
| FR-08 | Scoring implemented as a re-runnable SQL procedure, not baked into ingestion |
| FR-09 | Score is a transparent weighted formula with visible component breakdown in UI |
| NFR-03 | Rule-based scoring chosen over ML — see §5.3 |
| NFR-04 | Streamlit UI layer over raw Postgres — see §6 |

## 3. System Architecture
                ┌─────────────────────┐
                │   Neon PostgreSQL    │
                │  (cloud, serverless) │
                │                      │
                │  territories         │
                │  reps                │
                │  hcps                │
                │  products            │
                │  prescriptions       │
                │  calls               │
                └──────────┬───────────┘
                           │ psycopg2 / SQLAlchemy
                           │ (parameterized SQL,
                           │  read + write)
                ┌──────────▼───────────┐
                │   Streamlit app       │
                │  ─────────────────    │
                │  Rep View             │
                │  Manager View         │
                │  Coverage             │
                │  Decline Alerts       │
                └──────────┬───────────┘
                           │ HTTPS
                ┌──────────▼───────────┐
                │   End user (browser)  │
                │  Rep / Manager        │
                └───────────────────────┘


The architecture is intentionally simple — a single Postgres database and a single Streamlit application. For a v1 built to prove out requirements and get adoption, added infrastructure (message queues, separate services, a dedicated backend API) would be premature. See §9 for what changes at scale.

## 4. Data Model

### 4.1 Entity-Relationship overview
territories 1───∞ reps
territories 1───∞ hcps
reps 1───∞ calls
hcps 1───∞ calls
hcps 1───∞ prescriptions
products 1───∞ prescriptions


### 4.2 Tables

**territories**
| Column | Type | Notes |
|---|---|---|
| territory_id | SERIAL PK | |
| territory_name | TEXT | |
| region | TEXT | |

**reps**
| Column | Type | Notes |
|---|---|---|
| rep_id | SERIAL PK | |
| rep_name | TEXT | |
| territory_id | INT FK → territories | |

**hcps**
| Column | Type | Notes |
|---|---|---|
| hcp_id | SERIAL PK | |
| hcp_name | TEXT | |
| specialty | TEXT | e.g. Cardiology, Internal Medicine |
| territory_id | INT FK → territories | |

**products**
| Column | Type | Notes |
|---|---|---|
| product_id | SERIAL PK | |
| product_name | TEXT | |

**prescriptions**
| Column | Type | Notes |
|---|---|---|
| rx_id | SERIAL PK | |
| hcp_id | INT FK → hcps | |
| product_id | INT FK → products | |
| rx_month | DATE | first-of-month, one row per HCP/product/month |
| rx_volume | INT | units prescribed that month |

**calls**
| Column | Type | Notes |
|---|---|---|
| call_id | SERIAL PK | |
| rep_id | INT FK → reps | |
| hcp_id | INT FK → hcps | |
| call_date | DATE | |
| outcome | TEXT | e.g. Completed, Rescheduled, Declined |

Full DDL: [sql/schema.sql](../sql/schema.sql)

### 4.3 Design tradeoff: why prescriptions are monthly grain, not transaction-level

Real pharmacy claims/Rx data is transaction-level and extremely high volume. For a segmentation-and-coverage use case, monthly aggregation per HCP/product is sufficient granularity and keeps the model simple and queryable without a data warehouse layer. **Tradeoff accepted:** we lose day-level detail (e.g., can't see which day of the month a script was written) in exchange for a schema simple enough to serve interactively. This would need revisiting if the client later wanted intra-month trend detection.

## 5. Segmentation Algorithm Design

### 5.1 Requirement being solved

FR-01/02/03: every HCP needs a tier (A/B/C/D) derived from prescribing behavior, and FR-09 requires that tier to be explainable.

### 5.2 Scoring formula

For each HCP, over a trailing 3-month window:
volume_score = NTILE(4) of total Rx volume, across all HCPs in the same territory
growth_score = NTILE(4) of (latest month volume − 3-months-ago volume) / 3-months-ago volume

composite_score = (0.7 × volume_score) + (0.3 × growth_score)

tier = A if composite_score in top quartile
B if second quartile
C if third quartile
D if bottom quartile


Volume is weighted higher than growth (70/30) because absolute prescribing value is the primary driver of near-term revenue, while growth trend is a secondary signal used to catch rising prescribers before they'd otherwise surface in a volume-only ranking. Both components and the final tier are stored and displayed — not just the final label — so a rep or manager can see *why* an HCP landed in a given tier (NFR-03, FR-09).

### 5.3 Design tradeoff: rule-based scoring vs. machine learning

**Considered:** a clustering model (k-means on volume/growth/specialty features) or a predictive model (e.g., gradient boosting to predict next-quarter volume) to drive segmentation.

**Chosen:** a transparent weighted-quartile formula.

**Reasoning:**
- NFR-03 explicitly requires the model be defensible to a non-technical sales audience. A sales VP asking "why is Dr. Patel Tier A?" needs an answer like *"top-quartile volume in her territory, plus positive growth"* — not a decision boundary from a clustering algorithm.
- The HCP population and data volume here do not require the added complexity of a trained model to produce good rankings — the long-tail volume distribution is exactly what quartile-based scoring is suited to.
- A rule-based approach is trivially recomputed monthly (FR-08) with no retraining/monitoring overhead.
- **Where this tradeoff would flip:** if the client later wanted *predictive* next-best-action recommendations (not just a description of current value), or needed to score thousands of HCPs across dozens of products with feature interactions a human wouldn't hand-weight, a learned model would earn its complexity. That's flagged explicitly as out of scope for v1 in the BRD, not silently dropped.

### 5.4 Coverage & decline detection logic

- **Coverage %** = (actual calls to an HCP in the recommended period) ÷ (recommended calls per tier), computed via a `LEFT JOIN` from HCPs to calls so zero-call HCPs still appear at 0%, not silently excluded.
- **Decline alert** = flag HCPs where `rx_volume` has decreased in each of the last 2 consecutive months, using window functions (`LAG`) to compare each month to the prior one rather than just endpoints, so a dip-then-recovery isn't misflagged as a decline.

## 6. Tech Stack & Rationale

| Layer | Choice | Why |
|---|---|---|
| Database | PostgreSQL (Neon, serverless) | Free tier, no card required, supports window functions needed for the scoring/trend logic, matches what a production pharma commercial-analytics stack would actually run on |
| App/UI | Streamlit | Satisfies NFR-04 (no-SQL-knowledge users) with minimal build time; appropriate for an internal analytics tool, not a customer-facing product |
| DB access | SQLAlchemy + psycopg2 | Parameterized queries (no string-built SQL — avoids injection risk even though this is an internal tool) |
| Hosting | Streamlit Community Cloud | Free, sufficient for a v1 internal tool serving ~120 reps |

## 7. API / Module Design

The app is organized as:
- `db.py` — connection handling and all SQL as parameterized queries, one function per data need (e.g., `get_rep_hcp_list()`, `get_coverage_summary()`, `get_decline_alerts()`).
- `scoring.sql` — the segmentation logic as a standalone, re-runnable SQL script, separate from application code, so analytics team members can review/modify the formula without touching the app (directly supports FR-08's "must be able to recompute without manual recalculation").
- `app.py` — Streamlit UI, four tabs mapped directly to FR-04 and FR-07 (Rep View, Manager View, Coverage, Decline Alerts).

## 8. Non-Functional Considerations

- **Performance (NFR-01):** territory-scoped queries only, indexed on `territory_id` / `hcp_id` / `rep_id` foreign keys — avoids full-table scans as call/Rx history grows.
- **Explainability (NFR-03):** addressed structurally in §5.2/5.3, not just in the UI copy.
- **Extensibility (NFR-02):** new HCPs/reps/territories are just new rows — no schema change required to onboard a new territory.

## 9. What Changes at Scale (not built, noted for completeness)

If this went from a 120-rep v1 to a full national deployment:
- Move from monthly batch Rx aggregation to a proper data warehouse (dbt + a star schema) rather than aggregating directly in the transactional tables.
- Separate the scoring job into a scheduled pipeline (Airflow) rather than a SQL script run on demand.
- Move the app from Streamlit to a proper frontend/backend split (e.g., React + a REST/GraphQL API) once usage outgrows Streamlit's single-process model.
- Add real CRM integration (Veeva) instead of manual call logging.

These are explicitly *not* built here — the point of a v1 design is to solve the stated requirements without over-building, while documenting where the seams are for when scale demands it.

## 10. Testing Strategy

- Schema constraints (foreign keys, NOT NULL on required fields) enforced at the database level as the first line of defense.
- Scoring SQL validated against a small hand-computed sample (a handful of HCPs with known volume/growth) to confirm quartile and tier assignment match expectations before trusting it against the full dataset.
- Coverage logic checked against edge cases explicitly: an HCP with zero calls, an HCP with exactly the recommended number of calls, and an HCP with more calls than recommended.

