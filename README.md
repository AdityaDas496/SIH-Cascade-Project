# Grid AI — SIH26 Prototype

A real software prototype for the proposed **AI-Based Emergency Power Recovery System**.

## What is real here?

This is not a static HTML mockup. The prototype contains:

- A Python grid-engine backend
- A graph-based distribution-network model
- Failure injection
- Load-service and critical-load calculations
- Recovery-plan generation
- What-if simulation of candidate actions
- Objective-based recovery-plan ranking
- FastAPI APIs
- React/Vite operator dashboard
- Automated backend tests

## Current electrical model

The first engine uses a transparent DC-style approximation so the team can understand and test every calculation. It is intentionally small and deterministic for a hackathon MVP.

## Next engineering upgrade

Replace the internal power-flow implementation with `pandapower` AC power flow and one of its benchmark/CIGRE/IEEE networks. The current API contract can stay the same, so the frontend does not need to be rewritten.

## Demo story

1. Open the dashboard.
2. Click **Inject T3 Failure**.
3. Observe the grid fault and critical-load risk.
4. Compare generated Plan A/B/C/D.
5. Select a plan and click **Simulate**.
6. Apply the plan inside the simulation.
7. Capture screenshots for the SIH PPT.

## Team split

- Grid/Power: network model + pandapower upgrade
- AI/Optimization: scenario generation + ranking/model
- Backend: FastAPI + persistence
- Frontend: React dashboard + visualization
- Validation: scenarios, baselines, metrics, experiments
