"""Build the ETL result, OLAP report, and static GitHub Pages site."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pipeline.run import build as build_pipeline
from olap.build import build as build_olap


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "_site"


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "web", SITE)
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/architecture.svg", SITE / "assets/architecture.svg")
    pipeline_report = build_pipeline(ROOT / "data/raw/sales.csv", ROOT / "build/curated/sales.parquet")
    (SITE / "data/pipeline.json").write_text(json.dumps(pipeline_report, indent=2), encoding="utf-8")
    olap_report = build_olap(ROOT / "build/curated/sales.parquet", SITE / "data/olap.json")
    print(json.dumps({"pipeline": pipeline_report, "olap": {"orders": olap_report["orders"], "dimensions": olap_report["dimensions"]}}, indent=2))


if __name__ == "__main__":
    main()
