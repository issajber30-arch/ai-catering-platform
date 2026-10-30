import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy.orm import Session

from app.models.settings import BusinessSettings
from app.repositories import settings as repo

log = logging.getLogger(__name__)
Geocoder = Callable[[str], tuple[float, float] | None]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"  # fixed host: no SSRF
_lock = threading.Lock()
_last_call = 0.0
EARTH_KM = 6371.0
CENT = Decimal("0.01")


class GeocodeError(Exception):
    """Lookup failed (network/upstream), as opposed to "no such address"; never cached."""


PHOTON_URL = "https://photon.komoot.io/api/"  # fixed host: no SSRF
ISRAEL_BBOX = "34.2,29.4,35.95,33.35"  # min lon, min lat, max lon, max lat
USER_AGENT = "CaterKing/1.0 (catering order site)"


def _nominatim(address: str) -> tuple[float, float] | None:
    response = httpx.get(
        NOMINATIM_URL,
        params={"format": "json", "countrycodes": "il", "limit": 1, "q": address},
        headers={"User-Agent": USER_AGENT},
        timeout=5,
    )
    response.raise_for_status()
    rows = response.json()
    return (float(rows[0]["lat"]), float(rows[0]["lon"])) if rows else None


def _photon(address: str) -> tuple[float, float] | None:
    response = httpx.get(
        PHOTON_URL,
        params={"q": address, "limit": 1, "bbox": ISRAEL_BBOX},
        headers={"User-Agent": USER_AGENT},
        timeout=5,
    )
    response.raise_for_status()
    features = response.json()["features"]
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    return float(lat), float(lon)


# Nominatim first; Photon (same OpenStreetMap data) when Nominatim refuses cloud hosts.
PROVIDERS = (("nominatim", _nominatim), ("photon", _photon))


def nominatim(address: str) -> tuple[float, float] | None:
    """Look an address up, one upstream call per second process-wide (usage policies).
    A provider error falls through to the next; "no such address" is a real answer.
    shortcut: no per-client limit, so a flood of unique addresses queues behind the lock;
    add a rate limit at the proxy/app before public launch (Phase 6)."""
    global _last_call
    if not _lock.acquire(timeout=3):  # fail fast instead of piling up worker threads
        raise GeocodeError
    try:
        for name, provider in PROVIDERS:
            time.sleep(max(0.0, _last_call + 1.0 - time.monotonic()))
            try:
                return provider(address)
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                # never log the address
                log.warning("geocode failed provider=%s error=%s status=%s",
                            name, type(e).__name__, status)  # fmt: skip
            finally:
                _last_call = time.monotonic()
        raise GeocodeError
    finally:
        _lock.release()


def get_geocoder() -> Geocoder:
    return nominatim


def locate(db: Session, geocode: Geocoder, address: str) -> tuple[float, float] | None:
    key = " ".join(address.lower().split())
    if not key:
        return None
    if row := repo.cached(db, key):
        return (row.lat, row.lon) if row.found else None
    try:
        point = geocode(address)
    except GeocodeError:
        return None  # treated as not found this time; retried on the next lookup
    repo.cache(db, key, point)
    return point


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + (
        math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    km = 2 * EARTH_KM * math.asin(math.sqrt(a))
    return Decimal(repr(km)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def fee_for(km: Decimal, base: Decimal, per_km: Decimal) -> Decimal:
    return (base + per_km * km).quantize(CENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class Quote:
    found: bool
    km: Decimal | None = None
    lat: float | None = None
    lon: float | None = None
    fee: Decimal | None = None
    too_far: bool = False


def quote(db: Session, geocode: Geocoder, address: str, s: BusinessSettings) -> Quote:
    point = locate(db, geocode, address)
    if point is None:
        return Quote(found=False)
    km = haversine_km(s.kitchen_lat, s.kitchen_lon, *point)
    if km > s.delivery_max_km:
        return Quote(True, km, *point, too_far=True)
    return Quote(True, km, *point, fee_for(km, s.delivery_base_fee, s.delivery_per_km))
