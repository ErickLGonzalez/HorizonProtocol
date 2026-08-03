#!/usr/bin/env python3
"""One-time generator for the committed H5 replay fixtures.

Run manually whenever `horizon/fixtures.py`'s frozen geometry or seed
changes; the output is committed to `data/` and thereafter only ever
REPLAYED (loaded and re-verified), never regenerated at test or CI time -
see docs/h5-spec.md, section on fixture provenance.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.fixtures import (build_marginal_capture,  # noqa: E402
                              build_synthetic_consistent_capture)


def main():
    honest_cert, _ = build_synthetic_consistent_capture()
    marginal_cert, _ = build_marginal_capture()

    out_dir = os.path.join(ROOT, "data")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "h5_fixture_capture.json"), "w") as f:
        json.dump(honest_cert, f, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "h5_fixture_marginal.json"), "w") as f:
        json.dump(marginal_cert, f, indent=2, sort_keys=True)

    print("wrote data/h5_fixture_capture.json and data/h5_fixture_marginal.json")


if __name__ == "__main__":
    main()
