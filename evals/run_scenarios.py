"""Run every scenario in scenarios.json against the real CLI and save the transcript.

Usage (from the repo root): uv run python evals/run_scenarios.py
Scenarios that already have a result file are skipped, so a re-run resumes.
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
PAUSE_SECONDS = 20  # stay under the per-minute token limit

scenarios = json.loads((EVALS_DIR / "scenarios.json").read_text(encoding="utf-8"))
RESULTS_DIR.mkdir(exist_ok=True)
pending = [s for s in scenarios if not (RESULTS_DIR / f"{s['id']}.txt").exists()]

for index, scenario in enumerate(pending):
    if index:
        time.sleep(PAUSE_SECONDS)
    started = datetime.now(ZoneInfo("America/Campo_Grande"))
    # Same as typing the turns in the terminal, then /sair.
    run = subprocess.run(["uv", "run", "emporio-da-musica-agent"],
                         input="\n".join(scenario["turns"] + ["/sair"]) + "\n",
                         capture_output=True, text=True, timeout=300, cwd=REPO_ROOT)
    output = run.stdout + run.stderr
    path = RESULTS_DIR / f"{scenario['id']}.txt"
    turns = "\n".join(f"- {t}" for t in scenario["turns"])
    path.write_text(f"Run at: {started:%Y-%m-%d %H:%M:%S %Z}\nTurns:\n{turns}\n\n--- output ---\n{output}",
                    encoding="utf-8")
    if "Error code: 429" in output:
        path.unlink()  # rate limited: discard so a re-run retries it
        print(f"Rate limit (429) at scenario {scenario['id']}; re-run later to resume.")
        sys.exit(1)
    print(f"{scenario['id']} done")

print("All scenarios have results.")
