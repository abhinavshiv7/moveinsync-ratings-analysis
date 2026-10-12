# MoveInSync Play Store Ratings Analysis

This repository contains the reproducible data collection and analysis used for the MoveInSync Forward Deployed Engineer candidate case study.

## Objective

The analysis investigates why MoveInSync's public app ratings are below their potential and converts public review evidence into a prioritized product, engineering, operations, and support plan.

## Key findings

- The public Play Store rating was 4.3, while the latest 90-day written-review sample averaged 3.81.
- Login and OTP failures, booking and cancellation issues, stability problems, tracking and ETA errors, and route planning were the leading recent low-rating themes.
- Version 12.19.0 showed the clearest current startup and update-regression signal.
- Apple reviews contained many of the same journey complaints, suggesting that several problems require product and operations fixes rather than Android-only patches.
- Developer replies to recent reviews were substantially below the lifetime response rate.

These are review-derived hypotheses. Production telemetry, crash logs, booking events, location-freshness data, and support tickets should confirm root causes before large changes are shipped.

## Methodology

1. Query publicly exposed Google Play written reviews across 69 language parameters.
2. Query publicly visible Apple App Store review pages across country storefronts.
3. Deduplicate records by review ID while retaining source-language and storefront coverage.
4. Calculate rating distributions, monthly trends, recent-period comparisons, version signals, and developer-response coverage.
5. Apply a deterministic, multi-label phrase taxonomy aligned to the employee commute journey.
6. Compare recurring themes across Android and iOS and translate the strongest signals into prioritized actions and measurable outcomes.

The public datasets do not equal the storefront headline rating counts. Storefront totals include rating-only events and reviews that public endpoints do not enumerate.

## Repository structure

```text
analysis/
  collect_public_reviews.py  # Public Google Play and Apple review collector
  review_analysis.py         # Trends, themes, versions, evidence, and audit outputs
data/
  raw/                       # Generated locally and excluded from Git
```

## Reproduce the analysis

Python 3.11 or later is recommended.

```bash
python -m venv .venv
```

Activate the environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

Collect the public reviews:

```bash
python analysis/collect_public_reviews.py
```

Generate the analysis outputs:

```bash
python analysis/review_analysis.py --export
```

The collector accesses public storefront pages and may take time to complete. Results can change as stores update their public feeds.

## Tools used

- Python and pandas for collection, cleaning, analysis, and structured exports
- `google-play-scraper` for publicly exposed Google Play written reviews
- Requests and Beautiful Soup for public Apple storefront pages
- JavaScript-based artifact generation for the submitted Excel workbook and PowerPoint presentation
- AI-assisted analysis, drafting, and quality review

## Deliverables

The submitted package includes the recommendation presentation, supporting Excel analysis, and a methodology and tools note. They are distributed separately to preserve the original submission format and avoid committing generated binary files.

## Responsible use

The repository excludes raw review exports because they contain user-generated text and reviewer metadata. Run the collector to obtain the current publicly available data. Use the results for aggregate analysis and avoid identifying individual reviewers.

