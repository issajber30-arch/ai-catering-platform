import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.assistant import chat, get_llm
from app.api.catalog import Lang
from app.api.orders import Token
from app.core.db import Db
from app.models.ai import ProposalStatus
from app.schemas.ai import ChatIn, ChatOut, MessageOut, ProposalOut
from app.schemas.orders import OrderOut
from app.services import conversations, proposals

router = APIRouter(prefix="/api")
Llm = Annotated[object, Depends(get_llm)]


@router.post("/orders/{order_id}/chat")
def post_chat(
    order_id: uuid.UUID, body: ChatIn, db: Db, llm: Llm, token: Token = None, lang: Lang = "he"
) -> ChatOut:
    turn = chat(db, llm, order_id, token, body.message, lang)
    return ChatOut(
        reply=turn.reply, proposals=[ProposalOut.model_validate(p) for p in turn.proposals]
    )


@router.get("/orders/{order_id}/chat")
def get_chat(order_id: uuid.UUID, db: Db, token: Token = None) -> list[MessageOut]:
    return [MessageOut(**m) for m in conversations.visible(db, order_id, token)]


@router.get("/orders/{order_id}/proposals")
def list_proposals(
    order_id: uuid.UUID, db: Db, token: Token = None, status: ProposalStatus | None = None
) -> list[ProposalOut]:
    return [ProposalOut.model_validate(p) for p in proposals.list_for(db, order_id, token, status)]


@router.post("/orders/{order_id}/proposals/{proposal_id}/approve")
def approve(
    order_id: uuid.UUID, proposal_id: uuid.UUID, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return proposals.approve(db, order_id, token, proposal_id, lang)


@router.post("/orders/{order_id}/proposals/{proposal_id}/reject")
def reject(order_id: uuid.UUID, proposal_id: uuid.UUID, db: Db, token: Token = None) -> ProposalOut:
    return ProposalOut.model_validate(proposals.reject(db, order_id, token, proposal_id))
