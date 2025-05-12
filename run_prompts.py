#!/usr/bin/env python3
"""
run_prompts.py – Stage‑3   execute every prompt via Ollama

* Sends every prompt with the model it was built for.
* No model fallback – failures are logged, then the run continues.
* Keeps an SQLite 'done' list so repeats are skipped on re‑runs.
"""

import json, pathlib, requests, sqlite3, time

PROMPTS    = pathlib.Path("data/prompts")
OUT_DIR    = pathlib.Path("data/completions");  OUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_DB   = pathlib.Path("data/run_state.db")
OLLAMA_EP  = "http://localhost:11434/api/generate"
TIMEOUT_S  = 900          # generous – big models can be slow
PAUSE_S    = 0.5          # short breather between calls

db = sqlite3.connect(STATE_DB)
db.execute("CREATE TABLE IF NOT EXISTS done (gid TEXT PRIMARY KEY)")

def done(gid: str) -> bool:
    return bool(db.execute("SELECT 1 FROM done WHERE gid=?", (gid,)).fetchone())

def mark(gid: str) -> None:
    db.execute("INSERT OR IGNORE INTO done VALUES (?)", (gid,))
    db.commit()

def call_ollama(model: str, prompt: str) -> requests.Response:
    return requests.post(
        OLLAMA_EP,
        json={
            "model":  model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4}
        },
        timeout=TIMEOUT_S
    )

# ───────────────────────────────────────────────────────── main loop
for pf in sorted(PROMPTS.glob("*.jsonl")):
    rec = json.loads(pf.read_text())
    gid, model, prompt = rec["group_id"], rec["model"], rec["prompt"]

    if done(gid):
        continue

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
        print(f"🛑  {gid}: {model} failed – {e} – {error_txt}")
        # do NOT mark as done → you can fix & rerun later
        time.sleep(PAUSE_S)
        continue

    # —— success ———————————————————————————————
    answer = resp.json()["response"].strip()
    OUT_DIR.joinpath(pf.name).write_text(
        json.dumps({"group_id": gid, "model": model, "answer": answer}) + "\n",
        encoding="utf-8"
    )
    mark(gid)
    print(f"✅ {gid:25s} → {pf.name}")
    time.sleep(PAUSE_S)

db.close()
