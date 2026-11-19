"""Build a small star schema and publish query results as JSON."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, object]]:
    cursor = con.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def build(curated_parquet: Path, output_json: Path) -> dict[str, object]:
    curated_parquet = Path(curated_parquet)
    output_json = Path(output_json)
    if not curated_parquet.is_file():
        raise FileNotFoundError(f"Curated Parquet not found: {curated_parquet}")
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(":memory:") as con:
        con.execute("CREATE TEMP TABLE clean_sales AS SELECT * FROM read_parquet(?)", [str(curated_parquet)])
        con.execute("""
            CREATE TABLE dim_date AS
            SELECT ROW_NUMBER() OVER (ORDER BY order_date) AS date_key,
                   order_date,
                   STRFTIME(order_date, '%Y-%m') AS year_month,
                   DATE_PART('year', order_date)::INTEGER AS year,
                   DATE_PART('quarter', order_date)::INTEGER AS quarter
            FROM (SELECT DISTINCT order_date FROM clean_sales)
        """)
        con.execute("""
            CREATE TABLE dim_product AS
            SELECT ROW_NUMBER() OVER (ORDER BY product) AS product_key, product, category
            FROM (SELECT DISTINCT product, category FROM clean_sales)
        """)
        con.execute("""
            CREATE TABLE dim_region AS
            SELECT ROW_NUMBER() OVER (ORDER BY region) AS region_key, region
            FROM (SELECT DISTINCT region FROM clean_sales)
        """)
        con.execute("""
            CREATE TABLE fact_sales AS
            SELECT s.order_id, d.date_key, p.product_key, r.region_key,
                   s.quantity, s.unit_price, s.revenue
            FROM clean_sales s
            JOIN dim_date d USING (order_date)
            JOIN dim_product p USING (product, category)
            JOIN dim_region r USING (region)
        """)
        summary = con.execute("""
            SELECT COUNT(*) AS orders,
                   COALESCE(SUM(revenue), 0) AS revenue,
                   COALESCE(AVG(revenue), 0) AS average_order_value
            FROM fact_sales
        """).fetchone()
        monthly = _rows(con, """
            SELECT d.year_month, SUM(f.revenue) AS revenue, COUNT(*) AS orders
            FROM fact_sales f JOIN dim_date d USING (date_key)
            GROUP BY d.year_month ORDER BY d.year_month
        """)
        by_region = _rows(con, """
            SELECT r.region, SUM(f.revenue) AS revenue, COUNT(*) AS orders
            FROM fact_sales f JOIN dim_region r USING (region_key)
            GROUP BY r.region ORDER BY revenue DESC
        """)
        by_category = _rows(con, """
            SELECT p.category, SUM(f.revenue) AS revenue, COUNT(*) AS orders
            FROM fact_sales f JOIN dim_product p USING (product_key)
            GROUP BY p.category ORDER BY revenue DESC
        """)
        detail = _rows(con, """
            SELECT d.year_month, r.region, p.category, p.product,
                   SUM(f.quantity) AS units, SUM(f.revenue) AS revenue
            FROM fact_sales f
            JOIN dim_date d USING (date_key)
            JOIN dim_product p USING (product_key)
            JOIN dim_region r USING (region_key)
            GROUP BY d.year_month, r.region, p.category, p.product
            ORDER BY d.year_month, r.region, revenue DESC
        """)
        payload: dict[str, object] = {
            "orders": int(summary[0]),
            "revenue": float(summary[1]),
            "average_order_value": float(summary[2]),
            "monthly": [{**row, "revenue": float(row["revenue"])} for row in monthly],
            "by_region": [{**row, "revenue": float(row["revenue"])} for row in by_region],
            "by_category": [{**row, "revenue": float(row["revenue"])} for row in by_category],
            "detail": [{**row, "revenue": float(row["revenue"])} for row in detail],
            "dimensions": {
                "date": int(con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]),
                "product": int(con.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0]),
                "region": int(con.execute("SELECT COUNT(*) FROM dim_region").fetchone()[0]),
                "fact_rows": int(con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]),
            },
        }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = build(root / "build/curated/sales.parquet", root / "web/data/olap.json")
    print(json.dumps({"orders": result["orders"], "revenue": result["revenue"], "dimensions": result["dimensions"]}, indent=2))


if __name__ == "__main__":
    main()
