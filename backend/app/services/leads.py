import datetime as dt
import random
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.leads import Lead
from app.repositories import catalog as repo
from app.repositories import leads as leads_repo
from app.schemas.leads import LeadDetailOut, LeadOut
from app.services import lead_model
from app.services.catalog import need, update

TZ = ZoneInfo("Asia/Jerusalem")
OPEN = ("new", "contacted")
DEMO_NAMES = ("נועה לוי", "יוסי כהן", "מאיה אברהם", "דניאל מזרחי", "שירה פרץ", "איתי ביטון",
              "רחל דהן", "עומר אזולאי", "ליאת פרידמן", "אמיר חדאד", "סאמר חורי", "רים נסאר",
              "תמר שפירא", "אליה גבאי", "הדר אוחיון", "נדב רוזן")  # fmt: skip


def _today() -> dt.date:
    return dt.datetime.now(TZ).date()


def scored(lead: Lead, today: dt.date | None = None) -> LeadOut:
    chance, raw, clipped = lead_model.score(lead_model.features_of(lead, today or _today()))
    return LeadOut.model_validate(lead).model_copy(
        update={"chance": chance, "raw_prediction": raw, "clipped": clipped}
    )


def list_scored(db: Session) -> list[LeadOut]:
    today = _today()
    out = [scored(lead, today) for lead in leads_repo.list_leads(db)]
    # Open leads first (best chance on top), then won/lost.
    return sorted(out, key=lambda o: (o.status not in OPEN, -o.chance))


def detail(db: Session, lead_id) -> LeadDetailOut:
    lead = need(db, Lead, lead_id, "Lead")
    model, _ = lead_model.trained()
    base = scored(lead)
    parts = model.breakdown(lead_model.features_of(lead, _today()))
    return LeadDetailOut(**base.model_dump(), average_chance=model.intercept, breakdown=parts)


def create(db: Session, data: dict) -> LeadOut:
    return scored(repo.save(db, Lead(**data)))


def patch(db: Session, lead_id, data: dict) -> LeadOut:
    return scored(update(db, need(db, Lead, lead_id, "Lead"), data))


def delete(db: Session, lead_id) -> None:
    repo.remove(db, need(db, Lead, lead_id, "Lead"))


def add_demo(db: Session, n: int, rng: random.Random | None = None) -> list[LeadOut]:
    rng = rng or random.Random()  # noqa: S311  demo data, not security
    today = _today()
    leads = []
    for _ in range(n):
        f = lead_model.sample_features(rng)
        budget = f.pop("budget_per_guest")
        f["event_date"] = today + dt.timedelta(days=f.pop("days_until_event"))
        f["budget_per_guest"] = None if budget is None else Decimal(str(budget))
        leads.append(Lead(**f, full_name=rng.choice(DEMO_NAMES), is_demo=True))
    return [scored(lead, today) for lead in leads_repo.add_all(db, leads)]


def delete_demo(db: Session) -> int:
    return leads_repo.delete_demo(db)
