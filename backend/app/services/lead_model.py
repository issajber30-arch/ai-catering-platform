"""Lead scoring: ordinary least squares on synthetic history, output clipped to 0..1.

The owner chose a linear probability model (linear regression clipped to 0-100%) over logistic
regression knowingly; the model card reports how often the clip is hit. Training data is
synthetic: `_true_logit` below is a placeholder story, not a business fact (see OPEN_DECISIONS).
Pure Python on purpose: ~17 columns x 2000 rows needs no numpy.
"""

import datetime as dt
import math
import random
from dataclasses import dataclass
from functools import cache

from app.models.leads import LEAD_SOURCES
from app.models.orders import EVENT_TYPES

SEED = 20261116
N_HISTORY = 2000
MAX_DAYS = 365
SOON_DAYS, FAR_DAYS = 14, 150

# Synthetic "truth" (log-odds). Plausible placeholders; edit here and the model refits.
BASE = -2.4
EVENT_EFFECT = {"birthday": 0.0, "family_celebration": 0.4, "bar_bat_mitzvah": 1.3,
                "shabbat": -0.7, "other": -1.0}  # fmt: skip
SOURCE_EFFECT = {"instagram": 0.0, "google": 0.4, "referral": 2.1, "whatsapp": 0.8,
                 "phone": 1.3, "other": -0.4}  # fmt: skip
RETURNING, ASSISTANT, QUOTE = 2.5, 1.3, 2.0
SOURCE_WEIGHTS = (30, 25, 12, 15, 8, 10)
EVENT_WEIGHTS = (35, 20, 15, 15, 15)

# Field -> encoded columns. One-hot drops the first level; days -> "too soon" / "too far" flags.
FIELDS = ("event_type", "guests", "days_until_event", "source", "returning_customer",
          "used_assistant", "requested_quote", "budget_per_guest")  # fmt: skip


def _true_logit(r: dict) -> float:
    days = r["days_until_event"]
    z = BASE + EVENT_EFFECT[r["event_type"]] + SOURCE_EFFECT[r["source"]]
    z += 0.006 * (min(r["guests"], 300) - 60)
    z -= 1.6 * (days < SOON_DAYS) + 1.0 * (days > FAR_DAYS)  # too soon or too far lowers intent
    z += RETURNING * r["returning_customer"] + ASSISTANT * r["used_assistant"]
    z += QUOTE * r["requested_quote"]
    budget = r["budget_per_guest"]
    z += -0.3 if budget is None else 0.015 * (budget - 90)
    return z


def sample_features(rng: random.Random) -> dict:
    """One synthetic lead's model inputs (also used for demo leads)."""
    return {
        "event_type": rng.choices(EVENT_TYPES, EVENT_WEIGHTS)[0],
        "guests": max(5, min(400, int(rng.lognormvariate(math.log(50), 0.6)))),
        "days_until_event": rng.randint(3, 240),
        "source": rng.choices(LEAD_SOURCES, SOURCE_WEIGHTS)[0],
        "returning_customer": rng.random() < 0.2,
        "used_assistant": rng.random() < 0.35,
        "requested_quote": rng.random() < 0.4,
        "budget_per_guest": None if rng.random() < 0.3 else round(rng.uniform(40, 180), 2),
    }


def synthetic_history(n: int = N_HISTORY, seed: int = SEED) -> list[tuple[dict, int]]:
    rng = random.Random(seed)  # noqa: S311  synthetic data, not security
    rows = []
    for _ in range(n):
        r = sample_features(rng)
        p = 1 / (1 + math.exp(-_true_logit(r)))
        rows.append((r, int(rng.random() < p)))
    return rows


def _encode(r: dict, budget_mean: float) -> list[tuple[str, float]]:
    days = min(max(r["days_until_event"], 0), MAX_DAYS)
    budget = r["budget_per_guest"]
    cols = [("event_type", float(r["event_type"] == e)) for e in EVENT_TYPES[1:]]
    cols += [("guests", float(r["guests"])), ("days_until_event", float(days < SOON_DAYS)),
             ("days_until_event", float(days > FAR_DAYS))]  # fmt: skip
    cols += [("source", float(r["source"] == s)) for s in LEAD_SOURCES[1:]]
    cols += [(f, float(bool(r[f]))) for f in ("returning_customer", "used_assistant",
                                              "requested_quote")]  # fmt: skip
    cols += [("budget_per_guest", float(budget_mean if budget is None else budget)),
             ("budget_per_guest", float(budget is None))]  # fmt: skip
    return cols


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (a is small and square)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            raise ValueError("singular matrix")
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in reversed(range(n)):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


@dataclass(frozen=True)
class LinearModel:
    names: tuple[str, ...]  # owning field per column
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coef: tuple[float, ...]  # on standardized columns
    intercept: float  # = mean of y on the training rows (columns are centered)
    budget_mean: float

    def _z(self, r: dict) -> list[float]:
        vals = [v for _, v in _encode(r, self.budget_mean)]
        return [(v - m) / s for v, m, s in zip(vals, self.means, self.scales, strict=True)]

    def predict_raw(self, r: dict) -> float:
        return self.intercept + sum(c * z for c, z in zip(self.coef, self._z(r), strict=True))

    def breakdown(self, r: dict) -> dict[str, float]:
        """Contribution of each field vs. the average lead; sums to raw - intercept."""
        out = dict.fromkeys(FIELDS, 0.0)
        for name, c, z in zip(self.names, self.coef, self._z(r), strict=True):
            out[name] += c * z
        return out


def fit(rows: list[tuple[dict, int]]) -> LinearModel:
    known = [r["budget_per_guest"] for r, _ in rows if r["budget_per_guest"] is not None]
    budget_mean = sum(known) / len(known) if known else 0.0
    encoded = [_encode(r, budget_mean) for r, _ in rows]
    names = tuple(n for n, _ in encoded[0])
    xs = [[v for _, v in e] for e in encoded]
    ys = [float(y) for _, y in rows]
    k, n = len(names), len(xs)
    means = [sum(x[j] for x in xs) / n for j in range(k)]
    scales = [math.sqrt(sum((x[j] - means[j]) ** 2 for x in xs) / n) or 1.0 for j in range(k)]
    z = [[(x[j] - means[j]) / scales[j] for j in range(k)] for x in xs]
    y_mean = sum(ys) / n
    xtx = [[sum(r[i] * r[j] for r in z) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * (y - y_mean) for r, y in zip(z, ys, strict=True)) for i in range(k)]
    coef = _solve(xtx, xty)
    return LinearModel(names, tuple(means), tuple(scales), tuple(coef), y_mean, budget_mean)


def evaluate(model: LinearModel, rows: list[tuple[dict, int]]) -> dict:
    raw = [model.predict_raw(r) for r, _ in rows]
    ys = [y for _, y in rows]
    y_mean = sum(ys) / len(ys)
    sse = sum((y - p) ** 2 for y, p in zip(ys, raw, strict=True))
    sst = sum((y - y_mean) ** 2 for y in ys) or 1.0
    return {
        "r2": 1 - sse / sst,
        "clipped_share": sum(not 0 <= p <= 1 for p in raw) / len(raw),
        "accuracy_at_50": sum((p >= 0.5) == y for p, y in zip(raw, ys, strict=True)) / len(ys),
        "base_rate": y_mean,
    }


@cache
def trained() -> tuple[LinearModel, dict]:
    """Holdout metrics from an 80/20 split, then the scoring model refit on all rows."""
    rows = synthetic_history()
    cut = int(len(rows) * 0.8)
    card = evaluate(fit(rows[:cut]), rows[cut:])
    card.update(train_rows=len(rows), holdout_rows=len(rows) - cut, synthetic=True)
    return fit(rows), card


def features_of(lead, today: dt.date) -> dict:
    """Model inputs from a Lead row (or any object with the same attributes)."""
    budget = lead.budget_per_guest
    return {
        "event_type": lead.event_type,
        "guests": lead.guests,
        "days_until_event": (lead.event_date - today).days,
        "source": lead.source,
        "returning_customer": lead.returning_customer,
        "used_assistant": lead.used_assistant,
        "requested_quote": lead.requested_quote,
        "budget_per_guest": None if budget is None else float(budget),
    }


def score(features: dict) -> tuple[float, float, bool]:
    """(chance clipped to 0..1, raw linear prediction, whether the clip was applied)."""
    raw = trained()[0].predict_raw(features)
    chance = min(max(raw, 0.0), 1.0)
    return chance, raw, chance != raw
