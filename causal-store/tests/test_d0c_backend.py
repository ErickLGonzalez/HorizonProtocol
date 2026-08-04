"""D0-C: persistence is behind an interface; swappable without engine change. [SOUND]"""
import unittest
from causalstore.store import CausalStore, StoreBackend, InMemoryBackend
from causalstore.ordering import GeometricOrdering
from causalstore.geometry import C_NM_PER_NS


class ListBackend(StoreBackend):
    """A second, independent backend impl to prove the contract is real."""
    def __init__(self):
        self.data = []
    def append(self, event): self.data.append(event)
    def events_for_key(self, key):
        return [e for e in self.data if e["key"] == key]
    def all_events(self): return list(self.data)


def clk(t, x=0, u=1000): return {"time_ns": t, "pos_nm": [x, 0, 0], "u_ns": u}


class TestBackend(unittest.TestCase):
    def test_engine_works_with_alternate_backend(self):
        s = CausalStore(GeometricOrdering(), backend=ListBackend())
        r = s.write("k", "v", "n", clk(0))
        self.assertEqual(r.verdict, "ADMITTED")
        self.assertEqual(s.read("k")["value"], "v")

    def test_engine_never_imports_a_backend(self):
        # the store must depend only on the StoreBackend contract, not a concrete DB
        import causalstore.store as st, inspect
        src = inspect.getsource(st)
        for banned in ("sqlite", "postgres", "redis", "import os", "mnemesis"):
            self.assertNotIn(banned, src.lower())


if __name__ == "__main__":
    unittest.main()
