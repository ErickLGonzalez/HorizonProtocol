"""Adapter: neutral trace -> causal-store write().  [SOUND core]

Maps each trace op onto `CausalStore.write()`, assigning a geometric
clock from the op's declared origin region (via a caller-supplied
region -> {pos_nm, u_ns} map, e.g. the H8-LIVE Azure registry for a real
run) plus a per-region logical counter as the vector-clock fallback.
`commit_seq` is the backend's own append order - the driver already
guarantees a dependent op is never issued before its declared
predecessor's result exists (see driver.py), so `supersedes` always
resolves to a real, already-committed event_id.
"""
import itertools
import time

from causalstore.ordering import HybridOrdering
from causalstore.store import CausalStore

from .base import Adapter, AdapterUnavailable, OpResult


class CausalStoreAdapter(Adapter):
    name = "causal-store"

    def __init__(self, region_clocks, ordering=None):
        """`region_clocks`: {region_name: {"pos_nm": (x,y,z), "u_ns": int}}."""
        self.region_clocks = region_clocks
        self.ordering = ordering or HybridOrdering()
        self.store = None
        self._seq = None
        self._op_to_event = {}
        self._vc_counter = {}

    def setup(self, regions):
        missing = [r for r in regions if r not in self.region_clocks]
        if missing:
            raise AdapterUnavailable(
                f"causal-store adapter missing region_clocks entries for: {missing}")
        self.store = CausalStore(self.ordering)
        self._seq = itertools.count()
        self._op_to_event = {}
        self._vc_counter = {r: 0 for r in regions}

    def apply_op(self, op):
        region = op["origin_region"]
        rc = self.region_clocks[region]
        self._vc_counter[region] += 1
        clock = {"time_ns": op["t_logical_ns"], "pos_nm": list(rc["pos_nm"]),
                "u_ns": rc["u_ns"], "vc": {region: self._vc_counter[region]}}
        supersedes = [self._op_to_event[d] for d in op.get("depends_on", [])
                     if d in self._op_to_event]

        t0 = time.perf_counter()
        result = self.store.write(op["key"], op["value"], region, clock,
                                  supersedes=supersedes)
        latency_ns = int((time.perf_counter() - t0) * 1e9)

        accepted = result.verdict == "ADMITTED"
        commit_seq = next(self._seq) if accepted else None
        if accepted:
            self._op_to_event[op["op_id"]] = result.event_id
        rejected_reason = None if accepted else (result.witness or {}).get("reason")
        return OpResult(op["op_id"], accepted, commit_seq, latency_ns, rejected_reason)

    def diagnostics(self):
        if self.store is None:
            return {}
        return {"coordination_free_rate": self.store.coordination_free_rate(),
                **self.store.stats}
