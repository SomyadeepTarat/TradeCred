from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.domain import Organization, OrganizationType, Role, User
from app.security.passwords import hash_password

DEMO_ORGANIZATIONS = (
    ("ORG_EXPORTER_ALPHA", "Alpha Looms Demo", OrganizationType.EXPORTER),
    ("ORG_EXPORTER_BETA", "Beta Textiles Demo", OrganizationType.EXPORTER),
    ("ORG_BANK_CITI_DEMO", "Cedar Finance Demo", OrganizationType.FINANCIER),
    ("ORG_BANK_NBFC_DEMO", "Maple Credit Demo", OrganizationType.FINANCIER),
    ("ORG_SETTLEMENT_BANK", "Harbor Settlement Demo", OrganizationType.SETTLEMENT_BANK),
    ("ORG_CONSORTIUM_ADMIN", "TradeCred Demo Consortium", OrganizationType.CONSORTIUM),
)
DEMO_USERS = (
    ("exporter@tradecred.demo", "Demo Exporter", Role.EXPORTER, "ORG_EXPORTER_ALPHA"),
    ("bank@tradecred.demo", "Demo Financier", Role.FINANCIER, "ORG_BANK_CITI_DEMO"),
    ("nbfc@tradecred.demo", "Demo Second Financier", Role.FINANCIER, "ORG_BANK_NBFC_DEMO"),
    (
        "settlement@tradecred.demo",
        "Demo Settlement Operator",
        Role.SETTLEMENT_OPERATOR,
        "ORG_SETTLEMENT_BANK",
    ),
    ("admin@tradecred.demo", "Demo Administrator", Role.ADMIN, "ORG_CONSORTIUM_ADMIN"),
)


async def seed_demo(session: AsyncSession, password: str) -> None:
    """Create missing demo identities; never reset existing passwords or roles."""
    if len(password) < 12:
        raise ValueError("DEMO_PASSWORD must contain at least 12 characters.")
    # Serializes simultaneous seed invocations without relying on a check-then-insert race.
    await session.execute(text("SELECT pg_advisory_xact_lock(7007001)"))
    for org_id, name, kind in DEMO_ORGANIZATIONS:
        if await session.get(Organization, org_id) is None:
            session.add(Organization(id=org_id, name=name, organization_type=kind))
    await session.flush()
    for email, name, role, org_id in DEMO_USERS:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is None:
            encoded = await run_in_threadpool(hash_password, password)
            session.add(
                User(
                    email=email,
                    display_name=name,
                    role=role,
                    organization_id=org_id,
                    password_hash=encoded,
                )
            )
    await session.flush()
