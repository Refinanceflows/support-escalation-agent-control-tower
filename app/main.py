from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, new_trace_id, set_trace_id
from app.services.factory import ServiceContainer


class Container(ServiceContainer):
    """Compatibility alias for older local tests that import app.main.Container."""


def _coerce_settings(settings: Any | None) -> Settings:
    if settings is None:
        return get_settings()
    if isinstance(settings, Settings):
        return settings
    token = getattr(settings, "api_demo_token", "demo-control-tower-key")
    sqlite_path = getattr(settings, "sqlite_path", None)
    state_file = Path(sqlite_path).with_suffix(".json") if sqlite_path else Path("data/control_tower_state.json")
    return Settings(
        state_file=state_file,
        api_keys=token,
        demo_api_key=token,
        log_level=getattr(settings, "log_level", "INFO"),
        max_tool_attempts=getattr(settings, "max_tool_attempts", 3),
    )


def create_app(settings: Settings | Any | None = None) -> FastAPI:
    resolved = _coerce_settings(settings)
    configure_logging(resolved.log_level)
    app = FastAPI(title=resolved.app_name, version="0.1.0")
    app.state.container = Container(resolved)
    app.dependency_overrides[get_settings] = lambda: resolved

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or new_trace_id()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        return response

    app.include_router(router)
    return app


app = create_app()

