from fastapi import FastAPI

from backend.app.config import Settings
from backend.app.db import make_engine, make_session_factory
from backend.app.routes import health, pantry


def create_app() -> FastAPI:
    settings = Settings()
    engine = make_engine(settings.database_url)

    app = FastAPI(title="PantryOps Edge", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    app.include_router(health.router)
    app.include_router(pantry.router)

    return app
