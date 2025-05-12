#!/usr/bin/env python3
"""
prompt_builder.py – Stage‑2 prompt packager  (override‑aware)

Reads
  • extracted_groups.json
  • group_questions.yaml          (questions + optional difficulty tag)

Writes
  data/prompts/<group_id>.jsonl   (one record per prompt)

The model tags must match the names you pulled into Ollama, e.g.
  - phi3:mini
  - deepseek-llm:7b      ← change to :33b if you loaded the larger one
"""

from __future__ import annotations
import argparse, json, logging, textwrap
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("builder")

# ────────────────────────────── YAML helper
def parse_questions(raw: List) -> Tuple[List[str], int]:
    """
    Flatten a question list.
    Returns (list_of_text, number_of_hard_questions).
    """
    texts: List[str] = []
    hard_cnt = 0
    for item in raw:
        if isinstance(item, dict):                       # {text: “…”, difficulty: hard}
            texts.append(item["text"])
            if item.get("difficulty", "easy").lower() == "hard":
                hard_cnt += 1
        else:                                            # legacy plain string
            texts.append(str(item))
    return texts, hard_cnt

# ────────────────────────────── model picker
MODEL_EASY = "phi3:mini"
MODEL_HARD = "deepseek-llm:7b"     # ← swap to :33b if you have the VRAM

def choose_model(hard_cnt: int, total: int) -> str:
    """
    Use the heavyweight model only when a majority (>50 %) of questions
    in the group are tagged ‘hard’.  Mixed sets stay on phi‑3‑mini.
    """
    return MODEL_HARD if hard_cnt / total > 0.5 else MODEL_EASY

# ────────────────────────────── prompt template
SYSTEM_TMPL = textwrap.dedent("""\
    You are Qmirac’s strategy‑analysis engine. Answer each question ONLY
    with clear, numbered sentences grounded in the data table provided.
    If an answer is not inferable, reply “insufficient data”.
""")

def build_user_block(group_id: str,
                     rows: List[Dict[str, str]],
                     units,
                     questions: List[str]) -> str:
    # show header + first 5 rows to keep prompts compact
    header = ", ".join(rows[0].keys())
    body   = "\n".join(", ".join(map(str, r.values())) for r in rows[:5])
    csv_block = f"{header}\n{body}"

    unit_str = json.dumps(units) if units else "unknown"
    q_lines  = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    return textwrap.dedent(f"""\
        **Group:** {group_id}
        **Units/Scales:** {unit_str}

        **Data (CSV sample):**
        ```
        {csv_block}
        ```

        **Questions:**
        {q_lines}
    """)

# ────────────────────────────── main builder
def build_prompts(data_path: Path, q_path: Path, out_dir: Path) -> None:
    data   = json.loads(data_path.read_text())
    q_yaml = yaml.safe_load(q_path.read_text())

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

        q_texts, hard_cnt = parse_questions(raw_qs)
        model   = choose_model(hard_cnt, len(q_texts))
        prompt  = f"{SYSTEM_TMPL}\n\n{build_user_block(gid, rows, data['meta'].get(gid), q_texts)}"

        out_path = out_dir / f"{gid}.jsonl"
        out_path.write_text(json.dumps({
            "group_id": gid,
            "model":    model,
            "prompt":   prompt
        }) + "\n")

        produced += 1
        log.info("%s – prompt ready → %s  [%s]", gid, out_path.name, model)

    log.info("Built %d prompt files", produced)

# ────────────────────────────── CLI
def main() -> None:
    ap = argparse.ArgumentParser(description="Build Qmirac prompts per group")
    ap.add_argument("-d", "--data",      default="extracted_groups.json")
    ap.add_argument("-q", "--questions", default="group_questions.yaml")
    ap.add_argument("-o", "--out-dir",   default="data/prompts")
    args = ap.parse_args()
    build_prompts(Path(args.data), Path(args.questions), Path(args.out_dir))

if __name__ == "__main__":
    main()
