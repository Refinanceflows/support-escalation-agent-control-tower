from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


async def require_api_key(request: Request, settings: Settings = Depends(get_settings)) -> str:
    token = request.headers.get("x-api-key")
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    if token not in settings.allowed_api_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key")
    return token or ""

