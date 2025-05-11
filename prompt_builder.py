#!/usr/bin/env python3
"""
prompt_builder.py – Stage‑2 prompt packager  (override‑aware)

Reads:
  • extracted_groups.json
  • group_questions.yaml      (questions + optional difficulty tag)

Writes one JSONL prompt per group into  data/prompts/
"""

from __future__ import annotations
import argparse, json, logging, textwrap
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("builder")

# ────────────────────────────────────────────────────────────
# helper: flatten YAML question list  ➜  ([texts], contains_hard?)
# ────────────────────────────────────────────────────────────
def parse_questions(raw: List) -> Tuple[List[str], bool]:
    texts, hard = [], False
    for item in raw:
        if isinstance(item, dict):          # new style  {text: “…”, difficulty: hard}
            texts.append(item["text"])
            hard |= (item.get("difficulty", "easy").lower() == "hard")
        else:                               # legacy plain string
            texts.append(str(item))
    return texts, hard

def choose_model(has_hard_qs: bool) -> str:
    return "deepseek-llm" if has_hard_qs else "phi-3-mini"

# ────────────────────────────────────────────────────────────
SYSTEM_TMPL = textwrap.dedent("""\
    You are Qmirac’s strategy‑analysis engine. Answer each question ONLY
    with clear, numbered sentences grounded in the data table provided.
    If an answer is not inferable, reply “insufficient data”.
""")

def build_user_block(group_id: str,
                     rows: List[Dict[str, str]],
                     units,
                     questions: List[str]) -> str:
    # tiny CSV block (header + up to 5 rows for brevity)
    header = ", ".join(rows[0].keys())
    body   = "\n".join(", ".join(map(str, r.values())) for r in rows[:5])
    csv_block = f"{header}\n{body}"

    unit_str = json.dumps(units) if units else "unknown"

    q_lines = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    return textwrap.dedent(f"""\
        **Group:** {group_id}
        **Units/Scales:** {unit_str}

        **Data (CSV sample):**
        ```
        {csv_block}
        ```

        **Questions:**
        {q_lines}
    """)

# ────────────────────────────────────────────────────────────
def build_prompts(data_path: Path, q_path: Path, out_dir: Path) -> None:
    data       = json.loads(data_path.read_text())
    q_yaml     = yaml.safe_load(q_path.read_text())

    out_dir.mkdir(parents=True, exist_ok=True)
    produced = 0

    for gid, rows in data["groups"].items():
        if not rows:
            log.info("%s – skipped (no data)", gid)
            continue

        raw_qs = q_yaml.get(gid)
        if not raw_qs:
            log.info("%s – skipped (no questions)", gid)
            continue

        q_texts, has_hard = parse_questions(raw_qs)
        model   = choose_model(has_hard)
        prompt  = f"{SYSTEM_TMPL}\n\n{build_user_block(gid, rows, data['meta'].get(gid), q_texts)}"

        out_path = out_dir / f"{gid}.jsonl"
        out_path.write_text(json.dumps({"group_id": gid,
                                        "model": model,
                                        "prompt": prompt}) + "\n")

        produced += 1
        log.info("%s – prompt ready → %s  [%s]", gid, out_path.name, model)

    log.info("Built %d prompt files", produced)

# ────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Build Qmirac prompts per group")
    ap.add_argument("-d", "--data",      default="extracted_groups.json")
    ap.add_argument("-q", "--questions", default="group_questions.yaml")
    ap.add_argument("-o", "--out-dir",   default="data/prompts")
    args = ap.parse_args()
    build_prompts(Path(args.data), Path(args.questions), Path(args.out_dir))

if __name__ == "__main__":
    main()
