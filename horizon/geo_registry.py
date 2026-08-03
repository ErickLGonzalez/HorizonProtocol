"""Real-geography node registry: WGS84 lat/lon/alt -> exact nm lattice via
`GeoFrame`, wrapped as HMAC-authenticated `Station`s. [SOUND wrapper]

This is the bridge that lets H6 reuse H1's authenticated-receipt
machinery (`horizon.stations`) and H5's dual-floor budgeted gate
(`horizon.measure`) UNCHANGED over real cloud-region geography, instead of
inventing a second, parallel (and unauthenticated) gate. Every node
becomes an ordinary `Station` with a quantized nm position; every
declared per-node clock uncertainty is TRUSTED CALLER INPUT for
`verify_measured_certificate`'s `node_params` argument, exactly like
`horizon.fixtures.trusted_node_params` - never read from a certificate.
"""
import json
import os

from .geo_frame import GeoFrame
from .stations import demo_registry

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "h6_nodes.json")


def load_geo_registry(path: str = DATA_PATH):
    """Returns (frame, registry, node_llh, node_u_ns, spec).

    `registry` is a `{node_id: Station}` map, positions quantized onto the
    frame's nm lattice. `node_u_ns` is the TRUSTED per-node clock
    uncertainty - pass through `trusted_node_params` to
    `horizon.measure.verify_measured_certificate`.
    """
    with open(path) as f:
        spec = json.load(f)
    fo = spec["frame_origin"]
    frame = GeoFrame(fo["name"], fo["llh"], spec.get("quantization_nm", 1))
    specs, node_llh, node_u_ns = [], {}, {}
    for n in spec["nodes"]:
        pos_nm = frame.to_nm(tuple(n["llh"]))
        specs.append((n["id"], pos_nm, 0))
        node_llh[n["id"]] = n["llh"]
        node_u_ns[n["id"]] = n["u_ns"]
    registry = demo_registry(specs)
    return frame, registry, node_llh, node_u_ns, spec


def trusted_node_params(node_u_ns: dict) -> dict:
    """TRUSTED per-station uncertainty for `verify_measured_certificate` -
    never read from a certificate. See `horizon.fixtures.trusted_node_params`
    for the identical pattern and its erratum."""
    return {nid: {"u_ns": u_ns} for nid, u_ns in node_u_ns.items()}
