#!/usr/bin/env python3
"""
organise_csvs.py – Stage‑0 pre‑processor for Qmirac CSV drops

• Reads every *.csv in  data/raw/
• Decides which of the 30 blueprint groups it belongs to
• Copies (or moves) the file into  data/grouped/<group_id>/filename.csv
• Prints a summary and exits 1 if anything is still unmapped
"""

from __future__ import annotations
import argparse, csv, shutil, sys
from collections import defaultdict
from pathlib     import Path
from typing      import Dict

# ────────────────────────────────────────────────────────────
# 1) Exact filename → group map  (stem must be lowercase, no extension)
# ────────────────────────────────────────────────────────────
FILENAME_MAP: Dict[str, str] = {
    # Finance
    "revenuegrowthdata":           "revenue_growth",
    "opincomedatatable":           "operating_income",
    "cfodatatable":                "cash_flow",
    "gmdatatable":                 "gross_margin",
    "finmetricdatatable":          "finance_metrics",
    # HR
    "hrtimedatatable":             "time_to_hire",
    "empturndatatable":            "employee_turnover",
    "empengagedatatable":          "employee_engagement",
    "managementdatatable":         "management_team_quality",
    "hrmetricdatatable":           "hr_metrics",
    # OPS
    "invturndatatable":            "inventory_turnover",
    "otddatatable":                "on_time_delivery",
    "yielddatatable":              "first_pass_yield",
    "cycletimedatatable":          "total_cycle_time",
    "opsmetricdatatable":          "operations_metrics",
    # Sales & Marketing
    "arrdatatable":                "annual_recurring_revenue",
    "cacdatatable":                "customer_acquisition_cost",
    "dwdatatable":                 "design_win",
    "oppdatatable":                "opportunities_assessment",
    "swotopddatatable":            "opportunities_assessment",  # legacy duplicate
    "sandmmetricdatatable":        "sales_marketing_metrics",
    # Vision / SWOT misc
    "swotoppdatatable":            "opportunities_assessment",
    "mybusinessspecdatatable":     "vision",
    "riskdatatable":               "risk_assessment",
    "strengthsdatatable":          "strengths_assessment",
    "weakdatatable":               "weaknesses_assessment",
    "threatdatatable":             "threats_assessment",
}

# Family‑pattern stems (market1‑5, stratpos1‑5, …)
FAMILY_MAP = {"market": "market_assessment",
              "stratpos": "strategic_assessment"}

# ────────────────────────────────────────────────────────────
# 2) Fallback header hints
# ────────────────────────────────────────────────────────────
HEADER_HINTS = {
    "design_win":               ["design win"],
    "management_team_quality":  ["management", "team quality"],
    "opportunities_assessment": ["opportunity"],
}

# ──────────────────────────────────────────────────────────── helpers
def header_guess(csv_path: Path) -> str | None:
    """Look at the header row if filename guessing failed."""
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            headers = [h.lower() for h in next(csv.reader(f), [])]
    except (StopIteration, FileNotFoundError, PermissionError, UnicodeDecodeError):
        return None

    joined = " ".join(headers)
    for gid, hints in HEADER_HINTS.items():
        if any(h in joined for h in hints):
            return gid
    return None


def route(src: Path, group_id: str, dest_root: Path, *, move: bool) -> None:
    """Copy or move file into its group folder."""
    dest_dir = dest_root / group_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (shutil.move if move else shutil.copy2)(src, dest_dir / src.name)

# ──────────────────────────────────────────────────────────── core
def organise(raw_dir: Path, grouped_dir: Path, *, move: bool) -> None:
    summary, unmapped = defaultdict(int), []

    for csv_path in raw_dir.iterdir():
        if csv_path.suffix.lower() != ".csv":
            continue                                # ignore non‑CSV drops

        stem_lower = csv_path.stem.lower()
        gid = (
            FILENAME_MAP.get(stem_lower)
            or next((g for p, g in FAMILY_MAP.items()
                     if stem_lower.startswith(p)), None)
            or header_guess(csv_path)
        )

        if gid:
            route(csv_path, gid, grouped_dir, move=move)
            summary[gid] += 1
        else:
            unmapped.append(csv_path)

    # ─── summary output ──────────────────────────────────────
    GREEN, RED, END = "\033[92m", "\033[91m", "\033[0m"
    print("\n🗂  CSV grouping summary")
    for gid, n in sorted(summary.items()):
        print(f"  {GREEN}{gid:25s}{END} : {n} file(s)")
    if unmapped:
        print(f"\n{RED}⚠️  Unmapped files:{END}")
        for p in unmapped:
            print("  •", p.name)
        sys.exit(1)

# ──────────────────────────────────────────────────────────── CLI
def main() -> None:
    ap = argparse.ArgumentParser(description="Organise raw Qmirac CSVs into group folders")
    ap.add_argument("-r", "--raw-dir",     default="data/raw")
    ap.add_argument("-g", "--grouped-dir", default="data/grouped")
    ap.add_argument("--mode", choices=["copy", "move"], default="copy",
                    help="Copy (default) or move files")
    args = ap.parse_args()

    organise(Path(args.raw_dir), Path(args.grouped_dir),
             move=(args.mode == "move"))

if __name__ == "__main__":
    main()
