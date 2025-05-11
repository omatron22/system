#!/usr/bin/env python3
"""
group_data_extractor.py  – Stage‑1 loader

Reads every *.csv inside  data/grouped/<group_id>/  and emits a single JSON:
{
  "timestamp": "...",
  "group_count": 30,
  "data_points": N,
  "groups": { "<group_id>": [ {...row...}, ... ], ... }
}
"""

from __future__ import annotations
import argparse, csv, json, logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# ─────────────────────────
# Logging
# ─────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("extractor")

# ─────────────────────────
# Blueprint group IDs
# (kept solely to pre‑initialise result dict)
# ─────────────────────────
GROUP_IDS = {
    "vision","market_assessment","strategic_assessment","risk_assessment","competitive_assessment",
    "portfolio_assessment","strengths_assessment","weaknesses_assessment","opportunities_assessment",
    "threats_assessment","revenue_growth","operating_income","cash_flow","gross_margin","finance_metrics",
    "time_to_hire","employee_turnover","employee_engagement","management_team_quality","hr_metrics",
    "inventory_turnover","on_time_delivery","first_pass_yield","total_cycle_time","operations_metrics",
    "annual_recurring_revenue","customer_acquisition_cost","design_win","sales_opportunities",
    "sales_marketing_metrics",
}

# ─────────────────────────
# Extraction
# ─────────────────────────
def extract(grouped_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    results = {gid: [] for gid in GROUP_IDS}

    for group_dir in grouped_root.iterdir():
        if not group_dir.is_dir():
            continue
        gid = group_dir.name.lower()
        if gid not in GROUP_IDS:
            log.warning("Unknown group folder %s – skipping", gid)
            continue

        for csv_path in group_dir.glob("*.csv"):
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if any(row.values()):
                        results[gid].append({k: v.strip() for k, v in row.items()})
        log.info("%-25s : %d rows", gid, len(results[gid]))

    return results


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Wrote %s", path)


# ─────────────────────────
# CLI
# ─────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Load grouped CSVs into one JSON")
    ap.add_argument("-d", "--grouped-dir", default="data/grouped", help="Source directory")
    ap.add_argument("-o", "--output", default="extracted_groups.json", help="JSON output path")
    args = ap.parse_args()

    start = datetime.now()
    groups = extract(Path(args.grouped_dir))
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "group_count": len(groups),
        "data_points": sum(len(v) for v in groups.values()),
        "groups": groups,
    }
    save_json(payload, Path(args.output))
    log.info("Done in %.2fs", (datetime.now() - start).total_seconds())
    print(f"✅ Extraction complete → {args.output}")


if __name__ == "__main__":
    main()
