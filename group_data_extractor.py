#!/usr/bin/env python3
"""
group_data_extractor.py – Stage‑1 loader

Scans every *.csv in  data/grouped/<group_id>/  and emits a single JSON bundle.
"""

from __future__ import annotations
import argparse, csv, json, logging
from datetime import datetime
from decimal     import Decimal
from pathlib     import Path
from typing      import Any, Dict, List

from group_meta  import UNITS, NUMERIC_UNITS   # ← now import canonical constant

# ──────────────────────────────── logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("extractor")

# ──────────────────────────────── helpers
def coerce(value: str, unit: str):
    """Return Decimal for numeric cells, str otherwise (None for blanks)."""
    if not value:
        return None
    if unit in NUMERIC_UNITS or unit.startswith("score_"):
        try:
            return Decimal(value)
        except (ValueError, ArithmeticError):
            return value.strip()           # keep raw text if parsing fails
    return value.strip()

GROUP_IDS = set(UNITS)                      # blueprint

# ──────────────────────────────── core extraction
def extract(grouped_root: Path) -> Dict[str, List[Dict[str, Any]]]:
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
            try:
                with csv_path.open("r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not any(row.values()):
                            continue
                        coerced = {
                            col: coerce(val, unit_map.get(col.lower(), "") if isinstance(unit_map, dict) else unit_map)
                            for col, val in row.items()
                        }
                        results[gid].append(coerced)
            except csv.Error as e:
                log.error("CSV parse error in %s – %s (skipped file)", csv_path.name, e)

        log.info("%-25s : %d rows", gid, len(results[gid]))
    return results

# ──────────────────────────────── JSON serialisation
def _encode_json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"{obj!r} is not JSON serialisable")

def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=_encode_json), encoding="utf-8")
    log.info("Wrote %s", path)

# ──────────────────────────────── CLI
def main() -> None:
    ap = argparse.ArgumentParser(description="Combine grouped CSVs into one JSON")
    ap.add_argument("-d", "--grouped-dir", default="data/grouped")
    ap.add_argument("-o", "--output",      default="extracted_groups.json")
    args = ap.parse_args()

    start = datetime.now()
    groups  = extract(Path(args.grouped_dir))
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
