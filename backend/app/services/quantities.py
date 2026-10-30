import math
from dataclasses import dataclass
from decimal import Decimal

from app.models.catalog import PricingUnit


@dataclass(frozen=True)
class Rule:
    per_adult: Decimal
    per_child: Decimal
    round_step: Decimal


@dataclass(frozen=True)
class Selected:
    dish_id: object
    category_id: object
    pricing_unit: PricingUnit


@dataclass(frozen=True)
class Recommendation:
    dish_id: object
    category_id: object
    recommended: Decimal | None
    reason: str | None  # "no_rule" when the owner has not configured the category


def round_up(value: Decimal, step: Decimal) -> Decimal:
    return Decimal(math.ceil(value / step)) * step


def recommend(
    adults: int, children: int, selected: list[Selected], rules: dict[object, Rule]
) -> list[Recommendation]:
    """per_guest dishes get one per guest; others split the category's need evenly."""
    shared: dict[object, int] = {}
    for s in selected:
        if s.pricing_unit != PricingUnit.per_guest:
            shared[s.category_id] = shared.get(s.category_id, 0) + 1
    out = []
    for s in selected:
        if s.pricing_unit == PricingUnit.per_guest:
            out.append(Recommendation(s.dish_id, s.category_id, Decimal(adults + children), None))
        elif (rule := rules.get(s.category_id)) is None:
            out.append(Recommendation(s.dish_id, s.category_id, None, "no_rule"))
        else:
            need = adults * rule.per_adult + children * rule.per_child
            each = round_up(need / shared[s.category_id], rule.round_step)
            out.append(Recommendation(s.dish_id, s.category_id, each, None))
    return out
