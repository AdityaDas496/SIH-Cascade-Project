from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .grid_engine import GridEngine
from .ml_model import ImpactPredictor

app = FastAPI(title="Grid AI API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
engine = GridEngine()
predictor = ImpactPredictor()

class FailureRequest(BaseModel):
    line_id: str = "T3"

class PlanRequest(BaseModel):
    plan: str

@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "grid-ai-dc-prototype"}

@app.get("/api/grid")
def grid():
    return engine.state()

@app.post("/api/reset")
def reset():
    engine.reset()
    return engine.state()

@app.post("/api/fail")
def fail(req: FailureRequest):
    try:
        engine.inject_failure(req.line_id)
        return engine.state()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/plans")
def plans():
    if not engine.failure:
        return {"plans": [], "message": "Inject a failure first."}
    best, results = engine.best_plan()
    return {"best": best, "plans": results}

@app.post("/api/simulate")
def simulate(req: PlanRequest):
    if not engine.failure:
        raise HTTPException(status_code=400, detail="Inject a failure first.")
    mapping = {n: a for n, a in engine.candidate_plans()}
    if req.plan not in mapping:
        raise HTTPException(status_code=400, detail="Unknown plan")
    return engine.evaluate_plan(req.plan, mapping[req.plan])

@app.post("/api/apply")
def apply_plan(req: PlanRequest):
    if not engine.failure:
        raise HTTPException(status_code=400, detail="Inject a failure first.")
    mapping = {n: a for n, a in engine.candidate_plans()}
    if req.plan not in mapping:
        raise HTTPException(status_code=400, detail="Unknown plan")
    for action in mapping[req.plan]:
        engine.apply_action(action)
    return engine.state()

@app.get("/api/predict")
def predict(line_id: str = "T3", load_scale: float = 1.0):
    if line_id not in engine.lines:
        raise HTTPException(status_code=400, detail="Unknown line")
    return predictor.predict(line_id, load_scale)
