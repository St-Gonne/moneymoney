"""Private NSDL route helpers kept separate from legacy API routers."""
from __future__ import annotations

import re

from fastapi import HTTPException

from ..nsdl_store import NsdlStoreError


_IMPORT_REFERENCE = re.compile(r"im-[0-9a-f]{32}")


def safe_error(error: NsdlStoreError, *, import_reference: str | None = None) -> HTTPException:
    status = 422 if error.code.startswith("ERR_NSDL_") else 503
    if error.code in {"ERR_NSDL_UPLOAD_INVALID", "ERR_NSDL_IDEMPOTENCY_INVALID"}:
        status = 400
    elif error.code == "ERR_NSDL_LIMIT_EXCEEDED":
        status = 413
    elif error.code in {"ERR_NSDL_SAME_DATE_CONFLICT", "ERR_NSDL_OLDER_STATEMENT", "ERR_NSDL_ACCOUNT_SET_CONFLICT", "ERR_NSDL_REVISION_CONFLICT", "ERR_NSDL_IDEMPOTENCY_CONFLICT"}:
        status = 409
    elif error.code in {"ERR_NSDL_STORE_UNAVAILABLE", "ERR_NSDL_COMMIT_UNKNOWN", "ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN"}:
        status = 503
    headers = None
    if isinstance(import_reference, str) and _IMPORT_REFERENCE.fullmatch(import_reference):
        headers = {"X-MoneyMoney-Import-Ref": import_reference}
    return HTTPException(status_code=status, detail=error.code, headers=headers)
