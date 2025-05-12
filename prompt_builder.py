#!/usr/bin/env python3
"""
prompt_builder.py – Stage‑2 prompt packager  (override‑aware)

Reads
  • extracted_groups.json
  • group_questions.yaml

Writes
  data/prompts/<group_id>.jsonl   (one record per prompt)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import textwrap
from pathlib import Path
from typing import List, Tuple

import yaml

# ── fast YAML loader (C‑extension if libyaml is present) ───────────────
try:
    from yaml import CLoader as YAML_LOADER          # ≈3‑5× faster
except ImportError:                                  # pure‑Python fallback
    from yaml import SafeLoader as YAML_LOADER

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")
log = logging.getLogger("builder")

# ────────────────────────────── helper: flatten questions
def parse_questions(raw: List) -> Tuple[List[str], int]:
    """
    Returns ([texts …], hard_count) in a **single pass** for speed.
    """
    texts, hard_flags = zip(
        *(
            (
                item["text"] if isinstance(item, dict) else str(item),
                1
                if isinstance(item, dict)
                and item.get("difficulty", "").lower() == "hard"
                else 0,
            )
            for item in raw
        )
    )
    return list(texts), sum(hard_flags)


# ────────────────────────────── model choice
MODEL_EASY = "microsoft/phi-3-mini-4k-instruct"  # → phi:latest via MODEL_MAP
MODEL_HARD = "deepseek-llm"                      # → deepseek-llm:latest

def choose_model(hard_cnt: int, total: int) -> str:
    return MODEL_HARD if hard_cnt / total > 0.5 else MODEL_EASY


# ────────────────────────────── prompt template strings
SYSTEM_TMPL = textwrap.dedent(
    """\
    You are Qmirac’s strategy‑analysis engine. Answer each question ONLY
    with clear, numbered sentences grounded in the data table provided.
    If an answer is not inferable, reply “insufficient data”.
"""
)

def build_user_block(group_id: str, rows, units, questions: List[str]) -> str:
    header = ", ".join(rows[0].keys())
    body = "\n".join(", ".join(map(str, r.values())) for r in rows[:5])
    csv_block = f"{header}\n{body}"

    unit_str = json.dumps(units) if units else "unknown"
    q_lines = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    return textwrap.dedent(
        f"""\
        **Group:** {group_id}
        **Units/Scales:** {unit_str}

        **Data (CSV sample):**
        ```
        {csv_block}
        ```

        **Questions:**
        {q_lines}
    """
    )


# ────────────────────────────── main builder
def build_prompts(data_path: Path, q_path: Path, out_dir: Path) -> None:
    data = json.loads(data_path.read_text())

    q_yaml = yaml.load(q_path.read_text(), Loader=YAML_LOADER)

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
        model = choose_model(hard_cnt, len(q_texts))

        prompt = (
            f"{SYSTEM_TMPL}\n\n"
            f"{build_user_block(gid, rows, data['meta'].get(gid), q_texts)}"
        )

        out_path = out_dir / f"{gid}.jsonl"
        # buffered write (64 KiB) so the disk flushes only once
        with out_path.open("w", encoding="utf-8", buffering=64 * 1024) as fp:
            json.dump({"group_id": gid, "model": model, "prompt": prompt}, fp)
            fp.write("\n")

        produced += 1
        log.info("%s – prompt ready → %s  [%s]", gid, out_path.name, model)

    log.info("Built %d prompt files", produced)


# ────────────────────────────── CLI
def main() -> None:
    ap = argparse.ArgumentParser(description="Build Qmirac prompts per group")
    ap.add_argument("-d", "--data", default="extracted_groups.json")
    ap.add_argument("-q", "--questions", default="group_questions.yaml")
    ap.add_argument("-o", "--out-dir", default="data/prompts")
    args = ap.parse_args()
    build_prompts(Path(args.data), Path(args.questions), Path(args.out_dir))


if __name__ == "__main__":
    main()
