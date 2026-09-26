from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import SessionDependency
from app.models.domain import Role, User
from app.repositories.users import UserRepository
from app.schemas.auth import OrganizationResponse
from app.security.rbac import require_roles

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    admin: Annotated[User, Depends(require_roles(Role.ADMIN))],
    session: SessionDependency,
) -> list[OrganizationResponse]:
    organizations = await UserRepository(session).organizations()
    return [OrganizationResponse.model_validate(org) for org in organizations]
