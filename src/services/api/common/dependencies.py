from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app_settings import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> None:
    expected = settings.app.api_key.get_secret_value()
    if api_key is None or not compare_digest(
        api_key.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid API key")
