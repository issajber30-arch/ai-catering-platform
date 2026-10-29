from decimal import Decimal

from app.models.catalog import PricingUnit
from app.services.quantities import Rule, Selected, recommend, round_up

D = Decimal
SALADS, MAINS = "salads", "mains"


def sel(dish, cat, unit=PricingUnit.per_tray):
    return Selected(dish, cat, unit)


def test_rounds_up_to_step():
    assert round_up(D("7.1"), D("1")) == D("8")
    assert round_up(D("7"), D("1")) == D("7")
    assert round_up(D("2.1"), D("0.5")) == D("2.5")
    assert round_up(D("0"), D("1")) == D("0")


def test_need_from_adults_and_children():
    rules = {MAINS: Rule(D("0.25"), D("0.1"), D("1"))}  # 10*0.25 + 5*0.1 = 3.0
    [rec] = recommend(10, 5, [sel("a", MAINS)], rules)
    assert rec.recommended == D("3") and rec.reason is None
    [rec] = recommend(10, 6, [sel("a", MAINS)], rules)  # 3.1 -> 4
    assert rec.recommended == D("4")


def test_even_split_across_category_rounds_each_up():
    rules = {MAINS: Rule(D("0.5"), D("0"), D("1"))}  # need 5 over 2 dishes = 2.5 -> 3 each
    recs = recommend(10, 0, [sel("a", MAINS), sel("b", MAINS)], rules)
    assert [r.recommended for r in recs] == [D("3"), D("3")]


def test_no_rule_means_no_recommendation():
    [rec] = recommend(10, 0, [sel("a", SALADS)], {MAINS: Rule(D(1), D(1), D(1))})
    assert rec.recommended is None and rec.reason == "no_rule"


def test_per_guest_uses_headcount_regardless_of_rules():
    guest = sel("g", MAINS, PricingUnit.per_guest)
    rules = {MAINS: Rule(D(5), D(5), D(1))}
    [rec, other] = recommend(10, 4, [guest, sel("a", MAINS)], rules)
    assert rec.recommended == D("14") and rec.reason is None
    assert other.recommended == D("70")  # per_guest dish does not take part in the split
    [rec] = recommend(10, 4, [guest], {})
    assert rec.recommended == D("14")
