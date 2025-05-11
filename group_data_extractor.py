#!/usr/bin/env python3
"""
group_data_extractor.py  – Stage‑1 loader

Walks every *.csv in  data/grouped/<group_id>/  and emits one JSON:

{
  "timestamp": "...",
  "group_count": 30,
  "data_points": N,
  "meta": { "<group_id>": <unit/scale info>, ... },
  "groups": { "<group_id>": [ {...row...}, ... ], ... }
}
"""

from __future__ import annotations
import argparse, csv, json, logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from decimal import Decimal

from group_meta import UNITS                    # central unit / scale map

# ─────────────────────────
# Logging
# ─────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("extractor")

# ─────────────────────────
# Helper: numeric coercion
# ─────────────────────────
_NUMERIC_UNITS = {"%", "USD_M", "USD_k", "turns", "days", "num"}   # ← added "num"

def coerce(value: str, unit: str):
    """Coerce cell to Decimal when the unit marks it numeric."""
    if not value:
        return None
    if unit in _NUMERIC_UNITS or unit.startswith("score_"):
        try:
            return Decimal(value)
        except:
            return value.strip()            # keep raw text on failure
    return value.strip()

# ─────────────────────────
# Blueprint group IDs
# ─────────────────────────
GROUP_IDS = set(UNITS)                        # single source of truth

# ─────────────────────────
# Extraction
# ─────────────────────────
def extract(grouped_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Return {group_id: [rows…]} from every *.csv inside data/grouped/…"""
    results: Dict[str, List[Dict[str, Any]]] = {gid: [] for gid in GROUP_IDS}

    for group_dir in grouped_root.iterdir():
        if not group_dir.is_dir():
            continue
        gid = group_dir.name.lower()
        if gid not in GROUP_IDS:
            log.warning("Unknown group folder %s – skipped", gid)
            continue

        unit_map = UNITS.get(gid, "")

        for csv_path in group_dir.glob("*.csv"):
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if not any(row.values()):
                        continue

                    # choose a unit PER‑COLUMN if unit_map is a dict
                    coerced: Dict[str, Any] = {}
                    for col, val in row.items():
                        col_unit = unit_map.get(col.lower(), "") if isinstance(unit_map, dict) else unit_map
                        coerced[col] = coerce(val, col_unit)
                    results[gid].append(coerced)

        log.info("%-25s : %d rows", gid, len(results[gid]))
    return results

# ─────────────────────────
# JSON helper (Decimal → float)
# ─────────────────────────
def _encode_json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"{obj!r} is not JSON serialisable")

def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=_encode_json), encoding="utf-8")
    log.info("Wrote %s", path)

# ─────────────────────────
# CLI
# ─────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Combine grouped CSVs into one JSON")
    ap.add_argument("-d", "--grouped-dir", default="data/grouped",
                    help="Source directory")
    ap.add_argument("-o", "--output", default="extracted_groups.json",
                    help="JSON output path")
    args = ap.parse_args()

    start = datetime.now()
    groups = extract(Path(args.grouped_dir))
    payload = {
        "timestamp": start.isoformat(timespec="seconds"),
        "group_count": len(groups),
        "data_points": sum(len(v) for v in groups.values()),
        "meta": UNITS,
        "groups": groups,
    }
    save_json(payload, Path(args.output))
    log.info("Done in %.2fs", (datetime.now() - start).total_seconds())
    print(f"✅ Extraction complete → {args.output}")


if __name__ == "__main__":
    main()
