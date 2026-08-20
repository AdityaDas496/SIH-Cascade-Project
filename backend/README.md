# Grid AI backend

This is the real prototype engine, not a static mockup. It models a small distribution network, injects failures, computes a transparent DC-style power-flow approximation, evaluates recovery actions, and ranks recovery plans.

## Run

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the API.

## Engineering upgrade path

The prototype engine is deliberately transparent and dependency-light. The next electrical-model upgrade should use pandapower for AC power flow and benchmark networks; pandapower provides standard and benchmark networks and AC/DC power-flow functionality. Keep the same API contract so the UI does not change.
