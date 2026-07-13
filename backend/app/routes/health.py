import redis
from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

router = APIRouter()


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.state.settings.service_name}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, str]:
    checks = {}

    try:
        with request.app.state.session_factory() as session:
            session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unreachable"

    try:
        client = redis.Redis.from_url(
            request.app.state.settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unreachable"

    if any(state != "ok" for state in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", **checks}
    return {"status": "ok", **checks}
