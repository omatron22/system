#!/usr/bin/env python3
"""
generate_reports.py – compile Qmirac completion outputs into three polished PDFs

Usage
-----
python generate_reports.py --completions-dir data/completions --risk-level HIGH

This script will:
1. Load every <group_id>.jsonl file in the completions folder.
2. Build a coherent answer bundle that is fed to DeepSeek‑LLM via Ollama to
   create a **Strategy Summary Recommendation** tailored to the chosen risk tier
   (HIGH / MEDIUM / LOW).
3. Produce two simple goal‑tracking charts:
       • Strategic Assessment – Goals
       • Execution – Goals
   based on keyword extraction from the DeepSeek summary.
4. Assemble all three components into a single PDF named
   reports/<risk>_strategy_package.pdf

Libraries required (install if missing):
    pip install requests reportlab matplotlib python-slugify

DeepSeek must already be pulled in Ollama and listening at http://localhost:11434.
"""

from __future__ import annotations

import argparse, json, pathlib, textwrap, io, datetime
from typing import Dict, List
import requests
from slugify import slugify

# ────────────────────────────────────────────────────────── config
OLLAMA_URL      = "http://localhost:11434/api/generate"
OLLAMA_MODEL    = "deepseek-llm:latest"
TIMEOUT_S       = 900  # 15 mins for large context

REPORT_DIR      = pathlib.Path("reports"); REPORT_DIR.mkdir(exist_ok=True)

# Colours for matplotlib charts (left default so user can theme later)

# ────────────────────────────────────────────────────────── helpers

def load_completions(path: pathlib.Path) -> Dict[str, str]:
    """Return {group_id: llm_answer}."""
    answers = {}
    for file in path.glob("*.jsonl"):
        try:
            rec = json.loads(file.read_text())
            answers[rec["group_id"]] = rec["answer"].strip()
        except Exception as e:
            print(f"⚠️ Skipped {file.name}: {e}")
    return answers

# ------------------------------------------------------------------ LLM call

def deepseek_summarise(prompt: str) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4},
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()

# ------------------------------------------------------------------ PDF helpers
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import matplotlib.pyplot as plt

styles = getSampleStyleSheet()
H1 = styles["Heading1"]; H2 = styles["Heading2"]; BODY = styles["BodyText"]


def create_goal_chart(title: str, goals: List[str], filename: pathlib.Path):
    """Very simple bullet chart with equally spaced goal labels."""
    fig, ax = plt.subplots(figsize=(6, 1 + len(goals) * 0.4))
    ax.set_title(title, pad=20)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(goals))
    ax.set_xticks([])
    ax.set_yticks([])

    for i, goal in enumerate(goals):
        ax.text(0, len(goals) - i - 0.5, f"• {goal}", fontsize=10, va="center")

    plt.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)

# ------------------------------------------------------------------ main build

def build_report(completions: Dict[str, str], risk: str):
    # 1) Build master prompt from completions
    joined = "\n\n".join(f"### {gid}\n{ans}" for gid, ans in completions.items())
    prompt = textwrap.dedent(f"""
        You are Qmirac's expert strategy assistant.
        Your task: produce a concise (≈300‑word) strategy summary recommendation
        for a company given the LLM‑generated findings below. Tailor the
        recommendation to a **{risk.upper()} RISK** appetite (High / Medium / Low).
        Then output a bullet list of 3‑5 *strategic goals* and 3‑5 *execution
        goals* that align with that risk tier.
        Format exactly:
        SUMMARY:\n<paragraphs>\n\nSTRATEGIC_GOALS:\n- goal1\n- goal2 ...\n\nEXECUTION_GOALS:\n- goal1 ...

        Findings:
        {joined}
    """)

    summary_block = deepseek_summarise(prompt)

    # 2) Parse goals out of the block
    strat_goals, exec_goals = [], []
    lines = [l.strip("- \t") for l in summary_block.splitlines()]
    current = None
    for line in lines:
        if line.upper().startswith("STRATEGIC_GOALS"):
            current = "strat"; continue
        if line.upper().startswith("EXECUTION_GOALS"):
            current = "exec"; continue
        if current == "strat" and line:
            strat_goals.append(line)
        elif current == "exec" and line:
            exec_goals.append(line)

    # 3) Generate charts
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    strat_img = REPORT_DIR / f"{slugify(risk)}_strategic_{ts}.png"
    exec_img  = REPORT_DIR / f"{slugify(risk)}_execution_{ts}.png"
    create_goal_chart("Strategic Goals", strat_goals, strat_img)
    create_goal_chart("Execution Goals", exec_goals, exec_img)

    # 4) Assemble PDF
    pdf_path = REPORT_DIR / f"{slugify(risk)}_strategy_package.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=LETTER)
    elems = [Paragraph(f"Strategy Summary – Risk: {risk.upper()}", H1),
             Spacer(1, 12),
             Paragraph(summary_block.split("STRATEGIC_GOALS")[0], BODY),
             Spacer(1, 24),
             Paragraph("Strategic Assessment Chart", H2), Image(strat_img, width=6*inch, height=3*inch),
             Spacer(1, 24),
             Paragraph("Execution Chart", H2), Image(exec_img,  width=6*inch, height=3*inch)]
    doc.build(elems)

    print(f"✅ Built {pdf_path.relative_to(REPORT_DIR.parent)}")

# ------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description="Generate strategy PDFs from completion files")
    ap.add_argument("--completions-dir", default="data/completions")
    ap.add_argument("--risk-level", choices=["HIGH", "MEDIUM", "LOW"], required=True)
    args = ap.parse_args()

    comps = load_completions(pathlib.Path(args.completions_dir))
    if not comps:
        raise SystemExit("No completion files found – aborting")

    build_report(comps, args.risk_level.upper())

if __name__ == "__main__":
    main()
