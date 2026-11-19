---
title: "From CSV to Trusted Parquet: A Tiny Data Engineering Pipeline with Python, DuckDB, and GitHub Actions"
tags: dataengineering, python, duckdb, githubactions
---

A data pipeline is more than moving a file from one folder to another. The useful part is making the contract explicit: which rows are acceptable, what the output schema means, and what should happen when the input violates those rules.

For this SI-885 Unit 2 example, I built a small, reproducible pipeline around synthetic order data. The source is a CSV; the curated output is compressed Parquet; DuckDB performs the transformations; and GitHub Actions runs tests and publishes a static report to GitHub Pages. No AWS services are used.

**Try it:** [live report](https://andre-carbajal.github.io/si885-u2-analytics-lab/data-engineering/) · [public repository](https://github.com/andre-carbajal/si885-u2-analytics-lab)

![Architecture: CSV → validation and transformation → Parquet → DuckDB OLAP → GitHub Pages](https://andre-carbajal.github.io/si885-u2-analytics-lab/assets/architecture.svg)

## The pipeline contract

The source contains order ID, date, region, product, category, quantity, and unit price. The pipeline:

1. Reads the CSV with DuckDB, keeping source fields as strings at the boundary.
2. Rejects rows with missing dimensions, invalid dates, non-positive quantities or prices.
3. Rejects duplicate order IDs rather than quietly picking one.
4. Casts fields to usable types and derives <code>revenue = quantity × unit_price</code>.
5. Writes a typed Parquet file for the analytical step.

The important choice is to **fail instead of silently dropping bad records**. For a real pipeline, rejected rows would usually be written to a quarantine location with a reason and then surfaced to an owner; for this small teaching example, a failed build makes the problem visible.

## A quality gate in Python

The key code is in [pipeline/run.py](https://github.com/andre-carbajal/si885-u2-analytics-lab/blob/main/pipeline/run.py). It binds the file path as a parameter and checks quality before writing output:

~~~python
con.execute(
    "CREATE TEMP TABLE source_orders AS "
    "SELECT * FROM read_csv_auto(?, header = true, all_varchar = true)",
    [str(source)],
)

invalid_rows = con.execute(VALIDATION_SQL).fetchone()[0]
duplicate_ids = con.execute(
    "SELECT COUNT(*) FROM ("
    " SELECT TRIM(order_id) FROM source_orders"
    " GROUP BY TRIM(order_id) HAVING COUNT(*) > 1"
    ")"
).fetchone()[0]

if invalid_rows or duplicate_ids:
    raise ValueError("Data quality gate failed")

con.sql(TRANSFORM_SQL).write_parquet(str(destination), compression="zstd")
~~~

The SQL casts use <code>TRY_CAST</code> so malformed input can be counted by the validation query instead of crashing halfway through the transform. After the gate passes, the transform uses typed columns and derives revenue once, at the curated boundary.

DuckDB’s Python client can query local files directly and write query results to Parquet; that keeps this demo small without adding a separate database server. See the [DuckDB Python client](https://duckdb.org/docs/stable/clients/python/overview) and [Parquet documentation](https://duckdb.org/docs/stable/data/parquet/overview).

## One workflow, repeatable output

The GitHub Actions workflow in [.github/workflows/publish.yml](https://github.com/andre-carbajal/si885-u2-analytics-lab/blob/main/.github/workflows/publish.yml) runs the unit tests, rebuilds the report, uploads the generated site artifact, and deploys it to GitHub Pages. It runs on a push to <code>main</code>, a manual dispatch, and once a week. The workflow requests only the <code>contents: read</code>, <code>pages: write</code>, and <code>id-token: write</code> permissions needed for that job.

The tests prove two important behaviors: valid rows become Parquet with the expected revenue, while malformed rows and duplicate IDs fail the pipeline. That is a modest but useful acceptance check before anything is published.

## What the live page does—and does not do

The public [pipeline report](https://andre-carbajal.github.io/si885-u2-analytics-lab/data-engineering/) shows the row count, quality-gate results, and curated sales value computed during the latest successful build. The next stage reads the Parquet file to build the OLAP model.

This is a **batch pipeline**, not streaming and not a production-scale performance claim. GitHub Pages serves the generated HTML and JSON; it does not run DuckDB queries for each visitor. For larger or continuously arriving data, the design would need durable storage, incremental processing, stronger observability, and an orchestration or warehouse service appropriate to its volume and service-level objectives.

All example orders are synthetic. The displayed numbers use a PEN currency format for the Peruvian demo regions, but the CSV itself has no currency field; these are synthetic values, not real sales.

## Reproduce it

~~~
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python build_site.py
python -m http.server 8000 --directory _site
~~~

Then open <http://localhost:8000>. The source and the exact workflow are in the [repository](https://github.com/andre-carbajal/si885-u2-analytics-lab).
