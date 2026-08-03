"""Real geography -> exact nanometer lattice.  [SOUND output, HEURISTIC geodesy]

Converts WGS84 (latitude, longitude, altitude) coordinates for real cloud
regions into a local East-North-Up (ENU) frame expressed in exact integer
NANOMETERS, so the H1 light-cone kernel (`horizon.geometry`) applies
unchanged.

Design note on exactness:
  The ellipsoid -> ECEF -> ENU transform uses trigonometry, which is
  irreducibly floating point. The float math therefore runs ONCE, at
  frame-construction time, and every resulting coordinate is immediately
  QUANTIZED to an integer nanometer lattice. From that point on, every
  light-cone decision is exact integer arithmetic on the quantized
  positions. The quantization is the boundary between the (HEURISTIC)
  geodesy and the (SOUND) causal gate, and it is recorded
  (`quantization_nm`): `quantization_nm = 1` means positions are exact to
  1 nm on the lattice (not that the underlying geodesy is accurate to 1
  nm - it is not; see docs/h6-spec.md).

Straight-line ECEF chord distance is used, never great-circle/geodesic
path length: light travels through the earth, not around it.
"""
import math

# WGS84
_A = 6378137.0            # semi-major axis (m)
_F = 1.0 / 298.257223563  # flattening
_E2 = _F * (2 - _F)       # first eccentricity squared

M_TO_NM = 1_000_000_000   # 1 metre = 1e9 nanometres


def _llh_to_ecef(lat_deg, lon_deg, alt_m):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    N = _A / math.sqrt(1 - _E2 * sin_lat * sin_lat)
    x = (N + alt_m) * math.cos(lat) * math.cos(lon)
    y = (N + alt_m) * math.cos(lat) * math.sin(lon)
    z = (N * (1 - _E2) + alt_m) * sin_lat
    return x, y, z


def _ecef_to_enu(x, y, z, lat0_deg, lon0_deg, x0, y0, z0):
    lat0 = math.radians(lat0_deg)
    lon0 = math.radians(lon0_deg)
    dx, dy, dz = x - x0, y - y0, z - z0
    east = -math.sin(lon0) * dx + math.cos(lon0) * dy
    up_n = math.cos(lon0) * dx + math.sin(lon0) * dy
    north = -math.sin(lat0) * up_n + math.cos(lat0) * dz
    up = math.cos(lat0) * up_n + math.sin(lat0) * dz
    return east, north, up


class GeoFrame:
    """A local ENU frame anchored at a reference LLH, emitting integer-nm
    positions on a fixed lattice."""

    def __init__(self, origin_name, origin_llh, quantization_nm=1):
        self.origin_name = origin_name
        self.origin_llh = tuple(origin_llh)
        self.quantization_nm = int(quantization_nm)
        lat0, lon0, alt0 = origin_llh
        self._x0, self._y0, self._z0 = _llh_to_ecef(lat0, lon0, alt0)
        self._lat0, self._lon0 = lat0, lon0

    def to_nm(self, llh) -> tuple:
        """(lat, lon, alt_m) -> (x_nm, y_nm, z_nm) integers on the lattice."""
        x, y, z = _llh_to_ecef(*llh)
        e, n, u = _ecef_to_enu(x, y, z, self._lat0, self._lon0,
                               self._x0, self._y0, self._z0)
        q = self.quantization_nm

        def snap(v_m):
            nm = v_m * M_TO_NM
            return int(round(nm / q)) * q

        return (snap(e), snap(n), snap(u))

    def metadata(self) -> dict:
        return {
            "origin_name": self.origin_name,
            "origin_llh": list(self.origin_llh),
            "quantization_nm": self.quantization_nm,
            "geodesy": "WGS84 ellipsoid -> ECEF -> ENU, quantized to nm lattice",
        }
