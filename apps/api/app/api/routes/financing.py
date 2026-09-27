from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import SessionDependency, SettingsDependency
from app.integrations.ledger.base import LedgerActor
from app.schemas.financing import FinancingResult, FinancingView, OfferInput, OfferView
from app.security.rbac import CurrentUser
from app.services.financing_service import FinancingService

router = APIRouter(tags=["financing"])


def get_service(
    session: SessionDependency,
    settings: SettingsDependency,
    user: CurrentUser,
    request: Request,
    response: Response,
) -> FinancingService:
    response.headers["Cache-Control"] = "no-store"
    return FinancingService(
        session,
        settings,
        LedgerActor(user_id=user.id, organization_id=user.organization_id, role=user.role),
        request.state.request_id,
    )


Service = Annotated[FinancingService, Depends(get_service)]


@router.post("/receivables/{receivable_id}/offers", response_model=OfferView, status_code=201)
async def create_offer(receivable_id: UUID, payload: OfferInput, service: Service) -> OfferView:
    return await service.create_offer(receivable_id, payload)


@router.get("/receivables/{receivable_id}/offers", response_model=FinancingView)
async def offers(receivable_id: UUID, service: Service) -> FinancingView:
    return await service.view(receivable_id)


@router.post("/offers/{offer_id}/accept", response_model=FinancingResult)
async def accept(offer_id: UUID, service: Service) -> FinancingResult:
    return await service.accept(offer_id)


@router.post("/offers/{offer_id}/reject", response_model=OfferView)
async def reject(offer_id: UUID, service: Service) -> OfferView:
    return await service.reject(offer_id)


@router.post("/receivables/{receivable_id}/disbursement/mock", response_model=FinancingResult)
async def disburse(receivable_id: UUID, service: Service) -> FinancingResult:
    return await service.disburse(receivable_id)
