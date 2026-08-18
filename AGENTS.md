# Berry Intelligence OS

Local-first, evidence-based competitive intelligence for berry crops.

Standard lint/test/run commands are in `README.md`: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`, and `uvicorn app.main:app --reload`.

## Cursor Cloud specific instructions

Canonical application branch is `v2/intelligence-os`. This Cloud Agent environment config lives in `.cursor/environment.json`.

### Python venv

The default Cloud Agent image has Python 3.12 but **not** `ensurepip`. `python3 -m venv .venv` fails on a from-scratch build until `python3.12-venv` is installed. The environment `install` script does that with apt, then creates `.venv` and installs `requirements-dev.txt` plus `pagefind` / `pagefind_bin`. Do not drop the apt step. Recreating `.venv` is skipped when it already exists.

Use `.venv/bin/python` / `.venv/bin/pytest` rather than system Python.

### Dev server

`terminals.web` starts uvicorn on port 8000. Host port 8000 is often already taken by a leftover process; set `BIOS_APP_PORT` (for example `18000`) instead of killing processes by name. `docker` usually needs `sudo` in this VM.

Ordinary local/cloud development does not need review-login secrets. `PERPLEXITY_API_KEY` and other AI keys are optional and must never be printed.
