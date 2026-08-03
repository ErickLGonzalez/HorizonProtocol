"""MNX-A: vector-clock partial order. [SOUND]"""
import unittest
from mnemesis.vclock import happens_before, concurrent, merge


class TestVClock(unittest.TestCase):
    def test_happens_before(self):
        a = {"n1": 1, "n2": 0}
        b = {"n1": 2, "n2": 1}
        self.assertTrue(happens_before(a, b))
        self.assertFalse(happens_before(b, a))

    def test_concurrent(self):
        a = {"n1": 1, "n2": 0}
        b = {"n1": 0, "n2": 1}
        self.assertTrue(concurrent(a, b))
        self.assertTrue(concurrent(b, a))

    def test_merge_is_join(self):
        a = {"n1": 3, "n2": 1}
        b = {"n1": 1, "n2": 5}
        self.assertEqual(merge(a, b), {"n1": 3, "n2": 5})

    def test_identity_not_before_itself(self):
        a = {"n1": 1}
        self.assertFalse(happens_before(a, a))


if __name__ == "__main__":
    unittest.main()
