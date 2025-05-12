#!/usr/bin/env python3
"""
run_prompts.py – Stage‑3 execute every prompt via Ollama with parallel processing

* Processes multiple prompts in parallel to speed up execution
* Keeps track of completed tasks in SQLite
"""

import json, pathlib, requests, sqlite3, time
import concurrent.futures
import threading

PROMPTS = pathlib.Path("data/prompts")
OUT_DIR = pathlib.Path("data/completions"); OUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_DB = pathlib.Path("data/run_state.db")
OLLAMA_EP = "http://localhost:11434/api/generate"
TIMEOUT_S = 900  # generous – big models can be slow
MAX_WORKERS = 3  # Adjust based on your M4 Mac's performance

# Map the model names used in prompt_builder.py to Ollama model names
MODEL_MAP = {
    "microsoft/phi-3-mini-4k-instruct": "phi:latest",
    "deepseek-llm": "deepseek-llm:latest"
}

# Thread-safe SQLite connection
db_lock = threading.Lock()
db = sqlite3.connect(STATE_DB, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS done (gid TEXT PRIMARY KEY)")

def done(gid: str) -> bool:
    with db_lock:
        return bool(db.execute("SELECT 1 FROM done WHERE gid=?", (gid,)).fetchone())

def mark(gid: str) -> None:
    with db_lock:
        db.execute("INSERT OR IGNORE INTO done VALUES (?)", (gid,))
        db.commit()

def call_ollama(model: str, prompt: str) -> requests.Response:
    ollama_model = MODEL_MAP.get(model, model)  # Map to Ollama model name if needed
    
    return requests.post(
        OLLAMA_EP,
        json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4}
        },
        timeout=TIMEOUT_S
    )

def process_prompt(prompt_file):
    """Process a single prompt file."""
    rec = json.loads(prompt_file.read_text())
    gid, model, prompt = rec["group_id"], rec["model"], rec["prompt"]

    if done(gid):
        return f"⏩ {gid:25s} → already processed"

    try:
        resp = call_ollama(model, prompt)
        resp.raise_for_status()

    except requests.exceptions.HTTPError as e:
        # show *exactly* what Ollama said and move on
        error_txt = ""
        try:
            error_txt = resp.json().get("error", "")
        except Exception:
            error_txt = resp.text[:200]  # raw HTML or plain text
        return f"🛑 {gid:25s} → {model} failed – {e} – {error_txt}"

    # —— success ———————————————————————————————
    answer = resp.json()["response"].strip()
    OUT_DIR.joinpath(prompt_file.name).write_text(
        json.dumps({"group_id": gid, "model": model, "answer": answer}) + "\n",
        encoding="utf-8"
    )
    mark(gid)
    return f"✅ {gid:25s} → {prompt_file.name}"

# Main execution
prompt_files = sorted(PROMPTS.glob("*.jsonl"))
total = len(prompt_files)

print(f"Processing {total} prompt files with {MAX_WORKERS} parallel workers...")
start_time = time.time()

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Submit all tasks to the executor
    futures = [executor.submit(process_prompt, pf) for pf in prompt_files]
    
    # Process results as they complete
    for i, future in enumerate(concurrent.futures.as_completed(futures)):
        result = future.result()
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        
        # Show progress with completion rate
        print(f"[{i+1}/{total}] {result} ({rate:.2f} prompts/sec)")

db.close()
print(f"All processing complete! Total time: {time.time() - start_time:.2f} seconds")