#!/usr/bin/env python3
"""
run_prompts.py – Stage‑3 execute every prompt via Ollama with parallel processing
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import sqlite3
import threading
import time
from typing import Dict

import requests

# ────────────────────────────── config
PROMPTS = pathlib.Path("data/prompts")
OUT_DIR = pathlib.Path("data/completions"); OUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_DB = pathlib.Path("data/run_state.db")

OLLAMA_EP = "http://localhost:11434/api/generate"

TIMEOUTS = {
    "phi:latest": 600,
    "deepseek-llm:latest": 900,
}
DEFAULT_TIMEOUT = 300


# Let the machine decide—2× CPU count, capped at 8
MAX_WORKERS = min(8, (os.cpu_count() or 4) * 2)

# Map builder’s model names → Ollama tags
MODEL_MAP = {
    "microsoft/phi-3-mini-4k-instruct": "phi:latest",
    "deepseek-llm": "deepseek-llm:latest",
}

# ────────────────────────────── thread‑safe DB helper
db_lock = threading.Lock()
db = sqlite3.connect(STATE_DB, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS done (gid TEXT PRIMARY KEY)")

def done(gid: str) -> bool:
    with db_lock:
        return bool(db.execute("SELECT 1 FROM done WHERE gid=?", (gid,)).fetchone())

def mark_batch(gids) -> None:
    with db_lock:
        db.executemany("INSERT OR IGNORE INTO done VALUES (?)", [(g,) for g in gids])
        db.commit()

# ────────────────────────────── HTTP session (keeps TCP alive)
session = requests.Session()

def call_ollama(model: str, prompt: str) -> requests.Response:
    ollama_model = MODEL_MAP.get(model, model)
    t = TIMEOUTS.get(ollama_model, DEFAULT_TIMEOUT)

    return session.post(
        OLLAMA_EP,
        json={"model": ollama_model, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.4}},
        timeout=t,
    )

# ────────────────────────────── worker
def process_prompt(prompt_file):
    rec = json.loads(prompt_file.read_text())
    gid, model, prompt = rec["group_id"], rec["model"], rec["prompt"]

    if done(gid):
        return f"⏩ {gid:25s} → already processed"

    attempts = [model]               # 1st try with original
    if model == "microsoft/phi-3-mini-4k-instruct":
        attempts.append("deepseek-llm")   # fallback

    for attempt, mdl in enumerate(attempts, 1):
        resp = None
        try:
            resp = call_ollama(mdl, prompt)
            resp.raise_for_status()
            answer = resp.json()["response"].strip()
            OUT_DIR.joinpath(prompt_file.name).write_text(
                json.dumps({"group_id": gid, "model": mdl, "answer": answer}) + "\n",
                encoding="utf-8",
            )
            return gid  # success
        except requests.exceptions.RequestException as e:
            if attempt < len(attempts):
                continue  # try next model
            detail = ""
            if resp is not None:
                try:
                    detail = resp.json().get("error", "")
                except Exception:
                    detail = resp.text[:200]
            return (
                f"🛑 {gid:25s} → {mdl} failed – {e} – {detail}"
            )




# ────────────────────────────── main run
def main() -> None:
    prompt_files = sorted(PROMPTS.glob("*.jsonl"))
    total = len(prompt_files)
    print(f"Processing {total} prompt files with {MAX_WORKERS} workers...")

    start_time = time.time()
    completed_batch = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(process_prompt, pf): pf for pf in prompt_files}

        for i, fut in enumerate(concurrent.futures.as_completed(futures)):
            result = fut.result()
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed else 0

            if isinstance(result, str) and result.startswith("🛑"):
                # error line already formatted
                print(f"[{i+1}/{total}] {result} ({rate:.2f} prompts/s)")
            elif result.startswith("⏩"):
                print(f"[{i+1}/{total}] {result} ({rate:.2f} prompts/s)")
            else:
                # success → result is gid
                completed_batch.append(result)
                print(
                    f"[{i+1}/{total}] ✅ {result:25s} ({rate:.2f} prompts/s)"
                )

            # flush batch every 10 successes or at the end
            if len(completed_batch) >= 10 or i + 1 == total:
                mark_batch(completed_batch)
                completed_batch.clear()

    db.close()
    print(f"All processing complete! Total time: {time.time() - start_time:.2f} s")


if __name__ == "__main__":
    main()
