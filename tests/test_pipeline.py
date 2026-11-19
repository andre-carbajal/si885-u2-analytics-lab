"""Small checks for the data-quality gate and Parquet output."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from pipeline.run import build


class PipelineTests(unittest.TestCase):
    def test_curates_valid_csv_and_rejects_duplicate_order_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sales.csv"
            output = root / "sales.parquet"
            source.write_text(
                "order_id,order_date,region,product,category,quantity,unit_price\n"
                "A-1,2026-01-01,Tacna,Mug,Home,2,10.25\n",
                encoding="utf-8",
            )
            report = build(source, output)
            self.assertEqual(report["curated_rows"], 1)
            self.assertEqual(report["total_revenue"], 20.5)
            self.assertEqual(duckdb.connect().execute("SELECT COUNT(*) FROM read_parquet(?)", [str(output)]).fetchone()[0], 1)

            source.write_text(
                "order_id,order_date,region,product,category,quantity,unit_price\n"
                "A-1,2026-01-01,Tacna,Mug,Home,2,10.25\n"
                "A-1,2026-01-02,Tacna,Tea,Grocery,1,3.00\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate order IDs"):
                build(source, output)

    def test_rejects_invalid_rows_instead_of_silently_dropping_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.csv"
            source.write_text(
                "order_id,order_date,region,product,category,quantity,unit_price\n"
                "A-1,not-a-date,Tacna,Mug,Home,0,10.25\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "1 invalid rows"):
                build(source, Path(directory) / "bad.parquet")


if __name__ == "__main__":
    unittest.main()
