"""Validate synthetic CSV orders and curate them into compressed Parquet."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb


VALIDATION_SQL = """
    SELECT COUNT(*)
    FROM raw_orders
    WHERE COALESCE(TRIM(order_id), '') = ''
       OR TRY_CAST(order_date AS DATE) IS NULL
       OR COALESCE(TRIM(region), '') = ''
       OR COALESCE(TRIM(product), '') = ''
       OR COALESCE(TRIM(category), '') = ''
       OR TRY_CAST(quantity AS INTEGER) IS NULL
       OR TRY_CAST(quantity AS INTEGER) <= 0
       OR TRY_CAST(unit_price AS DECIMAL(12, 2)) IS NULL
       OR TRY_CAST(unit_price AS DECIMAL(12, 2)) <= 0
"""

TRANSFORM_SQL = """
    SELECT
        TRIM(order_id) AS order_id,
        TRY_CAST(order_date AS DATE) AS order_date,
        UPPER(TRIM(region)) AS region,
        TRIM(product) AS product,
        UPPER(TRIM(category)) AS category,
        TRY_CAST(quantity AS INTEGER) AS quantity,
        TRY_CAST(unit_price AS DECIMAL(12, 2)) AS unit_price,
        CAST(TRY_CAST(quantity AS INTEGER) * TRY_CAST(unit_price AS DECIMAL(12, 2)) AS DECIMAL(12, 2)) AS revenue
    FROM raw_orders
"""


def build(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise FileNotFoundError(f"Input CSV not found: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    with duckdb.connect(":memory:") as con:
        con.execute(
            "CREATE TEMP TABLE raw_orders AS SELECT * FROM read_csv_auto(?, header = true, all_varchar = true)",
            [str(source)],
        )
        row_count = con.execute("SELECT COUNT(*) FROM raw_orders").fetchone()[0]
        invalid_rows = con.execute(VALIDATION_SQL).fetchone()[0]
        duplicate_ids = con.execute(
            "SELECT COUNT(*) FROM (SELECT TRIM(order_id) FROM raw_orders GROUP BY TRIM(order_id) HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if invalid_rows or duplicate_ids:
            raise ValueError(f"Data quality gate failed: {invalid_rows} invalid rows, {duplicate_ids} duplicate order IDs")
        con.sql(TRANSFORM_SQL).write_parquet(str(destination), compression="zstd")
        total_revenue = con.execute(
            "SELECT COALESCE(SUM(revenue), 0) FROM read_parquet(?)", [str(destination)]
        ).fetchone()[0]

    return {
        "source_rows": row_count,
        "curated_rows": row_count,
        "invalid_rows": invalid_rows,
        "duplicate_ids": duplicate_ids,
        "total_revenue": float(total_revenue),
        "output_file": destination.name,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = build(root / "data/raw/sales.csv", root / "build/curated/sales.parquet")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
