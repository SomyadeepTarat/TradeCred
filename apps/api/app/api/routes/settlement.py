from fastapi import APIRouter, Request, Response

from app.api.dependencies import SessionDependency, SettingsDependency
from app.schemas.settlement import PaymentEventView
from app.security.rbac import CurrentUser
from app.services.settlement_service import SettlementService

router = APIRouter(tags=["settlement"])


@router.post("/settlement/events", response_model=PaymentEventView)
async def receive_event(
    request: Request, response: Response, session: SessionDependency, settings: SettingsDependency
) -> PaymentEventView:
    response.headers["Cache-Control"] = "no-store"
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            break
    return await SettlementService(session, settings, request.state.request_id).process(
        bytes(body),
        request.headers.get("X-TradeCred-Signature", ""),
        request.headers.get("X-TradeCred-Key-Id", ""),
    )


@router.get("/settlement/events/{event_id}", response_model=PaymentEventView)
async def get_event(
    event_id: str,
    request: Request,
    response: Response,
    session: SessionDependency,
    settings: SettingsDependency,
    user: CurrentUser,
) -> PaymentEventView:
    response.headers["Cache-Control"] = "no-store"
    return await SettlementService(session, settings, request.state.request_id).get(event_id, user)
