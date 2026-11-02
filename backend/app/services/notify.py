"""Opt-in SMS/WhatsApp updates through Twilio.

Called by the API layer AFTER the status change is committed, so no order row lock is held
during network I/O (same rule as geo.py). Never log phone numbers or message bodies.
"""

import datetime as dt
import logging
import re
import time
import uuid
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import notifications as repo

log = logging.getLogger(__name__)
SID_RE = re.compile(r"^AC[0-9a-f]{32}$")
LOCAL_RE = re.compile(r"^05\d{8}$")
INTL_RE = re.compile(r"^\+9725\d{8}$")  # Israeli mobile, the only kind that gets SMS

# EN: our translation, owner gave he/ar.
TEXTS = {
    "flying_lap": {
        "he": "[CaterKing Pit Wall] רדיו-צ'ק! ההזמנה שלך עלתה על המסלול ונמצאת כרגע ב-Flying Lap "
        "🏎️💨 השליח שלנו שורף את האספלט בדרך אליך.",
        "ar": "[CaterKing Pit Wall] فحص اللاسلكي! طلبك انطلق على المسار وهو الآن في وضع "
        "Flying Lap 🏎️💨 السائق يحرق الإطارات في طريقه إليك بأقصى سرعة.",
        "en": "[CaterKing Pit Wall] Radio check! Your order is out on track and on its Flying Lap "
        "🏎️💨 Our driver is burning rubber on the way to you.",
    },
    "safety_car": {
        "he": "[CaterKing Pit Wall - בקרת מרוץ] ⚠️ Safety Car נכנס למסלול! זיהינו עומס גבוה "
        "בפיט-ליין (המטבח). רכב הבטיחות מוביל כרגע את ההזמנות כדי להבטיח 100% מושלמות בכל מנה.",
        "ar": "[CaterKing Pit Wall - مراقبة السباق] ⚠️ تم إطلاق سيارة الأمان (Safety Car)! "
        "رصدنا ضغطاً عالياً في خط الصيانة (المطبخ). تقوم سيارة الأمان حالياً بضبط إقلاع الطلبات "
        "لضمان 100% من الجودة والدقة في كل وجبة.",
        "en": "[CaterKing Pit Wall - Race Control] ⚠️ The Safety Car is on track! We detected "
        "heavy load in the pit lane (the kitchen). The Safety Car is leading the orders for now "
        "to keep every dish 100% perfect.",
    },
}


class Sender(Protocol):
    channels: tuple[str, ...]  # subset of ("sms", "whatsapp"); empty = disabled

    def send(self, channel: str, to: str, body: str) -> None: ...


class DisabledSender:
    channels: tuple[str, ...] = ()

    def send(self, channel: str, to: str, body: str) -> None:
        log.info("sms disabled")


class TwilioSender:
    def __init__(self, sid: str, token: str, sms_from: str | None, wa_from: str | None):
        if not SID_RE.fullmatch(sid):
            raise ValueError("invalid Twilio account SID")
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"  # fixed host
        self.auth = (sid, token)
        self.numbers = {"sms": sms_from, "whatsapp": wa_from}
        self.channels = tuple(c for c, n in self.numbers.items() if n)

    def send(self, channel: str, to: str, body: str) -> None:
        sender = self.numbers[channel]
        prefix = "whatsapp:" if channel == "whatsapp" else ""
        response = httpx.post(
            self.url,
            auth=self.auth,
            data={"To": prefix + to, "From": prefix + sender, "Body": body},
            timeout=5,
        )
        response.raise_for_status()


def get_sender() -> Sender:
    s = get_settings()
    if (
        s.twilio_account_sid
        and s.twilio_auth_token
        and (s.twilio_sms_from or s.twilio_whatsapp_from)
    ):
        try:
            return TwilioSender(
                s.twilio_account_sid, s.twilio_auth_token, s.twilio_sms_from or None,
                s.twilio_whatsapp_from or None,
            )  # fmt: skip
        except ValueError:
            log.warning("twilio misconfigured: invalid account SID")
    return DisabledSender()


def normalize_phone(raw: str | None) -> str | None:
    """Israeli numbers only; anything else is skipped (no guessing)."""
    phone = re.sub(r"[\s-]", "", raw or "")
    if LOCAL_RE.fullmatch(phone):
        return "+972" + phone[1:]
    return phone if INTL_RE.fullmatch(phone) else None


# shortcut: sends run inside the owner's request; the budget keeps it well under Render's timeout.
# Unreached orders stay unclaimed (eligible next time). Move to a job queue if volume grows.
BUDGET_S = 20


def notify(db: Session, sender: Sender, kind: str, order_ids: list[uuid.UUID]) -> None:
    if not sender.channels:
        log.info("sms disabled")
        return
    deadline = time.monotonic() + BUDGET_S
    for order_id in order_ids:
        if time.monotonic() > deadline:
            log.warning("notify budget used up kind=%s", kind)
            break
        order = repo.get_order(db, order_id)
        to = normalize_phone(order.customer.phone) if order and order.sms_opt_in else None
        if to is None:
            continue
        body = TEXTS[kind][order.lang]
        for channel in sender.channels:
            if not repo.claim(db, order_id, kind, channel):
                continue  # already sent (or in flight): at most once per channel
            try:
                sender.send(channel, to, body)
                status = "sent"
            except Exception as e:  # noqa: BLE001  never raise into the owner's request
                log.warning("notify failed kind=%s channel=%s error=%s", kind, channel,
                            type(e).__name__)  # fmt: skip
                status = "failed"
            repo.finish(db, order_id, kind, channel, status)


def safety_car(db: Session, sender: Sender) -> None:
    today = dt.datetime.now(ZoneInfo(get_settings().business_timezone)).date()
    notify(db, sender, "safety_car", repo.active_order_ids(db, today))
