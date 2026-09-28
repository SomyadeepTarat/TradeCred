from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import SessionDependency, SettingsDependency
from app.models.domain import Role, User
from app.schemas.demo import SecurityView, SimulatorAsset, SimulatorInput, SimulatorResult
from app.security.rbac import require_roles
from app.services.audit_queries import security_events
from app.services.simulator_service import SimulatorService

router = APIRouter(tags=["demo and security audit"])
Operator = Annotated[User, Depends(require_roles(Role.SETTLEMENT_OPERATOR))]
Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]


def service(
    session: SessionDependency,
    settings: SettingsDependency,
    user: Operator,
    request: Request,
    response: Response,
) -> SimulatorService:
    response.headers["Cache-Control"] = "no-store"
    return SimulatorService(session, settings, user, request.state.request_id)


Service = Annotated[SimulatorService, Depends(service)]


@router.get("/simulator/assets", response_model=list[SimulatorAsset])
async def assets(simulator: Service) -> list[SimulatorAsset]:
    return await simulator.assets()


@router.post("/simulator/events", response_model=SimulatorResult)
async def send(payload: SimulatorInput, simulator: Service) -> SimulatorResult:
    return await simulator.send(payload)


@router.post("/simulator/events/{event_id}/replay", response_model=SimulatorResult)
async def replay(event_id: UUID, simulator: Service) -> SimulatorResult:
    return await simulator.replay(event_id)


@router.get("/audit/security-events", response_model=list[SecurityView])
async def security(
    admin: Admin,
    session: SessionDependency,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[SecurityView]:
    response.headers["Cache-Control"] = "no-store"
    return await security_events(session, limit, offset)
