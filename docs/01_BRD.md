# Business Requirements Document (BRD)
## HCP Targeting & Call Planning System

| | |
|---|---|
| **Project** | HCP Targeting & Call Planning System |
| **Client (simulated)** | Mid-size pharmaceutical company, cardiology portfolio |
| **Author** | Dhayal Ramesh |
| **Status** | Approved for design |
| **Document type** | Business Requirements Document (BRD) |

> **Note on this document:** This is a self-authored case study built to demonstrate the requirements-to-design workflow used in commercial analytics consulting (the kind of engagement a Business Technology Solutions Associate would run at a firm like ZS). The business context is realistic and modeled on how pharma field-force effectiveness problems are actually structured, but the "client" and stakeholder quotes are illustrative, not from a real engagement.

---

## 1. Executive Summary

The client's field sales organization (120 reps across 15 territories) currently plans which healthcare professionals (HCPs) to visit using static spreadsheets exported quarterly from the data warehouse. Reps have no consistent way to know which doctors are worth prioritizing, sales managers cannot see whether reps are covering high-value HCPs, and there is no closed loop between call activity and prescribing outcomes. This BRD defines the requirements for a system that segments HCPs by prescribing value, generates call-frequency recommendations, and tracks coverage against plan.

## 2. Business Context / Problem Statement

Pharmaceutical field reps have limited time — roughly 8-10 HCP calls per day. Not all HCPs are equal: a small percentage of prescribers typically account for a large share of volume in a given territory (a long-tail distribution, not a normal one). Today, reps decide who to visit based on personal relationships and memory rather than data, which means:

- High-potential HCPs with low current engagement are under-called.
- Reps over-invest time in already-loyal, low-growth-potential prescribers.
- Sales managers have no objective way to audit call plans or measure rep effectiveness.
- There is no mechanism to detect when a high-value HCP's prescribing is declining before it shows up in quarterly sales numbers.

## 3. Stakeholders

| Stakeholder | Interest |
|---|---|
| VP, Sales Operations | Wants territory-level visibility into coverage and ROI on rep time |
| District Sales Managers | Need to review and approve rep call plans weekly |
| Field Sales Reps | Need a prioritized, explainable list of who to see and how often |
| Commercial Analytics Team | Owns the segmentation logic and must be able to explain/defend it to Sales |

## 4. Business Objectives

1. Give every rep a data-driven, explainable list of HCPs ranked by priority.
2. Give managers a way to measure whether reps are actually covering high-priority HCPs.
3. Surface prescribing trend changes (especially declines) for high-value HCPs early.
4. Replace the quarterly static spreadsheet process with something reps and managers can query on demand.

## 5. Current State ("As-Is")

- Data warehouse exports an Rx (prescription) volume file quarterly.
- A regional analyst manually sorts this in Excel and emails territory lists to managers.
- Managers forward lists to reps with no standard prioritization logic — it's usually a flat list sorted by last quarter's raw volume.
- Call activity is logged in a separate CRM system that is never compared back against the plan.
- There is a **4-8 week lag** between a prescribing shift happening and anyone noticing it.

## 6. Proposed Future State

- HCPs are automatically segmented into tiers (A/B/C/D) using a transparent, explainable scoring model combining current prescribing volume and recent growth trend.
- Each tier maps to a recommended call frequency (e.g., Tier A → weekly, Tier D → quarterly).
- Reps see their prioritized list in one place, alongside their actual call history.
- Managers see a coverage view: planned vs. actual calls, by tier, by rep, by territory.
- The system flags HCPs with declining prescribing trend regardless of tier, so a drop-off is visible immediately rather than at quarter-end.

## 7. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System shall calculate a segmentation score for every HCP based on prescribing volume and growth trend. | Must |
| FR-02 | System shall assign each HCP to a tier (A/B/C/D) derived from the segmentation score. | Must |
| FR-03 | System shall map each tier to a recommended call frequency. | Must |
| FR-04 | System shall display, per rep, a prioritized HCP list filterable by territory and tier. | Must |
| FR-05 | System shall log call activity (rep, HCP, date, outcome) and compare it against the recommended frequency to produce a coverage percentage. | Must |
| FR-06 | System shall flag any Tier A or B HCP whose prescribing volume has declined over the last 2 consecutive months. | Must |
| FR-07 | System shall allow a manager to view coverage roll-ups by territory and by rep. | Should |
| FR-08 | System shall recompute segmentation on a defined refresh cycle (monthly) rather than requiring manual recalculation. | Should |
| FR-09 | Segmentation logic shall be explainable — a rep or manager can see *why* an HCP is Tier A, not just that it is. | Must |
| FR-10 | System shall support multiple products/brands, since reps often carry more than one. | Could |

## 8. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Segmentation and coverage views must load in under 3 seconds for a single territory. |
| NFR-02 | Underlying data model must support adding new HCPs, reps, and territories without schema changes. |
| NFR-03 | Scoring logic must be transparent enough to defend to a non-technical sales audience — no black-box ML model for v1. |
| NFR-04 | System must be usable by reps and managers with no SQL knowledge (UI layer required, not just database access). |

## 9. Success Metrics

- **Coverage compliance:** % of Tier A/B HCPs receiving the recommended call frequency, tracked monthly (target: >80%).
- **Time-to-detection:** average time between a prescribing decline starting and it being flagged (target: <2 weeks, down from 4-8 weeks today).
- **Adoption:** % of reps using the system-generated list instead of ad hoc planning within 60 days of rollout.

## 10. Assumptions & Constraints

- Prescription (Rx) volume data is assumed to be available monthly, by HCP, by product.
- The scoring model intentionally favors explainability over predictive sophistication for v1 — a rule-based weighted score, not a machine learning model, per NFR-03. This is a deliberate scope decision, expanded on in the Technical Design Document.
- The system does not handle rep territory *alignment* (deciding which HCPs belong to which rep) — that is assumed as an input, not something this system computes.
- No integration with the live CRM system is in scope for v1; call activity is captured directly.

## 11. Out of Scope (v1)

- Automated territory alignment / realignment.
- Predictive ML-based next-best-action recommendations.
- Mobile app for reps (web only).
- Integration with external CRM (Veeva, Salesforce) — data entry is manual for this version.

## 12. Glossary

| Term | Definition |
|---|---|
| HCP | Healthcare Professional (typically a physician) who can prescribe the product |
| Rx | Prescription — the volume unit used to measure a product's uptake with a given HCP |
| Tier | A/B/C/D classification of an HCP's priority for sales calls |
| Call | A sales rep's visit or interaction with an HCP |
| Coverage | The ratio of actual calls made to the recommended number of calls, for a given HCP or tier |