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


def nominatim(address: str) -> tuple[float, float] | None:
    """One upstream call per second process-wide (usage policy).
    shortcut: no per-client limit, so a flood of unique addresses queues behind the lock;
    add a rate limit at the proxy/app before public launch (Phase 6)."""
    global _last_call
    with _lock:
        time.sleep(max(0.0, _last_call + 1.0 - time.monotonic()))
        try:
            response = httpx.get(
                NOMINATIM_URL,
                params={"format": "json", "countrycodes": "il", "limit": 1, "q": address},
                headers={"User-Agent": "CaterKing/1.0 (catering order site)"},
                timeout=5,
            )
            response.raise_for_status()
            rows = response.json()
            return (float(rows[0]["lat"]), float(rows[0]["lon"])) if rows else None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            log.warning("geocode failed")  # never log the address
            raise GeocodeError from None
        finally:
            _last_call = time.monotonic()


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
