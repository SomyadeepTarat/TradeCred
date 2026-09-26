import logging
from io import BytesIO

from pypdf import PdfReader

from app.core.errors import APIError

# Parser diagnostics can contain attacker-controlled PDF fragments. Keep them out of logs.
_pdf_logger = logging.getLogger("pypdf")
_pdf_logger.addHandler(logging.NullHandler())
_pdf_logger.propagate = False


def validate_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise APIError(422, "INVALID_PDF", "Upload a complete PDF document.")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise ValueError("Unsupported PDF")
    except Exception as exc:
        # Parser diagnostics may contain document data; never include them in the response.
        raise APIError(
            422, "INVALID_PDF", "Upload a readable, unencrypted PDF of 1–100 pages."
        ) from exc
