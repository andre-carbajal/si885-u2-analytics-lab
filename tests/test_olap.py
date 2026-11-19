"""Integration check for the star schema and rollup totals."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from olap.build import build as build_olap
from pipeline.run import build as build_pipeline


class OlapTests(unittest.TestCase):
    def test_fact_rows_and_monthly_rollups_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sales.csv"
            curated = root / "sales.parquet"
            result = root / "olap.json"
            source.write_text(
                "order_id,order_date,region,product,category,quantity,unit_price\n"
                "A-1,2026-01-01,Tacna,Mug,Home,2,10.25\n"
                "A-2,2026-02-01,Lima,Tea,Grocery,1,5.00\n",
                encoding="utf-8",
            )
            build_pipeline(source, curated)
            report = build_olap(curated, result)
            self.assertEqual(report["orders"], 2)
            self.assertEqual(report["dimensions"]["fact_rows"], 2)
            self.assertEqual(sum(row["revenue"] for row in report["monthly"]), report["revenue"])
            self.assertEqual(len(report["monthly"]), 2)
            self.assertTrue(result.is_file())


if __name__ == "__main__":
    unittest.main()
