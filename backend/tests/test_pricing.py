from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.services.pricing import Line, line_total, price

D = Decimal


def line(qty, unit_price, currency="ILS"):
    return Line(D(qty), D(unit_price), currency)


@pytest.mark.parametrize(
    ("qty", "unit_price", "expected"),
    [
        ("30", "45.00", "1350.00"),  # per_guest
        ("2", "120.00", "240.00"),  # per_tray
        ("1.5", "89.90", "134.85"),  # per_weight
        ("12", "3.50", "42.00"),  # per_item
        ("0.5", "0.01", "0.01"),  # 0.005 rounds half up
        ("1.25", "0.10", "0.13"),  # 0.125 rounds half up
    ],
)
def test_line_total(qty, unit_price, expected):
    assert line_total(D(qty), D(unit_price)) == D(expected)


def test_price_with_delivery_fee():
    totals = price([line("2", "120.00"), line("1.5", "89.90")], D("25"))
    assert totals.subtotal == D("374.85")
    assert totals.delivery_fee == D("25.00")
    assert totals.total == D("399.85")
    assert totals.currency == "ILS"


def test_price_without_delivery_and_empty():
    assert price([line("1", "10")]).total == D("10.00")
    empty = price([])
    assert empty.total == D("0.00") and empty.currency is None


def test_recalculates_after_change():
    before = price([line("2", "100")]).total
    assert price([line("3", "100")]).total == before + D("100.00")


def test_mixed_currencies_rejected():
    with pytest.raises(AppError) as err:
        price([line("1", "10", "ILS"), line("1", "10", "USD")])
    assert err.value.status == 422
