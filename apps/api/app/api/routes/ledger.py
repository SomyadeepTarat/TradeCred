from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from app.api.dependencies import SessionDependency, SettingsDependency
from app.integrations.ledger.base import LedgerActor
from app.models.domain import ReceivableStatus as Status
from app.models.domain import Role, User
from app.models.ledger import AuditEvent
from app.schemas.ledger import (
    AuditResponse,
    HistoryResponse,
    LifecycleResponse,
    RegistryInput,
    RegistryResponse,
)
from app.security.rbac import CurrentUser, require_roles
from app.services.ledger_service import LedgerService

router = APIRouter(tags=["mock ledger and registry"])


def get_ledger_service(
    session: SessionDependency, settings: SettingsDependency, user: CurrentUser, request: Request
) -> LedgerService:
    return LedgerService(
        session,
        settings,
        LedgerActor(user_id=user.id, organization_id=user.organization_id, role=user.role),
        request.state.request_id,
    )


Service = Annotated[LedgerService, Depends(get_ledger_service)]


@router.post("/receivables/{receivable_id}/submit", response_model=LifecycleResponse)
async def submit(receivable_id: UUID, service: Service) -> LifecycleResponse:
    return await service.advance(receivable_id, Status.SUBMITTED)


@router.post("/receivables/{receivable_id}/verify", response_model=LifecycleResponse)
async def verify(receivable_id: UUID, service: Service) -> LifecycleResponse:
    return await service.advance(receivable_id, Status.VERIFIED)


@router.post("/receivables/{receivable_id}/register", response_model=LifecycleResponse)
async def register(receivable_id: UUID, service: Service) -> LifecycleResponse:
    return await service.advance(receivable_id, Status.REGISTERED)


@router.post("/receivables/{receivable_id}/open-financing", response_model=LifecycleResponse)
async def open_financing(receivable_id: UUID, service: Service) -> LifecycleResponse:
    return await service.advance(receivable_id, Status.FINANCE_AVAILABLE)


@router.get("/receivables/{receivable_id}/history", response_model=HistoryResponse)
async def history(receivable_id: UUID, service: Service) -> HistoryResponse:
    return await service.history(receivable_id)


@router.post("/registry/check", response_model=RegistryResponse, response_model_exclude_none=True)
async def check(payload: RegistryInput, service: Service) -> RegistryResponse:
    return await service.registry(payload.fingerprint())


@router.get(
    "/registry/fingerprint/{fingerprint}",
    response_model=RegistryResponse,
    response_model_exclude_none=True,
)
async def lookup(
    fingerprint: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")], service: Service
) -> RegistryResponse:
    return await service.registry(fingerprint)


@router.get("/audit/events", response_model=list[AuditResponse])
async def audit(
    admin: Annotated[User, Depends(require_roles(Role.ADMIN))],
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[AuditResponse]:
    rows = await session.scalars(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [AuditResponse.model_validate(row) for row in rows]
