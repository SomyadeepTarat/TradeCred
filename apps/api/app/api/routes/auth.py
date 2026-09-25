from fastapi import APIRouter, Response

from app.api.dependencies import AuthDependency
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.security.rbac import CurrentUser

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, auth: AuthDependency) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    return await auth.login(payload.email, payload.password.get_secret_value())


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser, response: Response) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse.model_validate(user)
