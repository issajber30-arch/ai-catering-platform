from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import AppError

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Line:
    quantity: Decimal
    unit_price: Decimal
    currency: str


@dataclass(frozen=True)
class Totals:
    line_totals: list[Decimal]
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    currency: str | None


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(CENT, ROUND_HALF_UP)


def price(lines: list[Line], delivery_fee: Decimal | None = None) -> Totals:
    """Catalog prices include VAT (decision #14), so there is no tax line."""
    currencies = {line.currency for line in lines}
    if len(currencies) > 1:
        raise AppError(422, "Order mixes currencies")
    totals = [line_total(line.quantity, line.unit_price) for line in lines]
    subtotal = sum(totals, Decimal("0.00"))
    fee = (delivery_fee or Decimal("0")).quantize(CENT, ROUND_HALF_UP)
    return Totals(totals, subtotal, fee, subtotal + fee, next(iter(currencies), None))
