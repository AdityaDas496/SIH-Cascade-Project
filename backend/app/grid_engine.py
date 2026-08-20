from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import combinations
from typing import Dict, List, Tuple
import copy
import math
import numpy as np
import networkx as nx


@dataclass
class Bus:
    id: int
    name: str
    kind: str
    load_mw: float = 0.0
    critical: bool = False


@dataclass
class Line:
    id: str
    from_bus: int
    to_bus: int
    capacity_mw: float
    reactance: float = 0.12
    in_service: bool = True
    tie: bool = False


class GridEngine:
    """Small transparent DC-style distribution prototype.

    This is intentionally a software prototype: it models topology, load,
    line capacities and approximate DC power flow. The same interfaces can
    later be backed by pandapower for AC power flow.
    """

    def __init__(self):
        self._build()
        self.reset()

    def _build(self):
        self.buses: Dict[int, Bus] = {
            0: Bus(0, "Substation", "source"),
            1: Bus(1, "Feeder A", "feeder"),
            2: Bus(2, "Feeder B", "feeder"),
            3: Bus(3, "Transformer T3", "transformer"),
            4: Bus(4, "Transformer T4", "transformer"),
            5: Bus(5, "Critical Bus", "bus"),
            6: Bus(6, "Hospital", "critical", 12.0, True),
            7: Bus(7, "Water Plant", "critical", 9.0, True),
            8: Bus(8, "Residential", "load", 18.0, False),
            9: Bus(9, "Industry", "load", 16.0, False),
        }
        self.lines: Dict[str, Line] = {
            "L01": Line("L01", 0, 1, 55),
            "L02": Line("L02", 0, 2, 55),
            "L13": Line("L13", 1, 3, 32),
            "L24": Line("L24", 2, 4, 32),
            "T3": Line("T3", 3, 5, 25, reactance=0.10),
            "T4": Line("T4", 4, 5, 30, reactance=0.10),
            "L56": Line("L56", 5, 6, 18),
            "L57": Line("L57", 5, 7, 16),
            "L58": Line("L58", 5, 8, 28),
            "L59": Line("L59", 5, 9, 25),
            # Normally open tie used by recovery plan B.
            "TIE": Line("TIE", 2, 5, 22, reactance=0.16, in_service=False, tie=True),
        }
        self.source_mw = 60.0
        self.failure: str | None = None
        self.load_scale = 1.0
        self.shed_fraction = 0.0
        self.tie_closed = False

    def reset(self):
        self.failure = None
        self.load_scale = 1.0
        self.shed_fraction = 0.0
        self.tie_closed = False
        for line in self.lines.values():
            line.in_service = not line.tie

    def snapshot(self):
        return copy.deepcopy(self)

    def restore(self, other: "GridEngine"):
        self.__dict__ = copy.deepcopy(other.__dict__)

    def total_load(self) -> float:
        return sum(b.load_mw for b in self.buses.values()) * self.load_scale

    def critical_load(self) -> float:
        return sum(b.load_mw for b in self.buses.values() if b.critical) * self.load_scale

    def active_edges(self):
        return [l for l in self.lines.values() if l.in_service]

    def graph(self):
        g = nx.Graph()
        g.add_nodes_from(self.buses.keys())
        for l in self.active_edges():
            g.add_edge(l.from_bus, l.to_bus, line_id=l.id, capacity=l.capacity_mw)
        return g

    def inject_failure(self, line_id: str):
        if line_id not in self.lines:
            raise ValueError(f"Unknown line: {line_id}")
        self.failure = line_id
        self.lines[line_id].in_service = False
        if self.lines[line_id].tie:
            self.tie_closed = False

    def _served_loads(self) -> Dict[int, float]:
        """Compute load service through line/transformer capacities.

        A min-cost flow is used so critical loads are preferred over
        non-critical loads when the network cannot serve everything.
        """
        g = nx.DiGraph()
        source = "SOURCE"
        sink = "SINK"
        total_demand = self.total_load()
        g.add_node(source); g.add_node(sink)
        # Source capacity is the available generation. An explicit unserved
        # edge lets the optimization remain feasible when demand is higher.
        g.add_edge(source, 0, capacity=self.source_mw, weight=0)
        g.add_edge(source, sink, capacity=total_demand, weight=10000)
        for line in self.active_edges():
            # Model each physical branch as bidirectional capacity.
            g.add_edge(line.from_bus, line.to_bus, capacity=line.capacity_mw, weight=1)
            g.add_edge(line.to_bus, line.from_bus, capacity=line.capacity_mw, weight=1)
        for bus in self.buses.values():
            if bus.id == 0 or bus.load_mw <= 0:
                continue
            demand = bus.load_mw * self.load_scale
            if not bus.critical:
                demand *= max(0.0, 1.0 - self.shed_fraction)
            # Critical demand has a much lower cost, so the solver protects it.
            cost = 0 if bus.critical else 100
            g.add_edge(bus.id, sink, capacity=demand, weight=cost)
        try:
            flow = nx.max_flow_min_cost(g, source, sink)
            served = {}
            for bus in self.buses.values():
                if bus.id == 0 or bus.load_mw <= 0:
                    continue
                served[bus.id] = float(flow.get(bus.id, {}).get(sink, 0.0))
            return served
        except (nx.NetworkXUnfeasible, nx.NetworkXError):
            return {b.id: 0.0 for b in self.buses.values() if b.id != 0 and b.load_mw > 0}

    def power_flow(self):
        g = self.graph()
        if 0 not in g:
            raise RuntimeError("Source bus missing")
        served = self._served_loads()
        injections = {i: -served.get(i, 0.0) for i in self.buses}
        injections[0] = sum(served.values())

        active_nodes = sorted(g.nodes())
        non_slack = [n for n in active_nodes if n != 0]
        idx = {n: i for i, n in enumerate(non_slack)}
        B = np.zeros((len(non_slack), len(non_slack)))
        for line in self.active_edges():
            if line.from_bus not in g or line.to_bus not in g:
                continue
            b = 1.0 / max(line.reactance, 1e-4)
            a, c = line.from_bus, line.to_bus
            if a != 0:
                B[idx[a], idx[a]] += b
            if c != 0:
                B[idx[c], idx[c]] += b
            if a != 0 and c != 0:
                B[idx[a], idx[c]] -= b
                B[idx[c], idx[a]] -= b
        theta = np.zeros(len(active_nodes))
        if non_slack:
            try:
                p = np.array([injections[n] for n in non_slack])
                sol = np.linalg.solve(B + np.eye(len(B)) * 1e-9, p)
                for n, v in zip(non_slack, sol):
                    theta[n] = v
            except np.linalg.LinAlgError:
                pass

        line_results = {}
        overloaded = 0
        for line in self.active_edges():
            flow = (theta[line.from_bus] - theta[line.to_bus]) / max(line.reactance, 1e-4)
            loading = abs(flow) / max(line.capacity_mw, 1e-6) * 100
            if loading > 100:
                overloaded += 1
            line_results[line.id] = {"flow_mw": round(float(flow), 2), "loading_pct": round(float(loading), 1)}

        total = self.total_load()
        served_total = sum(served.values())
        critical_total = self.critical_load()
        critical_served = sum(served.get(b.id, 0) for b in self.buses.values() if b.critical)
        unserved = max(0.0, total - served_total)
        critical_unserved = max(0.0, critical_total - critical_served)
        return {
            "served_mw": round(served_total, 2),
            "total_load_mw": round(total, 2),
            "unserved_mw": round(unserved, 2),
            "critical_served_mw": round(critical_served, 2),
            "critical_load_mw": round(critical_total, 2),
            "critical_unserved_mw": round(critical_unserved, 2),
            "load_served_pct": round(served_total / total * 100, 1) if total else 100,
            "critical_served_pct": round(critical_served / critical_total * 100, 1) if critical_total else 100,
            "overloaded_lines": overloaded,
            "lines": line_results,
        }

    def apply_action(self, action: str):
        if action == "close_tie":
            self.lines["TIE"].in_service = True
            self.tie_closed = True
        elif action == "shed_noncritical_10":
            self.shed_fraction = 0.10
        elif action == "shed_noncritical_25":
            self.shed_fraction = 0.25
        elif action == "restore_all":
            self.shed_fraction = 0.0
        else:
            raise ValueError(f"Unknown action: {action}")

    def evaluate_plan(self, name: str, actions: List[str]):
        sim = self.snapshot()
        for action in actions:
            sim.apply_action(action)
        result = sim.power_flow()
        # Weighted objective: critical supply is by far the highest priority.
        score = (
            result["critical_unserved_mw"] * 1000
            + result["unserved_mw"] * 20
            + result["overloaded_lines"] * 50
            + len(actions) * 4
        )
        result.update({"plan": name, "actions": actions, "objective": round(score, 2)})
        return result

    def candidate_plans(self):
        return [
            ("Plan A — Do Nothing", []),
            ("Plan B — Load Transfer", ["close_tie"]),
            ("Plan C — Critical First", ["close_tie", "shed_noncritical_10"]),
            ("Plan D — Strong Load Shedding", ["shed_noncritical_25"]),
        ]

    def best_plan(self):
        results = [self.evaluate_plan(n, a) for n, a in self.candidate_plans()]
        return sorted(results, key=lambda x: x["objective"])[0], results

    def state(self):
        pf = self.power_flow()
        return {
            "failure": self.failure,
            "tie_closed": self.tie_closed,
            "buses": [asdict(b) for b in self.buses.values()],
            "lines": [asdict(l) for l in self.lines.values()],
            "metrics": pf,
        }
