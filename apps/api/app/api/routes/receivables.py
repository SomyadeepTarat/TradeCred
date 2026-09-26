from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from starlette.datastructures import UploadFile

from app.api.dependencies import SessionDependency, SettingsDependency
from app.core.errors import APIError
from app.integrations.storage.local import LocalDocumentStorage
from app.models.domain import Role, User
from app.schemas.receivables import DraftResponse, IntegrityResponse
from app.security.rbac import require_roles
from app.services.receivable_service import ReceivableService

router = APIRouter(prefix="/receivables", tags=["invoice documents"])
Exporter = Annotated[User, Depends(require_roles(Role.EXPORTER))]


def get_receivable_service(
    session: SessionDependency, settings: SettingsDependency
) -> ReceivableService:
    return ReceivableService(
        session, LocalDocumentStorage(settings.document_storage_path), settings
    )


Service = Annotated[ReceivableService, Depends(get_receivable_service)]
UPLOAD_SCHEMA = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["metadata", "document"],
                    "properties": {
                        "metadata": {
                            "type": "string",
                            "description": "Invoice metadata JSON; amount is decimal text.",
                            "example": '{"buyerId":"BUYER-DE-001","invoiceNumber":"EXP-2026-1042",'
                            '"invoiceDate":"2026-09-21","currency":"EUR","amount":"10800.00",'
                            '"dueDate":"2026-11-25"}',
                        },
                        "document": {"type": "string", "format": "binary"},
                    },
                }
            }
        },
    }
}


@router.post("", response_model=DraftResponse, status_code=201, openapi_extra=UPLOAD_SCHEMA)
async def create_draft(request: Request, exporter: Exporter, service: Service) -> DraftResponse:
    async with request.form(max_files=1, max_fields=1, max_part_size=16384) as form:
        metadata, document = form.get("metadata"), form.get("document")
        if (
            len(form.multi_items()) != 2
            or not isinstance(metadata, str)
            or not isinstance(document, UploadFile)
        ):
            raise APIError(
                422, "INVALID_UPLOAD", "Provide one metadata JSON field and one document file."
            )
        return await service.create_draft(metadata, document, exporter)


@router.get("/{receivable_id}/document/integrity", response_model=IntegrityResponse)
async def integrity(receivable_id: UUID, exporter: Exporter, service: Service) -> IntegrityResponse:
    return await service.check_integrity(receivable_id, exporter)


@router.get("/{receivable_id}/document")
async def download(receivable_id: UUID, exporter: Exporter, service: Service) -> Response:
    data = await service.download(receivable_id, exporter)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice-{receivable_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox",
        },
    )
