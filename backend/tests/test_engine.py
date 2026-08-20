from app.grid_engine import GridEngine

def test_normal_grid_serves_load():
    e = GridEngine()
    r = e.power_flow()
    assert r["served_mw"] > 0
    assert r["critical_unserved_mw"] == 0

def test_failure_changes_state():
    e = GridEngine()
    e.inject_failure("T3")
    r = e.power_flow()
    assert e.failure == "T3"
    assert r["unserved_mw"] >= 0

def test_plans_are_evaluated():
    e = GridEngine(); e.inject_failure("T3")
    best, plans = e.best_plan()
    assert len(plans) == 4
    assert best["objective"] == min(p["objective"] for p in plans)
