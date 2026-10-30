import datetime as dt
import uuid
from decimal import Decimal

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ai import ChangeProposal, ProposalStatus
from app.models.catalog import Dish
from app.models.orders import Order, OrderItem, OrderStatus
from app.repositories import ai as repo
from app.repositories import catalog as crepo
from app.repositories import orders as orepo
from app.schemas.ai import Change, ProposeArgs
from app.services import orders, pricing
from app.services.catalog import need

CENT = Decimal("0.01")
_CHANGES = TypeAdapter(list[Change])


def _q(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(CENT), "f")


def _plan(db: Session, order: Order, changes: list[Change]):
    """Dry-run on a copy of the quantities; raises AppError for any invalid change."""
    current = {i.dish_id: i.quantity for i in order.items}
    new = dict(current)
    dishes = {i.dish_id: i.dish for i in order.items}
    for c in changes:
        dish = dishes.get(c.dish_id) or need(db, Dish, c.dish_id, "Dish")
        dishes[c.dish_id] = dish
        if c.op == "remove_item":
            if c.dish_id not in new:
                raise AppError(422, "Dish is not in the order")
            del new[c.dish_id]
            continue
        if c.op == "add_item" and c.dish_id in new:
            raise AppError(422, "Dish is already in the order; use set_quantity")
        if c.op == "set_quantity" and c.dish_id not in new:
            raise AppError(422, "Dish is not in the order; use add_item")
        orders.check_dish(dish, c.quantity)
        new[c.dish_id] = c.quantity
    touched = list(dict.fromkeys(c.dish_id for c in changes))
    if all(current.get(d) == new.get(d) for d in touched):
        raise AppError(422, "These changes would not change the order")
    return current, new, dishes, touched


def _lines(new, dishes):
    return [pricing.Line(q, dishes[d].unit_price, dishes[d].currency) for d, q in new.items()]


def create(
    db: Session, order_id: uuid.UUID, conversation_id: uuid.UUID | None, args: ProposeArgs,
    lang: str = "he",
) -> ChangeProposal:  # fmt: skip
    """Stores a pending proposal (expiring any older one). Never touches the order itself."""
    order = orepo.get_order(db, order_id, lock=True)
    if order is None:
        raise AppError(404, "Order not found")
    if order.status != OrderStatus.draft:
        raise AppError(409, "Order can no longer be changed", code="invalid_transition")
    current, new, dishes, touched = _plan(db, order, args.changes)
    now = orders.order_out(order, lang)
    after = pricing.price(_lines(new, dishes))
    diff = [
        {
            "dish_id": str(d),
            "name": getattr(dishes[d], f"name_{lang}") or dishes[d].name_he,
            "current": _q(current.get(d)),
            "proposed": _q(new.get(d)),
        }
        for d in touched
    ]
    repo.expire_pending(db, order_id)
    proposal = ChangeProposal(
        order_id=order_id, conversation_id=conversation_id, base_order_version=order.version,
        changes=[c.model_dump(mode="json") for c in args.changes], diff=diff,
        rationale=args.rationale, price_before=now.total,
        price_after=now.total - now.subtotal + after.subtotal,
    )  # fmt: skip
    return crepo.save(db, proposal)


def _locked(db: Session, order_id, token, proposal_id):
    order = orders.customer_order(db, order_id, token, lock=True)
    proposal = repo.proposal(db, order_id, proposal_id, lock=True)
    if proposal is None:
        raise AppError(404, "Proposal not found")
    if proposal.status != ProposalStatus.pending:
        raise AppError(409, "Proposal was already decided", code="proposal_not_pending")
    return order, proposal


def _close(db: Session, proposal: ChangeProposal, status: ProposalStatus, error: AppError):
    proposal.status, proposal.decided_at = status, dt.datetime.now(dt.UTC)
    db.commit()
    raise error


def approve(db: Session, order_id, token, proposal_id, lang: str = "he"):
    order, proposal = _locked(db, order_id, token, proposal_id)
    if order.status != OrderStatus.draft:
        err = AppError(409, "Order can no longer be changed", code="invalid_transition")
        _close(db, proposal, ProposalStatus.expired, err)
    if proposal.base_order_version != order.version:
        err = AppError(409, "Your order changed since this suggestion; ask again",
                       code="order_version_conflict")  # fmt: skip
        _close(db, proposal, ProposalStatus.expired, err)
    try:  # dishes may have become unavailable since the proposal was made
        _, new, dishes, _ = _plan(db, order, _CHANGES.validate_python(proposal.changes))
    except AppError as e:
        _close(db, proposal, ProposalStatus.failed, e)
    for item in [i for i in order.items if i.dish_id not in new]:
        order.items.remove(item)
    for dish_id, quantity in new.items():
        if item := orepo.get_item(order, dish_id):
            item.quantity = quantity
        else:
            order.items.append(OrderItem(dish_id=dish_id, quantity=quantity))
    order.version += 1  # exactly once, whatever the number of changes
    now = dt.datetime.now(dt.UTC)
    proposal.status, proposal.decided_at, proposal.executed_at = ProposalStatus.approved, now, now
    crepo.save(db, order)  # one commit: order + proposal
    return orders.order_out(orepo.get_order(db, order_id), lang)


def reject(db: Session, order_id, token, proposal_id) -> ChangeProposal:
    _, proposal = _locked(db, order_id, token, proposal_id)
    proposal.status, proposal.decided_at = ProposalStatus.rejected, dt.datetime.now(dt.UTC)
    return crepo.save(db, proposal)


def list_for(db: Session, order_id, token, status: ProposalStatus | None):
    orders.customer_order(db, order_id, token)
    return repo.proposals(db, order_id, status)
